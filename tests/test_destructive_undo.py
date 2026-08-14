# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for the undo_change tool."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.tools.destructive import undo_change_tool


class TestUndoOffline:
    async def test_reports_the_transaction_it_undid(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.return_value = {}
            result = await undo_change_tool({"transaction_id": 42})

        assert "42" in result[0].text
        assert "ndone" in result[0].text

    async def test_rejects_a_non_numeric_transaction_id(self):
        result = await undo_change_tool({"transaction_id": "not-a-number"})
        assert "Error" in result[0].text


@pytest.mark.integration
class TestUndoLive:
    async def test_undoes_a_deletion_it_performed(self, gramps_client, tree_id):
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
        from src.gramps_mcp.tools.destructive import delete_type_tool
        from tests.conftest import create_entity, delete_entity
        from tests.constants import PREFIX

        handle = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_NOTES,
            NoteSaveParams(text=f"{PREFIX} undo me", type="Transcript"),
            "note",
        )

        result = await delete_type_tool({"type": "note", "handle": handle})
        assert "Deleted" in result[0].text

        history = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_TRANSACTIONS_HISTORY,
            params={"page": 1, "pagesize": 1, "sort": "-id"},
            tree_id=tree_id,
        )
        transaction_id = history[0]["id"]

        undone = await undo_change_tool({"transaction_id": transaction_id})
        assert "undone" in undone[0].text

        # Reason: the Gramps Web resource docstring for this endpoint says
        # "Undo a transaction using background processing", so the record
        # may not have reappeared the instant the undo call returns. Poll
        # rather than sleep once, so a genuinely broken undo still fails.
        restored = None
        deadline = asyncio.get_event_loop().time() + 5
        while asyncio.get_event_loop().time() < deadline:
            try:
                restored = await gramps_client.make_api_call(
                    api_call=ApiCalls.GET_NOTE, tree_id=tree_id, handle=handle
                )
                break
            except Exception:
                await asyncio.sleep(0.5)

        assert restored is not None, "note was not restored within 5 seconds"
        assert restored["handle"] == handle

        await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_NOTE, handle)
