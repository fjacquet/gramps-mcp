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
Keep the documented detach_reference reachability table honest.

The usage guide is served to MCP clients as a resource, so an assistant
decides whether to attempt a detach by reading it. The table shipped on this
branch claimed `media_list`, `note_list`, `tag_list` and `attribute_list`
were unreachable on a person, and that citations, repositories, notes and
tags had no reachable list at all - all false, because PersonData,
CitationData, RepositoryData and SourceSaveParams inherit BaseDataModel.
An assistant reading that would decline the most common cleanup operations
the tool exists to enable.

These tests derive the table from `model_fields` and fail when the guide and
the models disagree, in either direction. When they fail, fix the guide
first and this file second - never this file alone.
"""

import re
from pathlib import Path

import pytest

from src.gramps_mcp.destructive import TYPE_ENDPOINTS
from src.gramps_mcp.models.api_mapping import get_param_model

GUIDE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "gramps_mcp"
    / "resources"
    / "gramps-usage-guide.md"
)

# Reason: matches the per-type bullets in the guide's Destructive Operations
# reachability table, e.g. "  - `person`: `attribute_list`, `note_list`" or
# "  - `note`: none". Anchored on two-space indentation so ordinary prose
# bullets elsewhere in the guide cannot be mistaken for table rows.
_ROW = re.compile(r"^  - `([a-z]+)`: (.+)$", re.MULTILINE)


def _documented_table() -> dict[str, set[str]]:
    """
    Parse the reachability table out of the shipped usage guide.

    Returns:
        dict[str, set[str]]: Record type to the list names the guide claims
            `detach_reference` can edit on it.
    """
    text = GUIDE.read_text(encoding="utf-8")
    start = text.index("### `detach_reference`")
    end = text.index("### `undo_change`", start)
    section = text[start:end]

    table: dict[str, set[str]] = {}
    for obj_type, listed in _ROW.findall(section):
        if obj_type not in TYPE_ENDPOINTS:
            continue
        table[obj_type] = set(re.findall(r"`(\w+_list)`", listed))
    return table


def _model_lists(obj_type: str) -> set[str]:
    """
    Return the list fields detach_reference can actually edit on a type.

    This mirrors detach_reference_tool's own guard, which refuses when
    `list_name not in write_model.model_fields`.

    Args:
        obj_type (str): A key of TYPE_ENDPOINTS.

    Returns:
        set[str]: The `_list` fields declared by the type's write model.
    """
    model = get_param_model(TYPE_ENDPOINTS[obj_type].put)
    assert model is not None, f"no write model registered for {obj_type}"
    return {name for name in model.model_fields if name.endswith("_list")}


def test_every_type_has_a_row_in_the_documented_table():
    """A type with no row is a type an assistant has no guidance for."""
    assert set(_documented_table()) == set(TYPE_ENDPOINTS)


@pytest.mark.parametrize("obj_type", sorted(TYPE_ENDPOINTS))
def test_documented_lists_match_the_write_model(obj_type):
    """
    The guide must name exactly the lists the write model declares.

    Under-claiming makes an assistant refuse work the tool supports;
    over-claiming makes it promise a detach that the tool then refuses.
    """
    documented = _documented_table()[obj_type]
    actual = _model_lists(obj_type)

    missing = actual - documented
    assert not missing, (
        f"the guide omits reachable lists for {obj_type}: {sorted(missing)}. "
        "Add them to the Destructive Operations table in "
        "src/gramps_mcp/resources/gramps-usage-guide.md."
    )
    extra = documented - actual
    assert not extra, (
        f"the guide claims unreachable lists for {obj_type}: {sorted(extra)}. "
        "detach_reference refuses these; remove them from the guide."
    )


def test_note_and_tag_really_have_no_reachable_list():
    """
    The one claim of total unreachability the guide still makes.

    Pinned separately so a future field added to NoteSaveParams or
    TagSaveParams turns the guide's "none" into a red test rather than a
    silently stale refusal.
    """
    assert _model_lists("note") == set()
    assert _model_lists("tag") == set()
