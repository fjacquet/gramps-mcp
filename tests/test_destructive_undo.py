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

    async def test_reports_success_after_polling_a_background_task(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = [
                {"task": {"id": "task-1", "href": "/api/tasks/task-1"}},
                {"state": "SUCCESS"},
            ]
            result = await undo_change_tool({"transaction_id": 7})

        assert "7" in result[0].text
        assert "ndone" in result[0].text

    async def test_reports_a_failed_background_undo(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = [
                {"task": {"id": "task-1", "href": "/api/tasks/task-1"}},
                {"state": "FAILURE", "info": "Object has changed"},
            ]
            result = await undo_change_tool({"transaction_id": 7})

        assert "Error" in result[0].text
        assert "Object has changed" in result[0].text


@pytest.mark.integration
class TestUndoLive:
    async def test_undo_requires_force_to_reverse_a_deletion(
        self, gramps_client, tree_id
    ):
        """
        Pins down a confirmed upstream Gramps Web bug rather than hiding it.

        gramps_webapi/api/tasks.py:782-791's old_unchanged() treats a
        missing object as "unchanged" only when the recorded prior state is
        literally None. For a delete transaction, Change._to_dict()
        (gramps_webapi/undodb.py:98-113) returns {} instead of None when
        there is no "new" JSON to report - and reverse_transaction()
        (gramps_webapi/api/resources/util.py:1584-1596) carries that {}
        into the reversed "add" item's old_data. old_unchanged() then sees
        a HandleError (the object really is gone) with old_data={} rather
        than None, and reports a false "Object has changed" conflict -
        confirmed by the server's own GET conflict-preflight for the same
        transaction reporting zero conflicts, and by force=true undoing the
        exact same transaction successfully every time.

        This test should start FAILING the day Gramps Web fixes that bug -
        that failure is the signal that undo_change no longer needs force
        for a plain delete, not a regression in gramps-mcp.
        """
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
        transaction = history[0]
        transaction_id = transaction["id"]

        # Reason: this tree is production data. "the newest transaction" is
        # not the same thing as "the transaction this test just made" - a
        # concurrent write between the delete above and this read would make
        # the rest of this test force-undo somebody else's work, and
        # force=True means the server's conflict check would not stop it.
        # Refuse to undo anything that does not name the handle created
        # here, and say so loudly rather than skipping quietly.
        touched = {
            change.get("obj_handle") for change in transaction.get("changes") or []
        }
        if not touched:
            # Some deployments omit `changes` from the list view; ask for the
            # single transaction, which always carries them.
            detail = await gramps_client.make_api_call(
                api_call=ApiCalls.GET_TRANSACTION_HISTORY,
                tree_id=tree_id,
                transaction_id=transaction_id,
            )
            entries = (
                detail if isinstance(detail, list) else detail.get("changes") or []
            )
            touched = {change.get("obj_handle") for change in entries}

        assert handle in touched, (
            f"transaction {transaction_id} does not concern the note this "
            f"test created ({handle}); it touched {sorted(h for h in touched if h)}. "
            "Something else wrote to the tree between the delete and this "
            "read - refusing to undo an unrelated transaction."
        )

        refused = await undo_change_tool({"transaction_id": transaction_id})
        assert "Error" in refused[0].text
        assert "force" in refused[0].text.lower()

        # The refusal must be real, not cosmetic: the note is still gone.
        with pytest.raises(Exception):
            await gramps_client.make_api_call(
                api_call=ApiCalls.GET_NOTE, tree_id=tree_id, handle=handle
            )

        forced = await undo_change_tool(
            {"transaction_id": transaction_id, "force": True}
        )
        assert "undone" in forced[0].text

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
