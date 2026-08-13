"""
Integration tests for search result totals against the real Gramps API.
"""

import pytest

from src.gramps_mcp.tools.search_basic import find_type_tool


class TestSearchTotals:
    """A truncated search must report the real match count."""

    @pytest.mark.asyncio
    async def test_truncated_search_reports_both_numbers(self):
        result = await find_type_tool(
            {"type": "person", "gql": 'gramps_id!=""', "max_results": 5}
        )
        text = result[0].text

        assert "error" not in text.lower()
        # Reason: with the page length used as the total, this read
        # "Found 5 people" and gave no hint the set was truncated.
        assert "showing" in text.lower()

    @pytest.mark.asyncio
    async def test_total_exceeds_displayed_count(self):
        result = await find_type_tool(
            {"type": "person", "gql": 'gramps_id!=""', "max_results": 5}
        )
        text = result[0].text

        import re

        found = re.search(r"Found (\d+)", text)
        showing = re.search(r"showing (\d+)", text)
        assert found is not None
        assert showing is not None
        assert int(found.group(1)) > int(showing.group(1))
