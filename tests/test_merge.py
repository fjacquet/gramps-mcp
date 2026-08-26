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

    def test_dict_items_without_ref_deduplicate_on_whole_content(self):
        existing = {"tag_list": [{"name": "x"}]}
        changes = {"tag_list": [{"name": "x"}]}
        merged = merge_put_data(existing, changes)
        assert merged["tag_list"] == [{"name": "x"}]

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


class TestReplaceLists:
    """A named list is replaced outright instead of merged."""

    def test_named_list_is_replaced(self):
        existing = {"placeref_list": [{"ref": "AAA"}]}
        changes = {"placeref_list": [{"ref": "BBB"}]}

        merged = merge_put_data(existing, changes, replace_lists=["placeref_list"])

        assert merged["placeref_list"] == [{"ref": "BBB"}]

    def test_unnamed_list_still_merges(self):
        existing = {"media_list": [{"ref": "AAA"}]}
        changes = {"media_list": [{"ref": "BBB"}]}

        merged = merge_put_data(existing, changes, replace_lists=["placeref_list"])

        assert merged["media_list"] == [{"ref": "AAA"}, {"ref": "BBB"}]

    def test_default_is_still_union(self):
        existing = {"placeref_list": [{"ref": "AAA"}]}
        changes = {"placeref_list": [{"ref": "BBB"}]}

        merged = merge_put_data(existing, changes)

        assert merged["placeref_list"] == [{"ref": "AAA"}, {"ref": "BBB"}]

    def test_replacing_with_an_empty_list_clears_it(self):
        existing = {"placeref_list": [{"ref": "AAA"}]}
        changes = {"placeref_list": []}

        merged = merge_put_data(existing, changes, replace_lists=["placeref_list"])

        assert merged["placeref_list"] == []

    def test_inputs_are_not_mutated(self):
        existing = {"placeref_list": [{"ref": "AAA"}]}
        changes = {"placeref_list": [{"ref": "BBB"}]}

        merge_put_data(existing, changes, replace_lists=["placeref_list"])

        assert existing == {"placeref_list": [{"ref": "AAA"}]}
        assert changes == {"placeref_list": [{"ref": "BBB"}]}


class TestAttributeDeduplication:
    """Dicts without a ref deduplicate on their whole content."""

    def test_identical_attribute_is_not_duplicated(self):
        attribute = {"type": "Occupation", "value": "Cordonnier"}
        existing = {"attribute_list": [attribute]}
        changes = {"attribute_list": [dict(attribute)]}

        merged = merge_put_data(existing, changes)

        assert merged["attribute_list"] == [attribute]

    def test_different_attribute_is_appended(self):
        existing = {"attribute_list": [{"type": "Occupation", "value": "Cordonnier"}]}
        changes = {"attribute_list": [{"type": "Occupation", "value": "Meunier"}]}

        merged = merge_put_data(existing, changes)

        assert merged["attribute_list"] == [
            {"type": "Occupation", "value": "Cordonnier"},
            {"type": "Occupation", "value": "Meunier"},
        ]

    def test_a_changed_attribute_updates_the_entry_in_place(self):
        # Reason: identity is ref plus role and rect; every other key is an
        # attribute, and a changed attribute updates the entry rather than
        # adding a duplicate or being discarded.
        existing = {"media_list": [{"ref": "AAA", "private": False}]}
        changes = {"media_list": [{"ref": "AAA", "private": True}]}

        merged = merge_put_data(existing, changes)

        assert merged["media_list"] == [{"ref": "AAA", "private": True}]

    def test_attribute_with_nested_dict_value_deduplicates(self):
        # Reason: if an attribute's value is itself a dict (e.g., structured
        # data), dict equality handles nested comparison without needing
        # serialization, and the `in` check must not crash.
        attribute = {"type": "CustomData", "value": {"a": 1, "b": 2}}
        existing = {"attribute_list": [attribute]}
        changes = {"attribute_list": [dict(attribute)]}

        merged = merge_put_data(existing, changes)

        assert merged["attribute_list"] == [attribute]

    def test_attribute_with_nested_list_value_deduplicates(self):
        # Reason: if an attribute's value is a list (e.g., array of choices),
        # dict equality handles the nested list without crashing, and the
        # same nested value must deduplicate.
        attribute = {"type": "Tags", "value": ["tag1", "tag2"]}
        existing = {"attribute_list": [attribute]}
        changes = {"attribute_list": [dict(attribute)]}

        merged = merge_put_data(existing, changes)

        assert merged["attribute_list"] == [attribute]

    def test_duplicate_within_incoming_list_is_collapsed(self):
        # Reason: comparing only against existing_items missed the case
        # where a single update carries the same attribute twice - both
        # passed the check and both got appended. The duplicated incoming
        # attribute must differ from the existing entry, or the old code
        # would filter both copies out anyway (each equal to the existing
        # entry) and this test would pass without discriminating anything.
        existing_attribute = {"type": "Occupation", "value": "Cordonnier"}
        new_attribute = {"type": "Occupation", "value": "Meunier"}
        existing = {"attribute_list": [existing_attribute]}
        changes = {"attribute_list": [dict(new_attribute), dict(new_attribute)]}

        merged = merge_put_data(existing, changes)

        assert merged["attribute_list"] == [existing_attribute, new_attribute]

    def test_duplicate_within_incoming_list_is_collapsed_with_no_existing(self):
        # Reason: the empty-existing-list path used to short-circuit to
        # plain concatenation before any dedup logic ran.
        attribute = {"type": "Occupation", "value": "Cordonnier"}
        existing = {"attribute_list": []}
        changes = {"attribute_list": [dict(attribute), dict(attribute)]}

        merged = merge_put_data(existing, changes)

        assert merged["attribute_list"] == [attribute]

    def test_an_unmentioned_attribute_survives_an_update(self):
        # Reason: when updating an entry with matching identity, unmentioned
        # attributes must survive so a caller can update one attribute without
        # losing others they never mentioned.
        existing = {
            "media_list": [{"ref": "m1", "private": False, "note_list": ["n1"]}]
        }
        changes = {"media_list": [{"ref": "m1", "private": True}]}

        merged = merge_put_data(existing, changes)

        assert merged["media_list"] == [
            {"ref": "m1", "private": True, "note_list": ["n1"]}
        ]

    def test_order_is_preserved_when_a_middle_entry_is_updated(self):
        # Reason: when updating an entry in a list, it must stay at its
        # existing position; the order of the list must not change.
        existing = {
            "media_list": [
                {"ref": "m1"},
                {"ref": "m2", "private": False},
                {"ref": "m3"},
            ]
        }
        changes = {"media_list": [{"ref": "m2", "private": True}]}

        merged = merge_put_data(existing, changes)

        assert merged["media_list"] == [
            {"ref": "m1"},
            {"ref": "m2", "private": True},
            {"ref": "m3"},
        ]

    def test_live_media_reference_shape_deduplicates(self):
        # Reason: every media reference the live server stores carries
        # "rect": [] - a falsy-but-present list - while the shape this
        # codebase's own tools recommend sending back is bare {"ref": ...}.
        # Both must resolve to the same identity or the same photo gets
        # attached twice on every no-op resend.
        existing = {
            "media_list": [
                {
                    "attribute_list": [],
                    "citation_list": [],
                    "note_list": ["n1"],
                    "private": False,
                    "rect": [],
                    "ref": "m1",
                }
            ]
        }
        changes = {"media_list": [{"ref": "m1"}]}

        merged = merge_put_data(existing, changes)

        assert len(merged["media_list"]) == 1
        assert merged["media_list"][0]["private"] is False
        assert merged["media_list"][0]["note_list"] == ["n1"]

    def test_unhashable_role_does_not_raise(self):
        # Reason: an LLM caller can compose a role as a nested object (e.g.
        # {"_class": "EventRoleType", "string": "Primary"}) rather than a
        # plain string. Identity must fall back to a stable key instead of
        # crashing the whole write on an unhashable dict.
        existing = {
            "event_ref_list": [
                {"ref": "e1", "role": {"_class": "EventRoleType", "string": "Primary"}}
            ]
        }
        changes = {
            "event_ref_list": [
                {"ref": "e1", "role": {"_class": "EventRoleType", "string": "Primary"}}
            ]
        }

        merged = merge_put_data(existing, changes)

        assert len(merged["event_ref_list"]) == 1

    def test_unhashable_rect_does_not_raise(self):
        # Reason: same failure mode as role, but for rect - a list of lists
        # ([[0, 0], [1, 1]]) rather than a flat list.
        existing = {"media_list": [{"ref": "m1", "rect": [[0, 0], [1, 1]]}]}
        changes = {"media_list": [{"ref": "m1", "rect": [[0, 0], [1, 1]]}]}

        merged = merge_put_data(existing, changes)

        assert len(merged["media_list"]) == 1

    def test_nested_dict_inside_a_reference_entry_is_preserved(self):
        # Reason: the in-place entry merge used a shallow dict spread, so a
        # nested object (e.g. "date") inside a placeref_list entry was
        # replaced wholesale instead of merged sub-key by sub-key - the same
        # destructive behaviour this branch exists to kill, one level deeper.
        existing = {
            "placeref_list": [{"ref": "P1", "date": {"year": 1800, "text": "1800"}}]
        }
        changes = {"placeref_list": [{"ref": "P1", "date": {"modifier": 1}}]}

        merged = merge_put_data(existing, changes)

        assert merged["placeref_list"] == [
            {
                "ref": "P1",
                "date": {"year": 1800, "text": "1800", "modifier": 1},
            }
        ]
