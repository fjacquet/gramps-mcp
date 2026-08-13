"""
Integration tests for media reference rendering against the real Gramps API.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.handlers.person_handler import format_person
from src.gramps_mcp.models.api_calls import ApiCalls


async def _find_person_with_media(client, tree_id: str) -> dict | None:
    """
    Find a person in the live tree that carries at least one media reference.

    Args:
        client (GrampsWebAPIClient): Client to query with.
        tree_id (str): Family tree identifier.

    Returns:
        dict | None: The first person carrying media, or None if the tree
            has none.
    """
    people = await client.make_api_call(
        api_call=ApiCalls.GET_PEOPLE, params={"pagesize": 200}, tree_id=tree_id
    )
    for person in people if isinstance(people, list) else []:
        if person.get("media_list"):
            return person
    return None


class TestMediaReferences:
    """A person's attached media must be resolved and displayed."""

    @pytest.mark.asyncio
    async def test_person_media_line_is_rendered(self):
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id

        person = await _find_person_with_media(client, tree_id)
        assert person is not None, (
            "the live tree has no person carrying media - this test needs one"
        )

        result = await format_person(client, tree_id, person["handle"])

        # Reason: with the collection endpoint the lookup raised and was
        # swallowed, so this line was never emitted.
        assert "Attached media:" in result
