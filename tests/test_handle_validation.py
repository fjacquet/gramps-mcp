"""
Handle-shaped fields on destructive tools must reject a non-handle.

A Gramps handle is lowercase hex, at least 16 characters. Anything else
reaching these fields is either a mistake worth naming or a crafted value
worth refusing, and these tools delete and merge records.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.destructive_params import (
    DeleteTypeParams,
    DetachReferenceParams,
    MergeTypeParams,
)


class TestDestructiveHandleValidation:
    @pytest.mark.parametrize(
        "crafted", ["../users/someuser", ".", "..", "abc?keys=x", "I0001", "short"]
    )
    def test_delete_type_refuses_a_non_handle(self, crafted):
        with pytest.raises(ValidationError):
            DeleteTypeParams(type="person", handle=crafted)

    def test_delete_type_accepts_a_real_handle(self):
        params = DeleteTypeParams(type="person", handle="103bcbfa97824cbb051f1c7a28b")
        assert params.handle == "103bcbfa97824cbb051f1c7a28b"

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
