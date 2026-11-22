"""
Integration tests for find_type_tool across the non-person object types.

Split out of test_search_basic.py (which now covers only person search
plus the offline pagination-params regression tests) to keep each file
under the project's 500-line limit. Covers family, event, place, source,
repository, citation, media, and note.
"""

import pytest
from dotenv import load_dotenv
from mcp.types import TextContent

from src.gramps_mcp.tools.search_basic import find_type_tool

# Load environment variables
load_dotenv()


class TestFindFamilyTool:
    """Test find_type_tool functionality for family with real API."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_find_family(self):
        """Test families search with GQL."""
        result = await find_type_tool(
            {
                "type": "family",
                "gql": 'father.primary_name.surname_list[0].surname == "Méléo"',
                "max_results": 3,
            }
        )

        print("\n--- FIND FAMILY RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text or "No families found" in result[0].text

        # Assert max_results is respected - count actual result entries
        if "Found" in result[0].text and "No families found" not in result[0].text:
            # Count the number of "• **" entries which indicate individual results
            result_count = result[0].text.count("• **")
            assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindEventTool:
    """Test find_type_tool functionality for event with real API."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_find_event(self):
        """Test events search with GQL."""
        result = await find_type_tool(
            {"type": "event", "gql": "date.dateval[2] > 1800", "max_results": 3}
        )

        print("\n--- FIND EVENT RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text or "No events found" in result[0].text

        # Assert max_results is respected - count actual result entries
        if "Found" in result[0].text and "No events found" not in result[0].text:
            # Count the number of "• **" entries which indicate individual results
            result_count = result[0].text.count("• **")
            assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindPlaceTool:
    """Test find_type_tool functionality for place with real API."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_find_place(self):
        """Test places search with GQL."""
        result = await find_type_tool(
            {"type": "place", "gql": '"Boston" in name.value', "max_results": 3}
        )

        print("\n--- FIND PLACE RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text or "No places found" in result[0].text

        # Assert max_results is respected - count actual result entries
        if "Found" in result[0].text and "No places found" not in result[0].text:
            # Count the number of "• **" entries which indicate individual results
            result_count = result[0].text.count("• **")
            assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindSourceTool:
    """Test find_type_tool functionality for source with real API."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_find_source(self):
        """Test sources search with GQL."""
        result = await find_type_tool(
            {"type": "source", "gql": '"census" in title', "max_results": 3}
        )

        print("\n--- FIND SOURCE RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text or "No sources found" in result[0].text

        # Assert max_results is respected - count actual result entries
        if "Found" in result[0].text and "No sources found" not in result[0].text:
            # Count the number of "• **" entries which indicate individual results
            result_count = result[0].text.count("• **")
            assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindRepositoryTool:
    """Test find_type_tool functionality for repository with real API."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_find_repository(self):
        """Test repositories search with GQL."""
        result = await find_type_tool(
            {"type": "repository", "gql": '"archive" in name', "max_results": 3}
        )

        print("\n--- FIND REPOSITORY RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text or "No repositories found" in result[0].text

        # Assert max_results is respected - count actual result entries
        if "Found" in result[0].text and "No repositories found" not in result[0].text:
            # Count the number of "• **" entries which indicate individual results
            result_count = result[0].text.count("• **")
            assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindCitationTool:
    """Test find_type_tool functionality for citation with real API."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_find_citation(self):
        """Test citations search with GQL."""
        result = await find_type_tool(
            {"type": "citation", "gql": '"1624" in page', "max_results": 3}
        )

        print("\n--- FIND CITATION RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text or "No citations found" in result[0].text

        # Assert max_results is respected - count actual result entries
        if "Found" in result[0].text and "No citations found" not in result[0].text:
            # Count the number of "• **" entries which indicate individual results
            result_count = result[0].text.count("• **")
            assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindMediaTool:
    """Test find_type_tool functionality for media with real API."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_find_media(self):
        """Test media search with GQL."""
        result = await find_type_tool(
            {"type": "media", "gql": '"pietrala" in desc', "max_results": 3}
        )

        print("\n--- FIND MEDIA RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text or "No media files found" in result[0].text

        # Assert max_results is respected - count actual result entries
        if "Found" in result[0].text and "No media files found" not in result[0].text:
            # Count the number of "• **" entries which indicate individual results
            result_count = result[0].text.count("• **")
            assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindNoteTool:
    """Test find_type_tool functionality for note with real API."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_find_note(self):
        """Test notes search with a GOQL expression."""
        result = await find_type_tool(
            {"type": "note", "gql": 'gramps_id == "N0001"', "max_results": 3}
        )

        print("\n--- FIND NOTE RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found 1 note" in result[0].text
        assert "N0001" in result[0].text

        # Assert max_results is respected - count actual result entries
        # Count the number of "• **" entries which indicate individual results
        result_count = result[0].text.count("• **")
        assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindTypeGoql:
    """find_type speaks GOQL and explains the old dialect's rejection."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_event_type_constant_matches_births(self):
        """EventType.BIRTH is the working way to filter events by type."""
        result = await find_type_tool(
            {
                "type": "event",
                "gql": "type.value == EventType.BIRTH",
                "max_results": 3,
            }
        )
        text = result[0].text
        assert "Found" in text and "No events found" not in text

    @pytest.mark.asyncio
    async def test_old_dialect_gives_goql_hint(self):
        """The pre-3.26 dialect is rejected with a pointer to GOQL docs."""
        result = await find_type_tool({"type": "person", "gql": "class = person"})
        text = result[0].text
        assert "GOQL" in text
        assert "gql://documentation" in text
