"""
Unit tests for the pure PUT merge logic in src/gramps_mcp/merge.py.

These are pure data-transformation tests - no API, no mocks needed.
"""

from src.gramps_mcp.merge import merge_put_data


class TestMergePutData:
    """Behavior pinned from the original inline logic in client.py."""

    def test_ref_object_lists_deduplicate_by_ref(self):
        existing = {"event_ref_list": [{"ref": "birth", "role": "Primary"}]}
        changes = {
            "event_ref_list": [
                {"ref": "birth", "role": "Primary"},
                {"ref": "death", "role": "Primary"},
            ]
        }
        merged = merge_put_data(existing, changes)
        refs = [item["ref"] for item in merged["event_ref_list"]]
        assert refs == ["birth", "death"]

    def test_string_handle_lists_deduplicate_by_value(self):
        existing = {"note_list": ["note1"]}
        changes = {"note_list": ["note1", "note2"]}
        merged = merge_put_data(existing, changes)
        assert merged["note_list"] == ["note1", "note2"]

    def test_existing_items_come_first(self):
        existing = {"note_list": ["a", "b"]}
        changes = {"note_list": ["c"]}
        assert merge_put_data(existing, changes)["note_list"] == ["a", "b", "c"]

    def test_dict_items_without_ref_concatenate_without_dedup(self):
        existing = {"tag_list": [{"name": "x"}]}
        changes = {"tag_list": [{"name": "x"}]}
        merged = merge_put_data(existing, changes)
        assert merged["tag_list"] == [{"name": "x"}, {"name": "x"}]

    def test_empty_existing_list_concatenates(self):
        existing = {"note_list": []}
        changes = {"note_list": ["n1"]}
        assert merge_put_data(existing, changes)["note_list"] == ["n1"]

    def test_empty_new_list_keeps_existing(self):
        existing = {"note_list": ["n1"]}
        changes = {"note_list": []}
        assert merge_put_data(existing, changes)["note_list"] == ["n1"]

    def test_non_list_fields_are_replaced(self):
        existing = {"private": False, "gender": 1}
        changes = {"private": True}
        merged = merge_put_data(existing, changes)
        assert merged["private"] is True
        assert merged["gender"] == 1

    def test_fields_absent_from_changes_are_preserved(self):
        existing = {"handle": "h1", "gramps_id": "I0001", "change": 1234567890}
        changes = {"handle": "h1"}
        merged = merge_put_data(existing, changes)
        assert merged["gramps_id"] == "I0001"
        assert merged["change"] == 1234567890

    def test_list_key_absent_from_existing_is_replaced_not_merged(self):
        existing = {"handle": "h1"}
        changes = {"note_list": ["n1"]}
        assert merge_put_data(existing, changes)["note_list"] == ["n1"]

    def test_inputs_are_not_mutated(self):
        existing = {"note_list": ["n1"], "private": False}
        changes = {"note_list": ["n2"], "private": True}
        merge_put_data(existing, changes)
        assert existing == {"note_list": ["n1"], "private": False}
        assert changes == {"note_list": ["n2"], "private": True}
