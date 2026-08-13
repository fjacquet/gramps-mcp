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
- Media (file path, title, date)
- Repository (name, type, URL, note)
- Source (title, author, publication info, abbreviation, media, note)

Date structures (regular, about, before, after with quality indicators) were
also listed here, but no creation tool takes the shape that block used, and
the modifier/quality values themselves are covered by `tests/test_date_params.py`
and `tests/test_date_handler.py`. See the note on `test_date_structure_attributes`
in the git history of this file.
"""

import re

import pytest

from src.gramps_mcp.tools.data_management import create_source_tool
from tests.workflow_helpers import create_test_media, create_test_note

pytestmark = pytest.mark.integration


class TestEntityAttributes:
    """Each entity type must accept its complete attribute set."""

    @pytest.mark.asyncio
    async def test_note_attributes(self):
        """A note is created from its text and type."""
        note_handle = await create_test_note(
            "This is a comprehensive test note demonstrating the note creation functionality.",
            "General",
        )
        print(f"Note created: {note_handle}")

    @pytest.mark.asyncio
    async def test_media_attributes(self):
        """A media object is created from its file path, title and date."""
        media_handle = await create_test_media(
            "tests/sample/33SQ-GP8N-NLK.jpg",
            "Test Document for Comprehensive Testing",
            {
                "year": 2024,
                "month": 1,
                "day": 15,
                "type": "regular",
                "quality": "regular",
            },
        )
        print(f"Media created: {media_handle}")

    @pytest.mark.asyncio
    async def test_repository_attributes(self, note_handle):
        """A repository is created with name, type, URL and note."""
        repository_result = await create_source_tool(
            {
                "title": "Test Repository for Comprehensive Testing",
                "type": "Archive",
                "url": {
                    "type": "Website",
                    "path": "https://test-archive.org",
                    "description": "Test archive website",
                },
                "note_handle": note_handle,
            }
        )

        assert isinstance(repository_result, list) and len(repository_result) == 1
        repo_text = repository_result[0].text
        repo_match = re.search(r"\[([a-f0-9]+)\]", repo_text)
        assert repo_match, f"No repository handle found in: {repo_text}"
        print(f"Repository created with all attributes: {repo_match.group(1)}")

    @pytest.mark.asyncio
    async def test_source_attributes(
        self, repository_handle, media_handle, note_handle
    ):
        """A source is created with every attribute the usage guide lists."""
        source_result = await create_source_tool(
            {
                "title": "Test Source Document with All Attributes",
                "repository_handle": repository_handle,
                "author": "Test Author Name",
                "publication_info": "Published by Test Publisher, 2024 Edition",
                "abbreviation": "TEST-SRC-2024",
                "media_handle": media_handle,
                "note_handle": note_handle,
            }
        )

        assert isinstance(source_result, list) and len(source_result) == 1
        source_text = source_result[0].text
        source_match = re.search(r"\[([a-f0-9]+)\]", source_text)
        assert source_match, f"No source handle found in: {source_text}"
        print(f"Source created with all attributes: {source_match.group(1)}")
