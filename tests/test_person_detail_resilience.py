"""
Integration tests for person detail degradation against the real Gramps API.
"""

import uuid

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.handlers.person_detail_handler import format_person_detail
from src.gramps_mcp.models.api_calls import ApiCalls


class TestPersonDetailResilience:
    """A dangling media reference must not destroy the whole detail."""

    @pytest.mark.asyncio
    async def test_dangling_media_ref_degrades_gracefully(self):
        """A person with a dangling media ref still returns a full detail.

        Regression test: the unguarded media/note loops in
        format_person_detail used to let a single 404 from a dangling
        handle raise GrampsAPIError, discarding relations, timeline, and
        citations along with it.

        Reason: creating a real media object and then deleting it does not
        reproduce the bug here - the Gramps Web API cascades the deletion
        and strips the reference from the person's media_list. The API
        does not validate that a media ref exists when a person is written,
        though, so attaching a handle that was never created reproduces
        the same 404-on-lookup condition without that cascade cleanup.
        """
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id
        surname = f"Pytest{uuid.uuid4().hex[:8]}"
        dangling_media_handle = uuid.uuid4().hex
        person_handle = None

        try:
            person_result = await client.make_api_call(
                api_call=ApiCalls.POST_PEOPLE,
                params={
                    "primary_name": {
                        "first_name": "Dangling",
                        "surname_list": [{"surname": surname}],
                    },
                    "gender": 2,
                    "media_list": [{"ref": dangling_media_handle}],
                },
                tree_id=tree_id,
            )
            person_handle = person_result[0]["new"]["handle"]

            result = await format_person_detail(client, tree_id, person_handle)

            # Reason: the unguarded call used to abort the whole detail.
            assert "error" not in result.lower()
            assert surname in result
        finally:
            if person_handle:
                await client.make_api_call(
                    api_call=ApiCalls.DELETE_PERSON,
                    tree_id=tree_id,
                    handle=person_handle,
                )
