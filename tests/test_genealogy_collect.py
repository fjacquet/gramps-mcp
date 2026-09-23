"""Tests for tree collection."""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.genealogy.collect import collect_tree


class TestCollectOffline:
    async def test_converts_people_and_families(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = [
                [
                    {
                        "handle": "p1",
                        "gramps_id": "I0001",
                        "gender": 1,
                        "primary_name": {
                            "first_name": "Jean",
                            "surname_list": [{"surname": "Jacquet"}],
                        },
                    }
                ],
                [
                    {
                        "handle": "f1",
                        "gramps_id": "F0001",
                        "father_handle": "p1",
                        "mother_handle": None,
                        "child_ref_list": [],
                    }
                ],
            ]
            from src.gramps_mcp.client import GrampsWebAPIClient

            result = await collect_tree(GrampsWebAPIClient(), "tree")

        assert [p.gramps_id for p in result.people] == ["I0001"]
        assert "f1" in result.families
        assert result.partial is False
        assert result.skipped == 0

    async def test_a_record_that_cannot_be_converted_is_counted_not_fatal(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = [
                [
                    {"handle": "p1"},
                    {
                        "handle": "p2",
                        "gramps_id": "I0002",
                        "gender": 1,
                        "primary_name": {
                            "first_name": "Anne",
                            "surname_list": [{"surname": "Raucaz"}],
                        },
                    },
                ],
                [],
            ]
            from src.gramps_mcp.client import GrampsWebAPIClient

            result = await collect_tree(GrampsWebAPIClient(), "tree")

        assert result.skipped == 1
        assert len(result.people) == 1

    async def test_a_person_missing_handle_is_counted_not_carried_forward(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = [
                [
                    {
                        "handle": "",
                        "gramps_id": "I0003",
                        "gender": 1,
                        "primary_name": {
                            "first_name": "Sans",
                            "surname_list": [{"surname": "Handle"}],
                        },
                    },
                    {
                        "handle": "p4",
                        "gramps_id": "I0004",
                        "gender": 2,
                        "primary_name": {
                            "first_name": "Marie",
                            "surname_list": [{"surname": "Villaudy"}],
                        },
                    },
                ],
                [],
            ]
            from src.gramps_mcp.client import GrampsWebAPIClient

            result = await collect_tree(GrampsWebAPIClient(), "tree")

        assert result.skipped == 1
        assert len(result.people) == 1

    async def test_limit_zero_stops_immediately_not_treated_as_unset(self):
        """`raw_people[:limit] if limit else raw_people` tests truthiness,
        so limit=0 ("stop after zero people") was indistinguishable from
        limit=None ("no limit") and scanned the whole tree. The parameter
        models now reject limit=0 with `ge=1`, but collect_tree is also
        called directly in tests and could be called directly elsewhere, so
        it must not silently treat 0 as "everyone" either.
        """
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = [
                [
                    {
                        "handle": "p1",
                        "gramps_id": "I0001",
                        "gender": 1,
                        "primary_name": {
                            "first_name": "Jean",
                            "surname_list": [{"surname": "Jacquet"}],
                        },
                    }
                ],
                [],
            ]
            from src.gramps_mcp.client import GrampsWebAPIClient

            result = await collect_tree(GrampsWebAPIClient(), "tree", limit=0)

        assert result.people == []

    async def test_a_failure_mid_scan_reports_partial(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = RuntimeError("connection reset")
            from src.gramps_mcp.client import GrampsWebAPIClient

            result = await collect_tree(GrampsWebAPIClient(), "tree")

        assert result.partial is True
        assert result.error is not None
        assert "connection reset" in result.error


def _person(n: int) -> dict:
    return {
        "handle": f"p{n}",
        "gramps_id": f"I{n:04d}",
        "gender": n % 2,
        "primary_name": {
            "first_name": f"Jean{n}",
            "surname_list": [{"surname": "Jacquet"}],
        },
    }


def _paged_server(people: list[dict], families: list[dict], page_cap: int):
    """A server that answers paged reads and times out on unbounded ones.

    This is the behaviour actually observed against the live tree: asking
    for every person at once, with `profile=all` and `extend`, never
    returned, while the same rows fetched 500 at a time came back in
    seconds.
    """
    from src.gramps_mcp.models.api_calls import ApiCalls

    async def serve(api_call=None, params=None, tree_id=None, **_):
        params = params or {}
        size = params.get("pagesize")
        if size is None or size > page_cap:
            raise TimeoutError("Request timeout")
        rows = people if api_call == ApiCalls.GET_PEOPLE else families
        start = (params.get("page", 1) - 1) * size
        return rows[start : start + size]

    return serve


class TestCollectPaginates:
    """The whole tree must come back, however many people it holds."""

    async def test_a_tree_larger_than_one_page_comes_back_whole(self):
        people = [_person(n) for n in range(1, 1204)]
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = _paged_server(people, [], page_cap=500)
            from src.gramps_mcp.client import GrampsWebAPIClient

            result = await collect_tree(GrampsWebAPIClient(), "tree")

        assert len(result.people) == 1203
        assert result.people[-1].gramps_id == "I1203"
        assert result.partial is False
        assert result.error is None

    async def test_a_server_that_times_out_on_unbounded_reads_still_scans(self):
        """The defect this guards: find_duplicates over the whole tree
        returned "Partial scan: Request timeout" and then "None found" -
        a scan that had read nothing at all, rendered like a result.
        """
        people = [_person(n) for n in range(1, 900)]
        families = [
            {
                "handle": f"f{n}",
                "gramps_id": f"F{n:04d}",
                "father_handle": f"p{n}",
                "mother_handle": None,
                "child_ref_list": [],
            }
            for n in range(1, 700)
        ]
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = _paged_server(people, families, page_cap=500)
            from src.gramps_mcp.client import GrampsWebAPIClient

            result = await collect_tree(GrampsWebAPIClient(), "tree")

        assert result.partial is False
        assert len(result.people) == 899
        assert len(result.families) == 699

    async def test_a_page_boundary_exactly_hit_does_not_lose_the_rest(self):
        """1000 people over a 500 page size: the second page is full too,
        so stopping on "a full page means maybe more" must keep going.
        """
        people = [_person(n) for n in range(1, 1001)]
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = _paged_server(people, [], page_cap=500)
            from src.gramps_mcp.client import GrampsWebAPIClient

            result = await collect_tree(GrampsWebAPIClient(), "tree")

        assert len(result.people) == 1000

    async def test_families_are_read_without_the_profile_the_server_chokes_on(
        self,
    ):
        """The defect this guards: audit_quality on the live tree ended in
        "Partial scan: Request timeout". A page of 500 families with
        `profile=all` never came back in 600 s, the same page without it in
        0.4 s - and `family_from_json` never reads the profile anyway.
        """
        from src.gramps_mcp.models.api_calls import ApiCalls

        people = [_person(n) for n in range(1, 3)]
        families = [
            {
                "handle": "f1",
                "gramps_id": "F0001",
                "father_handle": "p1",
                "mother_handle": "p2",
                "child_ref_list": [],
                "extended": {
                    "events": [
                        {
                            "type": "Marriage",
                            "date": {"dateval": [4, 3, 1794, False], "year": 1794},
                        }
                    ]
                },
            }
        ]
        paged = _paged_server(people, families, page_cap=500)

        async def serve(api_call=None, params=None, tree_id=None, **kw):
            if api_call == ApiCalls.GET_FAMILIES and "profile" in (params or {}):
                raise TimeoutError("Request timeout")
            return await paged(api_call=api_call, params=params, tree_id=tree_id)

        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = serve
            from src.gramps_mcp.client import GrampsWebAPIClient

            result = await collect_tree(GrampsWebAPIClient(), "tree")

        assert result.partial is False
        assert result.error is None
        assert len(result.people) == 2
        marriage = result.families["f1"].marriage
        assert marriage is not None
        assert marriage.year == 1794


class TestCollectLive:
    pytestmark = pytest.mark.integration

    async def test_reads_the_real_tree(self, gramps_client, tree_id):
        result = await collect_tree(gramps_client, tree_id, limit=25)

        assert result.partial is False
        assert result.error is None
        assert len(result.people) > 0
        assert all(p.gramps_id for p in result.people)
