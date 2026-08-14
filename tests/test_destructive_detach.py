"""Tests for the detach_reference tool."""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.tools.destructive import detach_reference_tool


class TestDetachOffline:
    async def test_refuses_when_the_handle_is_absent_from_the_list(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.return_value = {
                "handle": "p1",
                "gramps_id": "I0001",
                "note_list": ["other"],
            }
            result = await detach_reference_tool(
                {
                    "type": "person",
                    "handle": "p1",
                    "list_name": "note_list",
                    "ref_handle": "missing",
                }
            )

        assert "Error" in result[0].text
        assert "not present" in result[0].text

    async def test_reports_success_naming_what_was_detached(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.return_value = {
                "handle": "p1",
                "gramps_id": "I0001",
                "note_list": ["n1", "n2"],
            }
            result = await detach_reference_tool(
                {
                    "type": "person",
                    "handle": "p1",
                    "list_name": "note_list",
                    "ref_handle": "n1",
                }
            )

        text = result[0].text
        assert "Detached" in text
        assert "note_list" in text
        assert "I0001" in text

    async def test_refuses_a_list_the_write_model_does_not_declare(self):
        # EventSaveParams declares no media_list, attribute_list, or tag_list
        # (unlike PersonData, which shares them via BaseDataModel). A
        # payload filtered down to what the write model declares would
        # silently drop media_list here, so this must be refused up front
        # rather than reporting a detach that never reached the server.
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.return_value = {
                "handle": "e1",
                "gramps_id": "E0001",
                "media_list": ["m1"],
            }
            result = await detach_reference_tool(
                {
                    "type": "event",
                    "handle": "e1",
                    "list_name": "media_list",
                    "ref_handle": "m1",
                }
            )

        text = result[0].text
        assert "Error" in text
        assert "media_list" in text
        assert "cannot be edited" in text


@pytest.mark.integration
class TestDetachLive:
    async def test_detaches_a_note_from_a_person_it_created(
        self, gramps_client, tree_id
    ):
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
        from src.gramps_mcp.models.parameters.people_params import PersonData
        from tests.conftest import create_entity, delete_entity
        from tests.constants import PREFIX

        note = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_NOTES,
            NoteSaveParams(text=f"{PREFIX} detach me", type="Transcript"),
            "note",
        )
        person = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_PEOPLE,
            PersonData(
                primary_name={
                    "first_name": PREFIX,
                    "surname_list": [{"surname": "Detach"}],
                },
                gender=2,
                note_list=[note],
            ),
            "person",
        )
        try:
            result = await detach_reference_tool(
                {
                    "type": "person",
                    "handle": person,
                    "list_name": "note_list",
                    "ref_handle": note,
                }
            )
            assert "Detached" in result[0].text

            after = await gramps_client.make_api_call(
                api_call=ApiCalls.GET_PERSON, tree_id=tree_id, handle=person
            )
            assert note not in after["note_list"]
        finally:
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_PERSON, person)
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_NOTE, note)

    async def test_detaching_one_list_leaves_another_list_untouched(
        self, gramps_client, tree_id
    ):
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.event_params import EventSaveParams
        from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
        from src.gramps_mcp.models.parameters.people_params import PersonData
        from tests.conftest import create_entity, delete_entity
        from tests.constants import PREFIX

        note = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_NOTES,
            NoteSaveParams(text=f"{PREFIX} detach safety", type="Transcript"),
            "note",
        )
        event = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_EVENTS,
            EventSaveParams(type="Birth", citation_list=[]),
            "event",
        )
        person = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_PEOPLE,
            PersonData(
                primary_name={
                    "first_name": PREFIX,
                    "surname_list": [{"surname": "DetachSafety"}],
                },
                gender=2,
                note_list=[note],
                event_ref_list=[{"ref": event, "role": "Primary"}],
            ),
            "person",
        )
        try:
            result = await detach_reference_tool(
                {
                    "type": "person",
                    "handle": person,
                    "list_name": "note_list",
                    "ref_handle": note,
                }
            )
            assert "Detached" in result[0].text

            after = await gramps_client.make_api_call(
                api_call=ApiCalls.GET_PERSON, tree_id=tree_id, handle=person
            )
            assert after["note_list"] == []
            assert len(after["event_ref_list"]) == 1
            assert after["event_ref_list"][0]["ref"] == event
        finally:
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_PERSON, person)
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_EVENT, event)
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_NOTE, note)
