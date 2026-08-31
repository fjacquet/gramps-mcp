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

"""Switzerland resolver: swisstopo GeoAdmin SearchServer (WGS84 lat/lon).

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/geo/suisse.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.
"""

from __future__ import annotations

import re

import httpx

from ..domain import (
    DatedChain,
    DatedName,
    ParsedPlace,
    PlaceLevel,
    ResolvedPlace,
)
from ..rate_limit import get_rate_limiter
from .score import best_similarity, is_ambiguous

_URL = "https://api3.geo.admin.ch/rest/services/api/SearchServer"
_TAG = re.compile(r"<[^>]+>")
_PROVIDER = "Swisstopo"

# swisstopo étiquette chaque commune "Nom (XX)" où XX = code du canton. On
# récupère le canton comme niveau parent (Suisse › Canton › Commune), analogue
# au département FR / Land DE. Le type Gramps posé est `State` et non
# `Canton` : `Canton` n'est pas un type natif, et chaque type personnalisé est
# une ligne de plus à ne pas oublier dans les filtres par type.
_CANTON_RE = re.compile(r"\s*\(([A-Z]{2})\)\s*$")
_CANTONS = {
    "AG": "Argovie",
    "AI": "Appenzell Rhodes-Intérieures",
    "AR": "Appenzell Rhodes-Extérieures",
    "BE": "Berne",
    "BL": "Bâle-Campagne",
    "BS": "Bâle-Ville",
    "FR": "Fribourg",
    "GE": "Genève",
    "GL": "Glaris",
    "GR": "Grisons",
    "JU": "Jura",
    "LU": "Lucerne",
    "NE": "Neuchâtel",
    "NW": "Nidwald",
    "OW": "Obwald",
    "SG": "Saint-Gall",
    "SH": "Schaffhouse",
    "SO": "Soleure",
    "SZ": "Schwytz",
    "TG": "Thurgovie",
    "TI": "Tessin",
    "UR": "Uri",
    "VD": "Vaud",
    "VS": "Valais",
    "ZG": "Zoug",
    "ZH": "Zurich",
}


def _split_label(label: str) -> tuple[str, str | None]:
    """'Lausanne (VD)' -> ('Lausanne', 'Vaud').

    Sans code canton valide -> (label, None).
    """
    m = _CANTON_RE.search(label)
    if m:
        canton = _CANTONS.get(m.group(1))
        if canton:
            return label[: m.start()].strip(), canton
    return label.strip(), None


def split_canton_suffix(label: str) -> tuple[str, str | None]:
    """'Montreux (VD)' -> ('Montreux', 'Vaud').

    Alias public de `_split_label`, utilisé par le parseur de lieux pour
    reconnaître un nom suisse dépourvu de segment pays.
    """
    return _split_label(label)


def _http_get(url: str, params: dict) -> dict:
    get_rate_limiter().acquire(_PROVIDER)
    resp = httpx.get(url, params=params, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


def map_swiss(payload: dict, parsed: ParsedPlace) -> ResolvedPlace | None:
    """Pure map of a swisstopo SearchServer payload → ResolvedPlace (lat/lon WGS84)."""
    results = payload.get("results") or []
    if not results:
        return None
    labels = [_TAG.sub("", r["attrs"].get("label", "")).strip() for r in results]
    scores = [best_similarity(parsed.commune, lbl) for lbl in labels]
    best = max(range(len(results)), key=lambda i: scores[i])
    attrs = results[best]["attrs"]
    name, canton = _split_label(labels[best])
    levels = [PlaceLevel(name="Suisse", place_type="Country")]
    if canton:
        levels.append(PlaceLevel(name=canton, place_type="State"))
    return ResolvedPlace(
        name=name or parsed.commune,
        place_type="Municipality",
        lat=str(attrs["lat"]),
        long=str(attrs["lon"]),  # WGS84 ; jamais x/y (LV95)
        chains=[DatedChain(levels=levels)],
        alt_names=[DatedName(value=parsed.raw)],
        score=scores[best],
        ambiguous=is_ambiguous(scores),
        source="swisstopo",
        query=parsed.commune,
    )


def resolve_ch(parsed: ParsedPlace) -> ResolvedPlace | None:
    """Resolve a Swiss place by name via swisstopo. None if no commune to search."""
    if not parsed.commune:
        return None
    payload = _http_get(
        _URL,
        {
            "searchText": parsed.commune,
            "type": "locations",
            "origins": "gg25",
            "sr": "4326",
            "limit": 5,
        },
    )
    return map_swiss(payload, parsed)
