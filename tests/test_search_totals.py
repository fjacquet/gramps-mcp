"""
Integration tests for search result totals against the real Gramps API.
"""

import re

import pytest

from src.gramps_mcp.tools.search_basic import find_type_tool

pytestmark = pytest.mark.integration


class TestSearchTotals:
    """A truncated search must report the real match count."""

    @pytest.mark.asyncio
    async def test_total_exceeds_displayed_count(self):
        """Unpaginated call: displayed_count must reflect what's rendered.

        Folded from two tests that made an identical API call (no `page`)
        and only differed in how they parsed the same response text.
        """
        result = await find_type_tool(
            {"type": "person", "gql": 'gramps_id!=""', "max_results": 5}
        )
        text = result[0].text

        assert "error" not in text.lower()
        # Reason: with the page length used as the total, this read
        # "Found 5 people" and gave no hint the set was truncated.
        assert "showing" in text.lower()

        found = re.search(r"Found (\d+)", text)
        showing = re.search(r"showing (\d+)", text)
        assert found is not None
        assert showing is not None
        assert int(found.group(1)) > int(showing.group(1))

    @pytest.mark.asyncio
    async def test_paginated_search_reports_tree_wide_total(self):
        """Paginated call: the header, not the page length, is the total.

        With an explicit `page`, the API honors pagesize server-side, so
        the raw response list already equals the page length -
        `len(results)` and `displayed_count` collapse to the same number
        as they did before this fix. Only reading X-Total-Count catches
        this case; without it the tool reports "Found 5 people" with no
        hint of truncation, reintroducing the original bug from the other
        side.
        """
        result = await find_type_tool(
            {
                "type": "person",
                "gql": 'gramps_id!=""',
                "max_results": 5,
                "page": 1,
            }
        )
        text = result[0].text

        assert "error" not in text.lower()

        found = re.search(r"Found (\d+)", text)
        showing = re.search(r"showing (\d+)", text)
        assert found is not None
        assert showing is not None
        # Reason: do not hardcode the tree size - it grows over time.
        # Assert the relationship instead: the real total is far larger
        # than the single page requested.
        assert int(found.group(1)) > int(showing.group(1))
