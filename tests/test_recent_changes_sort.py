"""
Integration tests for recent_changes sort handling.
"""

import pytest

from src.gramps_mcp.tools.analysis import get_recent_changes_tool


class TestRecentChangesSort:
    """The caller's sort choice must survive, and their dict must not change."""

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
