"""
Integration tests for analysis tools using real Gramps Web API.

Tests get_descendants, get_ancestors, and get_recent_changes tools.
These tests require a working Gramps Web API instance with valid credentials.
"""

import re

import pytest
from dotenv import load_dotenv
from mcp.types import TextContent

from src.gramps_mcp.tools.analysis import (
    _validate_max_generations,
    get_ancestors_tool,
    get_descendants_tool,
    get_recent_changes_tool,
    get_tree_info_tool,
)

# Load environment variables from .env file
load_dotenv()

# Test constants
TEST_PAGESIZE = 3
TEST_MAX_GENERATIONS = 2
INVALID_GRAMPS_ID = "INVALID99999"


def extract_handle_from_search(search_text: str):
    """Extract handle from search result text."""
    import re

    # Format: Name (gender) - gramps_id - [handle]
    handle_match = re.search(r"\[([a-f0-9]+)\]", search_text)

    if handle_match:
        return handle_match.group(1)
    return None


def extract_gramps_id_from_search(search_text: str):
    """Extract gramps_id from search result text."""
    import re

    # Format: Name (gender) - gramps_id - [handle]
    id_match = re.search(r"\([FM]\) - ([^-]+) - \[", search_text)

    if id_match:
        return id_match.group(1).strip()
    return None


class TestGetDescendantsTool:
    """Test get_descendants_tool functionality."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_get_descendants_real_api(self):
        """Test get_descendants_tool with real API."""

        # First search for a person with children to get a valid handle for descendants test
        from src.gramps_mcp.tools.search_basic import find_person_tool

        search_result = await find_person_tool({"pagesize": TEST_PAGESIZE})

        # If we found a person, extract their gramps_id and use it directly
        if "[" in search_result[0].text and "]" in search_result[0].text:
            gramps_id = extract_gramps_id_from_search(search_result[0].text)

            if gramps_id:
                # Test with explicit max_generations
                result_explicit = await get_descendants_tool(
                    {"gramps_id": gramps_id, "max_generations": TEST_MAX_GENERATIONS}
                )

                # Test with default max_generations (should be 5)
                result_default = await get_descendants_tool({"gramps_id": gramps_id})

                # Test explicit result
                assert isinstance(result_explicit, list)
                assert len(result_explicit) == 1
                assert isinstance(result_explicit[0], TextContent)

                text_explicit = result_explicit[0].text
                print("\n=== DESCENDANTS TEST OUTPUT (EXPLICIT) ===")
                print(f"Person gramps_id used: {gramps_id}")
                print(f"Max generations: {TEST_MAX_GENERATIONS}")
                print(f"Total lines: {len(text_explicit.splitlines())}")

                # Test default result
                assert isinstance(result_default, list)
                assert len(result_default) == 1
                assert isinstance(result_default[0], TextContent)

                text_default = result_default[0].text
                print("\n=== DESCENDANTS TEST OUTPUT (DEFAULT) ===")
                print(f"Person gramps_id used: {gramps_id}")
                print("Max generations: DEFAULT (should be 5)")
                print(f"Total lines: {len(text_default.splitlines())}")
                print("=" * 50)

                # Both should contain actual descendants data
                for text in [text_explicit, text_default]:
                    assert isinstance(text, str)
                    assert len(text) > 0
                    assert len(text.strip()) > 50  # Should be substantial content
                    assert "report generated successfully" not in text.lower()
                    # Report should contain genealogy-related content
                    assert any(
                        keyword in text.lower()
                        for keyword in [
                            "person",
                            "name",
                            "birth",
                            "death",
                            "descendant",
                            "child",
                            "family",
                        ]
                    )
                    # Reason: the substring/keyword checks above pass on
                    # coincidental wording alone - they would not catch a
                    # broken format_traversal. These assert on the BFS
                    # output's actual structure: the heading, its
                    # generation/people count, and at least one indented
                    # child line carrying a gramps_id.
                    assert text.startswith("# Descendants of ")
                    assert re.search(r"\d+ generations?, \d+ people", text)
                    assert re.search(r"\n {2,}- .*\([A-Z]\d{4}\)", text)
        else:
            # If no people found in a populated tree, this is a test failure
            pytest.fail(
                "No people found for descendants test - tree should be populated"
            )

    @pytest.mark.asyncio
    async def test_get_descendants_invalid_gramps_id(self):
        """Test descendants retrieval with invalid gramps ID."""

        result = await get_descendants_tool({"gramps_id": INVALID_GRAMPS_ID})

        text = result[0].text
        assert "Error:" in text or "No descendants found" in text


class TestGetAncestorsTool:
    """Test get_ancestors_tool functionality."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_get_ancestors_real_api(self):
        """Test get_ancestors_tool with real API."""

        # Use specific person I0001 for ancestor testing (known to have ancestors)
        gramps_id = "I0001"

        # Test with explicit max_generations
        result_explicit = await get_ancestors_tool(
            {"gramps_id": gramps_id, "max_generations": TEST_MAX_GENERATIONS}
        )

        # Test with default max_generations (should be 5)
        result_default = await get_ancestors_tool({"gramps_id": gramps_id})

        # Test explicit result
        assert isinstance(result_explicit, list)
        assert len(result_explicit) == 1
        assert isinstance(result_explicit[0], TextContent)

        text_explicit = result_explicit[0].text
        print("\n=== ANCESTORS TEST OUTPUT (EXPLICIT) ===")
        print(f"Person gramps_id used: {gramps_id}")
        print(f"Max generations: {TEST_MAX_GENERATIONS}")
        print(f"Total lines: {len(text_explicit.splitlines())}")

        # Test default result
        assert isinstance(result_default, list)
        assert len(result_default) == 1
        assert isinstance(result_default[0], TextContent)

        text_default = result_default[0].text
        print("\n=== ANCESTORS TEST OUTPUT (DEFAULT) ===")
        print(f"Person gramps_id used: {gramps_id}")
        print("Max generations: DEFAULT (should be 5)")
        print(f"Total lines: {len(text_default.splitlines())}")
        print("=" * 50)

        # Both should contain actual ancestors data
        for text in [text_explicit, text_default]:
            assert isinstance(text, str)
            assert len(text) > 0
            assert len(text.strip()) > 50  # Should be substantial content
            assert "report generated successfully" not in text.lower()
            # Report should contain genealogy-related content - check for "Generation" which appears in ancestor reports
            assert "generation" in text.lower()
            # Reason: the substring check above passes on coincidental
            # wording alone - it would not catch a broken
            # format_traversal. These assert on the BFS output's actual
            # structure: the heading, its generation/people count, and at
            # least one indented child line carrying a gramps_id. I0001 is
            # the tree owner and has both parents recorded, so an indented
            # child line is guaranteed here.
            assert text.startswith("# Ancestors of ")
            assert re.search(r"\d+ generations?, \d+ people", text)
            assert re.search(r"\n {2,}- .*\([A-Z]\d{4}\)", text)

    @pytest.mark.asyncio
    async def test_get_ancestors_invalid_gramps_id(self):
        """Test ancestors retrieval with invalid gramps ID."""

        result = await get_ancestors_tool({"gramps_id": INVALID_GRAMPS_ID})

        text = result[0].text
        assert "Error:" in text or "No ancestors found" in text


class TestGetRecentChangesTool:
    """Test get_recent_changes_tool functionality."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_get_recent_changes_real_api(self):
        """Test get_recent_changes_tool with real API."""

        result = await get_recent_changes_tool({"page": 1, "pagesize": 10})

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)

        text = result[0].text
        print("\n=== RECENT CHANGES TEST OUTPUT ===")
        print(f"Result: {text}")
        print("=" * 50)

        assert "recent changes" in text.lower()
        # With populated tree, expect actual recent changes data
        assert "found" in text.lower() and "no recent changes found" not in text.lower()

        # Count the number of transaction entries (each starts with "• **")
        transaction_count = text.count("• **")
        assert 1 <= transaction_count <= 10, (
            f"Expected 1-10 transactions but got {transaction_count}"
        )

        # Should show gramps_id instead of handle
        if "Objects changed:" in text:
            # Gramps IDs follow pattern: Letter + 4 digits (e.g., I0001, F0002, O0506)
            import re

            assert re.search(r"[A-Z]\d{4}", text), (
                "Should show gramps IDs (letter + 4 digits)"
            )


class TestGetTreeInfoTool:
    """Test get_tree_info_tool functionality."""

    pytestmark = pytest.mark.integration

    @pytest.mark.asyncio
    async def test_get_tree_info_real_api(self):
        """Test get_tree_info_tool with real API."""

        result = await get_tree_info_tool({"include_statistics": True})

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)

        text = result[0].text
        print("\n=== TREE INFO TEST OUTPUT ===")
        print(f"Result: {text}")
        print("=" * 50)

        # Should contain tree information
        assert "Family Tree:" in text
        assert "Tree ID:" in text

        # Should contain statistics (not "Statistics not available")
        assert "Statistics not available" not in text

        # Should contain actual counts
        assert "People:" in text or "people_count" in text.lower()

        # Should show media storage in MB format
        assert "MB" in text


# Note: AnalysisClient tests removed as we now use unified GrampsWebAPIClient


class TestBfsAncestorOutput:
    """Live checks on the BFS output shape. Needs a populated tree."""

    pytestmark = pytest.mark.integration

    async def test_ancestors_of_i0001_name_the_known_parents(self):
        result = await get_ancestors_tool({"gramps_id": "I0001", "max_generations": 3})
        text = result[0].text
        assert text.startswith("# Ancestors of")
        # Reason: I0001 is the tree owner and has both parents recorded.
        # If this ever fails, check the tree before the code.
        assert text.count("\n  - ") >= 2

    async def test_fewer_generations_return_strictly_fewer_lines(self):
        shallow = await get_ancestors_tool({"gramps_id": "I0001", "max_generations": 1})
        deep = await get_ancestors_tool({"gramps_id": "I0001", "max_generations": 3})
        assert len(shallow[0].text.splitlines()) < len(deep[0].text.splitlines())

    async def test_every_person_line_carries_a_gramps_id(self):
        result = await get_ancestors_tool({"gramps_id": "I0001", "max_generations": 2})
        person_lines = [
            line
            for line in result[0].text.splitlines()
            if line.lstrip().startswith("- ")
        ]
        assert person_lines
        for line in person_lines:
            assert "(I" in line or "[unavailable" in line

    async def test_unknown_gramps_id_reports_an_error(self):
        result = await get_ancestors_tool({"gramps_id": "I999999"})
        # Reason: an unknown gramps_id is an expected outcome, not an
        # unexpected error - the design specifies this exact message, with
        # no "Unexpected error during..." wrapper.
        assert result[0].text == "Error: no person found with gramps_id I999999"


class TestValidateMaxGenerations:
    """Offline tests for the max_generations bound the stdio transport
    otherwise skips - see _validate_max_generations's docstring."""

    def test_absent_value_defaults_to_five(self):
        assert _validate_max_generations(None) == 5

    def test_zero_is_rejected_not_silently_defaulted(self):
        with pytest.raises(ValueError, match="1 through 20"):
            _validate_max_generations(0)

    def test_above_twenty_is_rejected(self):
        with pytest.raises(ValueError, match="1 through 20"):
            _validate_max_generations(21)

    def test_non_integer_is_rejected(self):
        with pytest.raises(ValueError, match="1 through 20"):
            _validate_max_generations("5")

    def test_bool_is_rejected_despite_being_an_int_subclass(self):
        with pytest.raises(ValueError, match="1 through 20"):
            _validate_max_generations(True)

    def test_valid_value_passes_through(self):
        assert _validate_max_generations(7) == 7
