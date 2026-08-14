"""
Entity attribute coverage for the Gramps MCP creation tools.

These tests come from `test_all_entity_attributes_comprehensive` in the old
`tests/test_complete_workflow.py`, which ran every entity type as one 665-line
test. Each block of that test is now its own test, so a failure names the
entity that broke instead of only saying "comprehensive".

Where a block used a record an earlier block had created, the test now takes
the matching shared fixture from `conftest.py` as a parameter. No block
depends on another having run first.

Attribute sets exercised here, as described in gramps-usage-guide.md:
- Note (text, type)
- Media (description)
- Repository (name, type, URL, note)
- Source (title, author, publication info, repository, media, note)

The usage guide also lists an abbreviation for a source, but `SourceSaveParams`
declares no field for it, so no test here can exercise it.

Date structures (regular, about, before, after with quality indicators) were
also listed here, but no creation tool takes the shape that block used, and
the modifier/quality values themselves are covered by `tests/test_date_params.py`
and `tests/test_date_handler.py`. See the note on `test_date_structure_attributes`
in the git history of this file.
"""

import re

import pytest

from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools.data_management import (
    create_repository_tool,
    create_source_tool,
)
from tests.constants import PREFIX

pytestmark = pytest.mark.integration


class TestEntityAttributes:
    """Each entity type must accept its complete attribute set."""

    @pytest.mark.asyncio
    async def test_note_attributes(self, gramps_client, tree_id, note_handle):
        """A note is created from its text and type."""
        note_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_NOTE, tree_id=tree_id, handle=note_handle
        )

        assert note_data["handle"] == note_handle, note_data
        assert PREFIX in note_data["text"]["string"], note_data
        assert note_data["type"] == "Transcript", note_data

    @pytest.mark.asyncio
    async def test_media_attributes(self, gramps_client, tree_id, media_handle):
        """A media object is created and carries its description."""
        media_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_MEDIA_ITEM, tree_id=tree_id, handle=media_handle
        )

        assert media_data["handle"] == media_handle, media_data
        assert PREFIX in media_data["desc"], media_data

    @pytest.mark.asyncio
    async def test_repository_attributes(self, note_handle):
        """A repository is created with name, type, URL and note."""
        repository_result = await create_repository_tool(
            {
                "name": "Test Repository for Comprehensive Testing",
                "type": "Archive",
                "urls": [
                    {
                        "type": "Web Home",
                        "path": "https://test-archive.org",
                        "desc": "Test archive website",
                    }
                ],
                "note_list": [note_handle],
            }
        )

        assert isinstance(repository_result, list) and len(repository_result) == 1
        repo_text = repository_result[0].text
        assert "Error:" not in repo_text, repo_text
        # Reason: the parameter models ignore unknown keys, so a handle alone
        # would still be returned if every attribute had been dropped. Each
        # attribute has to be visible in the output to prove it was accepted.
        assert "Test Repository for Comprehensive Testing" in repo_text, repo_text
        assert "Archive" in repo_text, repo_text
        assert "https://test-archive.org" in repo_text, repo_text
        assert "Attached notes:" in repo_text, repo_text
        repo_match = re.search(r"\[([a-f0-9]+)\]", repo_text)
        assert repo_match, f"No repository handle found in: {repo_text}"
        print(f"Repository created with all attributes: {repo_match.group(1)}")

    @pytest.mark.asyncio
    async def test_source_attributes(
        self, repository_handle, media_handle, note_handle
    ):
        """A source is created with title, author, publication info, repository,
        media and note.

        Abbreviation is listed by the usage guide but `SourceSaveParams` declares
        no field for it, so it cannot be exercised here.
        """
        source_result = await create_source_tool(
            {
                "title": "Test Source Document with All Attributes",
                "reporef_list": [{"ref": repository_handle}],
                "author": "Test Author Name",
                "pubinfo": "Published by Test Publisher, 2024 Edition",
                "media_list": [{"ref": media_handle}],
                "note_list": [note_handle],
            }
        )

        assert isinstance(source_result, list) and len(source_result) == 1
        source_text = source_result[0].text
        assert "Error:" not in source_text, source_text
        # Reason: the parameter models ignore unknown keys, so a handle alone
        # would still be returned if every attribute had been dropped. Each
        # attribute has to be visible in the output to prove it was accepted.
        assert "Test Source Document with All Attributes" in source_text, source_text
        assert "Test Author Name" in source_text, source_text
        assert "Published by Test Publisher, 2024 Edition" in source_text, source_text
        assert f"{PREFIX} repository" in source_text, source_text
        assert "Attached media:" in source_text, source_text
        assert "Attached notes:" in source_text, source_text
        source_match = re.search(r"\[([a-f0-9]+)\]", source_text)
        assert source_match, f"No source handle found in: {source_text}"
        print(f"Source created with all attributes: {source_match.group(1)}")
