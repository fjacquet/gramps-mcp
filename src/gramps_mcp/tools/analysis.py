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
Analysis MCP tools for genealogy operations.

This module contains 4 analysis tools for genealogy research including
tree statistics, ancestor/descendant discovery, and recent changes tracking.
"""

import logging

from mcp.types import TextContent

from ..client import GrampsAPIError, GrampsWebAPIClient
from ..config import get_settings
from ..handlers.traversal_handler import format_traversal
from ..models.api_calls import ApiCalls
from ..traversal import resolve_person_handle, walk_ancestors, walk_descendants
from ..utils import get_gramps_id_from_handle
from .search_basic import with_client

logger = logging.getLogger(__name__)


def _format_error_response(error: Exception, operation: str) -> list[TextContent]:
    """Format error into user-friendly MCP response."""
    if isinstance(error, (GrampsAPIError, ValueError)):
        # Reason: a ValueError raised in this package (an unknown gramps_id,
        # an out-of-range max_generations) is an expected, validated outcome
        # - not a surprise the "Unexpected error during..." wrapper implies.
        # Only genuinely unforeseen exceptions get that wrapper.
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"

    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


async def _format_recent_changes(
    transactions: list[dict], client: GrampsWebAPIClient, tree_id: str
) -> str:
    """Format transaction history results."""
    if not transactions:
        return "No recent changes found."

    result = f"Found {len(transactions)} recent changes:\n\n"

    for transaction in transactions:
        # Extract transaction information
        timestamp = transaction.get("timestamp", "Unknown time")
        description = transaction.get("description", "Transaction")

        # Convert timestamp to human readable format
        if isinstance(timestamp, (int, float)):
            from datetime import datetime

            formatted_time = datetime.fromtimestamp(timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        else:
            formatted_time = str(timestamp)

        # User information
        connection = transaction.get("connection", {})
        user = connection.get("user", {})
        user_name = user.get("name", "Unknown") if user else "Unknown"

        # Changes in this transaction
        changes = transaction.get("changes", [])
        change_count = len(changes)

        result += f"• **{description}**\n"
        result += f"  Time: {formatted_time}\n"
        result += f"  User: {user_name}\n"

        if changes:
            result += "  Objects changed:\n"
            for change in changes[:3]:  # Show first 3 changes
                obj_class = change.get("obj_class", "Unknown")
                obj_handle = change.get("obj_handle", "N/A")

                # Get gramps_id from handle using utility function
                gramps_id = await get_gramps_id_from_handle(
                    client, obj_class, obj_handle, tree_id
                )
                result += f"    - {obj_class}: {gramps_id}\n"
            if len(changes) > 3:
                result += f"    - ... and {len(changes) - 3} more\n"
        else:
            result += f"  Changes: {change_count} objects modified\n"

        result += "\n"

    return result


# ============================================================================
# Analysis Tools (4 tools)
# ============================================================================


def _validate_max_generations(raw) -> int:
    """
    Validate the raw max_generations argument for a traversal tool.

    The Pydantic parameter models (AncestorsParams, DescendantsParams)
    already enforce ``ge=1, le=20``, but that bound only applies on the
    HTTP transport, where server.py builds and validates a parameter model
    before calling the handler. The stdio transport's handle_call_tool
    passes params.arguments straight through with no validation, so this
    function is the only bound on that path.

    Args:
        raw: The raw ``max_generations`` value from tool arguments, of any
            type - absent keys surface here as None.

    Returns:
        int: A validated generation count, 1 through 20 inclusive. Missing
        or None input defaults to 5.

    Raises:
        ValueError: The value is not an integer, or is outside 1-20.
            ``bool`` is rejected even though it is a subclass of ``int`` in
            Python - True/False are not meaningful generation counts and
            passing one is almost certainly a mistake, not an intentional
            1.
    """
    if raw is None:
        return 5
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(
            f"max_generations must be an integer from 1 through 20, got {raw!r}"
        )
    if not 1 <= raw <= 20:
        raise ValueError(
            f"max_generations must be an integer from 1 through 20, got {raw}"
        )
    return raw


async def _traverse_and_format(
    client, arguments: dict, direction: str, walk
) -> list[TextContent]:
    """
    Resolve the subject, walk the graph, and render the result.

    Args:
        client: A GrampsWebAPIClient, injected by with_client.
        arguments (dict): Tool arguments carrying gramps_id and max_generations.
        direction (str): "ancestors" or "descendants", used in the heading.
        walk (Callable): walk_ancestors or walk_descendants.

    Returns:
        list[TextContent]: The rendered tree, or an error message.
    """
    try:
        gramps_id = arguments.get("gramps_id")
        if not gramps_id:
            raise ValueError("gramps_id is required")
        max_generations = _validate_max_generations(arguments.get("max_generations"))

        tree_id = get_settings().gramps_tree_id
        start_handle = await resolve_person_handle(client, tree_id, gramps_id)
        if start_handle is None:
            raise ValueError(f"no person found with gramps_id {gramps_id}")

        result = await walk(client, tree_id, start_handle, max_generations)
        return [TextContent(type="text", text=format_traversal(result, direction))]
    except Exception as e:
        return _format_error_response(e, f"{direction} search")


@with_client
async def get_descendants_tool(client, arguments: dict) -> list[TextContent]:
    """
    Find all descendants of a person.

    Args:
        client: A GrampsWebAPIClient, injected by with_client.
        arguments (dict): Tool arguments carrying gramps_id and max_generations.

    Returns:
        list[TextContent]: An indented markdown tree of descendants.
    """
    return await _traverse_and_format(
        client, arguments, "descendants", walk_descendants
    )


@with_client
async def get_ancestors_tool(client, arguments: dict) -> list[TextContent]:
    """
    Find all ancestors of a person.

    Args:
        client: A GrampsWebAPIClient, injected by with_client.
        arguments (dict): Tool arguments carrying gramps_id and max_generations.

    Returns:
        list[TextContent]: An indented markdown tree of ancestors.
    """
    return await _traverse_and_format(client, arguments, "ancestors", walk_ancestors)


def _apply_recent_changes_defaults(arguments: dict) -> dict:
    """
    Fill in recent_changes defaults, treating an explicit None/empty value
    the same as an absent key.

    Args:
        arguments (dict): Raw tool arguments, possibly containing explicit
            None values.

    Returns:
        dict: A new dict with ``sort`` defaulted to ``-id`` and ``page``
            defaulted to ``1`` whenever the caller did not supply a real
            value for either. A copy is returned so the caller's dict is
            never mutated.

    Reason:
        The MCP HTTP dispatcher (server.py's create_handler) always calls
        the tool handler with ``handler(arguments.model_dump())``, without
        ``exclude_none=True``. Every optional field the schema declares
        therefore arrives explicitly set to ``None`` rather than absent.
        ``dict.setdefault`` only fires when the key is missing, so it never
        catches this shape and the sort default below would silently no-op
        for every caller going through that transport - which is exactly
        how ``sort`` ended up always reaching the API as ``None``, even
        though most recent first is the intended default. Falsy values
        (``None`` or ``""``) are therefore treated as "not supplied"; a
        real caller-supplied value still wins.

        ``page`` gets the same treatment for a separate reason: the
        underlying API only honours ``pagesize`` when ``page`` is also
        given. A caller who sets ``pagesize`` alone (a very natural thing
        to do) previously got the entire transaction history rendered into
        the response, since ``page`` reached the API as ``None`` either
        way. Defaulting an absent/None ``page`` to ``1`` bounds the result
        the same way an explicit page request already did.
    """
    arguments = dict(arguments or {})
    if not arguments.get("sort"):
        arguments["sort"] = "-id"
    if not arguments.get("page"):
        arguments["page"] = 1
    return arguments


@with_client
async def get_recent_changes_tool(client, arguments: dict) -> list[TextContent]:
    """
    Get recent changes/modifications to the family tree.
    """
    try:
        # Import and validate parameters
        from ..models.parameters.transactions_params import TransactionHistoryParams

        arguments = _apply_recent_changes_defaults(arguments)
        params = TransactionHistoryParams(**arguments)

        # Get tree_id from settings
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Get recent transaction history using unified API
        changes = await client.make_api_call(
            api_call=ApiCalls.GET_TRANSACTIONS_HISTORY, params=params, tree_id=tree_id
        )

        formatted_changes = await _format_recent_changes(changes, client, tree_id)
        return [TextContent(type="text", text=formatted_changes)]

    except Exception as e:
        return _format_error_response(e, "recent changes retrieval")


def _format_tree_info(tree_info: dict) -> str:
    """Format tree information for display."""
    tree_id = tree_info.get("id", "N/A")
    name = tree_info.get("name", "Unnamed Tree")
    description = tree_info.get("description", "")

    result = f"# Family Tree: {name}\n\n"
    result += f"**Tree ID:** `{tree_id}`\n"
    if description:
        result += f"**Description:** {description}\n"
    result += "\n"

    # Statistics from usage fields
    usage_people = tree_info.get("usage_people")
    usage_media = tree_info.get("usage_media")

    result += "## Statistics\n\n"

    if usage_people is not None or usage_media is not None:
        if usage_people is not None:
            result += f"• **People:** {usage_people:,}\n"
        if usage_media is not None:
            usage_media_mb = usage_media / (1024 * 1024)
            result += f"• **Media Storage:** {usage_media_mb:.2f} MB\n"
        result += "\n"
    else:
        result += "Statistics not available\n\n"

    return result


@with_client
async def get_tree_info_tool(client, _arguments: dict) -> list[TextContent]:
    """
    Get information about a specific tree including statistics.

    Returns counts of people, families, events, etc.
    """
    try:
        # Get tree_id from settings
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Get tree info using unified API
        tree_info = await client.make_api_call(
            api_call=ApiCalls.GET_TREE, params=None, tree_id=tree_id
        )

        formatted_info = _format_tree_info(tree_info)
        return [TextContent(type="text", text=formatted_info)]

    except Exception as e:
        return _format_error_response(e, "tree information retrieval")
