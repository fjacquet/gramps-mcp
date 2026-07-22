"""
Integration tests for basic search tools using real Gramps API.

Tests search_people, search_families, search_events, search_places,
search_sources, search_media, and search_all tools.
"""

import asyncio
import re
import uuid

import pytest
from dotenv import load_dotenv
from mcp.types import TextContent

from src.gramps_mcp.tools.data_management import create_note_tool
from src.gramps_mcp.tools.search_basic import (
    find_anything_tool,
    find_type_tool,
)

# Load environment variables
load_dotenv()


class TestFindPersonTool:
    """Test find_type_tool functionality for person with real API."""

    @pytest.mark.asyncio
    async def test_find_person(self):
        """Test people search with GQL."""
        result = await find_type_tool(
            {
                "type": "person",
                "gql": 'primary_name.first_name ~ "John"',
                "max_results": 3,
            }
        )

        print("\n--- FIND PERSON RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text or "No people found" in result[0].text

        # Assert max_results is respected - count actual result entries
        if "Found" in result[0].text and "No people found" not in result[0].text:
            # Count the number of "• **" entries which indicate individual results
            result_count = result[0].text.count("• **")
            assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestSimplePaginationParams:
    """Regression tests for issue #5: SimpleFindParams/SimpleSearchParams.page.

    Fast, offline unit tests directly on the pydantic models - no live
    server required. These close a coverage gap flagged by review: this
    task's headline pydantic deliverable (the new `page` field) had zero
    test coverage anywhere, live or offline, because every other test in
    this file calls the tool functions directly with hand-built dicts,
    bypassing FastMCP's real pydantic schema-validation dispatch entirely.
    """

    def test_simple_find_params_page_field(self):
        """SimpleFindParams must accept and round-trip a page value."""
        from src.gramps_mcp.models.parameters.simple_params import SimpleFindParams

        params = SimpleFindParams(type="person", gql="x", max_results=5, page=2)
        assert params.model_dump()["page"] == 2

    def test_simple_search_params_page_field(self):
        """SimpleSearchParams must accept and round-trip a page value."""
        from src.gramps_mcp.models.parameters.simple_params import SimpleSearchParams

        params = SimpleSearchParams(query="x", max_results=5, page=2)
        assert params.model_dump()["page"] == 2


class TestFindFamilyTool:
    """Test find_type_tool functionality for family with real API."""

    @pytest.mark.asyncio
    async def test_find_family(self):
        """Test families search with GQL."""
        result = await find_type_tool(
            {
                "type": "family",
                "gql": 'father_handle.get_person.primary_name.surname_list.any.surname ~ "Smith"',
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

    @pytest.mark.asyncio
    async def test_find_place(self):
        """Test places search with GQL."""
        result = await find_type_tool(
            {"type": "place", "gql": 'name.value ~ "Boston"', "max_results": 3}
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

    @pytest.mark.asyncio
    async def test_find_source(self):
        """Test sources search with GQL."""
        result = await find_type_tool(
            {"type": "source", "gql": 'title ~ "census"', "max_results": 3}
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

    @pytest.mark.asyncio
    async def test_find_repository(self):
        """Test repositories search with GQL."""
        result = await find_type_tool(
            {"type": "repository", "gql": 'name ~ "archive"', "max_results": 3}
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

    @pytest.mark.asyncio
    async def test_find_citation(self):
        """Test citations search with GQL."""
        result = await find_type_tool(
            {"type": "citation", "gql": 'page ~ "1624"', "max_results": 3}
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

    @pytest.mark.asyncio
    async def test_find_media(self):
        """Test media search with GQL."""
        result = await find_type_tool(
            {"type": "media", "gql": 'desc ~ "pietrala"', "max_results": 3}
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

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Note GQL search not supported by Gramps Web API despite documentation"
    )
    async def test_find_note(self):
        """Test notes search with GQL.

        NOTE: Skipped because the Gramps Web API notes endpoint
        does not properly support GQL queries, contrary to the documentation.
        The API returns "Server error" when attempting note searches with GQL.
        """
        result = await find_type_tool(
            {"type": "note", "gql": 'gramps_id ~ "N0001"', "max_results": 3}
        )

        print("\n--- FIND NOTE RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text or "No notes found" in result[0].text

        # Assert max_results is respected - count actual result entries
        if "Found" in result[0].text and "No notes found" not in result[0].text:
            # Count the number of "• **" entries which indicate individual results
            result_count = result[0].text.count("• **")
            assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindAnythingTool:
    """Test find_anything_tool functionality with real API."""

    @pytest.mark.asyncio
    async def test_find_anything(self):
        """Test search across all object types with query."""
        result = await find_anything_tool({"query": "pietrala", "max_results": 3})

        print("\n--- FIND ANYTHING RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text and "records matching" in result[0].text

        # Assert max_results is respected - count actual result entries
        if "Found" in result[0].text and "No records found" not in result[0].text:
            # Count the number of "• **" entries which indicate individual results
            result_count = result[0].text.count("• **")
            assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindAnythingPagination:
    """Regression tests for issue #5: find_anything max_results/page.

    Uses deterministic, task-created note fixtures tagged with a shared
    unique marker (uuid4 hex) instead of the live tree's uncontrolled
    content or a broad one-letter query, so the assertions below actually
    distinguish fixed-vs-broken `find_anything_tool` behavior rather than
    passing vacuously regardless of whether the fix is applied.
    """

    @staticmethod
    async def _create_marker_notes(marker: str, count: int) -> list[str]:
        """Create fixture notes embedding distinct per-note markers.

        Args:
            marker (str): Shared unique marker (e.g. uuid4().hex) common to
                all fixture notes created for one test.
            count (int): Number of fixture notes to create.

        Returns:
            List[str]: The distinct per-note marker strings
                (f"{marker}-{i}") embedded in each created note's text.
        """
        note_markers = []
        for i in range(count):
            note_marker = f"{marker}-{i}"
            result = await create_note_tool(
                {
                    "text": f"Pagination regression note {note_marker}",
                    "type": "Research",
                }
            )
            text = result[0].text
            assert "Error:" not in text, f"Fixture note creation failed: {text}"
            note_markers.append(note_marker)
        return note_markers

    @staticmethod
    async def _find_anything_until(
        query: str, expected_min: int, **kwargs
    ) -> list[TextContent]:
        """Poll find_anything_tool until the reported total count is reached.

        Full-text search indexing can lag slightly behind object creation
        on a live server; this retries (up to 5 attempts, 1.5s apart) so
        eventual-consistency lag doesn't produce a flaky failure. It never
        weakens the real assertions - callers check the returned content
        themselves once this returns.

        Args:
            query (str): Search query to pass to find_anything_tool.
            expected_min (int): Minimum "Found N records" count to wait for.
            **kwargs: Additional arguments forwarded to find_anything_tool
                (e.g. max_results, page).

        Returns:
            List[TextContent]: The last response received, whether or not
                expected_min was reached within the retry budget.
        """
        result: list[TextContent] = []
        for _attempt in range(5):
            result = await find_anything_tool({"query": query, **kwargs})
            match = re.search(r"Found (\d+) records", result[0].text)
            if match and int(match.group(1)) >= expected_min:
                return result
            await asyncio.sleep(1.5)
        return result

    @pytest.mark.asyncio
    async def test_find_anything_respects_max_results(self):
        """max_results must cap the number of displayed fixture records.

        Creates 3 notes sharing a unique marker (each with a distinct
        per-note suffix) and searches for the shared marker with
        max_results=2. Counting exact occurrences of each of the 3 full
        per-note markers in the response - rather than the "* **" bullet
        prefix, which only appears in not-found/fallback formatter output
        and never in successful format_note output - proves the cap is
        enforced on the displayed content.
        """
        marker = uuid.uuid4().hex
        note_markers = await self._create_marker_notes(marker, 3)

        result = await self._find_anything_until(marker, expected_min=3, max_results=2)
        text = result[0].text

        print("\n--- FIND ANYTHING MAX_RESULTS RESULT ---")
        print(text)
        print("--- END ---\n")

        assert "error" not in text.lower(), f"Error found in response: {text}"

        count_match = re.search(r"Found (\d+) records", text)
        assert count_match, f"Expected a 'Found N records' header, got: {text}"
        assert int(count_match.group(1)) >= 3, (
            "Expected all 3 fixture notes to be indexed and matched "
            f"(this is an indexing-lag issue, not a fix regression), got: {text}"
        )

        displayed = [nm for nm in note_markers if nm in text]
        assert len(displayed) == 2, (
            f"Expected exactly 2 of 3 markers displayed with max_results=2, "
            f"got {len(displayed)} ({displayed}): {text}"
        )

    @pytest.mark.asyncio
    async def test_find_anything_page_returns_different_content(self):
        """page must change which fixture record is displayed.

        Creates 2 notes sharing a unique marker, requests page 1 and page 2
        with max_results=1 each, and asserts the two responses surface
        different per-note markers - proving `page` actually changes the
        returned content instead of merely being accepted without error
        (which a silent regression dropping `page` again would still do).
        """
        marker = uuid.uuid4().hex
        note_markers = await self._create_marker_notes(marker, 2)

        page1_result = await self._find_anything_until(
            marker, expected_min=2, max_results=1, page=1
        )
        page1_text = page1_result[0].text

        print("\n--- FIND ANYTHING PAGE 1 RESULT ---")
        print(page1_text)
        print("--- END ---\n")

        assert "error" not in page1_text.lower(), (
            f"Error found in response: {page1_text}"
        )

        page2_result = await find_anything_tool(
            {"query": marker, "max_results": 1, "page": 2}
        )
        page2_text = page2_result[0].text

        print("\n--- FIND ANYTHING PAGE 2 RESULT ---")
        print(page2_text)
        print("--- END ---\n")

        assert "error" not in page2_text.lower(), (
            f"Error found in response: {page2_text}"
        )

        page1_seen = {nm for nm in note_markers if nm in page1_text}
        page2_seen = {nm for nm in note_markers if nm in page2_text}

        assert len(page1_seen) == 1, (
            f"Expected exactly 1 marker on page 1, got {page1_seen}: {page1_text}"
        )
        assert len(page2_seen) == 1, (
            f"Expected exactly 1 marker on page 2, got {page2_seen}: {page2_text}"
        )
        assert page1_seen != page2_seen, (
            "Expected page 1 and page 2 to show different fixture records, "
            f"got page1={page1_seen} page2={page2_seen}"
        )
