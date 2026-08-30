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


class FindDuplicatesParams(BaseModel):
    """Parameters for finding candidate duplicate people."""

    limit: int | None = Field(
        None,
        description=(
            "Stop after this many people, for a cheap probe. Omit to scan "
            "the whole tree."
        ),
    )


class AuditQualityParams(BaseModel):
    """Parameters for the deterministic quality audit."""

    limit: int | None = Field(
        None,
        description=(
            "Stop after this many people, for a cheap probe. Omit to scan "
            "the whole tree."
        ),
    )
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
