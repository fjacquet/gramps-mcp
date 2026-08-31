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

"""Formatting for destructive-operation results and previews."""

from ..destructive import ParentConflict


def _person_name(obj: dict) -> str | None:
    """
    Assemble a readable name from a record's primary_name, if it has one.

    Args:
        obj (dict): The record as returned by the API.

    Returns:
        str | None: "Given SURNAME" when the record carries a primary_name
            with any content, otherwise None.
    """
    name = obj.get("primary_name")
    if not isinstance(name, dict):
        return None
    given = (name.get("first_name") or "").strip()
    surnames = " ".join(
        (entry.get("surname") or "").strip()
        for entry in name.get("surname_list") or []
        if isinstance(entry, dict)
    ).strip()
    return f"{given} {surnames}".strip() or None


def _label(obj: dict) -> str:
    """
    Return the most human-readable label a record offers.

    Args:
        obj (dict): The record as returned by the API.

    Returns:
        str: A name, title or description, truncated to 80 characters, or
            "(no label)" when the record offers nothing readable. The
            gramps_id is deliberately not used - the caller already prints
            it, and repeating it names nothing.
    """
    # Reason: a person record carries none of the title/desc/text/page keys,
    # so without this branch a person merge preview would show two opaque ids
    # and ask the caller to check a direction the preview never showed them.
    person_name = _person_name(obj)
    if person_name:
        return person_name[:80]

    for key in ("title", "desc", "text", "page", "name"):
        value = obj.get(key)
        if isinstance(value, dict):
            value = value.get("string") or value.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()[:80]
    return "(no label)"


def format_parent_merge_refusal(
    conflicts: list[ParentConflict], labels: dict[str, str]
) -> str:
    """
    Explain why a family merge was refused, naming who would be destroyed.

    The wording avoids "keep" and "choose" on purpose. Both this server's
    parameter descriptions and the Gramps Web API's own schema use them, and
    both readings are wrong: the parameter does not pick one of two
    survivors, it picks which of two people absorbs the other.

    Args:
        conflicts (list[ParentConflict]): Unacknowledged parent
            disagreements, from `destructive.parent_merge_conflicts`.
        labels (dict[str, str]): Person handle to a readable label, for
            every handle named in `conflicts`.

    Returns:
        str: The refusal, naming both people per conflict and the parameter
        that acknowledges it.
    """

    def label(handle: str) -> str:
        return labels.get(handle, f"({handle})")

    lines = ["Refused: this merge would destroy a person you did not name."]
    for conflict in conflicts:
        lines.append(
            f"  The two families have different {conflict.role}s: "
            f"{label(conflict.phoenix_handle)} on the surviving family, "
            f"{label(conflict.titanic_handle)} on the one being absorbed. "
            f"Merging does not choose between them - it merges the two "
            f"people into one, and the other ceases to exist."
        )
        lines.append(
            f"  Pass phoenix_{conflict.role}_handle to name which of them "
            f"absorbs the other, or merge the two people yourself first "
            f"with merge_type(type='person')."
        )
    return "\n".join(lines)


def format_merge_preview(phoenix: dict, titanic: dict, obj_type: str) -> str:
    """
    Describe a merge without performing it.

    Args:
        phoenix (dict): The record that survives.
        titanic (dict): The record that is absorbed and disappears.
        obj_type (str): The record type being merged.

    Returns:
        str: A preview naming both records and what happens to each.
    """
    return (
        f"Merge preview for {obj_type}:\n"
        f"  SURVIVES (phoenix): {phoenix.get('gramps_id', '?')} - "
        f"{_label(phoenix)}\n"
        f"  ABSORBED (titanic): {titanic.get('gramps_id', '?')} - "
        f"{_label(titanic)}\n"
        "The absorbed record disappears and every reference to it is "
        "repointed at the surviving one.\n"
        "Check the direction: if these are the wrong way round, swap "
        "phoenix_handle and titanic_handle.\n"
        "Call again with confirm=true to perform the merge."
    )
