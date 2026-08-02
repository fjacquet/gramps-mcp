# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
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
Pydantic models for analysis and query tools that use direct dict access
(tree stats, ancestors/descendants, relationship, living status, timeline).
"""

from pydantic import BaseModel, Field


class TreeInfoParams(BaseModel):
    include_statistics: bool = Field(True, description="Include statistics")


class DescendantsParams(BaseModel):
    gramps_id: str = Field(..., description="Person ID")
    max_generations: int | None = Field(
        5,
        description=(
            "Max generations to retrieve (default: 5, use higher values "
            "carefully as they can overflow context)"
        ),
    )


class AncestorsParams(BaseModel):
    gramps_id: str = Field(..., description="Person ID")
    max_generations: int | None = Field(
        5,
        description=(
            "Max generations to retrieve (default: 5, use higher values "
            "carefully as they can overflow context)"
        ),
    )


class RelationshipQueryParams(BaseModel):
    person1: str = Field(..., description="Handle or gramps_id of the first person")
    person2: str = Field(..., description="Handle or gramps_id of the second person")
    all_relationships: bool = Field(
        False,
        description=(
            "If true, return all possible relationships; if false, only "
            "the most direct one"
        ),
    )
    depth: int | None = Field(
        None, ge=1, description="Search depth in generations (API default: 15)"
    )


class LivingStatusParams(BaseModel):
    person: str = Field(
        ..., description="Handle or gramps_id of the person to evaluate"
    )
    average_generation_gap: int | None = Field(None, ge=1)
    max_age_probably_alive: int | None = Field(None, ge=1)
    max_sibling_age_difference: int | None = Field(None, ge=0)
    include_dates: bool = Field(
        True, description="Also fetch estimated birth/death dates"
    )


class TimelineQueryParams(BaseModel):
    scope: str = Field(
        ...,
        description=(
            "One of: 'person', 'family', 'people', 'families' - whose timeline to build"
        ),
    )
    target: str | None = Field(
        None,
        description=(
            "Handle or gramps_id of the person/family (required when scope "
            "is 'person' or 'family'; optional anchor for scope 'people')"
        ),
    )
    dates: str | None = Field(
        None, description="Date range filter, e.g. '1900/1/1-1950/1/1'"
    )
    handles: str | None = Field(
        None, description="Comma-delimited handles (scope 'people'/'families' only)"
    )
    events: str | None = Field(
        None, description="Comma-delimited event types to include"
    )
    event_classes: str | None = Field(
        None, description="Comma-delimited event classes to include"
    )
    ratings: bool | None = Field(
        None,
        description=(
            "Include citation count and confidence score (not used for scope 'person')"
        ),
    )
    precision: int | None = Field(
        None, ge=1, le=3, description="Date precision, 1-3 (scope 'people' only)"
    )
    discard_empty: bool | None = Field(
        None, description="Discard undated events (not used for scope 'person')"
    )
    first: bool | None = Field(
        None,
        description=(
            "Include events before the anchor's first event "
            "(scope 'person'/'people' only)"
        ),
    )
    last: bool | None = Field(
        None,
        description=(
            "Include events after the anchor's last event "
            "(scope 'person'/'people' only)"
        ),
    )
    page: int | None = Field(
        None, ge=0, description="Page number (not used for scope 'person')"
    )
    pagesize: int | None = Field(
        None, gt=0, description="Items per page (not used for scope 'person')"
    )
