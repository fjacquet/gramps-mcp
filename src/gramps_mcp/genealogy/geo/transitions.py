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

"""Data-driven temporal transitions (sovereignty/name changes). Dataset-agnostic.

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/geo/transitions.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.

The source resolves its data path as `parent.parent / "data"` because its
`geo/` and `data/` siblings both hang off `tools/genealogy/`. Here `data/`
sits directly under `geo/`, so the path expression is `parent / "data"`.

Gramps natively models dated names and dated placerefs. This module emits two
dated parent chains (before/after) + a dated alt_name WHEN a transition row
matches the resolved country. Empty dataset -> single undated chain (generic).
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from ..domain import (
    DatedChain,
    DatedName,
    ParsedPlace,
    PlaceLevel,
    ResolvedPlace,
)

_DATA = Path(__file__).resolve().parent / "data" / "transitions.csv"
_COLS = ("modern_country", "historical_country", "historical_parent", "date")


class Transition(BaseModel):
    """One known transition: the modern country splits from a historical parent.

    Splits at `date`.
    """

    modern_country: str
    historical_country: str
    historical_parent: str
    date: str  # ISO YYYY-MM-DD


@lru_cache(maxsize=1)
def load_transitions() -> list[Transition]:
    """Load transitions from the embedded CSV (empty/missing -> [])."""
    if not _DATA.exists():
        return []
    with _DATA.open(encoding="utf-8") as f:
        return [
            Transition(**{c: row[c] for c in _COLS})
            for row in csv.DictReader(f)
            if row.get("modern_country")
        ]


def apply_transition(
    resolved: ResolvedPlace | None,
    parsed: ParsedPlace,
    transitions: list[Transition],
) -> ResolvedPlace | None:
    """Split into two dated chains + dated alt_name when a transition matches.

    Matches on `parsed.country`.
    """
    if resolved is None:
        return resolved
    t = next((t for t in transitions if t.modern_country == parsed.country), None)
    if t is None:
        return resolved
    modern = [
        DatedChain(levels=c.levels, date_qualifier=f"après {t.date}")
        for c in resolved.chains
    ] or [
        DatedChain(
            levels=[PlaceLevel(name=parsed.country, place_type="Country")],
            date_qualifier=f"après {t.date}",
        )
    ]
    hist_levels = [
        PlaceLevel(name=t.historical_parent, place_type="Country"),
        PlaceLevel(name=t.historical_country, place_type="Region"),
    ]
    if parsed.departement:
        hist_levels.append(PlaceLevel(name=parsed.departement, place_type="Department"))
    historical = DatedChain(levels=hist_levels, date_qualifier=f"avant {t.date}")
    return resolved.model_copy(
        update={
            "chains": [*modern, historical],
            "alt_names": [
                DatedName(value=parsed.raw, date_qualifier=f"avant {t.date}")
            ],
        }
    )
