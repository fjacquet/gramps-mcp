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
Pure decision logic for destructive operations.

Deleting a record, and removing one element from a list, both need a decision
made before any request is sent: may this deletion proceed, and what does the
list look like afterwards. That logic lives here as pure, side-effect-free
functions so it can be unit-tested without a live server, exactly as
merge.py does for PUT merging.
"""

from typing import NamedTuple

from .models.api_calls import ApiCalls


class TypeEndpoints(NamedTuple):
    """The API calls that serve one record type."""

    get: ApiCalls
    put: ApiCalls
    delete: ApiCalls
    merge: ApiCalls | None
    # Reason: the collection endpoint for the type, used to resolve a
    # gramps_id to a handle. Kept here rather than in a second dict beside
    # this one, so a type cannot be mapped to one endpoint for delete and a
    # different one for lookup.
    plural: ApiCalls


TYPE_ENDPOINTS: dict[str, TypeEndpoints] = {
    "person": TypeEndpoints(
        ApiCalls.GET_PERSON,
        ApiCalls.PUT_PERSON,
        ApiCalls.DELETE_PERSON,
        ApiCalls.MERGE_PERSON,
        ApiCalls.GET_PEOPLE,
    ),
    "family": TypeEndpoints(
        ApiCalls.GET_FAMILY,
        ApiCalls.PUT_FAMILY,
        ApiCalls.DELETE_FAMILY,
        ApiCalls.MERGE_FAMILY,
        ApiCalls.GET_FAMILIES,
    ),
    "event": TypeEndpoints(
        ApiCalls.GET_EVENT,
        ApiCalls.PUT_EVENT,
        ApiCalls.DELETE_EVENT,
        ApiCalls.MERGE_EVENT,
        ApiCalls.GET_EVENTS,
    ),
    "place": TypeEndpoints(
        ApiCalls.GET_PLACE,
        ApiCalls.PUT_PLACE,
        ApiCalls.DELETE_PLACE,
        ApiCalls.MERGE_PLACE,
        ApiCalls.GET_PLACES,
    ),
    "source": TypeEndpoints(
        ApiCalls.GET_SOURCE,
        ApiCalls.PUT_SOURCE,
        ApiCalls.DELETE_SOURCE,
        ApiCalls.MERGE_SOURCE,
        ApiCalls.GET_SOURCES,
    ),
    "citation": TypeEndpoints(
        ApiCalls.GET_CITATION,
        ApiCalls.PUT_CITATION,
        ApiCalls.DELETE_CITATION,
        ApiCalls.MERGE_CITATION,
        ApiCalls.GET_CITATIONS,
    ),
    "repository": TypeEndpoints(
        ApiCalls.GET_REPOSITORY,
        ApiCalls.PUT_REPOSITORY,
        ApiCalls.DELETE_REPOSITORY,
        ApiCalls.MERGE_REPOSITORY,
        ApiCalls.GET_REPOSITORIES,
    ),
    "media": TypeEndpoints(
        ApiCalls.GET_MEDIA_ITEM,
        ApiCalls.PUT_MEDIA_ITEM,
        ApiCalls.DELETE_MEDIA_ITEM,
        ApiCalls.MERGE_MEDIA,
        ApiCalls.GET_MEDIA,
    ),
    "note": TypeEndpoints(
        ApiCalls.GET_NOTE,
        ApiCalls.PUT_NOTE,
        ApiCalls.DELETE_NOTE,
        ApiCalls.MERGE_NOTE,
        ApiCalls.GET_NOTES,
    ),
    # Reason: tags are deletable but Gramps Web offers no tag merge endpoint.
    "tag": TypeEndpoints(
        ApiCalls.GET_TAG,
        ApiCalls.PUT_TAG,
        ApiCalls.DELETE_TAG,
        None,
        ApiCalls.GET_TAGS,
    ),
}

MAX_LISTED_BACKLINKS = 20


class ParentConflict(NamedTuple):
    """Two families disagree on one parent, and no survivor was named."""

    role: str
    """Either "father" or "mother"."""
    phoenix_handle: str
    """The parent on the surviving family."""
    titanic_handle: str
    """The parent on the family being absorbed."""


def parent_merge_conflicts(
    phoenix: dict,
    titanic: dict,
    phoenix_father_handle: str | None,
    phoenix_mother_handle: str | None,
) -> list[ParentConflict]:
    """
    Find parent disagreements that a family merge would resolve destructively.

    Merging two families whose fathers differ does not detach one man from
    the family: it merges the two people into one, and the absorbed man
    ceases to exist. Measured on a live tree on 2026-08-31 - the titanic's
    father returned 404 afterwards and the survivor had gained the other's
    name as an alternate. Neither this server's parameter descriptions nor
    the Gramps Web API's own schema said so; all of them describe
    `phoenix_father_handle` as naming "the person to keep", which reads as a
    choice between two people who both survive.

    Only both-present-and-different counts. With one side empty there is no
    second person to absorb. That narrower case was not measured, and the
    guard stays out of it rather than refusing on a suspicion.

    Args:
        phoenix (dict): The surviving family record.
        titanic (dict): The family being absorbed.
        phoenix_father_handle (str | None): The caller's named surviving
            father, if any. Naming one acknowledges the consequence.
        phoenix_mother_handle (str | None): The same for the mother.

    Returns:
        list[ParentConflict]: One entry per unacknowledged disagreement,
        fathers before mothers. Empty when the merge destroys no one.
    """
    acknowledged = {
        "father": phoenix_father_handle,
        "mother": phoenix_mother_handle,
    }
    conflicts: list[ParentConflict] = []
    for role in ("father", "mother"):
        ours = phoenix.get(f"{role}_handle")
        theirs = titanic.get(f"{role}_handle")
        if not ours or not theirs or ours == theirs:
            continue
        if acknowledged[role] is not None:
            continue
        conflicts.append(ParentConflict(role, ours, theirs))
    return conflicts


def should_refuse_delete(backlinks: dict[str, list[str]]) -> str | None:
    """
    Decide whether a deletion must be refused because references remain.

    Args:
        backlinks (dict): Mapping of object type to referencing handles, as
            returned by GET {type}/{handle}?backlinks=1.

    Returns:
        str | None: A refusal message naming what still references the record,
            or None when nothing does and the deletion may proceed.
    """
    present = {kind: handles for kind, handles in backlinks.items() if handles}
    if not present:
        return None

    lines = []
    for kind in sorted(present):
        handles = present[kind]
        shown = handles[:MAX_LISTED_BACKLINKS]
        suffix = "" if len(handles) <= MAX_LISTED_BACKLINKS else ", ..."
        lines.append(f"  {len(handles)} {kind}: {', '.join(shown)}{suffix}")

    total = sum(len(h) for h in present.values())
    return (
        f"Refused: {total} object(s) still reference this record.\n"
        + "\n".join(lines)
        + "\nDeleting it would sever those references. Detach them first with "
        "detach_reference, or pass force=true to delete anyway."
    )


def remove_from_list(obj: dict, list_name: str, ref_handle: str) -> dict:
    """
    Return a copy of obj with ref_handle removed from the named list.

    Handles both shapes Gramps uses: a list of plain handle strings (note_list,
    tag_list) and a list of reference dicts carrying a "ref" key
    (event_ref_list, media_list, child_ref_list).

    Args:
        obj (dict): The record as returned by the API.
        list_name (str): Name of the list field to edit.
        ref_handle (str): The handle to remove.

    Returns:
        dict: A new record with the element removed. The input is not mutated.

    Raises:
        ValueError: If the record has no such list, or the handle is absent
            from it. Both are refused rather than silently succeeding.
    """
    if list_name not in obj or not isinstance(obj[list_name], list):
        raise ValueError(f"Record has no list named '{list_name}'")

    current = obj[list_name]

    def matches(item: object) -> bool:
        if isinstance(item, dict):
            return item.get("ref") == ref_handle
        return item == ref_handle

    remaining = [item for item in current if not matches(item)]
    if len(remaining) == len(current):
        raise ValueError(f"Handle '{ref_handle}' is not present in '{list_name}'")

    return {**obj, list_name: remaining}
