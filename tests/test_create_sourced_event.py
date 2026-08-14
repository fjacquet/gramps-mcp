"""
Integration tests for the composite create_sourced_event_tool using real
Gramps Web API.

Split out of `tests/test_create_sourcing.py`, which covers the individual
create_repository_tool, create_source_tool, and create_citation_tool - this
module covers only the composite tool that chains source, citation, and
event creation in one call. These tests require a working Gramps Web API
instance with valid credentials. Only tests actual API integration -
Pydantic validation is tested elsewhere.
"""

import uuid

import pytest

from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools.sourced_event import create_sourced_event_tool
from tests.constants import PREFIX
from tests.workflow_helpers import handle_on_line

pytestmark = pytest.mark.integration


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

        citation_handle = handle_on_line(text, "Page 7, composite test entry")
        event_handle = handle_on_line(text, "Birth")

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

        citation_handle = handle_on_line(text, "Page 9, media test entry")

        citation_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_CITATION,
            tree_id=tree_id,
            handle=citation_handle,
        )

        media_refs = citation_data.get("media_list") or []
        assert media_refs, (
            f"Expected media attached to citation {citation_handle} but "
            f"media_list was: {media_refs}"
        )
        media_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_MEDIA_ITEM,
            tree_id=tree_id,
            handle=media_refs[-1]["ref"],
        )
        # Guards the raw-handle regression: this line used to print
        # media_info["handle"] rather than its gramps_id.
        assert f"Attached media: {media_data['gramps_id']}" in text, (
            f"Expected the uploaded media's gramps_id in: {text}"
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
        source_handle = handle_on_line(first_text, "Reuse Register")

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

        citation_handle = handle_on_line(second_text, "Page 1, death")
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
        text = result[0].text
        assert "Error:" in text
        assert "supply exactly one of source_title or source_handle" in text, (
            f"Expected the mutual-exclusivity validator's own wording, got: {text}"
        )

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
