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

    Pages through GET_PEOPLE rather than trusting a single page, since a
    person carrying media is not guaranteed to fall within the first
    `pagesize` results. Stops at the first match, or once a page comes
    back shorter than requested (the last page), or after a bounded
    number of pages so a misunderstanding of the paging contract cannot
    spin forever.

    Args:
        client (GrampsWebAPIClient): Client to query with.
        tree_id (str): Family tree identifier.

    Returns:
        dict | None: The first person carrying media, or None if the tree
            has none.
    """
    pagesize = 200
    max_pages = 20  # Reason: sane upper bound (4000 people) against a
    # misunderstood paging contract; the live tree has ~908 people.
    # Reason: GET_PEOPLE pages are 1-indexed - page=0 returns 422 from
    # the live API.
    for page in range(1, max_pages + 1):
        people = await client.make_api_call(
            api_call=ApiCalls.GET_PEOPLE,
            params={"page": page, "pagesize": pagesize},
            tree_id=tree_id,
        )
        people = people if isinstance(people, list) else []
        for person in people:
            if person.get("media_list"):
                return person
        if len(people) < pagesize:
            return None
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
