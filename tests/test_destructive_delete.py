"""Tests for the delete_type tool."""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.tools.destructive import delete_type_tool


class TestDeleteRefusal:
    """Offline: the refusal path, exercised through the transport seam."""

    async def test_refuses_when_backlinks_exist_and_force_is_unset(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.return_value = {
                "handle": "h1",
                "gramps_id": "N0001",
                "backlinks": {"person": ["p1", "p2"]},
            }
            result = await delete_type_tool(
                {"type": "note", "handle": "h1", "force": False}
            )

        text = result[0].text
        assert "Refused" in text
        assert "2 person" in text
        assert "force=true" in text

    async def test_deletes_when_no_backlinks(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.return_value = {"handle": "h1", "gramps_id": "N0001", "backlinks": {}}
            result = await delete_type_tool({"type": "note", "handle": "h1"})

        assert "Deleted" in result[0].text
        assert "N0001" in result[0].text

    async def test_rejects_an_unknown_type(self):
        result = await delete_type_tool({"type": "banana", "handle": "h1"})
        assert "Error" in result[0].text

    async def test_requires_handle_or_gramps_id(self):
        result = await delete_type_tool({"type": "note"})
        assert "Error" in result[0].text


@pytest.mark.integration
class TestDeleteLive:
    """
    Live tests against the configured tree.

    Two hard rules, because the reference tree is production data:
    a test never passes a handle it did not create in that same test, and
    force=true is never used on anything but a record the test created.
    """

    async def test_deletes_a_note_it_created(self, gramps_client, tree_id):
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
        from tests.conftest import create_entity
        from tests.constants import PREFIX

        handle = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_NOTES,
            NoteSaveParams(text=f"{PREFIX} delete me", type="Transcript"),
            "note",
        )

        result = await delete_type_tool({"type": "note", "handle": handle})
        assert "Deleted" in result[0].text

        second = await delete_type_tool({"type": "note", "handle": handle})
        assert "Error" in second[0].text
