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

"""Worldwide fallback resolver: Nominatim/OSM (ODbL, 1 req/s, User-Agent).

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/geo/nominatim.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.
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
from .score import best_similarity, is_ambiguous

_URL = "https://nominatim.openstreetmap.org/search"
_UA = "genecrew/1.0 (genealogy place standardizer; +https://github.com/)"
_PROVIDER = "Nominatim"


def _http_get(params: dict) -> list:
    get_rate_limiter().acquire(_PROVIDER)
    resp = httpx.get(_URL, params=params, headers={"User-Agent": _UA}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


def map_nominatim(results: list[dict], parsed: ParsedPlace) -> ResolvedPlace | None:
    """Pure map of Nominatim results → ResolvedPlace (worldwide, fuzzy).

    Picks the candidate with the best name-similarity score, not
    Nominatim's raw importance order.
    """
    if not results:
        return None
    scores = [
        best_similarity(parsed.commune, r.get("display_name", "").split(",")[0])
        for r in results
    ]
    best = max(range(len(results)), key=lambda i: scores[i])
    top = results[best]
    levels = []
    if parsed.country:
        levels.append(PlaceLevel(name=parsed.country, place_type="Country"))
    return ResolvedPlace(
        name=top.get("display_name", parsed.commune).split(",")[0].strip(),
        place_type="Municipality",
        lat=str(top["lat"]),
        long=str(top["lon"]),
        chains=[DatedChain(levels=levels)],
        alt_names=[DatedName(value=parsed.raw)],
        score=scores[best],
        ambiguous=is_ambiguous(scores),
        source="Nominatim/OSM",
        query=f"{parsed.commune}, {parsed.country}".strip(", "),
    )


def resolve_world(parsed: ParsedPlace) -> ResolvedPlace | None:
    """Resolve any place by name via Nominatim. None if nothing to search."""
    if not parsed.commune:
        return None
    q = f"{parsed.commune}, {parsed.country}".strip(", ")
    # accept-language=fr : sans lui, Nominatim renvoie les toponymes en
    # écriture locale (ex. Souk Ahras -> "سوق أهراس"), que la similarité
    # latine note ~0.1 -> indécidable.
    return map_nominatim(
        _http_get({"q": q, "format": "jsonv2", "limit": 5, "accept-language": "fr"}),
        parsed,
    )
