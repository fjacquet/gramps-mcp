"""
Integration tests for replacing a place's parent against the real Gramps API.
"""

import uuid

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls


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

            # Reason: PlaceSaveParams requires place_type on every save
            # (POST and PUT share one model), so a partial PUT that only
            # touches placeref_list must still supply it.
            await client.make_api_call(
                api_call=ApiCalls.PUT_PLACE,
                params={"placeref_list": [{"ref": parent_a}], "place_type": "City"},
                tree_id=tree_id,
                handle=child,
            )

            await client.make_api_call(
                api_call=ApiCalls.PUT_PLACE,
                params={"placeref_list": [{"ref": parent_b}], "place_type": "City"},
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
