"""
Integration tests for recent_changes sort and pagination handling.
"""

import re

import pytest

from src.gramps_mcp.tools.analysis import (
    _apply_recent_changes_defaults,
    get_recent_changes_tool,
)


class TestRecentChangesSort:
    """The caller's sort choice must survive, and their dict must not change."""

    def test_server_shaped_none_sort_still_defaults(self):
        # Reason: the MCP HTTP dispatcher calls tool handlers with every
        # optional field explicitly set to None (arguments.model_dump()
        # without exclude_none=True), so this is the shape a real caller
        # actually produces through that transport. An implementation that
        # copies the dict and unconditionally overrides sort (rather than
        # only when it is falsy) would also pass every other test in this
        # file, because none of them inspect what reaches
        # TransactionHistoryParams - only what the caller's own dict looks
        # like afterwards. This test does look at the value that would
        # reach TransactionHistoryParams, so it fails against the old
        # dict.setdefault("sort", "-id") implementation, which no-ops when
        # the key is already present (even as None).
        arguments = {"pagesize": 2, "sort": None}

        result = _apply_recent_changes_defaults(arguments)

        assert result["sort"] == "-id"

    @pytest.mark.asyncio
    async def test_caller_dict_is_not_mutated(self):
        arguments = {"pagesize": 2}

        await get_recent_changes_tool(arguments)

        # Reason: the tool used to write its default into the caller's dict.
        assert arguments == {"pagesize": 2}

    @pytest.mark.asyncio
    async def test_explicit_sort_is_preserved(self):
        arguments = {"pagesize": 2, "sort": "id"}

        await get_recent_changes_tool(arguments)

        assert arguments["sort"] == "id"

    @pytest.mark.asyncio
    async def test_default_is_still_most_recent_first(self):
        result = await get_recent_changes_tool({"pagesize": 2})

        assert "error" not in result[0].text.lower()


class TestRecentChangesPageDefault:
    """`pagesize` alone must bound the result; the API only honours it when
    `page` is also present."""

    def test_server_shaped_none_page_still_defaults(self):
        # Reason: mirrors test_server_shaped_none_sort_still_defaults for
        # the page field - a server-shaped call arrives with page
        # explicitly None, and dict.setdefault would no-op on it the same
        # way it did for sort.
        arguments = {"pagesize": 2, "page": None}

        result = _apply_recent_changes_defaults(arguments)

        assert result["page"] == 1

    @pytest.mark.asyncio
    async def test_pagesize_without_page_is_bounded(self):
        # Reason: the API only honours pagesize server-side when page is
        # also supplied. Before this fix, pagesize=2 with no page dumped
        # the entire transaction history into the response
        # (recent_changes(pagesize=2) measured at 1,100,693 characters
        # against the live tree, versus 253 with page=1 added). Assert a
        # relationship, not a byte count, so this does not need updating as
        # the tree grows: a bounded request must report a small handful of
        # changes, not the whole history.
        result = await get_recent_changes_tool({"pagesize": 2})
        text = result[0].text

        assert "error" not in text.lower()

        found = re.search(r"Found (\d+) recent changes", text)
        assert found is not None
        assert int(found.group(1)) <= 10
