"""Tests for the merge_type tool."""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.handlers.destructive_handler import format_merge_preview
from src.gramps_mcp.tools.destructive import merge_type_tool


class TestMergePreviewFormatting:
    def test_preview_names_which_record_survives(self):
        text = format_merge_preview(
            {"handle": "a", "gramps_id": "S0001", "title": "Keep me"},
            {"handle": "b", "gramps_id": "S0002", "title": "Absorb me"},
            "source",
        )
        assert "S0001" in text
        assert "S0002" in text
        assert "survives" in text.lower()
        assert "confirm=true" in text


class TestMergeOffline:
    async def test_without_confirm_it_previews_and_does_not_merge(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = [
                {"handle": "a", "gramps_id": "S0001", "title": "Keep"},
                {"handle": "b", "gramps_id": "S0002", "title": "Absorb"},
            ]
            result = await merge_type_tool(
                {
                    "type": "source",
                    "phoenix_handle": "a",
                    "titanic_handle": "b",
                }
            )

        assert "confirm=true" in result[0].text
        assert call.await_count == 2

    async def test_rejects_merging_a_record_with_itself(self):
        result = await merge_type_tool(
            {"type": "source", "phoenix_handle": "a", "titanic_handle": "a"}
        )
        assert "Error" in result[0].text

    async def test_rejects_tag_which_has_no_merge_endpoint(self):
        result = await merge_type_tool(
            {"type": "tag", "phoenix_handle": "a", "titanic_handle": "b"}
        )
        assert "Error" in result[0].text


@pytest.mark.integration
class TestMergeLive:
    async def test_merges_two_sources_it_created(self, gramps_client, tree_id):
        from src.gramps_mcp.client import GrampsAPIError
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.source_params import SourceSaveParams
        from tests.conftest import create_entity, delete_entity
        from tests.constants import PREFIX

        keep = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_SOURCES,
            SourceSaveParams(title=f"{PREFIX} phoenix source"),
            "source",
        )
        absorb = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_SOURCES,
            SourceSaveParams(title=f"{PREFIX} titanic source"),
            "source",
        )
        try:
            preview = await merge_type_tool(
                {"type": "source", "phoenix_handle": keep, "titanic_handle": absorb}
            )
            assert "confirm=true" in preview[0].text

            done = await merge_type_tool(
                {
                    "type": "source",
                    "phoenix_handle": keep,
                    "titanic_handle": absorb,
                    "confirm": True,
                }
            )
            assert "Merged" in done[0].text

            with pytest.raises(GrampsAPIError):
                await gramps_client.make_api_call(
                    api_call=ApiCalls.GET_SOURCE, tree_id=tree_id, handle=absorb
                )
        finally:
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_SOURCE, keep)
