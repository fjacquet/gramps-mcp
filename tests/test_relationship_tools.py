"""
Integration tests for relationship analysis tools using the real Gramps API.

Uses only generic tree-structural IDs (I0001, I0002) - no real person
details are referenced or asserted on.
"""

import pytest

from src.gramps_mcp.tools.relationship_tools import (
    check_living_tool,
    get_relationship_tool,
    get_timeline_tool,
)


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


class TestCheckLivingTool:
    """Test the check_living_tool against a live Gramps Web server."""

    @pytest.mark.asyncio
    async def test_check_living_by_gramps_id(self):
        result = await check_living_tool({"person": "I0001"})
        text = result[0].text
        assert "error" not in text.lower()
        assert "**Living:**" in text

    @pytest.mark.asyncio
    async def test_check_living_without_dates(self):
        result = await check_living_tool({"person": "I0001", "include_dates": False})
        text = result[0].text
        assert "error" not in text.lower()
        assert "**Living:**" in text

    @pytest.mark.asyncio
    async def test_missing_person_argument_returns_error(self):
        result = await check_living_tool({})
        text = result[0].text
        assert "error" in text.lower()


class TestGetTimelineTool:
    """Test the get_timeline_tool against a live Gramps Web server."""

    @pytest.mark.asyncio
    async def test_person_scope(self):
        result = await get_timeline_tool({"scope": "person", "target": "I0001"})
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_family_scope(self):
        result = await get_timeline_tool({"scope": "family", "target": "F0001"})
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_people_scope_without_anchor(self):
        result = await get_timeline_tool({"scope": "people", "pagesize": 5})
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_families_scope(self):
        result = await get_timeline_tool({"scope": "families", "pagesize": 5})
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_invalid_scope_returns_error(self):
        result = await get_timeline_tool({"scope": "nonsense"})
        text = result[0].text
        assert "error" in text.lower()

    @pytest.mark.asyncio
    async def test_person_scope_without_target_returns_error(self):
        result = await get_timeline_tool({"scope": "person"})
        text = result[0].text
        assert "error" in text.lower()
