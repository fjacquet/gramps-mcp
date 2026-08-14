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
Destructive MCP tools: delete, merge, detach and undo.

Every tool here can remove data. The guard rails live in destructive.py as
pure functions; this module does the I/O and the formatting.
"""

import logging

from mcp.types import TextContent

from ..client import GrampsAPIError
from ..config import get_settings
from ..destructive import TYPE_ENDPOINTS, should_refuse_delete
from ..models.parameters.destructive_params import DeleteTypeParams
from .search_basic import with_client

logger = logging.getLogger(__name__)


def _format_error_response(error: Exception, operation: str) -> list[TextContent]:
    """Format an error into a user-facing MCP response."""
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"
    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


async def resolve_target_handle(
    client, tree_id: str, obj_type: str, handle: str | None, gramps_id: str | None
) -> str:
    """
    Return the handle for a target named by handle or by gramps_id.

    Args:
        client (GrampsWebAPIClient): Client to issue the lookup with.
        tree_id (str): Family tree identifier.
        obj_type (str): One of the keys of TYPE_ENDPOINTS.
        handle (str | None): Handle, used directly when given.
        gramps_id (str | None): Gramps ID, resolved by a GQL search.

    Returns:
        str: The resolved handle.

    Raises:
        ValueError: If neither identifier is given, or the gramps_id matches
            no record.
    """
    if handle:
        return handle
    if not gramps_id:
        raise ValueError("Either handle or gramps_id is required")

    from ..models.api_calls import ApiCalls

    plural = {
        "person": ApiCalls.GET_PEOPLE,
        "family": ApiCalls.GET_FAMILIES,
        "event": ApiCalls.GET_EVENTS,
        "place": ApiCalls.GET_PLACES,
        "source": ApiCalls.GET_SOURCES,
        "citation": ApiCalls.GET_CITATIONS,
        "repository": ApiCalls.GET_REPOSITORIES,
        "media": ApiCalls.GET_MEDIA,
        "note": ApiCalls.GET_NOTES,
        "tag": ApiCalls.GET_TAGS,
    }[obj_type]

    results = await client.make_api_call(
        api_call=plural,
        params={"gql": f'gramps_id="{gramps_id}"', "pagesize": 1},
        tree_id=tree_id,
    )
    if not results:
        raise ValueError(f"No {obj_type} found with gramps_id {gramps_id}")
    return results[0]["handle"]


@with_client
async def delete_type_tool(client, arguments: dict) -> list[TextContent]:
    """Delete one record, refusing while other records still reference it."""
    try:
        params = DeleteTypeParams(**arguments)
        tree_id = get_settings().gramps_tree_id
        endpoints = TYPE_ENDPOINTS[params.type]

        handle = await resolve_target_handle(
            client, tree_id, params.type, params.handle, params.gramps_id
        )

        record = await client.make_api_call(
            api_call=endpoints.get,
            params={"backlinks": True},
            tree_id=tree_id,
            handle=handle,
        )
        gramps_id = record.get("gramps_id", handle)
        backlinks = record.get("backlinks") or {}

        refusal = should_refuse_delete(backlinks)
        if refusal and not params.force:
            return [
                TextContent(
                    type="text",
                    text=f"{params.type} {gramps_id}\n{refusal}",
                )
            ]

        await client.make_api_call(
            api_call=endpoints.delete, tree_id=tree_id, handle=handle
        )

        severed = ""
        if refusal:
            total = sum(len(v) for v in backlinks.values() if v)
            severed = f" {total} reference(s) were severed (force=true)."
        return [
            TextContent(
                type="text",
                text=f"Deleted {params.type} {gramps_id}.{severed}",
            )
        ]

    except Exception as e:
        return _format_error_response(e, "deletion")
