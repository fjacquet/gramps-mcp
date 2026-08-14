"""
Integration tests for the sourcing-chain data management tools using real
Gramps Web API.

Covers create_repository_tool, create_source_tool, and create_citation_tool.
The composite create_sourced_event_tool has its own tests in
`tests/test_create_sourced_event.py`, split out to keep this module under
the project's 500-line limit. These tests require a working Gramps Web API
instance with valid credentials. Only tests actual API integration -
Pydantic validation is tested elsewhere.
"""

import pytest

from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools.data_management import (
    create_citation_tool,
    create_repository_tool,
    create_source_tool,
)
from tests.constants import PREFIX
from tests.workflow_helpers import _handle_on_line

pytestmark = pytest.mark.integration


class TestCreateRepositoryTool:
    """Test create_repository_tool functionality - Third in workflow."""

    @pytest.mark.asyncio
    async def test_create_repository_success(self, note_handle):
        """Test successful repository creation with a note attached."""
        result = await create_repository_tool(
            {
                "name": "National Archives - Boston Branch",
                "type": "Archive",
                "urls": [
                    {
                        "type": "Web Home",
                        "path": "https://www.archives.gov/boston",
                        "desc": "Official website",
                    }
                ],
                "note_list": [note_handle],
            }
        )

        print("\n--- SAVE REPOSITORY CREATE SUCCESS RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        # Assert all required fields from usage guide are in output
        assert "National Archives - Boston Branch" in text, (
            f"Expected repository name (required) in output but got: {text}"
        )
        assert "Archive" in text, (
            f"Expected repository type (required) in output but got: {text}"
        )

        # Assert optional fields that were provided
        assert "https://www.archives.gov/boston" in text, (
            f"Expected URL path in output but got: {text}"
        )
        assert "Official website" in text, (
            f"Expected URL description in output but got: {text}"
        )
        # Check that attached notes shows some note reference
        assert "Attached notes: N" in text, (
            f"Expected note reference after 'Attached notes:' in output but got: {text}"
        )


class TestCreateSourceTool:
    """Test create_source_tool functionality - Fourth in workflow."""

    @pytest.mark.asyncio
    async def test_create_source_success(
        self, repository_handle, media_handle, note_handle
    ):
        """Test successful source creation using repository and media handles."""
        result = await create_source_tool(
            {
                "title": "Birth Register 1850-1860",
                "reporef_list": [{"ref": repository_handle}],
                "author": "City Clerk's Office",
                "pubinfo": "Boston City Records, Volume 12",
                "media_list": [{"ref": media_handle}],
                "note_list": [note_handle],
            }
        )

        print("\n--- SAVE SOURCE CREATE SUCCESS RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        # Assert all required fields from usage guide are in output
        assert "Birth Register 1850-1860" in text, (
            f"Expected source title (required) in output but got: {text}"
        )
        assert f"{PREFIX} repository" in text, (
            f"Expected repository reference (required) in output but got: {text}"
        )

        # Assert optional fields that were provided
        assert "City Clerk's Office" in text, (
            f"Expected author in output but got: {text}"
        )
        assert "Boston City Records, Volume 12" in text, (
            f"Expected publication info in output but got: {text}"
        )
        # Should show the linked media and note that were passed in
        assert "Attached media: O" in text, (
            f"Expected linked media reference in output but got: {text}"
        )
        assert "Attached notes: N" in text, (
            f"Expected linked note reference in output but got: {text}"
        )

    @pytest.mark.asyncio
    async def test_create_source_with_media_path(
        self, gramps_client, tree_id, repository_handle
    ):
        """media_path uploads a local file inline on create_source too."""
        result = await create_source_tool(
            {
                "title": "Inline Media Source Test",
                "reporef_list": [{"ref": repository_handle}],
                "media_path": "tests/sample/33SQ-GP8N-NLK.jpg",
            }
        )

        print("\n--- CREATE SOURCE WITH MEDIA_PATH RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()
        assert "media_path" not in text, (
            f"media_path must not leak into the response but got: {text}"
        )
        # The formatters emit "Attached media: <gramps_id>", never a MIME
        # type - format_media is the only place a MIME type appears. Assert
        # the exact gramps_id so a raw handle cannot satisfy this by chance.
        source_handle = _handle_on_line(text, "Inline Media Source Test")
        source_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_SOURCE, tree_id=tree_id, handle=source_handle
        )
        media_refs = source_data.get("media_list") or []
        assert media_refs, f"No media attached to the source: {text}"
        media_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_MEDIA_ITEM,
            tree_id=tree_id,
            handle=media_refs[-1]["ref"],
        )
        assert f"Attached media: {media_data['gramps_id']}" in text, (
            f"Expected the uploaded media's gramps_id in: {text}"
        )

    @pytest.mark.asyncio
    async def test_create_source_with_abbrev(
        self, gramps_client, tree_id, repository_handle
    ):
        """abbrev survives a round trip through POST /sources.

        The shipped usage guide (gramps-usage-guide.md:186) offers abbrev on
        source creation. This test decides whether the guide is true: if the
        value comes back, the field belongs on SourceSaveParams; if it does
        not, the guide is wrong and the mention has to go.
        """
        result = await create_source_tool(
            {
                "title": f"{PREFIX} Abbrev Round Trip",
                "reporef_list": [{"ref": repository_handle}],
                "abbrev": "ARR",
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"

        source_handle = _handle_on_line(text, "Abbrev Round Trip")
        source_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_SOURCE,
            tree_id=tree_id,
            handle=source_handle,
        )
        assert source_data.get("abbrev") == "ARR", (
            f"POST /sources did not store abbrev; got {source_data.get('abbrev')!r}"
        )


class TestCreateCitationTool:
    """Test create_citation_tool functionality - Fifth in workflow."""

    @pytest.mark.asyncio
    async def test_create_citation_success(
        self, source_handle, media_handle, note_handle
    ):
        """Test successful citation creation using source handle."""
        result = await create_citation_tool(
            {
                "source_handle": source_handle,
                "page": "Page 45, Entry 23",
                "date": {
                    "dateval": [15, 1, 2024, False],
                    "quality": 1,  # estimated
                    "modifier": 3,  # about
                },
                "media_list": [{"ref": media_handle}],
                "note_list": [note_handle],
            }
        )

        print("\n--- SAVE CITATION CREATE SUCCESS RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        # Assert all required fields from usage guide are in output
        assert f"{PREFIX} source" in text, (
            f"Expected source reference (required) in output but got: {text}"
        )

        # Assert optional fields that were provided
        assert "Page 45, Entry 23" in text, (
            f"Expected citation page in output but got: {text}"
        )
        # Assert date shows full date with modifier and quality
        # Date format: [2024, 1, 15, False] with quality=1 (estimated) and modifier=3 (about)
        assert "about 15 January 2024 (estimated)" in text, (
            f"Expected full citation date with modifier and quality in output but got: {text}"
        )
        # Should show the linked media and note that were passed in
        assert "Attached media: O" in text, (
            f"Expected linked media reference in output but got: {text}"
        )
        assert "Attached notes: N" in text, (
            f"Expected linked note reference in output but got: {text}"
        )

    @pytest.mark.asyncio
    async def test_create_citation_with_media_path(
        self, gramps_client, tree_id, source_handle, media_handle
    ):
        """media_path uploads a local file inline, without a prior
        create_media call, and is additive with an existing media_list."""
        result = await create_citation_tool(
            {
                "source_handle": source_handle,
                "page": "Page 12, inline media test",
                "media_list": [{"ref": media_handle}],
                "media_path": "tests/sample/33SQ-GP8N-NLK.jpg",
            }
        )

        print("\n--- CREATE CITATION WITH MEDIA_PATH RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        # media_path itself must never leak into the API body/response
        assert "media_path" not in text, (
            f"media_path must not leak into the response but got: {text}"
        )

        # Both the pre-existing and the inline-uploaded media should be
        # attached. format_citation emits "Attached media: <gramps_id>" per
        # ref, never a MIME type, so assert each media's gramps_id directly.
        citation_handle = _handle_on_line(text, "Page 12, inline media test")
        citation_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_CITATION, tree_id=tree_id, handle=citation_handle
        )
        media_refs = citation_data.get("media_list") or []
        assert len(media_refs) == 2, (
            "Expected both the pre-existing and the inline-uploaded media "
            f"but citation media_list was: {media_refs}"
        )
        for media_ref in media_refs:
            media_data = await gramps_client.make_api_call(
                api_call=ApiCalls.GET_MEDIA_ITEM,
                tree_id=tree_id,
                handle=media_ref["ref"],
            )
            assert media_data["gramps_id"] in text, (
                f"Media {media_data['gramps_id']} missing from output: {text}"
            )
