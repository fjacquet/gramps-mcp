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
Record management MCP tools for genealogy operations.

This module contains tools for managing tags and retrieving tree facts.
"""

import logging
from typing import Dict, List

from mcp.types import TextContent

from ..client import GrampsAPIError
from ..config import get_settings
from ..handlers.tag_handler import format_tag, format_tags
from ..models.api_calls import ApiCalls
from ..models.parameters.tag_params import TagSaveParams, TagSearchParams
from .search_basic import with_client

logger = logging.getLogger(__name__)


def _format_error_response(error: Exception, operation: str) -> List[TextContent]:
    """Format error into user-friendly MCP response."""
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"

    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


@with_client
async def manage_tags_tool(client, arguments: Dict) -> List[TextContent]:
    """
    List, get, or create/update tags.
    """
    try:
        action = arguments.get("action")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        if action == "list":
            params = TagSearchParams(
                page=arguments.get("page"),
                pagesize=arguments.get("pagesize"),
                sort=arguments.get("sort"),
            )
            result = await client.make_api_call(
                api_call=ApiCalls.GET_TAGS, params=params, tree_id=tree_id
            )
            formatted = format_tags(result)

        elif action == "get":
            handle = arguments.get("handle")
            if not handle:
                raise ValueError("handle is required for action 'get'")
            result = await client.make_api_call(
                api_call=ApiCalls.GET_TAG, params=None, tree_id=tree_id, handle=handle
            )
            formatted = format_tag(result)

        elif action == "create":
            handle = arguments.get("handle")
            name = arguments.get("name")
            if not handle and not name:
                raise ValueError("name is required to create a new tag")

            # Reason: name may be None here (update-only-color/priority case);
            # TagSaveParams.name has no default, so passing None raises a
            # ValidationError at runtime, converted to a normal error response
            # by the surrounding try/except. Silenced for mypy since this is
            # an intentional runtime-validated shortcut, not a bug.
            save_params = TagSaveParams(
                handle=handle,
                name=name,  # type: ignore[arg-type]
                color=arguments.get("color"),
                priority=arguments.get("priority"),
                change=None,
            )

            if handle:
                await client.make_api_call(
                    api_call=ApiCalls.PUT_TAG,
                    params=save_params,
                    tree_id=tree_id,
                    handle=handle,
                )
                formatted = f"Tag '{name}' updated."
            else:
                await client.make_api_call(
                    api_call=ApiCalls.POST_TAGS, params=save_params, tree_id=tree_id
                )
                formatted = f"Tag '{name}' created."

        else:
            raise ValueError(f"Invalid action: {action}")

        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, "tag management")
