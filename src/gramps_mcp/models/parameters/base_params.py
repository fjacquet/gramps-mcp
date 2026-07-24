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
Base parameter classes for common patterns across Gramps API operations.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

# Common choices for validation
PROFILE_CHOICES = [
    "all",
    "self",
    "families",
    "events",
    "age",
    "span",
    "ratings",
    "references",
]

EXTEND_CHOICES = [
    "all",
    "citation_list",
    "event_ref_list",
    "family_list",
    "media_list",
    "note_list",
    "parent_family_list",
    "person_ref_list",
    "primary_parent_family",
    "tag_list",
    "backlinks",
]


class BaseGetMultipleParams(BaseModel):
    """Common parameters for GET operations that return multiple objects."""

    gramps_id: str | None = Field(
        None, description="An alternate user managed identifier"
    )
    page: int | None = Field(
        None, description="Page number representing a subset of results"
    )
    pagesize: int | None = Field(
        None, description="The number of items that constitute a page"
    )
    sort: str | None = Field(
        None, description="Comma delimited list of keys to sort the result set by"
    )
    gql: str | None = Field(
        None, description="A Gramps QL query string that is used to filter the objects"
    )
    backlinks: bool | None = Field(
        None, description="Include handles to objects referring to the object"
    )
    extend: str | None = Field(
        None, description="Enables the return of extended record information"
    )
    profile: str | None = Field(
        None,
        description="Enables the return of summarized information about the object",
    )

    @field_validator("extend")
    @classmethod
    def validate_extend(cls, v):
        if v is not None:
            extend_list = [choice.strip() for choice in v.split(",")]
            for choice in extend_list:
                if choice not in EXTEND_CHOICES:
                    raise ValueError(
                        f"Invalid extend choice: {choice}. "
                        f"Must be one of {EXTEND_CHOICES}"
                    )
        return v

    @field_validator("profile")
    @classmethod
    def validate_profile(cls, v):
        if v is not None:
            profile_list = [choice.strip() for choice in v.split(",")]
            for choice in profile_list:
                if choice not in PROFILE_CHOICES:
                    raise ValueError(
                        f"Invalid profile choice: {choice}. "
                        f"Must be one of {PROFILE_CHOICES}"
                    )
        return v


class BaseGetSingleParams(BaseModel):
    """Common parameters for GET operations that return a single object."""

    backlinks: bool | None = Field(
        None, description="Include handles to objects referring to the object"
    )
    extend: str | None = Field(
        None, description="Enables the return of extended record information"
    )
    profile: str | None = Field(
        None,
        description="Enables the return of summarized information about the object",
    )

    @field_validator("extend")
    @classmethod
    def validate_extend(cls, v):
        if v is not None:
            extend_list = [choice.strip() for choice in v.split(",")]
            for choice in extend_list:
                if choice not in EXTEND_CHOICES:
                    raise ValueError(
                        f"Invalid extend choice: {choice}. "
                        f"Must be one of {EXTEND_CHOICES}"
                    )
        return v

    @field_validator("profile")
    @classmethod
    def validate_profile(cls, v):
        if v is not None:
            profile_list = [choice.strip() for choice in v.split(",")]
            for choice in profile_list:
                if choice not in PROFILE_CHOICES:
                    raise ValueError(
                        f"Invalid profile choice: {choice}. "
                        f"Must be one of {PROFILE_CHOICES}"
                    )
        return v


class BaseDataModel(BaseModel):
    """Base class for data models used in POST/PUT operations."""

    handle: str | None = Field(None, description="Object's unique handle identifier")
    gramps_id: str | None = Field(
        None, description="An alternate user managed identifier"
    )
    note_list: list[str] | None = Field(None, description="List of handles for notes")
    media_list: list[dict[str, Any]] | None = Field(
        None, description="List of references to media"
    )
    attribute_list: list[dict[str, Any]] | None = Field(
        None, description="List of attributes"
    )
    tag_list: list[str] | None = Field(None, description="List of handles to tags")
    private: bool | None = Field(None, description="Whether the object is private")
    change: int | None = Field(
        None, description="Time in epoch format the record was last modified"
    )

    model_config = {"populate_by_name": True}
