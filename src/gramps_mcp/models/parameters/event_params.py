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
Pydantic models for event-related operations.

API calls supported in this category:
- GET_EVENTS: Get information about multiple events
- POST_EVENTS: Add a new event to the database
- GET_EVENT: Get information about a specific event
- PUT_EVENT: Update the event
- DELETE_EVENT: Delete the event
- GET_EVENT_SPAN: Get elapsed time span between two events
"""

import re

from pydantic import BaseModel, Field, field_validator

from .base_params import BaseGetMultipleParams, StrictModel
from .date_params import DateValue

# Reason: a Gramps handle is a lowercase hexadecimal string. Live-tree
# sampling (2026-08-13, GET_PLACES) found handles of 26-32 lowercase hex
# characters (0-9a-f only - no uppercase, no g-z). Place names contain
# spaces, hyphens or accents, or are simply short, so this pattern separates
# them. The 16-char floor stays below the smallest observed handle (26) to
# tolerate handle shapes not covered by that sample. Passing a name here
# used to overwrite a valid handle with text that resolves to nothing - the
# trap documented in CLAUDE.md.
#
# Reason: matched with re.fullmatch (not re.match), so no ^/$ anchors are
# needed here. re.match plus a "$" anchor accepts a trailing newline because
# "$" matches just before a final newline; fullmatch has no such gap.
HANDLE_PATTERN = r"[0-9a-f]{16,}"


class EventSearchParams(BaseGetMultipleParams):
    """Parameters for searching multiple events."""

    dates: str | None = Field(
        None, description="Date filter (y/m/d, -y/m/d, y/m/d-y/m/d, y/m/d-)"
    )


class EventSaveParams(StrictModel):
    """Parameters for creating or updating an event."""

    handle: str | None = Field(
        None, description="Event's handle (for updates; omit for new event)"
    )
    type: str = Field(description="Event type (Birth, Death, Marriage, etc.)")
    date: DateValue | None = Field(None, description="Event date")
    description: str | None = Field(None, description="Event description")
    place: str | None = Field(
        None,
        description=(
            "Place handle where the event occurred. This is a handle, not a "
            "name: use find_type(type='place', ...) to obtain one. Passing a "
            "name overwrites the event's existing place."
        ),
    )
    citation_list: list[str] = Field(..., description="List of citation handles")
    note_list: list[str] | None = Field(None, description="List of note handles")

    @field_validator("place")
    @classmethod
    def validate_place_is_handle(cls, value: str | None) -> str | None:
        """Reject a place name where a handle is required.

        A bare Pydantic ``pattern=`` constraint raises its own generic
        error and drops the field's ``description``, so the caller never
        sees the guidance on how to fix the call. This validator raises
        instead, carrying the offending value and pointing at
        ``find_type`` so the failure is loud and actionable, not just loud.

        Args:
            value (str | None): The proposed place value.

        Returns:
            str | None: The value unchanged, if it is a valid handle.

        Raises:
            ValueError: If value is not None and does not match
                HANDLE_PATTERN.
        """
        if value is not None and not re.fullmatch(HANDLE_PATTERN, value):
            raise ValueError(
                f"place must be a place handle, not a name. Got: {value!r}. "
                "Use find_type(type='place', ...) to obtain the handle for "
                "this place."
            )
        return value


class EventSpanParams(BaseModel):
    """Parameters for getting elapsed time span between two events."""

    handle1: str = Field(description="The unique identifier for the first event")
    handle2: str = Field(description="The unique identifier for the second event")
    as_age: bool | None = Field(None, description="Return result as an age")
    precision: int | None = Field(
        None, ge=1, le=3, description="Number of significant levels (1-3)"
    )
