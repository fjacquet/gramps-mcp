"""
Integration tests for relationship analysis tools using the real Gramps API.

Uses only generic tree-structural IDs (I0001, I0002) - no real person
details are referenced or asserted on.
"""

import pytest

from src.gramps_mcp.tools.relationship_tools import get_relationship_tool


class TestGetRelationshipTool:
    """Test the get_relationship_tool against a live Gramps Web server."""

    @pytest.mark.asyncio
    async def test_get_relationship_by_gramps_id(self):
        result = await get_relationship_tool({"person1": "I0001", "person2": "I0002"})
        text = result[0].text
        assert "error" not in text.lower()
        assert "**Relationship:**" in text

    @pytest.mark.asyncio
    async def test_get_all_relationships_by_gramps_id(self):
        result = await get_relationship_tool(
            {"person1": "I0001", "person2": "I0002", "all_relationships": True}
        )
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_missing_person_argument_returns_error(self):
        result = await get_relationship_tool({"person1": "I0001"})
        text = result[0].text
        assert "error" in text.lower()
