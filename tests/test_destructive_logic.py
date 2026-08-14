"""Unit tests for the pure destructive-operation logic."""

import pytest

from src.gramps_mcp.destructive import (
    TYPE_ENDPOINTS,
    remove_from_list,
    should_refuse_delete,
)
from src.gramps_mcp.models.api_calls import ApiCalls


class TestShouldRefuseDelete:
    def test_no_backlinks_allows_delete(self):
        assert should_refuse_delete({}) is None

    def test_empty_backlink_lists_allow_delete(self):
        assert should_refuse_delete({"person": [], "family": []}) is None

    def test_backlinks_produce_a_refusal_naming_types_and_counts(self):
        refusal = should_refuse_delete({"person": ["h1", "h2"], "family": ["h3"]})
        assert refusal is not None
        assert "2 person" in refusal
        assert "1 family" in refusal
        assert "force=true" in refusal

    def test_refusal_lists_the_referencing_handles(self):
        refusal = should_refuse_delete({"citation": ["abc123"]})
        assert "abc123" in refusal


class TestRemoveFromList:
    def test_removes_a_plain_string_handle(self):
        obj = {"note_list": ["a", "b", "c"]}
        assert remove_from_list(obj, "note_list", "b") == {"note_list": ["a", "c"]}

    def test_removes_a_ref_dict_by_ref_key(self):
        obj = {"event_ref_list": [{"ref": "a", "role": "Primary"}, {"ref": "b"}]}
        result = remove_from_list(obj, "event_ref_list", "a")
        assert result["event_ref_list"] == [{"ref": "b"}]

    def test_does_not_mutate_the_input(self):
        obj = {"note_list": ["a", "b"]}
        remove_from_list(obj, "note_list", "a")
        assert obj == {"note_list": ["a", "b"]}

    def test_leaves_other_keys_untouched(self):
        obj = {"note_list": ["a"], "gramps_id": "I0001", "media_list": [{"ref": "m"}]}
        result = remove_from_list(obj, "note_list", "a")
        assert result["gramps_id"] == "I0001"
        assert result["media_list"] == [{"ref": "m"}]

    def test_absent_handle_raises(self):
        with pytest.raises(ValueError, match="not present"):
            remove_from_list({"note_list": ["a"]}, "note_list", "zzz")

    def test_absent_list_raises(self):
        with pytest.raises(ValueError, match="no list"):
            remove_from_list({"note_list": ["a"]}, "nope_list", "a")


class TestTypeEndpoints:
    def test_covers_the_nine_record_types_plus_tag(self):
        assert set(TYPE_ENDPOINTS) == {
            "person",
            "family",
            "event",
            "place",
            "source",
            "citation",
            "repository",
            "media",
            "note",
            "tag",
        }

    def test_tag_is_deletable_but_not_mergeable(self):
        assert TYPE_ENDPOINTS["tag"].delete is not None
        assert TYPE_ENDPOINTS["tag"].merge is None

    def test_every_non_tag_type_is_mergeable(self):
        for name, endpoints in TYPE_ENDPOINTS.items():
            if name != "tag":
                assert endpoints.merge is not None, name

    def test_every_type_has_get_put_and_delete(self):
        for name, endpoints in TYPE_ENDPOINTS.items():
            assert endpoints.get is not None, name
            assert endpoints.put is not None, name
            assert endpoints.delete is not None, name


class TestMergeAndUndoEndpoints:
    def test_merge_person_endpoint_shape(self):
        assert ApiCalls.MERGE_PERSON.method == "POST"
        assert (
            ApiCalls.MERGE_PERSON.endpoint
            == "people/{phoenix_handle}/merge/{titanic_handle}"
        )

    def test_every_merge_call_is_a_post_with_both_handles(self):
        merges = [c for c in ApiCalls if c.name.startswith("MERGE_")]
        assert len(merges) == 9
        for call in merges:
            assert call.method == "POST", call.name
            assert "{phoenix_handle}" in call.endpoint, call.name
            assert "{titanic_handle}" in call.endpoint, call.name

    def test_undo_endpoint_shape(self):
        assert ApiCalls.POST_TRANSACTION_UNDO.method == "POST"
        assert (
            ApiCalls.POST_TRANSACTION_UNDO.endpoint
            == "transactions/history/{transaction_id}/undo"
        )
