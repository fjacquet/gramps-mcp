"""
Handle-shaped fields on destructive tools must reject a non-handle.

A Gramps handle does not have one describable format: a 3425-handle check
across the live tree (2026-08-26) found real handles that are lowercase
hex, a UUID, and gramps_id-shaped (e.g. "C0055"). What is constant across
all of them is narrower - a handle lands in a URL path segment, so it must
not contain a character that means something there. Anything that does is
a crafted value worth refusing, and these tools delete and merge records.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.destructive_params import (
    DeleteTypeParams,
    DetachReferenceParams,
    MergeTypeParams,
)
from src.gramps_mcp.models.parameters.event_params import EventSaveParams


class TestDestructiveHandleValidation:
    @pytest.mark.parametrize(
        "crafted",
        [
            "../users/someuser",
            ".",
            "..",
            "abc?keys=x",
            "abc#frag",
            "//evil.example.com/x",
            "a/../../../",
            "",
            "..%2fusers",
            "back\\slash",
        ],
    )
    def test_delete_type_refuses_a_non_handle(self, crafted):
        with pytest.raises(ValidationError):
            DeleteTypeParams(type="person", handle=crafted)

    def test_delete_type_accepts_a_real_handle(self):
        params = DeleteTypeParams(type="person", handle="103bcbfa97824cbb051f1c7a28b")
        assert params.handle == "103bcbfa97824cbb051f1c7a28b"

    # Reason: these three are shapes actually found in the live tree's
    # 3425-handle check (2026-08-26) - hex, a UUID, and a citation whose
    # handle equals its gramps_id. Do not narrow
    # URL_SAFE_IDENTIFIER_PATTERN to reject any of them again.
    @pytest.mark.parametrize(
        "real_handle",
        [
            "103bcbfa97824cbb051f1c7a28b",
            "d747a30b-33a1-418b-a572-35d65b20ed62",
            "C0055",
        ],
    )
    def test_delete_type_accepts_every_real_handle_shape(self, real_handle):
        params = DeleteTypeParams(type="person", handle=real_handle)
        assert params.handle == real_handle

    # Reason: this pins the reason the two rules are separate constants.
    # The destructive tools' handle field only needs to keep URL-breaking
    # characters out (URL_SAFE_IDENTIFIER_PATTERN, in base_params.py), so
    # an ordinary word like "Lyon" is a legitimate (if useless) value there
    # and must be accepted. EventSaveParams.place needs to catch exactly
    # that same ordinary word, because there the job is telling a place
    # NAME apart from a place HANDLE (PLACE_HANDLE_PATTERN, in
    # event_params.py, deliberately narrower - lowercase hex only). If
    # this test ever fails because both accept or both refuse "Lyon", the
    # two rules have been merged back into one and need separating again.
    def test_url_safety_and_place_handle_rules_differ_on_an_ordinary_word(self):
        accepted = DeleteTypeParams(type="person", handle="Lyon")
        assert accepted.handle == "Lyon"

        with pytest.raises(ValidationError):
            EventSaveParams(type="Birth", citation_list=[], place="Lyon")

    def test_delete_type_still_accepts_a_gramps_id_instead(self):
        # Reason: handle and gramps_id are alternatives; tightening one
        # must not make the other unusable.
        params = DeleteTypeParams(type="person", gramps_id="I0001")
        assert params.handle is None

    @pytest.mark.parametrize("crafted", ["../users/someuser", "."])
    def test_detach_reference_refuses_a_non_handle(self, crafted):
        with pytest.raises(ValidationError):
            DetachReferenceParams(
                type="person",
                handle=crafted,
                list_name="media_list",
                ref_handle="103bcbfa97824cbb051f1c7a28b",
            )

    @pytest.mark.parametrize("crafted", ["../users/someuser", "."])
    def test_detach_reference_refuses_a_non_handle_ref(self, crafted):
        with pytest.raises(ValidationError):
            DetachReferenceParams(
                type="person",
                handle="103bcbfa97824cbb051f1c7a28b",
                list_name="media_list",
                ref_handle=crafted,
            )

    @pytest.mark.parametrize("crafted", ["../users/someuser", "."])
    def test_merge_type_refuses_a_non_handle_on_either_side(self, crafted):
        with pytest.raises(ValidationError):
            MergeTypeParams(
                type="person",
                phoenix_handle=crafted,
                titanic_handle="103bcbfa97824cbb051f1c7a28b",
            )
        with pytest.raises(ValidationError):
            MergeTypeParams(
                type="person",
                phoenix_handle="103bcbfa97824cbb051f1c7a28b",
                titanic_handle=crafted,
            )
