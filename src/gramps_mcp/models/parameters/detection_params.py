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

"""
Pydantic models for the read-only detection tools.

Tools supported in this category:
- find_duplicates: candidate duplicate people, clustered
- audit_quality: deterministic consistency anomalies
- geocode_place: a free-text place name resolved against gazetteers
"""

from typing import Literal

from pydantic import BaseModel, Field


class _CollectLimitParams(BaseModel):
    """Shared `limit` field for the two collect_tree-backed tools.

    `find_duplicates` and `audit_quality` both bound their scan to the same
    parameter, with the same wording - factored here so the two stay in
    sync rather than drifting apart the way the two `limit` blocks already
    had before this was extracted.
    """

    limit: int | None = Field(
        None,
        ge=1,
        description=(
            "Stop after this many people. Cheap when set: the request asks "
            "the API for exactly this many people (page=1, pagesize=limit) "
            "instead of downloading everyone and trimming client-side. "
            "Families are always fetched whole regardless of this bound. "
            "Omit to scan the whole tree."
        ),
    )


class FindDuplicatesParams(_CollectLimitParams):
    """Parameters for finding candidate duplicate people."""


class AuditQualityParams(_CollectLimitParams):
    """Parameters for the deterministic quality audit."""

    # Reason: Anomaly.severity (genealogy/domain.py) is a closed set of
    # three French values, produced only by rules.py's own literals - never
    # user input. A free-form `str` here would let a caller pass "high" or
    # "haute " and silently get zero matches, indistinguishable from a
    # clean tree. Literal makes an unsupported value a validation error
    # instead of a quiet no-op.
    severity: Literal["haute", "moyenne", "basse"] | None = Field(
        None,
        description=(
            "Report only anomalies at this severity - haute, moyenne or "
            "basse. Omit to report every severity."
        ),
    )


class GeocodePlaceParams(BaseModel):
    """Parameters for resolving a free-text place name."""

    query: str = Field(
        description="Free-text place name, for example 'Bourges, Cher, France'"
    )
    min_score: float = Field(
        0.90,
        ge=0.0,
        le=1.0,
        description=(
            "Score at or above which the resolution is considered solid. "
            "Below it, the result is rendered as a proposal to review."
        ),
    )
