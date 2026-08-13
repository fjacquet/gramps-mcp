# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Integration tests for resolving a gramps_id in get_type.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools.search_details import _resolve_gramps_id, get_type_tool

pytestmark = pytest.mark.integration

# A real family gramps_id from the live tree, found via a direct
# ApiCalls.GET_FAMILIES probe (F0308 -> handle 103f77ffdd8f25ec1684cd0236c4),
# the same way I0076 was confirmed for the person case.
KNOWN_FAMILY_GRAMPS_ID = "F0308"


class TestGetTypeResolution:
    """A gramps_id resolves through the API, and a missing one says so."""

    @pytest.mark.asyncio
    async def test_known_gramps_id_resolves(self):
        result = await get_type_tool({"type": "person", "gramps_id": "I0076"})
        text = result[0].text

        assert "not yet implemented" not in text
        assert "I0076" in text

    @pytest.mark.asyncio
    async def test_missing_gramps_id_says_not_found(self):
        result = await get_type_tool({"type": "person", "gramps_id": "I999999"})
        text = result[0].text

        # Reason: this used to report the tool as unimplemented, because the
        # regex found no bracket to scrape and both branches fell through.
        assert "not yet implemented" not in text
        assert "I999999" in text

    @pytest.mark.asyncio
    async def test_handle_still_works(self):
        # Reason: resolves I0076 to a real handle first (rather than
        # hardcoding one), then calls get_type_tool with that handle
        # directly, so this exercises the handle branch instead of
        # duplicating the gramps_id resolution test above it.
        handle = await _resolve_gramps_id("person", "I0076")
        assert handle is not None

        result = await get_type_tool({"type": "person", "handle": handle})
        text = result[0].text

        assert not text.startswith("Error: ")
        assert "not yet implemented" not in text
        assert "I0076" in text

    @pytest.mark.asyncio
    async def test_missing_type_and_identifier_names_the_problem(self):
        # Reason: neither handle nor gramps_id is supplied, so the tool
        # falls through both branches to the final message. An earlier lot
        # removed a literal "not yet implemented" string here in favor of a
        # message naming what was wrong; this pins that replacement.
        result = await get_type_tool({"type": "person"})
        text = result[0].text

        assert "not yet implemented" not in text
        assert "person" in text
        assert "handle" in text or "gramps_id" in text

    @pytest.mark.asyncio
    async def test_unsupported_type_names_the_problem(self):
        # Reason: no gramps_id or handle is supplied, so this reaches the
        # final fallthrough (search_details.py:206-213) rather than the
        # "No {type} found with gramps_id" exit that a supplied identifier
        # would trigger (already covered by test_missing_gramps_id_says_
        # not_found). An earlier version of this test passed a gramps_id
        # alongside "banana" and landed in that other, already-covered
        # branch instead - fixed per review.
        result = await get_type_tool({"type": "banana"})
        text = result[0].text

        assert "not yet implemented" not in text
        assert "banana" in text

    @pytest.mark.asyncio
    async def test_family_gramps_id_resolves(self):
        result = await get_type_tool(
            {"type": "family", "gramps_id": KNOWN_FAMILY_GRAMPS_ID}
        )
        text = result[0].text

        assert "not yet implemented" not in text
        assert KNOWN_FAMILY_GRAMPS_ID in text

    @pytest.mark.asyncio
    async def test_quote_in_gramps_id_reports_formatted_error(self):
        # Reason: gramps_id is interpolated into a GQL filter string
        # unescaped (see the "Reason:" comment on the gql= call in
        # _resolve_gramps_id), so an id containing a double quote builds a
        # malformed filter the live server rejects with a real 422 error.
        # This exercises the try/except around _resolve_gramps_id through
        # the actual API, with no mock, and pins the shape of what a
        # caller sees on failure.
        result = await get_type_tool({"type": "person", "gramps_id": 'I0076"'})
        text = result[0].text

        assert text.startswith("Error: ")
        assert "not yet implemented" not in text

    @pytest.mark.asyncio
    async def test_well_formed_quote_injection_is_refused(self):
        # Reason: the benign half above (a stray quote making the filter
        # malformed) is not the dangerous case. A quote crafted to keep the
        # filter well-formed - verified live to resolve to a real,
        # unrelated person - would otherwise have get_type silently
        # present someone else's record as the answer. This pins the
        # refusal added to _resolve_gramps_id rather than exercising the
        # injection itself.
        result = await get_type_tool(
            {"type": "person", "gramps_id": 'x" or gramps_id!="'}
        )
        text = result[0].text

        assert text.startswith("Error: ")
        assert "not yet implemented" not in text

    @pytest.mark.asyncio
    async def test_backslash_in_gramps_id_is_refused(self):
        result = await get_type_tool({"type": "person", "gramps_id": "I0076\\"})
        text = result[0].text

        assert text.startswith("Error: ")


class TestResolveGrampsIdIndependentOfRendering:
    """
    _resolve_gramps_id must return the correct handle on its own, proven
    against a ground-truth handle fetched through a separate, direct
    structured API call rather than through get_type_tool's formatted
    output. This is the decoupling half of the fix: resolution no longer
    depends on how results are rendered for display, so it stays correct
    even if the display formatting changes.
    """

    @pytest.mark.asyncio
    async def test_resolve_gramps_id_matches_ground_truth_handle_for_person(self):
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id

        # Ground truth obtained directly from the API, independent of
        # _resolve_gramps_id and of any text formatter.
        ground_truth = await client.make_api_call(
            api_call=ApiCalls.GET_PEOPLE,
            params={"gramps_id": "I0076"},
            tree_id=tree_id,
        )
        expected_handle = ground_truth[0]["handle"]

        handle = await _resolve_gramps_id("person", "I0076")

        assert handle == expected_handle

    @pytest.mark.asyncio
    async def test_resolve_gramps_id_matches_ground_truth_handle_for_family(self):
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id

        ground_truth = await client.make_api_call(
            api_call=ApiCalls.GET_FAMILIES,
            params={"gramps_id": KNOWN_FAMILY_GRAMPS_ID},
            tree_id=tree_id,
        )
        expected_handle = ground_truth[0]["handle"]

        handle = await _resolve_gramps_id("family", KNOWN_FAMILY_GRAMPS_ID)

        assert handle == expected_handle

    @pytest.mark.asyncio
    async def test_resolve_gramps_id_returns_none_for_missing_id(self):
        handle = await _resolve_gramps_id("person", "I999999")
        assert handle is None
