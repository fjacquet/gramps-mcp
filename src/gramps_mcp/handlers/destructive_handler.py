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


def _label(obj: dict) -> str:
    """Return the most human-readable label a record offers."""
    for key in ("title", "desc", "text", "page", "gramps_id", "handle"):
        value = obj.get(key)
        if isinstance(value, dict):
            value = value.get("string") or value.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()[:80]
    return "(no label)"


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
