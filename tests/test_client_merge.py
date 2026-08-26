"""
Unit tests for the client.py merge logic in PUT operations.

This test demonstrates the DESIRED behavior for Issue #9 - when updating a person
with new event references, the existing event_ref_list should be merged with the
new events, not replaced.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.merge import merge_put_data
from src.gramps_mcp.models.api_calls import ApiCalls


class TestClientMergeLogic:
    """Test the merge logic for PUT operations in the client."""

    @pytest.mark.asyncio
    async def test_put_operation_should_preserve_existing_events_when_adding_new(self):
        """Test that PUT operations should preserve existing events when adding new ones.

        This is the actual Issue #9 scenario: user has a person with existing events,
        and wants to add a new event. They provide only the new event in event_ref_list,
        expecting the existing events to be preserved.
        """

        # Create a client instance
        client = GrampsWebAPIClient()

        # Mock the auth manager to avoid actual authentication
        client.auth_manager = MagicMock()
        client.auth_manager.get_token = AsyncMock()
        client.auth_manager.get_headers = MagicMock(
            return_value={"Authorization": "Bearer test"}
        )
        client.auth_manager.client = MagicMock()
        client.auth_manager.close = AsyncMock()

        # Existing person data with one event (Birth) and other fields
        existing_person_data = {
            "handle": "test_person_handle",
            "gramps_id": "I0001",
            "primary_name": {
                "first_name": "John",
                "surname_list": [{"surname": "Smith"}],
            },
            "gender": 1,
            "change": 1234567890,
            "private": False,
            "event_ref_list": [{"ref": "birth_event_handle", "role": "Primary"}],
            "note_list": ["existing_note_handle"],
            "media_list": [{"ref": "existing_media_handle"}],
        }

        # User provides NEW event plus updates to other fields
        # This tests both list merging AND regular field updates
        update_data = {
            "handle": "test_person_handle",
            "primary_name": {
                "first_name": "Jonathan",  # Changed from "John"
                "surname_list": [{"surname": "Smith-Jones"}],  # Changed surname
            },
            "gender": 1,
            "private": True,  # Changed from False
            "event_ref_list": [{"ref": "death_event_handle", "role": "Primary"}],
            "note_list": ["new_note_handle"],  # New note, should merge with existing
        }

        # Mock the _make_request method to capture what's being sent
        with patch.object(
            client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            # First call returns existing data (GET)
            # Second call is the PUT with merged data
            mock_request.side_effect = [
                existing_person_data,  # GET response
                {"success": True},  # PUT response
            ]

            # Make the API call
            await client.make_api_call(
                api_call=ApiCalls.PUT_PERSON,
                params=update_data,
                tree_id="test_tree",
                handle="test_person_handle",
            )

            # Verify the GET request was made
            assert mock_request.call_count == 2

            # Get the PUT request call (second call)
            put_call = mock_request.call_args_list[1]

            # Extract the json_data argument from the PUT request
            put_json_data = put_call.kwargs.get("json_data") or put_call[1].get(
                "json_data"
            )

            # DESIRED BEHAVIOR: The existing event should be preserved
            assert put_json_data is not None, "PUT request should have json_data"
            assert "event_ref_list" in put_json_data, (
                "PUT data should have event_ref_list"
            )

            # Test 1: List fields should be MERGED (existing + new)
            event_refs = put_json_data["event_ref_list"]
            assert len(event_refs) == 2, (
                f"Should have 2 events (existing + new), got {len(event_refs)}: {event_refs}"
            )
            event_handles = {e["ref"] for e in event_refs}
            assert "birth_event_handle" in event_handles, (
                "Should preserve existing birth event"
            )
            assert "death_event_handle" in event_handles, "Should add new death event"

            note_refs = put_json_data["note_list"]
            assert len(note_refs) == 2, (
                f"Should have 2 notes (existing + new), got {len(note_refs)}: {note_refs}"
            )
            assert "existing_note_handle" in note_refs, "Should preserve existing note"
            assert "new_note_handle" in note_refs, "Should add new note"

            media_refs = put_json_data["media_list"]
            assert len(media_refs) == 1, (
                f"Should preserve existing media, got {len(media_refs)}: {media_refs}"
            )
            assert media_refs[0]["ref"] == "existing_media_handle", (
                "Should preserve existing media"
            )

            # Test 2: Non-list fields should be UPDATED (new values replace old)
            assert put_json_data.get("primary_name")["first_name"] == "Jonathan", (
                "Should update first_name"
            )
            assert (
                put_json_data.get("primary_name")["surname_list"][0]["surname"]
                == "Smith-Jones"
            ), "Should update surname"
            assert put_json_data.get("private") is True, "Should update private field"

            # Test 3: Fields not in update should be PRESERVED
            assert put_json_data.get("gramps_id") == "I0001", (
                "Should preserve gramps_id from existing data"
            )
            assert put_json_data.get("change") == 1234567890, (
                "Should preserve change field"
            )
            assert put_json_data.get("gender") == 1, "Should preserve gender"

        await client.close()

    @pytest.mark.asyncio
    async def test_event_ref_list_deduplication(self):
        """Test that duplicate event references are not added during merge."""
        # Setup mock API client
        client = GrampsWebAPIClient()
        client.auth_manager.close = AsyncMock()

        # Mock existing person with one event
        existing_person = {
            "handle": "person123",
            "primary_name": {
                "first_name": "John",
                "surname_list": [{"surname": "Smith"}],
            },
            "gender": 1,
            "gramps_id": "I001",
            "change": 1234567890,
            "event_ref_list": [{"ref": "event_birth", "role": "Primary"}],
        }

        # Mock update data that includes the same event plus a new one
        update_data = {
            "handle": "person123",
            "primary_name": {
                "first_name": "John",
                "surname_list": [{"surname": "Smith"}],
            },
            "gender": 1,
            "event_ref_list": [
                {"ref": "event_birth", "role": "Primary"},  # Duplicate
                {"ref": "event_death", "role": "Primary"},  # New
            ],
        }

        with patch.object(client, "_make_request") as mock_request:
            # First call (GET) returns existing person
            # Second call (PUT) will receive the merged data
            mock_request.side_effect = [existing_person, {"success": True}]

            # Make the API call
            await client.make_api_call(
                api_call=ApiCalls.PUT_PERSON,
                params=update_data,
                tree_id="test_tree",
                handle="person123",
            )

            # Verify the PUT request was made with deduplicated event_ref_list
            assert len(mock_request.call_args_list) == 2
            put_call = mock_request.call_args_list[1]
            put_data = put_call.kwargs.get("json_data") or put_call[1].get("json_data")

            # Should only have 2 events (birth once, death once), not 3
            assert len(put_data["event_ref_list"]) == 2
            event_refs = {event["ref"] for event in put_data["event_ref_list"]}
            assert event_refs == {"event_birth", "event_death"}

            print(
                f"DEBUG: Final event_ref_list has {len(put_data['event_ref_list'])} events"
            )
            for event in put_data["event_ref_list"]:
                print(f"  - {event['ref']}: {event['role']}")

        await client.close()

    @pytest.mark.asyncio
    async def test_generic_list_deduplication(self):
        """Test that deduplication works for all types of reference lists."""
        # Setup mock API client
        client = GrampsWebAPIClient()
        client.auth_manager.close = AsyncMock()

        # Mock existing person with various reference types
        existing_person = {
            "handle": "person123",
            "primary_name": {
                "first_name": "John",
                "surname_list": [{"surname": "Smith"}],
            },
            "gender": 1,
            "event_ref_list": [{"ref": "event1", "role": "Primary"}],
            "media_list": [{"ref": "media1"}],
            "note_list": ["note1"],  # Simple string handles
            "change": 1234567890,
            "gramps_id": "I001",
        }

        # Mock update data with duplicates and new items
        update_data = {
            "handle": "person123",
            "primary_name": {
                "first_name": "John",
                "surname_list": [{"surname": "Smith"}],
            },
            "gender": 1,
            "event_ref_list": [
                {"ref": "event1", "role": "Primary"},  # Duplicate
                {"ref": "event2", "role": "Primary"},  # New
            ],
            "media_list": [
                {"ref": "media1"},  # Duplicate
                {"ref": "media2"},  # New
            ],
            "note_list": ["note1", "note2"],  # Duplicate + new
        }

        with patch.object(client, "_make_request") as mock_request:
            mock_request.side_effect = [existing_person, {"success": True}]

            await client.make_api_call(
                api_call=ApiCalls.PUT_PERSON,
                params=update_data,
                tree_id="test_tree",
                handle="person123",
            )

            # Verify deduplication for all list types
            put_call = mock_request.call_args_list[1]
            put_data = put_call.kwargs.get("json_data") or put_call[1].get("json_data")

            # Event references (objects with ref field)
            assert len(put_data["event_ref_list"]) == 2
            event_refs = {e["ref"] for e in put_data["event_ref_list"]}
            assert event_refs == {"event1", "event2"}

            # Media references (objects with ref field)
            assert len(put_data["media_list"]) == 2
            media_refs = {m["ref"] for m in put_data["media_list"]}
            assert media_refs == {"media1", "media2"}

            # Note handles (simple strings) - deduplication test
            assert len(put_data["note_list"]) == 2
            assert set(put_data["note_list"]) == {"note1", "note2"}

        await client.close()

    def test_urls_merge_instead_of_replacing(self):
        # Reason: urls is a declared writable list on person, family, place
        # and repository, but its name does not end in _list. Dispatching on
        # the name rather than the value replaced it, destroying every URL
        # the caller did not resend.
        existing = {"urls": [{"path": "https://a.example", "desc": "A"}]}
        changes = {"urls": [{"path": "https://b.example", "desc": "B"}]}
        result = merge_put_data(existing, changes)
        assert result["urls"] == [
            {"path": "https://a.example", "desc": "A"},
            {"path": "https://b.example", "desc": "B"},
        ]

    def test_alt_names_merge_instead_of_replacing(self):
        existing = {"alt_names": [{"value": "Lugdunum"}, {"value": "Lyon"}]}
        changes = {"alt_names": [{"value": "Lyons"}]}
        result = merge_put_data(existing, changes)
        assert result["alt_names"] == [
            {"value": "Lugdunum"},
            {"value": "Lyon"},
            {"value": "Lyons"},
        ]

    def test_replace_lists_still_wins_for_a_non_list_suffixed_key(self):
        existing = {"urls": [{"path": "https://a.example"}]}
        changes = {"urls": [{"path": "https://b.example"}]}
        result = merge_put_data(existing, changes, replace_lists=["urls"])
        assert result["urls"] == [{"path": "https://b.example"}]

    def test_a_non_list_value_still_replaces(self):
        # Reason: widening the rule must not turn scalar replacement into
        # anything else - a changed surname must overwrite the old one.
        existing = {"gender": 1, "gramps_id": "I0001"}
        changes = {"gender": 0}
        result = merge_put_data(existing, changes)
        assert result["gender"] == 0
        assert result["gramps_id"] == "I0001"

    def test_a_list_absent_from_existing_is_taken_as_is(self):
        existing = {"gramps_id": "I0001"}
        changes = {"urls": [{"path": "https://a.example"}]}
        result = merge_put_data(existing, changes)
        assert result["urls"] == [{"path": "https://a.example"}]

    def test_partial_primary_name_keeps_the_sub_keys_it_omits(self):
        # Reason: primary_name is required on PersonData, so every person
        # update resends it. Replacing it wholesale destroyed 13 of the 15
        # sub-keys every person in the live tree carries.
        existing = {
            "primary_name": {
                "first_name": "Jean-Pierre",
                "surname_list": [{"surname": "Jacquet"}],
                "suffix": "Jr",
                "call": "JP",
                "type": "Birth Name",
            }
        }
        changes = {"primary_name": {"first_name": "Jean"}}
        result = merge_put_data(existing, changes)
        assert result["primary_name"] == {
            "first_name": "Jean",
            "surname_list": [{"surname": "Jacquet"}],
            "suffix": "Jr",
            "call": "JP",
            "type": "Birth Name",
        }

    def test_a_stated_nested_list_replaces_so_a_surname_can_be_corrected(self):
        # Reason: a list nested inside a descriptive object is stated, not
        # appended to. Unioning it would make correcting a surname
        # impossible - fixing Smith to Smith-Jones would yield both.
        existing = {"primary_name": {"surname_list": [{"surname": "Smith"}]}}
        changes = {"primary_name": {"surname_list": [{"surname": "Smith-Jones"}]}}
        result = merge_put_data(existing, changes)
        assert result["primary_name"]["surname_list"] == [{"surname": "Smith-Jones"}]

    def test_an_unmentioned_nested_list_is_kept(self):
        # Reason: replacement applies only to a list the caller stated. A
        # nested list they never mentioned must survive like any sub-key.
        existing = {
            "primary_name": {
                "first_name": "Jean",
                "surname_list": [{"surname": "Jacquet"}],
                "citation_list": ["c1"],
            }
        }
        changes = {"primary_name": {"first_name": "Pierre"}}
        result = merge_put_data(existing, changes)
        assert result["primary_name"]["surname_list"] == [{"surname": "Jacquet"}]
        assert result["primary_name"]["citation_list"] == ["c1"]

    def test_a_partial_place_name_keeps_lang_and_date(self):
        existing = {"name": {"value": "Lyon", "lang": "fr", "date": {"year": 1800}}}
        changes = {"name": {"value": "Lugdunum"}}
        result = merge_put_data(existing, changes)
        assert result["name"] == {
            "value": "Lugdunum",
            "lang": "fr",
            "date": {"year": 1800},
        }

    def test_a_dict_absent_from_existing_is_taken_as_is(self):
        existing = {"gramps_id": "I0001"}
        changes = {"primary_name": {"first_name": "Jean"}}
        result = merge_put_data(existing, changes)
        assert result["primary_name"] == {"first_name": "Jean"}

    def test_a_dict_replacing_a_scalar_is_taken_as_is(self):
        # Reason: type mismatch between existing and new means the record
        # shape changed; merging two incompatible types would invent data.
        existing = {"name": "Lyon"}
        changes = {"name": {"value": "Lyon", "lang": "fr"}}
        result = merge_put_data(existing, changes)
        assert result["name"] == {"value": "Lyon", "lang": "fr"}

    def test_neither_input_is_mutated_by_a_nested_merge(self):
        existing = {"primary_name": {"first_name": "Jean", "suffix": "Jr"}}
        changes = {"primary_name": {"first_name": "Pierre"}}
        merge_put_data(existing, changes)
        assert existing == {"primary_name": {"first_name": "Jean", "suffix": "Jr"}}
        assert changes == {"primary_name": {"first_name": "Pierre"}}

    def test_a_changed_role_on_the_same_event_is_applied(self):
        # Reason: deduplicating on ref alone silently discarded the change
        # and reported success. Recording someone as a witness on an event
        # where they already appear in another role is routine.
        existing = {"event_ref_list": [{"ref": "ev1", "role": "Primary"}]}
        changes = {"event_ref_list": [{"ref": "ev1", "role": "Witness"}]}
        result = merge_put_data(existing, changes)
        assert result["event_ref_list"] == [
            {"ref": "ev1", "role": "Primary"},
            {"ref": "ev1", "role": "Witness"},
        ]

    def test_an_identical_ref_entry_is_still_deduplicated(self):
        existing = {"event_ref_list": [{"ref": "ev1", "role": "Primary"}]}
        changes = {"event_ref_list": [{"ref": "ev1", "role": "Primary"}]}
        result = merge_put_data(existing, changes)
        assert result["event_ref_list"] == [{"ref": "ev1", "role": "Primary"}]

    def test_the_same_photo_in_two_regions_is_kept_twice(self):
        existing = {"media_list": [{"ref": "m1", "rect": [0, 0, 10, 10]}]}
        changes = {"media_list": [{"ref": "m1", "rect": [50, 50, 60, 60]}]}
        result = merge_put_data(existing, changes)
        assert result["media_list"] == [
            {"ref": "m1", "rect": [0, 0, 10, 10]},
            {"ref": "m1", "rect": [50, 50, 60, 60]},
        ]

    def test_a_bare_ref_addition_still_deduplicates(self):
        existing = {"citation_list": [{"ref": "c1"}]}
        changes = {"citation_list": [{"ref": "c1"}, {"ref": "c2"}]}
        result = merge_put_data(existing, changes)
        assert result["citation_list"] == [{"ref": "c1"}, {"ref": "c2"}]
