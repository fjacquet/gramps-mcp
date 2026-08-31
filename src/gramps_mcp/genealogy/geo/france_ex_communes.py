# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2026 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Résolveur des ex-communes françaises (communes associées / déléguées).

geo.api.gouv.fr/communes ne connaît que les communes VIVANTES : une commune fusionnée
(loi Marcellin, 1971) y est introuvable, et `resolve_fr` bascule alors sur Nominatim,
qui perd la hiérarchie. L'endpoint /communes_associees_deleguees les connaît, mais ne
donne aucune date de fusion — Wikidata la fournit (P576).

On ne date les rattachements que si les deux sources concordent sur le successeur.

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/geo/france_ex_communes.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.

Ported from `requests` to `httpx`: `sparql_rows` (geo/sparql.py) now raises
`httpx.HTTPError`, not `requests.RequestException`, on network/JSON failure -
the except clause below was updated to match.

Correction (code review, round 1): the source's single
`except requests.RequestException:` covered BOTH network failure and a
malformed reply, because `requests.exceptions.JSONDecodeError` genuinely
subclasses `RequestException`. httpx has no equivalent relationship -
`response.json()` in `sparql.py` raises the stdlib `json.JSONDecodeError`
directly, which is a `ValueError`, not an `httpx.HTTPError`. The first pass
of this port caught only `httpx.HTTPError`, which silently narrowed the
catch: a malformed/non-JSON reply from Wikidata would have propagated and
crashed `resolve_fr_ex_commune` / `resolve_place` instead of degrading to
"no datation". Fixed by catching `(httpx.HTTPError, json.JSONDecodeError)`.

Divergence: added a `typing.cast(ExCommuneFacts, facts)` where `concordant`
guards use of `facts.merged_on` in `resolve_fr_ex_commune`. mypy --strict
cannot see that `facts` is not None there - `concordant` already required
`facts is not None` in the boolean expression above it. No runtime behavior
changed; the cast is erased at import time.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import cast

import httpx
from pydantic import BaseModel

from ..domain import (
    DatedChain,
    DatedName,
    ParsedPlace,
    PlaceLevel,
    ResolvedPlace,
)
from ..rate_limit import get_rate_limiter
from .france import _FIELDS as _COMMUNE_FIELDS
from .france import map_commune, pick_exact_by_name
from .sparql import sparql_rows

_WKT_POINT_RE = re.compile(
    r"^\s*Point\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)\s*$", re.IGNORECASE
)

# Une seule requête rend la dissolution, le successeur ET le GPS : la garde de
# recoupement (successeur vs chefLieu) ne coûte donc aucun appel supplémentaire.
#
# ?dissolved passe par le nœud de déclaration (p:P576/psv:P576) plutôt que par le
# raccourci wdt:P576 : wdt: rend toujours un xsd:dateTime complet, quelle que soit
# la précision réelle de la déclaration (une dissolution saisie en précision
# ANNÉE sort quand même "1972-01-01T00:00:00Z"). Il faut ?prec (wikibase:timePrecision)
# pour distinguer une vraie date au jour près (11) d'une année maquillée en date —
# voir wikidata_ex_commune, qui rejette tout ce qui n'est pas prec=11.
_SPARQL = """SELECT ?item ?dissolved ?succInsee ?coord ?prec WHERE {{
  ?item wdt:P374 "{insee}" .
  OPTIONAL {{ ?item p:P576/psv:P576 ?v . ?v wikibase:timeValue ?dissolved ;
                                            wikibase:timePrecision ?prec }}
  OPTIONAL {{ ?item wdt:P1366 ?succ . ?succ wdt:P374 ?succInsee }}
  OPTIONAL {{ ?item wdt:P625 ?coord }}
}} LIMIT 10"""

_DAY_PRECISION = "11"  # wikibase:timePrecision pour une date au jour près


class ExCommuneFacts(BaseModel):
    """Ce que Wikidata sait d'une ex-commune, identifiée par son code INSEE."""

    dissolved: str | None = None  # "YYYY-MM-DD" — DERNIER jour d'existence
    # (P576, fait brut de Wikidata ; ce n'est PAS
    # le premier jour du rattachement moderne)
    merged_on: str | None = None  # "YYYY-MM-DD" — PREMIER jour du rattachement
    # (dissolved + 1 jour) ; c'est cette date qui
    # doit dater les DatedChain, pas `dissolved`
    successor_insee: str | None = None
    lat: str | None = None  # WGS84 décimal
    long: str | None = None


def merged_on_from_dissolved(dissolved: str | None) -> str | None:
    """Lendemain de `dissolved`, en date calendaire — pas en manipulation de chaîne.

    P576 donne le DERNIER jour d'existence de la commune (`dissolved`) ; le premier
    jour de son rattachement moderne (`merged_on`) est le jour suivant. Wikipédia
    l'énonce ainsi en toutes lettres (« Le 1er janvier 1973, la commune est
    rattachée à… ») pour une dissolution au 1972-12-31 — vérifié concordant sur
    plusieurs communes de la Meuse.

    Passe par `datetime.date` (et `timedelta(days=1)`) pour que les passages de
    mois et d'année, ainsi que le 29 février des années bissextiles, soient
    justes. `None` si `dissolved` est absent ou non parsable (ex. une année
    seule comme "1973") — ne lève jamais.
    """
    if not dissolved:
        return None
    try:
        day = date.fromisoformat(dissolved)
    except ValueError:
        return None
    return (day + timedelta(days=1)).isoformat()


def parse_wkt_point(wkt: str) -> tuple[str, str] | None:
    """'Point(lon lat)' -> ('lat', 'long'). None si non parsable.

    ATTENTION : le WKT met la LONGITUDE en premier, comme GeoJSON. Inverser rendrait
    des coordonnées parfaitement bien formées, et fausses.
    """
    match = _WKT_POINT_RE.match(wkt or "")
    if match is None:
        return None
    lon, lat = match.group(1), match.group(2)
    return lat, lon


def _precise_dissolved(rows: list[dict]) -> str | None:
    """Ne retient une dissolution que si sa précision Wikidata est le JOUR (prec=11).

    P576 accepte des déclarations en précision année/décennie/siècle — wdt:P576 les
    rend toutes comme un xsd:dateTime complet, ce qui fabrique une fausse illusion
    de précision. On ignore donc toute ligne dont `prec` n'est pas "11", qu'elle
    soit absente (déclaration sans P576 du tout) ou porte une autre valeur.

    Plusieurs lignes en précision 11 portant des valeurs *différentes* sont des
    déclarations P576 contradictoires — une vraie ambiguïté, qu'on ne tranche pas
    arbitrairement. Plusieurs lignes portant la *même* valeur ne sont que du
    fan-out SPARQL (ex. `?coord` multivaluée) : bénin, la datation passe.
    """
    precise = {
        row["dissolved"]
        for row in rows
        if row.get("prec") == _DAY_PRECISION and row.get("dissolved")
    }
    if len(precise) != 1:
        return None
    return precise.pop()


def wikidata_ex_commune(insee: str) -> ExCommuneFacts | None:
    """Faits Wikidata pour une ex-commune.

    None si 0, ou >1 entité *distincte*, porte ce code INSEE.

    Wikidata n'est qu'un enrichisseur : toute panne réseau rend None (pas de datation)
    plutôt que de faire échouer la résolution entière.
    """
    try:
        rows = sparql_rows(_SPARQL.format(insee=insee))
    except (httpx.HTTPError, json.JSONDecodeError):
        # Réseau (httpx.HTTPError, incl. HTTPStatusError et DecodingError si
        # httpx elle-même échoue à décoder) ET JSON malformé/non-JSON renvoyé
        # par Wikidata (json.JSONDecodeError, levée par `response.json()` dans
        # sparql.py - PAS une sous-classe de httpx.HTTPError, contrairement à
        # requests.exceptions.JSONDecodeError qui héritait de RequestException
        # dans la source ; voir la note de portage en tête de fichier).
        # Volontairement étroit : un KeyError ou une ValidationError seraient des
        # bugs de ce module, et doivent remonter plutôt que se déguiser en
        # « pas de datation » — même convention que places_apply.py.
        return None
    if not rows:  # 0 ligne : code INSEE inconnu de Wikidata
        return None
    items = {row.get("item") for row in rows}
    if len(items) != 1:
        # On compte les ?item DISTINCTS, pas les lignes : les trois OPTIONAL de la
        # requête produisent un fan-out SPARQL dès qu'une propriété est multivaluée
        # (P625 porte couramment plusieurs revendications de coordonnées pour un
        # même lieu) — plusieurs lignes pour une seule et même entité, ce n'est pas
        # une ambiguïté. On ne refuse de dater que si les lignes rendent effectivement
        # plus d'une entité distincte.
        return None
    row = rows[0]
    lat = long = None
    if row.get("coord"):
        point = parse_wkt_point(row["coord"])
        if point is not None:
            lat, long = point
    dissolved = _precise_dissolved(rows)
    dissolved_date = dissolved.split("T")[0] if dissolved else None
    return ExCommuneFacts(
        dissolved=dissolved_date,
        merged_on=merged_on_from_dissolved(dissolved_date),
        successor_insee=row.get("succInsee"),
        lat=lat,
        long=long,
    )


_BASE = "https://geo.api.gouv.fr"
_ASSOCIEE_FIELDS = "nom,code,type,chefLieu,centre,departement,region"
_PROVIDER = "GeoApiGouvFr"


def _http_get(path: str, params: dict):
    """Thin HTTP GET (monkeypatché dans les tests). WGS84 GeoJSON en sortie."""
    get_rate_limiter().acquire(_PROVIDER)
    resp = httpx.get(f"{_BASE}{path}", params=params, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


def resolve_fr_ex_commune(parsed: ParsedPlace) -> ResolvedPlace | None:
    """Résout une commune française fusionnée (associée/déléguée).

    Deux chaînes datées quand geo.api.gouv.fr et Wikidata s'accordent sur le
    successeur ; sinon une seule chaîne non datée — jamais de date inventée.
    """
    if not parsed.commune:
        return None
    results = _http_get(
        "/communes_associees_deleguees",
        {"nom": parsed.commune, "fields": _ASSOCIEE_FIELDS, "limit": 10},
    )
    if not isinstance(results, list) or not results:
        return None
    exact = pick_exact_by_name(results, parsed)
    if not exact:
        return None  # repli Nominatim côté registre
    ex = exact[0]
    chef_code = ex.get("chefLieu")
    if not chef_code:
        return None
    chef = _http_get(f"/communes/{chef_code}", {"fields": _COMMUNE_FIELDS})
    if not isinstance(chef, dict) or "centre" not in chef:
        return None
    # map_commune est réutilisé pour la hiérarchie France>Région>Département,
    # déjà testée.
    modern = map_commune(chef, parsed)
    parents = list(modern.chains[0].levels)
    chef_level = PlaceLevel(
        name=modern.name, place_type="Municipality", code=modern.code
    )

    facts = wikidata_ex_commune(ex["code"])
    # Garde de recoupement : on ne date que si les DEUX sources désignent le même
    # successeur ET que la borne du rattachement (merged_on, pas dissolved) est
    # calculable. Une date de fusion fausse route silencieusement les événements
    # vers la mauvaise branche — pire qu'une date absente.
    concordant = (
        facts is not None and facts.merged_on and facts.successor_insee == chef_code
    )
    if concordant:
        # mypy --strict cannot see that `facts` is not None here: `concordant`
        # already required `facts is not None` above. No runtime behavior
        # changed; the cast is erased at import time.
        facts_dated = cast(ExCommuneFacts, facts)
        chains = [
            DatedChain(levels=parents, date_qualifier=f"avant {facts_dated.merged_on}"),
            DatedChain(
                levels=[*parents, chef_level],
                date_qualifier=f"après {facts_dated.merged_on}",
            ),
        ]
        source = "geo.api.gouv.fr/communes_associees_deleguees + Wikidata"
    else:
        chains = [DatedChain(levels=[*parents, chef_level])]
        source = "geo.api.gouv.fr/communes_associees_deleguees"

    # GPS : Wikidata (centre du bourg) de préférence au `centre` de l'API, qui est le
    # centroïde du territoire — mesuré à ~700 m du village sur Saint-Agnant. En
    # généalogie on veut l'église, pas le barycentre cadastral. Exception assumée à
    # map_commune, qui prend toujours le centre de l'API pour les communes vivantes.
    lon, lat = (ex.get("centre") or {}).get("coordinates", [None, None])
    if facts is not None and facts.lat and facts.long:
        lat, lon = facts.lat, facts.long

    resolved = ResolvedPlace(
        name=ex["nom"],
        place_type="Municipality",
        lat=str(lat) if lat is not None else None,
        long=str(lon) if lon is not None else None,
        code=ex["code"],
        chains=chains,
        alt_names=[DatedName(value=parsed.raw)],
        score=1.0,
        source=source,
        query=f"/communes_associees_deleguees?nom={parsed.commune}",
    )
    if len(exact) > 1:
        resolved.ambiguous = True  # vrais homonymes -> proposition
        resolved.source = f"{source} ({len(exact)} homonymes)"
    return resolved
