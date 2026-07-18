"""
Integration tests for record management tools using the real Gramps API.
"""

import uuid

import pytest

from src.gramps_mcp.tools.records_tools import manage_tags_tool


class TestManageTagsTool:
    """Test the manage_tags_tool against a live Gramps Web server."""

    @pytest.mark.asyncio
    async def test_list_tags(self):
        result = await manage_tags_tool({"action": "list", "pagesize": 5})
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_create_and_get_tag(self):
        unique_name = f"test-tag-{uuid.uuid4().hex[:8]}"

        create_result = await manage_tags_tool(
            {"action": "create", "name": unique_name, "color": "#ff0000"}
        )
        create_text = create_result[0].text
        assert "error" not in create_text.lower()
        assert unique_name in create_text

        list_result = await manage_tags_tool({"action": "list", "pagesize": 100})
        list_text = list_result[0].text
        assert unique_name in list_text

    @pytest.mark.asyncio
    async def test_get_without_handle_returns_error(self):
        result = await manage_tags_tool({"action": "get"})
        text = result[0].text
        assert "error" in text.lower()

    @pytest.mark.asyncio
    async def test_create_without_name_returns_error(self):
        result = await manage_tags_tool({"action": "create"})
        text = result[0].text
        assert "error" in text.lower()

    @pytest.mark.asyncio
    async def test_invalid_action_returns_error(self):
        result = await manage_tags_tool({"action": "delete"})
        text = result[0].text
        assert "error" in text.lower()
