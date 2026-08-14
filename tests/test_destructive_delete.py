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

    async def test_the_backlink_guard_fires_and_force_overrides_it(
        self, gramps_client, tree_id
    ):
        """
        The refusal path and force=true, end to end against the real API.

        The offline tests feed should_refuse_delete a hand-written dict, so
        nothing there proves the real `backlinks` response shape, nor that
        `?backlinks=true` is honoured on the GET route. If the real shape
        differed, should_refuse_delete({}) would return None and the guard
        would silently never fire while every offline test stayed green.
        force=true, the most dangerous flag in the branch, had no end-to-end
        coverage at all.

        Both records are created here, so force is only ever applied to a
        record this test owns.
        """
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
        from src.gramps_mcp.models.parameters.people_params import PersonData
        from tests.conftest import create_entity, delete_entity
        from tests.constants import PREFIX

        note = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_NOTES,
            NoteSaveParams(text=f"{PREFIX} referenced note", type="Transcript"),
            "note",
        )
        person = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_PEOPLE,
            PersonData(
                primary_name={
                    "first_name": PREFIX,
                    "surname_list": [{"surname": "Backlink"}],
                },
                gender=1,
                note_list=[note],
            ),
            "person",
        )
        note_survived = True
        try:
            refused = await delete_type_tool({"type": "note", "handle": note})
            text = refused[0].text
            assert "Refused" in text, text
            assert "person" in text
            assert person in text
            assert "force=true" in text

            # The refusal must be real, not cosmetic: the note is still there
            # and the person still references it.
            still_there = await gramps_client.make_api_call(
                api_call=ApiCalls.GET_NOTE, tree_id=tree_id, handle=note
            )
            assert still_there["handle"] == note
            before = await gramps_client.make_api_call(
                api_call=ApiCalls.GET_PERSON, tree_id=tree_id, handle=person
            )
            assert note in before["note_list"]

            forced = await delete_type_tool(
                {"type": "note", "handle": note, "force": True}
            )
            assert "Deleted" in forced[0].text
            assert "severed" in forced[0].text
            note_survived = False

            after = await gramps_client.make_api_call(
                api_call=ApiCalls.GET_PERSON, tree_id=tree_id, handle=person
            )
            assert note not in after["note_list"]
        finally:
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_PERSON, person)
            if note_survived:
                await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_NOTE, note)
