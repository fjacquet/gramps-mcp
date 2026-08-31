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

"""France resolver: authoritative INSEE-code → geo.api.gouv.fr commune.

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/geo/france.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.

Divergence (code review, round 2): the source's `_http_get` called
`resp.raise_for_status()` unconditionally, so a 404 from
`GET /communes/{insee}` - an unknown or no-longer-living INSEE code -
raised `httpx.HTTPStatusError` instead of returning `None`. Because
`_BY_COUNTRY["France"]` in `registry.py` is
`lambda p: resolve_fr(p) or resolve_fr_ex_commune(p)`, that exception
escaped the whole chain: `resolve_fr_ex_commune` (france_ex_communes.py)
never ran, even though a 404 here - a commune fusionnee absent from
`/communes` - is exactly the case it exists to handle. Fixed by treating
404 as "not found" in `_http_get` and returning `None`, letting the `or`
fall through as designed. Every other status still raises.
"""

from __future__ import annotations

import httpx

from ..domain import (
    DatedChain,
    DatedName,
    ParsedPlace,
    PlaceLevel,
    ResolvedPlace,
)
from ..rate_limit import get_rate_limiter
from .score import _norm

_BASE = "https://geo.api.gouv.fr"
_FIELDS = "nom,code,centre,departement,region"
_PROVIDER = "GeoApiGouvFr"


def _http_get(path: str, params: dict) -> dict | None:
    """Thin HTTP GET (monkeypatched in tests). WGS84 GeoJSON out.

    Returns None on a 404 - "not found" is a normal outcome for a commune
    lookup (an unknown INSEE code, or a commune fusionnee absent from the
    living-communes endpoint), not a transport failure - so the caller can
    treat it the same as an empty result instead of propagating an
    exception. Every other status still raises via raise_for_status().
    """
    get_rate_limiter().acquire(_PROVIDER)
    resp = httpx.get(f"{_BASE}{path}", params=params, timeout=15.0)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def map_commune(payload: dict, parsed: ParsedPlace) -> ResolvedPlace:
    """Pure map of a geo.api.gouv.fr commune payload → authoritative ResolvedPlace."""
    lon, lat = payload["centre"]["coordinates"]  # GeoJSON = [lon, lat]
    dep = payload.get("departement") or {}
    reg = payload.get("region") or {}
    levels = [PlaceLevel(name="France", place_type="Country")]
    if reg.get("nom"):
        levels.append(
            PlaceLevel(name=reg["nom"], place_type="Region", code=reg.get("code"))
        )
    if dep.get("nom"):
        levels.append(
            PlaceLevel(name=dep["nom"], place_type="Department", code=dep.get("code"))
        )
    return ResolvedPlace(
        name=payload["nom"],
        place_type="Municipality",
        lat=str(lat),
        long=str(lon),
        code=payload.get("code"),
        chains=[DatedChain(levels=levels)],
        alt_names=[DatedName(value=parsed.raw)],
        score=1.0,
        source="geo.api.gouv.fr",
        query=f"/communes/{payload.get('code')}",
    )


def resolve_fr(parsed: ParsedPlace) -> ResolvedPlace | None:
    """Résout une commune française.

    Code INSEE prioritaire (autoritaire) ; sinon par nom.
    """
    if parsed.insee:
        payload = _http_get(f"/communes/{parsed.insee}", {"fields": _FIELDS})
        if isinstance(payload, dict) and "centre" in payload:
            return map_commune(payload, parsed)
        return None
    if not parsed.commune:
        return None
    return _resolve_fr_by_name(parsed)


def pick_exact_by_name(results: list, parsed: ParsedPlace) -> list:
    """Ne garder que les correspondances de nom EXACTES, désambiguïsées par contexte.

    La recherche `nom` de geo.api.gouv.fr est floue : un quasi-homonyme ne doit
    jamais passer pour une résolution. Partagé par le résolveur des communes
    vivantes et par celui des ex-communes, qui interrogent deux endpoints au
    format identique.
    """
    exact = [c for c in results if _norm(c.get("nom", "")) == _norm(parsed.commune)]
    ctx = _norm(parsed.departement) or _norm(parsed.region)
    if ctx and len(exact) > 1:
        filtered = [
            c
            for c in exact
            if ctx
            in (
                _norm((c.get("departement") or {}).get("nom", "")),
                _norm((c.get("region") or {}).get("nom", "")),
            )
            or (
                bool(parsed.departement)
                and (c.get("departement") or {}).get("code", "") == parsed.departement
            )
        ]
        if filtered:
            exact = filtered
    return exact


def _resolve_fr_by_name(parsed: ParsedPlace) -> ResolvedPlace | None:
    """Résolution par nom via geo.api.gouv.fr.

    La recherche `nom` est floue -> on ne garde que les correspondances de
    nom EXACTES. 1 exact -> autoritaire ; >1 -> proposition ; 0 -> None.
    """
    results = _http_get(
        "/communes",
        {"nom": parsed.commune, "fields": _FIELDS, "boost": "population", "limit": 10},
    )
    if not isinstance(results, list) or not results:
        return None
    exact = pick_exact_by_name(results, parsed)
    if not exact:
        return None  # abréviations/fautes -> bascule registre
    if "centre" not in exact[0]:
        return None  # payload malformé -> pas de coordonnées
    resolved = map_commune(exact[0], parsed)  # exact[0] = le plus peuplé (boost)
    if len(exact) > 1:
        resolved.ambiguous = True  # vrais homonymes -> proposition
        resolved.source = f"geo.api.gouv.fr ({len(exact)} homonymes)"
    return resolved
