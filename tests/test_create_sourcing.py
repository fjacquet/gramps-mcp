"""
Integration tests for the sourcing-chain data management tools using real
Gramps Web API.

Covers create_repository_tool, create_source_tool, create_citation_tool, and
the composite create_sourced_event_tool. These tests require a working
Gramps Web API instance with valid credentials. Only tests actual API
integration - Pydantic validation is tested elsewhere.
"""

import re
import uuid

import pytest

from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools.data_management import (
    create_citation_tool,
    create_repository_tool,
    create_source_tool,
)
from src.gramps_mcp.tools.sourced_event import create_sourced_event_tool
from tests.constants import PREFIX

pytestmark = pytest.mark.integration


def _handle_on_line(text: str, marker: str) -> str:
    """Find the [handle] on the line containing marker - avoids picking up
    an unrelated handle (e.g. a repository or media ref) from elsewhere in
    a concatenated multi-entity response."""
    for line in text.splitlines():
        if marker in line:
            match = re.search(r"\[([a-f0-9]+)\]", line)
            if match:
                return match.group(1)
    raise AssertionError(f"No handle found on a line containing {marker!r} in: {text}")


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
    async def test_create_source_with_media_path(self, repository_handle):
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
        assert "image/jpeg" in text, (
            f"Expected inline-uploaded media to be attached but got: {text}"
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
    async def test_create_citation_with_media_path(self, source_handle, media_handle):
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

        # The newly-uploaded media should be attached
        assert "image/jpeg" in text, (
            f"Expected inline-uploaded media to be attached but got: {text}"
        )

        # The existing media_list ref was also provided, so both should show -
        # count attached media references via the format_citation output
        assert text.count("image/") >= 2, (
            "Expected both the pre-existing and the inline-uploaded media "
            f"to be attached but got: {text}"
        )


class TestCreateSourcedEventTool:
    """Test create_sourced_event_tool - composite source+citation+event."""

    @pytest.mark.asyncio
    async def test_create_sourced_event_success(self, gramps_client, tree_id):
        """Source, citation, and event are created in one call, with the
        citation auto-wired onto the event - the exact chain that used to
        require three separate calls and a copy-pasted handle."""
        # Reason: a fixed title collides with itself on a second run now that
        # create_sourced_event refuses a duplicate title instead of creating
        # another copy - the tree already carries dozens of same-titled
        # sources from historical runs before that refusal existed. A
        # per-run suffix keeps this test creating a source it can find,
        # regardless of what earlier runs left behind.
        title = f"Sourced Event Composite Test Register {uuid.uuid4().hex[:8]}"
        result = await create_sourced_event_tool(
            {
                "source_title": title,
                "citation_page": "Page 7, composite test entry",
                "event_type": "Birth",
                "event_date": {
                    "dateval": [3, 4, 1890, False],
                    "quality": 0,
                    "modifier": 0,
                },
            }
        )

        print("\n--- CREATE SOURCED EVENT SUCCESS RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert title in text, f"Expected source title in output but got: {text}"
        assert "Page 7, composite test entry" in text, (
            f"Expected citation page in output but got: {text}"
        )
        assert "Birth" in text, f"Expected event type in output but got: {text}"

        citation_handle = _handle_on_line(text, "Page 7, composite test entry")
        event_handle = _handle_on_line(text, "Birth")

        # The whole point of this tool: verify the event actually got the
        # citation attached, not just that the response text claims success.
        # Reason: the shared gramps_client fixture is used rather than a
        # throwaway client - GrampsWebAPIClient.close() tears down the
        # AuthManager singleton's httpx client, which every other test shares.
        event_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_EVENT,
            tree_id=tree_id,
            handle=event_handle,
        )

        assert citation_handle in event_data.get("citation_list", []), (
            f"Expected citation {citation_handle} attached to event "
            f"{event_handle} but citation_list was: "
            f"{event_data.get('citation_list')}"
        )

    @pytest.mark.asyncio
    async def test_create_sourced_event_with_media_path(self, gramps_client, tree_id):
        """media_path on the composite tool attaches to the citation, not
        the event or source."""
        # Reason: same rerun-collision hazard as the composite-success test
        # above - a fixed title now collides with historical duplicates
        # once create_sourced_event refuses a repeat title.
        title = f"Sourced Event Media Test Register {uuid.uuid4().hex[:8]}"
        result = await create_sourced_event_tool(
            {
                "source_title": title,
                "citation_page": "Page 9, media test entry",
                "event_type": "Death",
                "media_path": "tests/sample/33SQ-GP8N-NLK.jpg",
            }
        )

        print("\n--- CREATE SOURCED EVENT WITH MEDIA_PATH RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "media_path" not in text, (
            f"media_path must not leak into the response but got: {text}"
        )
        assert "image/jpeg" in text, (
            f"Expected inline-uploaded media to be attached but got: {text}"
        )

        citation_handle = _handle_on_line(text, "Page 9, media test entry")

        citation_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_CITATION,
            tree_id=tree_id,
            handle=citation_handle,
        )

        assert citation_data.get("media_list"), (
            f"Expected media attached to citation {citation_handle} but "
            f"media_list was: {citation_data.get('media_list')}"
        )

    @pytest.mark.asyncio
    async def test_reuses_an_existing_source_by_handle(self, gramps_client, tree_id):
        """A second fact from the same document shares one source."""
        # Reason: a fixed title would collide with itself on a second run of
        # this suite against the same tree, once create_sourced_event
        # refuses a duplicate title - failing on the refusal below before
        # this test's real assertions run at all. The uuid suffix keeps the
        # test's own fixture data from colliding across runs; PREFIX keeps
        # leftovers findable for manual cleanup. Do not "simplify" this back
        # to a fixed string.
        title = f"{PREFIX} Reuse Register {uuid.uuid4().hex[:8]}"
        first = await create_sourced_event_tool(
            {
                "source_title": title,
                "citation_page": "Page 1, birth",
                "event_type": "Birth",
            }
        )
        first_text = first[0].text
        assert "Error:" not in first_text, first_text
        source_handle = _handle_on_line(first_text, "Reuse Register")

        second = await create_sourced_event_tool(
            {
                "source_handle": source_handle,
                "citation_page": "Page 1, death",
                "event_type": "Death",
            }
        )
        second_text = second[0].text
        assert "Error:" not in second_text, second_text
        assert source_handle in second_text, (
            f"Second call did not attach to the existing source: {second_text}"
        )

        citation_handle = _handle_on_line(second_text, "Page 1, death")
        citation_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_CITATION,
            tree_id=tree_id,
            handle=citation_handle,
        )
        assert citation_data.get("source_handle") == source_handle

    @pytest.mark.asyncio
    async def test_refuses_a_duplicate_source_title(self):
        """Creating a second source with an existing title is refused, not
        guessed: two documents can legitimately share a title."""
        # Reason: the uuid suffix makes this run's title distinct from any
        # earlier run's leftovers, so the collision below is proven to come
        # from the two create_sourced_event_tool calls in this test - not
        # from a stale same-titled source a previous run left behind. Do not
        # revert to a fixed string; that would make this test collide with
        # itself on rerun instead of testing the collision it names.
        title = f"{PREFIX} Collision Register {uuid.uuid4().hex[:8]}"
        first = await create_sourced_event_tool(
            {
                "source_title": title,
                "citation_page": "Page 1",
                "event_type": "Birth",
            }
        )
        assert "Error:" not in first[0].text, first[0].text

        second = await create_sourced_event_tool(
            {
                "source_title": title,
                "citation_page": "Page 2",
                "event_type": "Death",
            }
        )
        second_text = second[0].text
        assert "Error:" in second_text, (
            f"Expected a refusal on the duplicate title but got: {second_text}"
        )
        assert "source_handle" in second_text, (
            f"The refusal must name the way forward: {second_text}"
        )

    @pytest.mark.asyncio
    async def test_refuses_both_source_title_and_source_handle(self):
        """The two are mutually exclusive."""
        # Reason: the mutual-exclusivity validator rejects the call before
        # any API call is made, so this title never reaches the tree - no
        # rerun hazard exists here. The uuid suffix is kept anyway so all
        # five tests in this class follow one convention.
        result = await create_sourced_event_tool(
            {
                "source_title": f"{PREFIX} Both Register {uuid.uuid4().hex[:8]}",
                "source_handle": "103f77fe86ec4c13f3fac1a420ec",
                "event_type": "Birth",
            }
        )
        assert "Error:" in result[0].text

    @pytest.mark.asyncio
    async def test_create_sourced_event_missing_required_fields(self):
        """Omitting source_title/event_type must produce a clean validation
        error, not a crash."""
        result = await create_sourced_event_tool(
            {
                "citation_page": "Page 1",
            }
        )

        text = result[0].text
        assert "Error:" in text, f"Expected a clean validation error but got: {text}"
