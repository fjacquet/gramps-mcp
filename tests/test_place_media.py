"""
Integration test for attaching media to a place, against the real Gramps API.
"""

import uuid

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.parameters.place_params import PlaceSaveParams

pytestmark = pytest.mark.integration


class TestPlaceMedia:
    """A place must accept a media reference in the shape the API expects."""

    def test_model_accepts_media_ref_objects(self):
        """PlaceSaveParams.media_list must accept MediaRef-shaped dicts."""
        params = PlaceSaveParams(
            name={"value": "Somewhere"},
            place_type="City",
            media_list=[{"ref": "103c4094f2414e2400974f979824"}],
        )

        assert params.media_list == [{"ref": "103c4094f2414e2400974f979824"}]

    @pytest.mark.asyncio
    async def test_media_can_be_attached_to_a_place(self):
        """A media item created via the API can be attached to a new place."""
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id
        suffix = uuid.uuid4().hex[:8]
        place_handle = None
        media_handle = None

        try:
            # Reason: POST_MEDIA takes no JSON body (file upload only, see
            # api_mapping.py), so media objects are created via the
            # multipart upload endpoint, not make_api_call(POST_MEDIA, ...).
            upload_result = await client.upload_media_file(
                file_content=f"pytest media {suffix}".encode(),
                mime_type="text/plain",
                tree_id=tree_id,
            )
            media_handle = upload_result[0]["new"]["handle"]

            created = await client.make_api_call(
                api_call=ApiCalls.POST_PLACES,
                params={
                    "name": {"value": f"PytestPlace{suffix}"},
                    "place_type": "City",
                    "media_list": [{"ref": media_handle}],
                },
                tree_id=tree_id,
            )
            place_handle = created[0]["new"]["handle"]

            fetched = await client.make_api_call(
                api_call=ApiCalls.GET_PLACE, tree_id=tree_id, handle=place_handle
            )
            refs = [entry.get("ref") for entry in fetched.get("media_list", [])]

            assert media_handle in refs
        finally:
            if place_handle:
                await client.make_api_call(
                    api_call=ApiCalls.DELETE_PLACE, tree_id=tree_id, handle=place_handle
                )
            if media_handle:
                await client.make_api_call(
                    api_call=ApiCalls.DELETE_MEDIA_ITEM,
                    tree_id=tree_id,
                    handle=media_handle,
                )


class TestPlaceCreationWithoutType:
    """Creation without place_type must not error, and its default must be pinned."""

    @pytest.mark.asyncio
    async def test_creating_without_place_type_defaults_to_unknown(self):
        """Omitting place_type on create must succeed with a Gramps default."""
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id
        suffix = uuid.uuid4().hex[:8]
        place_handle = None

        try:
            created = await client.make_api_call(
                api_call=ApiCalls.POST_PLACES,
                params={"name": {"value": f"PytestNoType{suffix}"}},
                tree_id=tree_id,
            )
            place_handle = created[0]["new"]["handle"]

            fetched = await client.make_api_call(
                api_call=ApiCalls.GET_PLACE, tree_id=tree_id, handle=place_handle
            )

            assert fetched.get("place_type") == "Unknown"
        finally:
            if place_handle:
                await client.make_api_call(
                    api_call=ApiCalls.DELETE_PLACE, tree_id=tree_id, handle=place_handle
                )


class TestPartialPlaceUpdate:
    """A partial update must not demand fields it is not changing."""

    def test_place_type_is_optional(self):
        """place_type must be omittable when only updating other fields."""
        params = PlaceSaveParams(
            handle="103c4094f2414e2400974f979824",
            placeref_list=[{"ref": "103c732d2adc19424a3fad17954c"}],
        )

        assert params.place_type is None

    def test_creation_still_carries_a_type(self):
        """place_type must still be settable when creating a new place."""
        params = PlaceSaveParams(name={"value": "Somewhere"}, place_type="City")

        assert params.place_type == "City"
