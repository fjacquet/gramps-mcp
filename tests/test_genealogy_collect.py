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


class TestCollectLive:
    pytestmark = pytest.mark.integration

    async def test_reads_the_real_tree(self, gramps_client, tree_id):
        result = await collect_tree(gramps_client, tree_id, limit=25)

        assert result.partial is False
        assert result.error is None
        assert len(result.people) > 0
        assert all(p.gramps_id for p in result.people)
