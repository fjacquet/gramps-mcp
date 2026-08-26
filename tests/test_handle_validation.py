"""
Handle-shaped fields on destructive tools must reject a non-handle.

A Gramps handle does not have one describable format: a sweep of every
handle in the live tree - all ten record categories, 6496 handles
(2026-08-26) - found real handles that are lowercase hex, a UUID,
gramps_id-shaped (e.g. "C0055"), and one that ends in three literal dots
("103da162..."). What is constant across all of them is narrower - a
handle lands in a URL path segment, so it must not contain a character
that means something there, and must not be a relative-path segment in its
own right. Anything that is, is a crafted value worth refusing, and these
tools delete and merge records.
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
            "...",
            "....",
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

    # Reason: these four are shapes actually found in the live tree by a
    # sweep of every handle in all ten record categories (2026-08-26,
    # 6496 handles): hex, a UUID, a citation whose handle equals its
    # gramps_id, and a corrupt citation handle that ends in three literal
    # dots. The last one was missed by an earlier survey that reached only
    # 3425 handles because it did not cover every category, and the pattern
    # was narrowed on that incomplete evidence until this sweep found the
    # gap. Every one of these is a value the server itself resolves - GET
    # /api/citations/103da162... returns 200 - so refusing it here only
    # removes a repair (DetachReferenceParams.ref_handle is required and
    # has no gramps_id alternative) without removing a risk. Narrow this
    # again only after re-running the full sweep and showing the shape you
    # want to refuse is absent from every category.
    @pytest.mark.parametrize(
        "real_handle",
        [
            "103bcbfa97824cbb051f1c7a28b",
            "d747a30b-33a1-418b-a572-35d65b20ed62",
            "C0055",
            "103da162...",
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

    # Reason: this pins the exact boundary the dot rule draws. A dot is
    # only a path-traversal hazard when it is the whole segment, so the
    # refusal must be a dot-only membership test - not a character-class
    # exclusion, which would also have to refuse the live tree's
    # "103da162...". Both halves are asserted together so a future change
    # cannot satisfy one by breaking the other.
    @pytest.mark.parametrize("dots", [".", "..", "...", "..........."])
    def test_dot_only_values_are_refused_but_mixed_dots_are_not(self, dots):
        with pytest.raises(ValidationError):
            DeleteTypeParams(type="person", handle=dots)

        mixed = f"103da162{dots}"
        assert DeleteTypeParams(type="person", handle=mixed).handle == mixed

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
