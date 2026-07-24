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

from pydantic import BaseModel, Field

from .base_params import BaseGetMultipleParams, BaseGetSingleParams


class PlaceSearchParams(BaseGetMultipleParams):
    """Parameters for searching places."""

    pass


class PlaceDetailsParams(BaseGetSingleParams):
    """Parameters for getting specific place details."""

    pass


class PlaceSaveParams(BaseModel):
    """Parameters for creating or updating a place."""

    handle: str | None = Field(
        None, min_length=8, description="Place handle (for updates; omit for new place)"
    )
    gramps_id: str | None = Field(None, description="Alternate user managed identifier")
    name: dict | None = Field(None, description="Place name object with 'value' field")
    code: str | None = Field(None, description="Place code")
    alt_loc: list[dict] | None = Field(None, description="Alternative locations")
    place_type: str = Field(..., description="Place type")
    placeref_list: list[dict] | None = Field(
        None, description="List of place references"
    )
    alt_names: list[str] | None = Field(None, description="Alternative names")
    lat: str | None = Field(None, description="Latitude coordinate")
    long: str | None = Field(None, description="Longitude coordinate")
    urls: list[dict] | None = Field(None, description="Associated URLs")
    media_list: list[str] | None = Field(None, description="List of media handles")
    citation_list: list[str] | None = Field(
        None, description="List of citation handles"
    )
    note_list: list[str] | None = Field(None, description="List of note handles")
    tag_list: list[str] | None = Field(None, description="List of tag handles")
    private: bool | None = Field(None, description="Mark as private")
