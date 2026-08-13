"""
Integration tests for the standalone record data management tools using
real Gramps Web API.

Covers create_note_tool, create_media_tool, create_place_tool, and
create_event_tool. These tests require a working Gramps Web API instance
with valid credentials. Only tests actual API integration - Pydantic
validation is tested elsewhere.
"""

import pytest

from src.gramps_mcp.tools.data_management import (
    create_event_tool,
    create_media_tool,
    create_note_tool,
    create_place_tool,
)
from tests.constants import PREFIX

pytestmark = pytest.mark.integration


class TestCreateNoteTool:
    """Test create_note_tool functionality - First in workflow."""

    @pytest.mark.asyncio
    async def test_create_note_success(self):
        """Test successful note creation with proper text structure and type."""
        result = await create_note_tool(
            {
                "text": "This is a test research note about the family history.",
                "type": "Research",
            }
        )

        print("\n--- SAVE NOTE CREATE SUCCESS RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        # Assert all required fields from usage guide are in output
        assert "This is a test research note about the family history." in text, (
            f"Expected note text in output but got: {text}"
        )
        assert "Research" in text, (
            f"Expected note type 'Research' in output but got: {text}"
        )

    @pytest.mark.asyncio
    async def test_create_note_via_fastmcp_transport(self):
        """Regression test for issue #27.

        server.py's create_handler calls arguments.model_dump() on the
        NoteSaveParams schema instance before create_note_tool ever sees
        the dict. This must not crash NoteSaveParams(**params) downstream.
        """
        from src.gramps_mcp.models.parameters.note_params import NoteSaveParams

        schema_instance = NoteSaveParams(
            text="Regression test note for FastMCP transport path.",
            type="Research",
        )
        transport_dict = schema_instance.model_dump()

        result = await create_note_tool(transport_dict)

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "Regression test note for FastMCP transport path." in text, (
            f"Expected note text in output but got: {text}"
        )


class TestCreateMediaTool:
    """Test create_media_tool functionality - Second in workflow."""

    @pytest.mark.asyncio
    async def test_create_media_success(self):
        """Test successful media creation with actual file upload."""
        result = await create_media_tool(
            {
                "media_path": "tests/sample/33SQ-GP8N-NLK.jpg",
                "desc": "Birth register page showing John Smith entry",
                "date": {"dateval": [15, 1, 2024, False], "quality": 0, "modifier": 0},
            }
        )

        print("\n--- SAVE MEDIA CREATE RESULT ---")
        print(repr(result[0].text))
        print("--- END ---\n")

        # Debug: Show what we sent
        print("\n--- DEBUG: Parameters sent ---")
        print("media_path: tests/sample/33SQ-GP8N-NLK.jpg")
        print("desc: Birth register page showing John Smith entry")
        print("--- END DEBUG ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()
        assert "media" in text.lower()

        # Assert all required fields from usage guide are in output
        # New format: file type - gramps id - handle \n desc - date
        assert "Birth register page showing John Smith entry" in text, (
            f"Expected desc in output but got: {text}"
        )
        # Should show proper image MIME type
        assert "image/jpeg" in text, f"Expected image MIME type but got: {text}"
        # Assert formatted date from date_handler (not raw dateval components)
        assert "15 January 2024" in text, (
            f"Expected formatted date '15 January 2024' in output but got: {text}"
        )


class TestCreatePlaceTool:
    """Test create_place_tool functionality - Sixth in workflow."""

    @pytest.mark.asyncio
    async def test_create_place_success(self):
        """Test successful place creation with proper hierarchy."""
        # First create country (top level)
        country_result = await create_place_tool(
            {"name": {"value": "United States"}, "place_type": "Country"}
        )

        print("\n--- Country creation result ---")
        print(country_result[0].text)
        print("--- END ---\n")

        # Extract country handle
        import re

        country_handle_match = re.search(r"\[([a-f0-9]+)\]", country_result[0].text)
        country_handle = country_handle_match.group(1) if country_handle_match else None

        if not country_handle:
            pytest.fail("Could not extract country handle")

        # Create state enclosed by country
        state_result = await create_place_tool(
            {
                "name": {"value": "Massachusetts"},
                "place_type": "State",
                "placeref_list": [{"ref": country_handle}],
            }
        )

        # Extract state handle
        state_handle_match = re.search(r"\[([a-f0-9]+)\]", state_result[0].text)
        state_handle = state_handle_match.group(1) if state_handle_match else None

        if not state_handle:
            pytest.fail("Could not extract state handle")

        # Create city enclosed by state
        result = await create_place_tool(
            {
                "name": {"value": "Boston"},
                "place_type": "City",
                "placeref_list": [{"ref": state_handle}],
                "urls": [
                    {
                        "type": "Web Home",
                        "path": "https://www.boston.gov",
                        "description": "Official city website",
                    }
                ],
            }
        )

        print("\n--- SAVE PLACE CREATE SUCCESS RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        # Assert all required fields from usage guide are in output
        assert "Boston" in text, (
            f"Expected place title (required) in output but got: {text}"
        )
        assert "City" in text, (
            f"Expected place type (required) in output but got: {text}"
        )
        assert "Massachusetts" in text, (
            f"Expected enclosed_by reference in output but got: {text}"
        )

        # Assert optional fields that were provided
        urls = re.findall(r'(https?://[^\s"\',]+)', text)
        assert any(url == "https://www.boston.gov" for url in urls), (
            f"Expected exact URL 'https://www.boston.gov' in output URLs {urls} but got: {text}"
        )
        assert "Official city website" in text, (
            f"Expected URL description in output but got: {text}"
        )


class TestCreateEventTool:
    """Test create_event_tool functionality - Seventh in workflow."""

    @pytest.mark.asyncio
    async def test_create_event_success(self, citation_handle, place_handle):
        """Test successful event creation using citation and place handles."""
        result = await create_event_tool(
            {
                "type": "Birth",
                "citation_list": [citation_handle],
                "date": {"dateval": [15, 6, 1878, False], "quality": 0, "modifier": 0},
                "place": place_handle,
            }
        )

        print("\n--- SAVE EVENT CREATE SUCCESS RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        # Assert all required fields from usage guide are in output
        assert "Birth" in text, f"Expected type (required) in output but got: {text}"
        # Assert citation is referenced by gramps_id (will be different each run)
        assert "Attached citations: C" in text, (
            f"Expected citation gramps_id (required) in output but got: {text}"
        )

        # Assert optional fields that were provided
        # Assert formatted date (15 June 1878)
        assert "15 June 1878" in text, (
            f"Expected formatted event date in output but got: {text}"
        )
        # Should show linked place if present
        assert f"{PREFIX} place" in text, (
            f"Expected linked place in output but got: {text}"
        )
