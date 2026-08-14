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
    phoenix_handle: str | None = Field(
        None, description="Handle of the record that survives"
    )
    phoenix_gramps_id: str | None = Field(
        None,
        description=(
            "Gramps ID of the record that survives (alternative to phoenix_handle)"
        ),
    )
    titanic_handle: str | None = Field(
        None, description="Handle of the record that is absorbed and disappears"
    )
    titanic_gramps_id: str | None = Field(
        None,
        description=(
            "Gramps ID of the record that is absorbed and disappears "
            "(alternative to titanic_handle)"
        ),
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


class FamilyMergeBody(StrictModel):
    """
    Optional JSON body for a family merge (MERGE_FAMILY).

    Mirrors Gramps Web's FamilyMergeArgs schema, whose fields both default to
    None server-side (keep the phoenix family's existing parent).
    """

    phoenix_father_handle: str | None = Field(
        None,
        description=(
            "Handle of the person to keep as father of the merged family. "
            "If omitted, the phoenix family's existing father is kept."
        ),
    )
    phoenix_mother_handle: str | None = Field(
        None,
        description=(
            "Handle of the person to keep as mother of the merged family. "
            "If omitted, the phoenix family's existing mother is kept."
        ),
    )


class UndoChangeParams(StrictModel):
    """Parameters for undoing a recorded transaction."""

    transaction_id: int = Field(
        description=(
            "Transaction id to undo, as listed by recent_changes. Undoing "
            "reverses every object change that transaction made."
        )
    )
    force: bool = Field(
        False,
        description=(
            "Bypass the server's check that the affected object has not "
            "changed since the transaction being undone. Currently REQUIRED "
            "to undo a deletion: Gramps Web has an upstream bug where the "
            "emptied side of a delete/add change is recorded as {} instead "
            "of None, which makes that check misfire and refuse every "
            "non-forced delete-undo with a false 'Object has changed' "
            "conflict, even when nothing else touched the record. Risk: if "
            "the object genuinely was changed after the original "
            "transaction, forcing the undo discards that later change "
            "without warning."
        ),
    )


class UndoTransactionQueryParams(StrictModel):
    """
    Query-string parameters for POST_TRANSACTION_UNDO.

    Mirrors Gramps Web's UndoQueryArgs schema (history.py), which reads
    "force" and "message" from the query string rather than a JSON body.
    Only "force" is exposed here - undo_change_tool never sets "message", so
    the server's own default ("Undo") applies.
    """

    force: bool = Field(
        False,
        description=(
            "If true, force the undo even though the server reports the "
            "affected object has changed since the transaction."
        ),
    )


class PersonMergeBody(StrictModel):
    """
    Optional JSON body for a person merge (MERGE_PERSON).

    Mirrors Gramps Web's PersonMergeArgs schema. Not exposed through
    MergeTypeParams: merge_type_tool never populates family_merger, so a
    person merge always sends no body and the server's own default
    (family_merger=True) applies. This model exists only so MERGE_PERSON has
    a registered param model in api_mapping.py, matching every other
    endpoint that can carry a body, and so a future caller that does need to
    set family_merger has a model already validating it correctly.
    """

    family_merger: bool | None = Field(
        None,
        description=(
            "If true (the server default when omitted), merge duplicate "
            "spouse/parent families that result from merging the two "
            "persons."
        ),
    )
