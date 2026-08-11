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
User management MCP tool for Gramps Web accounts.

Self-contained by design: schema, handler and output formatting live here
rather than being split across models/, handlers/ and tools/. The tool is
small enough that the split would cost more than it buys.
"""

import logging
from typing import Literal

from mcp.types import TextContent
from pydantic import BaseModel, Field

from ..client import GrampsAPIError
from ..config import get_settings
from ..models.api_calls import ApiCalls
from .search_basic import with_client

logger = logging.getLogger(__name__)

# Role IDs from gramps_webapi/auth/const.py. owner (4) and admin (5) are
# deliberately absent: this tool must not be able to grant them.
ROLE_IDS = {"guest": 0, "member": 1, "contributor": 2, "editor": 3}

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{2,64}$"
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# 16 bytes, about 128 bits of entropy, URL-safe so it survives copy-paste.
PASSWORD_BYTES = 16

MAX_BATCH = 50


class NewUser(BaseModel):
    """One account to create."""

    name: str = Field(..., pattern=USERNAME_PATTERN)
    email: str = Field(..., pattern=EMAIL_PATTERN)
    full_name: str = ""
    role: Literal["guest", "member", "contributor", "editor"] = "member"


class UserCreateBody(BaseModel):
    """Request body for POST /users/{name}/."""

    email: str
    full_name: str
    password: str
    role: int


class ManageUsersParams(BaseModel):
    """Parameters for the manage_users tool."""

    action: Literal["list", "get", "create"]
    name: str | None = None
    users: list[NewUser] | None = Field(default=None, max_length=MAX_BATCH)


def _format_error_response(error: Exception, operation: str) -> list[TextContent]:
    """
    Format an exception into a user-friendly MCP response.

    Args:
        error (Exception): The exception to report.
        operation (str): Name of the operation that failed.

    Returns:
        list[TextContent]: Single-element error response.
    """
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"

    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


def _role_name(role_id: int) -> str:
    """
    Convert a Gramps Web role ID to its name.

    Args:
        role_id (int): Numeric role from the API.

    Returns:
        str: Role name, or the raw ID as a string if unknown.
    """
    # Reason: owner/admin/disabled are absent from ROLE_IDS because the tool
    # cannot grant them, but existing accounts hold them and must display.
    by_id = {value: key for key, value in ROLE_IDS.items()}
    by_id.update({4: "owner", 5: "admin", -1: "disabled", -2: "unconfirmed"})
    return by_id.get(role_id, str(role_id))


def _format_user_rows(users: list[dict]) -> str:
    """
    Format user objects as aligned text rows.

    Args:
        users (list[dict]): User objects from the API.

    Returns:
        str: One row per user: name, e-mail, full name, role.
    """
    if not users:
        return "No users found."

    rows = []
    for user in users:
        rows.append(
            f"{user.get('name', '-'):<20} "
            f"{user.get('email', '-'):<30} "
            f"{user.get('full_name', '-'):<25} "
            f"{_role_name(user.get('role', -99))}"
        )
    return "\n".join(rows)


@with_client
async def manage_users_tool(client, arguments: dict) -> list[TextContent]:
    """
    List, get, or create Gramps Web user accounts.

    Args:
        client (GrampsWebAPIClient): Injected by the with_client decorator.
        arguments (dict): Raw tool arguments, validated against
            ManageUsersParams.

    Returns:
        list[TextContent]: Formatted result, or an error message.
    """
    try:
        params = ManageUsersParams(**arguments)
        tree_id = get_settings().gramps_tree_id

        if params.action == "list":
            result = await client.make_api_call(
                api_call=ApiCalls.GET_USERS, params=None, tree_id=tree_id
            )
            formatted = _format_user_rows(result if isinstance(result, list) else [])

        elif params.action == "get":
            if not params.name:
                raise ValueError("name is required for action 'get'")
            result = await client.make_api_call(
                api_call=ApiCalls.GET_USER,
                params=None,
                tree_id=tree_id,
                name=params.name,
            )
            formatted = _format_user_rows([result] if result else [])

        else:
            raise ValueError(f"Unsupported action: {params.action}")

        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, f"manage_users({arguments.get('action')})")
