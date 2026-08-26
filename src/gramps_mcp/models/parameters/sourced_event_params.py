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
Pydantic model for the create_sourced_event composite tool.

Chains source + citation + event creation into one call, auto-wiring the
citation onto the event so callers never retype a handle between steps.
"""

import re

from pydantic import Field, field_validator, model_validator

from .base_params import StrictModel
from .date_params import DateValue
from .event_params import PLACE_HANDLE_PATTERN


class SourcedEventData(StrictModel):
    """Composite parameters for create_sourced_event."""

    # Source fields
    source_title: str | None = Field(
        None,
        description=(
            "Title of a new source to create. Mutually exclusive with "
            "source_handle: supply exactly one."
        ),
        min_length=1,
    )
    source_handle: str | None = Field(
        None,
        description=(
            "Handle of an existing source to attach the new citation to. "
            "Mutually exclusive with source_title: supply exactly one. Use "
            "this to record several facts from one document without "
            "creating a duplicate source for each."
        ),
    )
    source_author: str | None = Field(None, description="Source author")
    source_pubinfo: str | None = Field(None, description="Source publication info")

    # Citation fields
    citation_page: str | None = Field(
        None, description="Page or location within the source"
    )
    citation_date: DateValue | None = Field(None, description="Citation date")

    # Event fields
    event_type: str = Field(
        ..., description="Event type (Birth, Death, Marriage, etc.)"
    )
    event_date: DateValue | None = Field(None, description="Event date object")
    event_place: str | None = Field(
        None,
        description=(
            "Place handle where the event occurred. This is a handle, not a "
            "name: use find_type(type='place', ...) to obtain one. Passing a "
            "name overwrites the event's existing place."
        ),
    )
    event_description: str | None = Field(None, description="Event description")

    # Attaches to the citation, matching this codebase's existing sourcing
    # convention (see TestCreateCitationTool)
    media_path: str | None = Field(
        None, description="Local file to upload and attach to the citation"
    )
    note_list: list[str] | None = Field(
        None, description="Note handles to attach to the citation"
    )

    @field_validator("event_place")
    @classmethod
    def validate_event_place_is_handle(cls, value: str | None) -> str | None:
        """Reject a place name before any source/citation/event is created.

        This mirrors ``EventSaveParams.validate_place_is_handle`` (see
        ``event_params.py``), but must run here too: by the time this value
        reaches ``EventSaveParams`` in ``create_sourced_event_tool``, the
        source, media and citation have already been committed to the live
        tree, so a refusal at that point leaves orphans behind. Validating
        it on this model refuses the call before any network call is made.

        Args:
            value (str | None): The proposed place value.

        Returns:
            str | None: The value unchanged, if it is a valid handle.

        Raises:
            ValueError: If value is not None and does not match
                PLACE_HANDLE_PATTERN.
        """
        if value is not None and not re.fullmatch(PLACE_HANDLE_PATTERN, value):
            raise ValueError(
                f"event_place must be a place handle, not a name. Got: "
                f"{value!r}. Use find_type(type='place', ...) to obtain the "
                "handle for this place."
            )
        return value

    @model_validator(mode="after")
    def check_exactly_one_source(self) -> "SourcedEventData":
        """
        Require exactly one of source_title or source_handle.

        Returns:
            SourcedEventData: The validated model.

        Raises:
            ValueError: If both are given or neither is.
        """
        if bool(self.source_title) == bool(self.source_handle):
            raise ValueError(
                "supply exactly one of source_title or source_handle: "
                "source_title creates a new source, source_handle attaches "
                "the citation to an existing one."
            )
        return self
