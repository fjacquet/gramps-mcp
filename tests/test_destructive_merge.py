"""Tests for the merge_type tool."""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.handlers.destructive_handler import format_merge_preview
from src.gramps_mcp.tools.destructive import merge_type_tool


class TestMergePreviewFormatting:
    def test_preview_names_which_record_survives(self):
        text = format_merge_preview(
            {"handle": "a", "gramps_id": "S0001", "title": "Keep me"},
            {"handle": "b", "gramps_id": "S0002", "title": "Absorb me"},
            "source",
        )
        assert "S0001" in text
        assert "S0002" in text
        assert "survives" in text.lower()
        assert "confirm=true" in text


class TestMergeOffline:
    async def test_without_confirm_it_previews_and_does_not_merge(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = [
                {"handle": "a", "gramps_id": "S0001", "title": "Keep"},
                {"handle": "b", "gramps_id": "S0002", "title": "Absorb"},
            ]
            result = await merge_type_tool(
                {
                    "type": "source",
                    "phoenix_handle": "a",
                    "titanic_handle": "b",
                }
            )

        assert "confirm=true" in result[0].text
        assert call.await_count == 2

    async def test_rejects_merging_a_record_with_itself(self):
        result = await merge_type_tool(
            {"type": "source", "phoenix_handle": "a", "titanic_handle": "a"}
        )
        assert "Error" in result[0].text

    async def test_rejects_tag_via_pydantic_validation(self):
        """
        MergeableType already excludes "tag", so this never actually
        exercises the `endpoints.merge is None` guard in merge_type_tool -
        pydantic rejects the type literal before the function body runs.
        Kept to prove the tool still refuses tag merges end to end, even
        though the guard it looks like it's testing is dead code.
        """
        result = await merge_type_tool(
            {"type": "tag", "phoenix_handle": "a", "titanic_handle": "b"}
        )
        assert "Error" in result[0].text

    async def test_rejects_when_both_gramps_ids_resolve_to_the_same_handle(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = [
                [{"handle": "same"}],
                [{"handle": "same"}],
            ]
            result = await merge_type_tool(
                {
                    "type": "source",
                    "phoenix_gramps_id": "S0001",
                    "titanic_gramps_id": "S0002",
                }
            )

        assert "Error" in result[0].text
        # Reason: only the two gramps_id resolutions ran - the self-merge
        # check fires before either record is fetched with a GET.
        assert call.await_count == 2


@pytest.mark.integration
class TestMergeLive:
    async def test_merges_two_sources_it_created(self, gramps_client, tree_id):
        from src.gramps_mcp.client import GrampsAPIError
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.source_params import SourceSaveParams
        from tests.conftest import create_entity, delete_entity
        from tests.constants import PREFIX

        keep = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_SOURCES,
            SourceSaveParams(title=f"{PREFIX} phoenix source"),
            "source",
        )
        absorb = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_SOURCES,
            SourceSaveParams(title=f"{PREFIX} titanic source"),
            "source",
        )
        try:
            preview = await merge_type_tool(
                {"type": "source", "phoenix_handle": keep, "titanic_handle": absorb}
            )
            assert "confirm=true" in preview[0].text

            done = await merge_type_tool(
                {
                    "type": "source",
                    "phoenix_handle": keep,
                    "titanic_handle": absorb,
                    "confirm": True,
                }
            )
            assert "Merged" in done[0].text

            with pytest.raises(GrampsAPIError):
                await gramps_client.make_api_call(
                    api_call=ApiCalls.GET_SOURCE, tree_id=tree_id, handle=absorb
                )
        finally:
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_SOURCE, keep)

    async def test_merges_two_people_sending_no_merge_body(
        self, gramps_client, tree_id
    ):
        """
        Confirms MERGE_PERSON now having a registered param model
        (PersonMergeBody) doesn't break the common case of a person merge
        that supplies no body at all.
        """
        from src.gramps_mcp.client import GrampsAPIError
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.people_params import PersonData
        from tests.conftest import create_entity, delete_entity
        from tests.constants import PREFIX

        keep = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_PEOPLE,
            PersonData(
                primary_name={
                    "first_name": PREFIX,
                    "surname_list": [{"surname": "PhoenixPerson"}],
                },
                gender=1,
            ),
            "person",
        )
        absorb = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_PEOPLE,
            PersonData(
                primary_name={
                    "first_name": PREFIX,
                    "surname_list": [{"surname": "TitanicPerson"}],
                },
                gender=1,
            ),
            "person",
        )
        try:
            done = await merge_type_tool(
                {
                    "type": "person",
                    "phoenix_handle": keep,
                    "titanic_handle": absorb,
                    "confirm": True,
                }
            )
            assert "Merged" in done[0].text

            with pytest.raises(GrampsAPIError):
                await gramps_client.make_api_call(
                    api_call=ApiCalls.GET_PERSON, tree_id=tree_id, handle=absorb
                )
        finally:
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_PERSON, keep)

    async def test_merges_two_families_and_keeps_the_chosen_father(
        self, gramps_client, tree_id
    ):
        """
        Proves phoenix_father_handle actually reaches the server: creates
        two families with different fathers, merges them overriding which
        father survives, and reads the merged family back to confirm.
        """
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.family_params import FamilySaveParams
        from src.gramps_mcp.models.parameters.people_params import PersonData
        from tests.conftest import create_entity, delete_entity
        from tests.constants import PREFIX

        father_a = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_PEOPLE,
            PersonData(
                primary_name={
                    "first_name": PREFIX,
                    "surname_list": [{"surname": "FatherA"}],
                },
                gender=1,
            ),
            "person",
        )
        father_b = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_PEOPLE,
            PersonData(
                primary_name={
                    "first_name": PREFIX,
                    "surname_list": [{"surname": "FatherB"}],
                },
                gender=1,
            ),
            "person",
        )
        keep = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_FAMILIES,
            FamilySaveParams(father_handle=father_a),
            "family",
        )
        absorb = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_FAMILIES,
            FamilySaveParams(father_handle=father_b),
            "family",
        )
        try:
            done = await merge_type_tool(
                {
                    "type": "family",
                    "phoenix_handle": keep,
                    "titanic_handle": absorb,
                    "confirm": True,
                    "phoenix_father_handle": father_b,
                }
            )
            assert "Merged" in done[0].text

            merged = await gramps_client.make_api_call(
                api_call=ApiCalls.GET_FAMILY, tree_id=tree_id, handle=keep
            )
            assert merged.get("father_handle") == father_b
        finally:
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_FAMILY, keep)
            await delete_entity(
                gramps_client, tree_id, ApiCalls.DELETE_PERSON, father_a
            )
            await delete_entity(
                gramps_client, tree_id, ApiCalls.DELETE_PERSON, father_b
            )
