"""
Integration tests for replacing a place's parent against the real Gramps API.
"""

import uuid

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools.data_management import create_place_tool


class TestPlaceMove:
    """Replacing placeref_list must move a place, not add a second parent."""

    @pytest.mark.asyncio
    async def test_replacing_placeref_list_moves_the_place(self):
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id
        suffix = uuid.uuid4().hex[:8]
        handles = []

        try:
            for label in ("ParentA", "ParentB", "Child"):
                created = await client.make_api_call(
                    api_call=ApiCalls.POST_PLACES,
                    params={
                        "name": {"value": f"Pytest{label}{suffix}"},
                        "place_type": "City",
                    },
                    tree_id=tree_id,
                )
                handles.append(created[0]["new"]["handle"])
            parent_a, parent_b, child = handles

            await client.make_api_call(
                api_call=ApiCalls.PUT_PLACE,
                params={"placeref_list": [{"ref": parent_a}]},
                tree_id=tree_id,
                handle=child,
            )

            await client.make_api_call(
                api_call=ApiCalls.PUT_PLACE,
                params={"placeref_list": [{"ref": parent_b}]},
                tree_id=tree_id,
                handle=child,
                replace_lists=["placeref_list"],
            )

            moved = await client.make_api_call(
                api_call=ApiCalls.GET_PLACE, tree_id=tree_id, handle=child
            )
            refs = [entry.get("ref") for entry in moved.get("placeref_list", [])]

            # Reason: without replacement this reads [parent_a, parent_b] and
            # Gramps keeps the first, so the move silently does nothing.
            assert refs == [parent_b]
        finally:
            for handle in reversed(handles):
                await client.make_api_call(
                    api_call=ApiCalls.DELETE_PLACE, tree_id=tree_id, handle=handle
                )

    @pytest.mark.asyncio
    async def test_create_place_tool_moves_the_place(self):
        """Same assertion, but through create_place_tool - the layer that
        pops replace_lists out of raw arguments (data_management.py:109)
        before PlaceSaveParams is built. Without that line, replace_lists
        would land in PlaceSaveParams as data, be ignored by Gramps, and
        this move would silently do nothing - with the rest of the suite
        still green, since test_replacing_placeref_list_moves_the_place
        above bypasses the tool layer entirely.
        """
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id
        suffix = uuid.uuid4().hex[:8]
        handles = []

        try:
            for label in ("ParentA", "ParentB", "Child"):
                created = await client.make_api_call(
                    api_call=ApiCalls.POST_PLACES,
                    params={
                        "name": {"value": f"Pytest{label}{suffix}"},
                        "place_type": "City",
                    },
                    tree_id=tree_id,
                )
                handles.append(created[0]["new"]["handle"])
            parent_a, parent_b, child = handles

            await create_place_tool(
                {
                    "handle": child,
                    "placeref_list": [{"ref": parent_a}],
                }
            )

            await create_place_tool(
                {
                    "handle": child,
                    "placeref_list": [{"ref": parent_b}],
                    "replace_lists": ["placeref_list"],
                }
            )

            moved = await client.make_api_call(
                api_call=ApiCalls.GET_PLACE, tree_id=tree_id, handle=child
            )
            refs = [entry.get("ref") for entry in moved.get("placeref_list", [])]

            # Reason: without the replace_lists pop, this reads
            # [parent_a, parent_b] instead of a real move.
            assert refs == [parent_b]
        finally:
            for handle in reversed(handles):
                await client.make_api_call(
                    api_call=ApiCalls.DELETE_PLACE, tree_id=tree_id, handle=handle
                )

    @pytest.mark.asyncio
    async def test_bare_string_replace_lists_is_rejected(self):
        """A bare string is a plausible typo for a one-element list and is
        itself iterable, so set(replace_lists or ()) would silently expand
        "placeref_list" into a set of single characters. No key would then
        match, the replacement would be skipped, and the place would keep
        its old parent - the exact bug this lot exists to fix, reintroduced
        by a typo. This must be rejected loudly instead, before any network
        call (no live server needed for this assertion).
        """
        result = await create_place_tool(
            {
                "handle": "0" * 26,
                "placeref_list": [{"ref": "1" * 26}],
                "replace_lists": "placeref_list",
            }
        )

        text = result[0].text
        assert "Error" in text
        assert "replace_lists" in text
        assert "list" in text
