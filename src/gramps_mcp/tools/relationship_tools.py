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
Relationship analysis MCP tools for genealogy operations.

This module contains tools for calculating relationships between people,
checking living status, and building timelines.
"""

import logging
import re
from typing import Dict, List, Optional

from mcp.types import TextContent
from pydantic import BaseModel

from ..client import GrampsAPIError
from ..config import get_settings
from ..handlers.relationship_handler import format_relationship, format_relationships
from ..models.api_calls import ApiCalls
from ..models.parameters.relations_params import RelationParams
from ..utils import resolve_person_handle
from .search_basic import with_client

logger = logging.getLogger(__name__)

GRAMPS_ID_PATTERN = re.compile(r"^[A-Z]+[0-9]+$")


class _RelationsQueryParams(BaseModel):
    """
    Query-string-only parameters for the Gramps Web relations endpoints.

    The relations endpoints (``relations/{handle1}/{handle2}`` and
    ``.../all``) take handle1/handle2 as URL path segments and only accept
    ``depth`` as a query parameter; the API rejects unknown query fields.
    RelationParams bundles handle1/handle2 with depth for input validation,
    but handing that full model to the client would also serialize
    handle1/handle2 into the query string. This model carries just the
    query-eligible field through to the request.
    """

    depth: Optional[int] = None


def _format_error_response(error: Exception, operation: str) -> List[TextContent]:
    """Format error into user-friendly MCP response."""
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"

    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


async def _resolve_person(client, tree_id: str, value: str) -> str:
    """
    Resolve a person reference that may be a handle or a gramps_id.

    Values matching GRAMPS_ID_PATTERN (one or more uppercase letters
    followed by one or more digits, e.g. "I0044") are treated as a
    gramps_id and resolved; anything else is treated as an already-valid
    handle.

    Args:
        client: Gramps API client instance
        tree_id: Family tree identifier
        value: Handle or gramps_id string

    Returns:
        A resolved handle

    Raises:
        ValueError: If value looks like a gramps_id but no matching person
            is found
    """
    if GRAMPS_ID_PATTERN.match(value):
        handle = await resolve_person_handle(client, tree_id, value)
        if not handle:
            raise ValueError(f"No person found with gramps_id '{value}'")
        return handle
    return value


@with_client
async def get_relationship_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Calculate the relationship between two people.
    """
    try:
        person1 = arguments.get("person1")
        person2 = arguments.get("person2")
        all_relationships = arguments.get("all_relationships", False)
        depth = arguments.get("depth")

        if not person1 or not person2:
            raise ValueError("person1 and person2 are required")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        handle1 = await _resolve_person(client, tree_id, person1)
        handle2 = await _resolve_person(client, tree_id, person2)

        params = RelationParams(handle1=handle1, handle2=handle2, depth=depth)

        api_call = (
            ApiCalls.GET_RELATIONS_ALL if all_relationships else ApiCalls.GET_RELATIONS
        )

        result = await client.make_api_call(
            api_call=api_call,
            params=_RelationsQueryParams(depth=params.depth),
            tree_id=tree_id,
            handle1=handle1,
            handle2=handle2,
        )

        if all_relationships:
            formatted = await format_relationships(result, client, tree_id)
        else:
            formatted = format_relationship(result)

        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, "relationship calculation")
