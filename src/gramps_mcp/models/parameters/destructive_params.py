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

"""Parameter models for the destructive operation tools."""

from typing import Literal

from pydantic import Field

from .base_params import StrictModel

RecordType = Literal[
    "person",
    "family",
    "event",
    "place",
    "source",
    "citation",
    "repository",
    "media",
    "note",
    "tag",
]

MergeableType = Literal[
    "person",
    "family",
    "event",
    "place",
    "source",
    "citation",
    "repository",
    "media",
    "note",
]


class DeleteTypeParams(StrictModel):
    """Parameters for deleting a single record."""

    type: RecordType = Field(description="Record type to delete")
    handle: str | None = Field(None, description="Object handle")
    gramps_id: str | None = Field(
        None, description="Gramps ID, for example I0001 (alternative to handle)"
    )
    force: bool = Field(
        False,
        description=(
            "Delete even though other records still reference this one, "
            "severing those references. Without it the call is refused and "
            "the referencing records are listed."
        ),
    )


class DetachReferenceParams(StrictModel):
    """Parameters for removing one element from a record's list."""

    type: RecordType = Field(description="Type of the record holding the list")
    handle: str | None = Field(None, description="Object handle")
    gramps_id: str | None = Field(
        None,
        description="Gramps ID (alternative to handle)",
    )
    list_name: str = Field(
        description=(
            "Name of the list to edit, for example event_ref_list, "
            "child_ref_list, media_list, note_list, citation_list, tag_list"
        )
    )
    ref_handle: str = Field(description="Handle of the element to remove")


class MergeTypeParams(StrictModel):
    """Parameters for merging two records of the same type."""

    type: MergeableType = Field(
        description="Record type to merge (tags cannot be merged)"
    )
    phoenix_handle: str = Field(description="Handle of the record that survives")
    titanic_handle: str = Field(
        description="Handle of the record that is absorbed and disappears"
    )
    confirm: bool = Field(
        False,
        description=(
            "Perform the merge. Without it the call returns a preview of both "
            "records and changes nothing."
        ),
    )
    phoenix_father_handle: str | None = Field(
        None, description="Family merges only: which father the result keeps"
    )
    phoenix_mother_handle: str | None = Field(
        None, description="Family merges only: which mother the result keeps"
    )
