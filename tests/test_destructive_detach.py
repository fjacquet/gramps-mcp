"""Tests for the detach_reference tool."""

import warnings
from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.tools.destructive import detach_reference_tool

# An event as the API returns it. `date` is a raw dict against EventSaveParams'
# declared DateValue sub-model, which is exactly the field that would be
# truncated if the whole record were round-tripped through the write model.
EVENT_AS_STORED = {
    "handle": "e1",
    "gramps_id": "E0001",
    "type": "Birth",
    "date": {
        "calendar": 0,
        "modifier": 0,
        "quality": 0,
        "dateval": [12, 3, 1878, False],
        "text": "12 mars 1878",
        "sortval": 2407123,
        "newyear": 0,
    },
    "place": "place-handle-1",
    "description": "naissance",
    "citation_list": ["c1", "c2"],
    "note_list": ["n1"],
    "change": 1700000000,
}


class TestDetachPayload:
    """
    The PUT body, asserted at the transport seam.

    The convention here matches tests/test_client_merge.py and
    tests/test_http_error_detail.py: patch _make_request, not make_api_call,
    so what is asserted is what would actually go on the wire. The existing
    detach tests patch make_api_call, one layer too high, which is why this
    path had never run offline.
    """

    async def _detach(self, arguments, get_result, reget_result=None):
        """Run a detach with the transport stubbed; return the PUT body."""
        with patch.object(
            GrampsWebAPIClient, "_make_request", new_callable=AsyncMock
        ) as request:
            request.side_effect = [
                get_result,  # the tool's own GET
                # make_api_call's re-GET before merging
                get_result if reget_result is None else reget_result,
                {},  # the PUT response
            ]
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = await detach_reference_tool(arguments)

        put_call = request.call_args_list[-1]
        assert put_call.kwargs["method"] == "PUT"
        return result, put_call.kwargs["json_data"], caught

    async def test_the_put_body_carries_only_the_edited_list_from_the_caller(self):
        """
        Everything but the edited list must come from the server's own copy.

        The record used to be round-tripped in full through the write model,
        so every non-list field was rebuilt by pydantic's inferred
        serialization before merge_put_data replaced the stored value with
        it. Only the edited list may originate from this tool now.
        """
        result, body, _ = await self._detach(
            {
                "type": "event",
                "handle": "e1",
                "list_name": "citation_list",
                "ref_handle": "c1",
            },
            EVENT_AS_STORED,
        )

        assert "Detached" in result[0].text
        # The one intended change.
        assert body["citation_list"] == ["c2"]
        # Every other key is byte-identical to what the server had stored -
        # in particular `date`, the raw dict a narrowed serialization
        # fallback would have truncated to DateValue's declared fields.
        for key, stored in EVENT_AS_STORED.items():
            if key == "citation_list":
                continue
            assert body[key] == stored, f"{key} was rewritten by the detach"
        assert body["date"]["text"] == "12 mars 1878"
        assert body["date"]["sortval"] == 2407123

    async def test_the_detach_emits_no_serialization_warning(self):
        """
        The PydanticSerializationUnexpectedValue warning was the visible
        symptom of building a declared sub-model from a raw dict. No field
        of the write model is built from the record any more, so it must
        stay absent.

        This one is a guard, not a discriminator: the warning surfaced
        against the live server, not against this stub, so it passes with
        the old payload too. The test that actually fails on the old
        behaviour is
        test_non_list_fields_come_from_the_server_not_from_this_tool.
        """
        _, _, caught = await self._detach(
            {
                "type": "event",
                "handle": "e1",
                "list_name": "citation_list",
                "ref_handle": "c1",
            },
            EVENT_AS_STORED,
        )

        offenders = [
            w
            for w in caught
            if "SerializationUnexpectedValue" in type(w.message).__name__
        ]
        assert not offenders, [str(w.message) for w in offenders]

    async def test_an_unrelated_list_is_not_sent_and_keeps_its_stored_value(self):
        """
        note_list is untouched here, so the tool must not send it at all -
        the stored value survives because make_api_call merged into the
        server's copy, not because this tool echoed it back.
        """
        _, body, _ = await self._detach(
            {
                "type": "event",
                "handle": "e1",
                "list_name": "citation_list",
                "ref_handle": "c1",
            },
            EVENT_AS_STORED,
        )
        assert body["note_list"] == ["n1"]

    async def test_non_list_fields_come_from_the_server_not_from_this_tool(self):
        """
        The decisive check that the payload really is one field wide.

        make_api_call re-GETs the record before merging, so if the tool
        echoed the record it read, that echo would overwrite the server's
        value for every non-list field. Here the re-GET reports a different
        description and date text; both must survive into the PUT body,
        which is only possible if the tool sent neither.
        """
        server_copy = {
            **EVENT_AS_STORED,
            "description": "changed by someone else",
            "date": {**EVENT_AS_STORED["date"], "text": "12 mars 1879"},
        }
        _, body, _ = await self._detach(
            {
                "type": "event",
                "handle": "e1",
                "list_name": "citation_list",
                "ref_handle": "c1",
            },
            EVENT_AS_STORED,
            reget_result=server_copy,
        )

        assert body["description"] == "changed by someone else"
        assert body["date"]["text"] == "12 mars 1879"
        assert body["citation_list"] == ["c2"]


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
