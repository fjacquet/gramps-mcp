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
Detail retrieval MCP tools for genealogy operations.

This module contains 2 detail retrieval tools for getting comprehensive
person and family information using direct API calls.
"""

import logging

from mcp.types import TextContent

from ..client import GrampsAPIError
from ..config import get_settings
from ..handlers.family_detail_handler import format_family_detail
from ..handlers.person_detail_handler import format_person_detail
from ..models.api_calls import ApiCalls
from ..models.parameters.base_params import BaseGetMultipleParams
from .search_basic import with_client

logger = logging.getLogger(__name__)


def _format_error_response(error: Exception, operation: str) -> list[TextContent]:
    """Format error into user-friendly MCP response."""
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"

    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


@with_client
async def get_person_tool(client, arguments: dict) -> list[TextContent]:
    """
    Get comprehensive person information using direct API calls.
    """
    try:
        # Extract handle from arguments
        handle = arguments.get("person_handle")
        if not handle:
            raise ValueError("person_handle is required")

        # Get tree_id from settings
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Use the detailed person handler to get comprehensive formatted data
        formatted_person = await format_person_detail(client, tree_id, handle)

        return [TextContent(type="text", text=formatted_person)]

    except Exception as e:
        return _format_error_response(e, "person details retrieval")


@with_client
async def get_family_tool(client, arguments: dict) -> list[TextContent]:
    """
    Get detailed family information using direct API calls.
    """
    try:
        # Extract handle from arguments
        handle = arguments.get("family_handle")
        if not handle:
            raise ValueError("family_handle is required")

        # Get tree_id from settings
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Use the detailed family handler to get comprehensive formatted data
        formatted_family = await format_family_detail(client, tree_id, handle)

        return [TextContent(type="text", text=formatted_family)]

    except Exception as e:
        return _format_error_response(e, "family details retrieval")


_GRAMPS_ID_API_CALLS = {
    "person": ApiCalls.GET_PEOPLE,
    "family": ApiCalls.GET_FAMILIES,
}


@with_client
async def _resolve_gramps_id(client, entity_type: str, gramps_id: str) -> str | None:
    """
    Look up an entity's handle from its user-facing identifier.

    Args:
        entity_type (str): "person" or "family".
        gramps_id (str): The identifier shown in the Gramps interface.

    Returns:
        str | None: The handle, or None when no record matches or the
            entity type is unsupported.
    """
    api_call = _GRAMPS_ID_API_CALLS.get(entity_type)
    if api_call is None:
        return None

    settings = get_settings()
    tree_id = settings.gramps_tree_id

    # Reason: the ignore comment below suppresses a mypy false positive -
    # mypy's dataclass_transform support does not recognize
    # BaseGetMultipleParams' other Optional fields (declared as
    # Field(None, ...) with a positional default) as having defaults, so it
    # flags them as missing even though they are optional at runtime; see
    # the identical pattern in search_basic.py's find_anything_tool.
    params = BaseGetMultipleParams(  # type: ignore[call-arg]
        gql=f'gramps_id="{gramps_id}"', pagesize=1
    )
    results = await client.make_api_call(
        api_call=api_call, params=params, tree_id=tree_id
    )

    if not results:
        return None

    handle = results[0].get("handle")
    return handle if handle else None


async def get_type_tool(arguments: dict) -> list[TextContent]:
    """Universal get tool for person and family details."""
    entity_type = arguments.get("type")
    handle = arguments.get("handle")
    gramps_id = arguments.get("gramps_id")

    # If gramps_id provided but no handle, resolve it through the API
    if gramps_id and not handle:
        # Reason: this used to regex-scrape the handle out of text formatted
        # for display, so any change to the rendering silently broke lookup by
        # identifier. Read the structured record instead.
        handle = await _resolve_gramps_id(entity_type, gramps_id)
        if handle is None:
            return [
                TextContent(
                    type="text",
                    text=(
                        f"No {entity_type} found with gramps_id {gramps_id}. "
                        f"Check the identifier, or use find_type to search."
                    ),
                )
            ]

    if entity_type == "person" and handle:
        return await get_person_tool({"person_handle": handle})
    elif entity_type == "family" and handle:
        return await get_family_tool({"family_handle": handle})

    return [
        TextContent(
            type="text",
            text=(
                f"Unable to resolve type '{entity_type}': provide a supported "
                f"type ('person' or 'family') together with a handle or "
                f"gramps_id."
            ),
        )
    ]
