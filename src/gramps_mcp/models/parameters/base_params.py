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

# Reason: this does NOT describe what a Gramps handle looks like. A sweep
# of every handle in the live tree - all ten record categories, 6496
# handles (2026-08-26) - found real production handles in four different
# shapes: lowercase hex, a UUID (with dashes), citation handles equal to
# their own gramps_id ("C0055" - uppercase letters and digits), and one
# corrupt citation handle that ends in three literal dots
# ("103da162...", gramps_id C0620). No character-class-plus-length pattern
# can describe "a handle" across those without either rejecting a real
# record or accepting arbitrary text.
#
# The dot was added to this class after that sweep, correcting an earlier
# version of this rule. That version was written from a survey covering
# only 3425 handles - it did not reach every category - and its comment
# claimed dots could be excluded because no handle contained one. The full
# sweep disproved that: the server resolves GET /api/citations/103da162...
# with 200, and so does the percent-encoded form the client actually sends
# (/api/citations/103da162%2E%2E%2E). Refusing that value here removed a
# repair without removing a risk, because DetachReferenceParams.ref_handle
# is required and has no gramps_id alternative, so detaching that corrupt
# citation from its event was unreachable through the tools. Narrowing
# this again is not forbidden, but it needs the same evidence: re-run the
# full ten-category sweep and show the shape being refused is absent.
#
# What this pattern actually constrains does not depend on guessing a
# handle's format: a handle lands in a URL path segment, so it must not
# contain a character that means something there (/, ?, #, %, whitespace,
# backslash, etc). A dot is only dangerous when it is the *whole* segment
# ("." and ".." are the current and parent directory), which is why
# is_dot_only_segment below refuses those separately rather than the
# character class refusing every dot - a dot mixed with other characters
# never forms a relative-path segment. USERNAME_PATTERN in
# tools/user_tools.py, r"[A-Za-z0-9_.-]{2,64}", guards a value with the
# same URL-path fate and now permits the same character set; it has no
# dot-only check, and does not need one, because percent-encoding in
# _build_url_with_substitution is what confines both values to their
# segment.
#
# This name-for-the-job (not "HANDLE_PATTERN") is deliberate: a name that
# does not say which job it does is how a stricter, narrower rule
# (place-name-vs-handle discrimination, PLACE_HANDLE_PATTERN in
# event_params.py) and this URL-safety rule got merged into one constant
# and broke each other - see commit e0a07eb.
#
# Reason: matched with re.fullmatch (not re.match), so no ^/$ anchors are
# needed here. re.match plus a "$" anchor accepts a trailing newline because
# "$" matches just before a final newline; fullmatch has no such gap.
URL_SAFE_IDENTIFIER_PATTERN = r"[A-Za-z0-9_.-]+"


def is_dot_only_segment(value: str) -> bool:
    """
    Report whether a value consists of nothing but dots.

    Values like ".", ".." and "..." are relative-path segments rather than
    identifiers. This is a membership test, not a pattern, so it refuses
    every such value at any length while leaving a dot that appears
    alongside other characters alone.

    Args:
        value (str): The candidate identifier.

    Returns:
        bool: True when the value is non-empty and every character is a dot.
    """
    return bool(value) and set(value) == {"."}


def validate_handle_shape(value: str | None) -> str | None:
    """
    Reject a value that is not shaped like a Gramps handle.

    Wired into three models only - DeleteTypeParams, DetachReferenceParams
    and MergeTypeParams, in destructive_params.py - not into parameter
    models generally. Applying it more broadly is a deliberate follow-up,
    not a consequence of this function's existence.

    Args:
        value (str | None): The candidate handle, or None when the field
            is optional and unset.

    Returns:
        str | None: The value unchanged when it is None or well-shaped.

    Raises:
        ValueError: When the value is present and either contains a
            character other than a letter, digit, underscore, dot or dash,
            or consists of nothing but dots.
    """
    # Reason: a handle lands in a URL path segment. Encoding in the client
    # already stops a crafted value from leaving its segment, but refusing
    # it here fails before any request is issued and names the problem,
    # rather than 404ing against an endpoint the caller never meant to hit.
    if value is None:
        return value
    if not re.fullmatch(URL_SAFE_IDENTIFIER_PATTERN, value) or is_dot_only_segment(
        value
    ):
        raise ValueError(
            f"'{value}' is not a Gramps handle. A handle may contain only "
            "letters, digits, underscore, dot and dash, and may not consist "
            "of dots alone. To identify a record by its Gramps ID instead, "
            "use the gramps_id field."
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
