"""
Integration tests for recent_changes sort handling.
"""

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
