"""Integration tests: gql expressions travel as MatchesQuery rules."""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.models.api_calls import ApiCalls

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_gql_param_filters_people() -> None:
    """A gql param narrows GET_PEOPLE to the matching record."""
    client = GrampsWebAPIClient()
    result = await client.make_api_call(
        ApiCalls.GET_PEOPLE, {"gql": 'gramps_id == "I0001"', "pagesize": 1}
    )
    assert [p["gramps_id"] for p in result] == ["I0001"]


@pytest.mark.asyncio
async def test_total_count_header_survives() -> None:
    """X-Total-Count still reports the filtered count."""
    client = GrampsWebAPIClient()
    _, headers = await client.make_api_call(
        ApiCalls.GET_PEOPLE,
        {"gql": 'gramps_id == "I0001"', "pagesize": 1},
        with_headers=True,
    )
    assert {k.lower(): v for k, v in headers.items()}["x-total-count"] == "1"


@pytest.mark.asyncio
async def test_unicode_expression() -> None:
    """A non-ASCII surname in the expression reaches the server intact."""
    client = GrampsWebAPIClient()
    result = await client.make_api_call(
        ApiCalls.GET_PEOPLE,
        {"gql": 'primary_name.surname_list[0].surname == "Méléo"', "pagesize": 5},
    )
    assert len(result) >= 1
