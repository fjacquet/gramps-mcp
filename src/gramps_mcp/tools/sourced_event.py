# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Composite create_sourced_event tool.

Chains source + citation (optional inline media) + event creation into one
MCP call, auto-wiring the citation onto the event so callers never retype a
handle between steps - the exact copy-paste mistake this tool exists to
prevent.
"""

from typing import Any

from mcp.types import TextContent

from ..client import GrampsAPIError, GrampsWebAPIClient
from ..config import get_settings
from ..handlers.citation_handler import format_citation
from ..handlers.event_handler import format_event
from ..handlers.source_handler import format_source
from ..models.api_calls import ApiCalls
from ..models.parameters.citation_params import CitationData
from ..models.parameters.event_params import EventSaveParams
from ..models.parameters.source_params import SourceSaveParams
from ..models.parameters.sourced_event_params import SourcedEventData
from ..utils import resolve_source_handles_by_title
from .data_management import _extract_entity_data, _format_error_response
from .media_upload import upload_media_from_path


async def create_sourced_event_tool(arguments: dict) -> list[TextContent]:
    """
    Create a source, citation (with optional inline media), and event in
    one call, wiring citation_list automatically so callers never retype
    a handle between steps.
    """
    try:
        params = SourcedEventData(**arguments)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        # 1. Source - reuse an existing one, or create after a collision check
        if params.source_handle:
            source_handle = params.source_handle
        else:
            # Reason: check_exactly_one_source guarantees source_title is set
            # whenever source_handle is not; mypy cannot see across the
            # validator, so narrow the type explicitly instead of loosening
            # resolve_source_handles_by_title's signature to Optional. An
            # `assert` would be stripped under `python -O`, letting a None
            # title reach resolve_source_handles_by_title and blow up with
            # an opaque AttributeError on `.replace` - raise explicitly
            # instead, which narrows identically for mypy and survives -O.
            if params.source_title is None:
                raise GrampsAPIError(
                    "source_title is required when source_handle is not set."
                )
            existing = await resolve_source_handles_by_title(
                client, tree_id, params.source_title
            )
            if existing:
                # Reason: refuse rather than reuse. Source titles repeat
                # heavily in genealogy ("Etat civil, Paris"), so silently
                # attaching to a same-titled source would be invisible and
                # wrong - worse than the visible duplicate this guards
                # against. Only the caller knows if it is the same document.
                # resolve_source_handles_by_title caps its search at 10
                # matches, so note when the list may be a truncated subset
                # rather than the exhaustive set of duplicates.
                partial_note = (
                    " (list may be partial - more than 10 matches exist)"
                    if len(existing) >= 10
                    else ""
                )
                raise GrampsAPIError(
                    f"A source titled {params.source_title!r} already exists "
                    f"({', '.join(existing)}){partial_note}. Call again with "
                    "source_handle set to one of those to attach this "
                    "citation to it, or use a distinct title if this is a "
                    "different document."
                )
            source_kwargs: dict[str, Any] = {
                "title": params.source_title,
                "author": params.source_author,
                "pubinfo": params.source_pubinfo,
            }
            source_params = SourceSaveParams(**source_kwargs)
            source_result = await client.make_api_call(
                api_call=ApiCalls.POST_SOURCES,
                params=source_params,
                tree_id=tree_id,
            )
            source_data = _extract_entity_data(source_result)
            source_handle = source_data["handle"]

        # 2. Media (optional) - shared upload helper, not create_media_tool
        media_list = None
        media_info = None
        if params.media_path:
            media_info = await upload_media_from_path(
                client, params.media_path, tree_id
            )
            media_list = [{"ref": media_info["handle"]}]

        # 3. Citation
        citation_kwargs: dict[str, Any] = {
            "source_handle": source_handle,
            "page": params.citation_page,
            "date": params.citation_date,
            "media_list": media_list,
            "note_list": params.note_list,
        }
        citation_params = CitationData(**citation_kwargs)
        citation_result = await client.make_api_call(
            api_call=ApiCalls.POST_CITATIONS,
            params=citation_params,
            tree_id=tree_id,
        )
        citation_data = _extract_entity_data(citation_result)
        citation_handle = citation_data["handle"]

        # 4. Event, citation auto-wired
        event_kwargs: dict[str, Any] = {
            "type": params.event_type,
            "date": params.event_date,
            "description": params.event_description,
            "place": params.event_place,
            "citation_list": [citation_handle],
        }
        event_params = EventSaveParams(**event_kwargs)
        event_result = await client.make_api_call(
            api_call=ApiCalls.POST_EVENTS, params=event_params, tree_id=tree_id
        )
        event_data = _extract_entity_data(event_result)
        event_handle = event_data["handle"]

        # 5. Combined response - all handles visible in call order
        source_fmt = await format_source(client, tree_id, source_handle)
        citation_fmt = await format_citation(client, tree_id, citation_handle)
        event_fmt = await format_event(client, tree_id, event_handle)

        response = (
            "Successfully created sourced event:\n\n"
            f"{source_fmt}\n{citation_fmt}\n{event_fmt}"
        )
        if media_info:
            # Reason: every other site emits a gramps_id here
            # (source_handler.py:116, citation_handler.py:117,
            # person_handler.py:171, family_handler.py:206). media_info is
            # the raw new-media object from the upload, which carries both.
            response += f"\nAttached media: {media_info.get('gramps_id', 'N/A')}\n"

        return [TextContent(type="text", text=response)]

    except Exception as e:
        return _format_error_response(e, "sourced event creation")
