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

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Reason: this does NOT describe what a Gramps handle looks like - a
# 3425-handle check across every record type in the live tree (2026-08-26)
# found 21 real production handles that are not lowercase hex: one person
# handle is a UUID (with dashes), and twenty citation handles equal their
# own gramps_id (e.g. "C0055" - uppercase letters and digits, no dashes).
# Handles come in at least three shapes in this tree alone - hex, UUID,
# gramps_id-like - so no character-class-plus-length pattern can describe
# "a handle" without either rejecting real records or accepting arbitrary
# text. Do not try to narrow this again to look more handle-shaped.
#
# What this pattern actually constrains is narrower and does not depend on
# guessing a handle's format: a handle lands in a URL path segment, so it
# must not contain a character that means something there (/, ., ?, #, %,
# whitespace, backslash, etc). That is the same property USERNAME_PATTERN
# in tools/user_tools.py enforces on a value with the same URL-path fate,
# for the same reason.
#
# Reason: matched with re.fullmatch (not re.match), so no ^/$ anchors are
# needed here. re.match plus a "$" anchor accepts a trailing newline because
# "$" matches just before a final newline; fullmatch has no such gap.
HANDLE_PATTERN = r"[A-Za-z0-9_-]+"


def validate_handle_shape(value: str | None) -> str | None:
    """
    Reject a value that is not shaped like a Gramps handle.

    Args:
        value (str | None): The candidate handle, or None when the field
            is optional and unset.

    Returns:
        str | None: The value unchanged when it is None or well-shaped.

    Raises:
        ValueError: When the value is present and contains a character
            other than a letter, digit, underscore or dash.
    """
    # Reason: a handle lands in a URL path segment. Encoding in the client
    # already stops a crafted value from leaving its segment, but refusing
    # it here fails before any request is issued and names the problem,
    # rather than 404ing against an endpoint the caller never meant to hit.
    if value is not None and not re.fullmatch(HANDLE_PATTERN, value):
        raise ValueError(
            f"'{value}' is not a Gramps handle. A handle may contain only "
            "letters, digits, underscore and dash. To identify a record by "
            "its Gramps ID instead, use the gramps_id field."
        )
    return value


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
    # Reason: this field is declared only to be rejected. Without it,
    # pydantic's default extra="ignore" would silently drop a "query" key
    # instead of raising, leaving the caller with an unfiltered result set
    # they believe is filtered - the exact bug traced across six call sites
    # (issue #18). Declaring it lets validate_query() turn the mistake into
    # a loud error that names the two real search paths.
    query: str | None = Field(
        None,
        description=(
            "Not a supported parameter - present only so it can be rejected. "
            "Use gql= for an exact structured filter, or find_anything_tool "
            "for free-text search."
        ),
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        if v is not None:
            raise ValueError(
                "'query' is not a supported parameter here and was previously "
                "silently ignored (extra='ignore'), so any prior call using it "
                "ran unfiltered rather than doing what it looked like it did. "
                "Use gql= for an exact structured GQL filter, or "
                "find_anything_tool (find_anything) for genuine free-text "
                "search - that is the only search surface that honours 'query'."
            )
        return v

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


class StrictModel(BaseModel):
    """
    Base for write-path models: refuse unknown keys instead of dropping them.

    Pydantic's default is extra="ignore", which silently discards any key a
    model does not declare. On a write that means an incomplete record
    reaches Gramps while the call reports success - the failure mode behind
    issues #16 and #17. Read-path models keep the permissive default: a
    dropped key there only widens a result set.
    """

    model_config = {"extra": "forbid", "populate_by_name": True}


class BaseDataModel(StrictModel):
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
