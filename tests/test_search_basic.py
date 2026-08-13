"""
Integration tests for basic search tools using real Gramps API.

Tests find_type_tool for the person object type plus the offline
SimpleFindParams/SimpleSearchParams `page` regression tests. The
remaining find_type_tool object types live in test_search_find_type.py
and the find_anything_tool tests live in test_search_find_anything.py -
split out to keep each file under the 500-line project limit while
preserving the original per-class test groupings.
"""

import pytest
from dotenv import load_dotenv
from mcp.types import TextContent

from src.gramps_mcp.tools.search_basic import find_type_tool

# Load environment variables
load_dotenv()


class TestFindPersonTool:
    """Test find_type_tool functionality for person with real API."""

    pytestmark = pytest.mark.integration

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
