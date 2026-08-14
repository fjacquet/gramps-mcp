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
Pydantic models for place-related operations.

API calls supported in this category:
- GET_PLACES: Get information about multiple places
- POST_PLACES: Add a new place to the database
- GET_PLACE: Get information about a specific place
- PUT_PLACE: Update the place
- DELETE_PLACE: Delete the place
"""

from typing import Any

from pydantic import Field, field_validator

from .base_params import BaseGetMultipleParams, BaseGetSingleParams, StrictModel


class PlaceSearchParams(BaseGetMultipleParams):
    """Parameters for searching places."""

    pass


class PlaceDetailsParams(BaseGetSingleParams):
    """Parameters for getting specific place details."""

    pass


class PlaceSaveParams(StrictModel):
    """Parameters for creating or updating a place."""

    handle: str | None = Field(
        None, min_length=8, description="Place handle (for updates; omit for new place)"
    )
    gramps_id: str | None = Field(None, description="Alternate user managed identifier")
    name: dict | None = Field(None, description="Place name object with 'value' field")
    code: str | None = Field(None, description="Place code")
    alt_loc: list[dict] | None = Field(None, description="Alternative locations")
    place_type: str | None = Field(
        None,
        description=(
            "Place type, for example City or Parish. Optional in both "
            "directions: supply it when creating a place, since otherwise "
            "Gramps records the type as 'Unknown'; it can be omitted when "
            "updating one, so a partial update does not have to resupply it."
        ),
    )
    placeref_list: list[dict] | None = Field(
        None, description="List of place references"
    )
    alt_names: list[dict[str, Any]] | None = Field(
        None,
        description=(
            "Alternative names as PlaceName objects, for example "
            "[{'value': 'Lugdunum'}]"
        ),
    )
    lat: str | None = Field(None, description="Latitude coordinate")
    long: str | None = Field(None, description="Longitude coordinate")
    urls: list[dict] | None = Field(None, description="Associated URLs")
    media_list: list[dict[str, Any]] | None = Field(
        None,
        description="Media references as objects, for example [{'ref': '<handle>'}]",
    )
    citation_list: list[str] | None = Field(
        None, description="List of citation handles"
    )
    note_list: list[str] | None = Field(None, description="List of note handles")
    tag_list: list[str] | None = Field(None, description="List of tag handles")
    private: bool | None = Field(None, description="Mark as private")
    replace_lists: list[str] | None = Field(
        None,
        description=(
            "List field names to overwrite rather than add to, for example "
            "['placeref_list'] to move a place to a different parent instead "
            "of giving it a second one. Omit to add to existing lists. "
            "Note: this value is consumed from the raw tool arguments and "
            "popped before this model is built, so validated_params.replace_lists "
            "is always None at runtime - it is declared here only so it "
            "appears in the tool's advertised input schema."
        ),
    )

    @field_validator("alt_names", mode="before")
    @classmethod
    def validate_alt_names_shape(
        cls, value: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]] | None:
        """Reject non-object entries with a message naming the expected shape.

        A bare ``list[dict[str, Any]]`` constraint raises Pydantic's generic
        "Input should be a valid dictionary or object to extract fields
        from", which drops the field's description and never mentions the
        PlaceName object shape a caller needs. This validator raises
        instead, showing what was received and what is expected - the same
        treatment ``EventSaveParams.validate_place_is_handle`` gives a bad
        place value.

        Args:
            value (list[dict[str, Any]] | None): The proposed alt_names value.

        Returns:
            list[dict[str, Any]] | None: The value unchanged, if every entry
                is already a dict.

        Raises:
            ValueError: If any entry is not a dict.
        """
        if value is not None:
            for entry in value:
                if not isinstance(entry, dict):
                    raise ValueError(
                        "alt_names entries must be PlaceName objects, not "
                        f"bare strings. Got: {entry!r}. Use a shape like "
                        "[{'value': 'Lugdunum'}]."
                    )
        return value

    @field_validator("media_list", mode="before")
    @classmethod
    def validate_media_list_shape(
        cls, value: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]] | None:
        """Reject non-object entries with a message naming the expected shape.

        Mirrors ``validate_alt_names_shape``: a bare handle string used to
        be accepted here (before this branch changed the type to
        ``list[dict[str, Any]]``), so callers following the old shape now
        hit a generic Pydantic error with no mention of the new one. This
        raises with the expected object shape instead.

        Args:
            value (list[dict[str, Any]] | None): The proposed media_list value.

        Returns:
            list[dict[str, Any]] | None: The value unchanged, if every entry
                is already a dict.

        Raises:
            ValueError: If any entry is not a dict.
        """
        if value is not None:
            for entry in value:
                if not isinstance(entry, dict):
                    raise ValueError(
                        "media_list entries must be MediaRef objects, not "
                        f"bare handle strings. Got: {entry!r}. Use a shape "
                        "like [{'ref': '<handle>'}]."
                    )
        return value
