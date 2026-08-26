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
import secrets
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

PERMISSION_MESSAGE = (
    "Permission denied - the account in .env must have the "
    "owner or admin role to create users"
)


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
    # Reason: this value ends up in the request URL path (see
    # GrampsWebAPIClient._build_url_with_substitution). What confines it to
    # its own path segment is that method's percent-encoding, alone:
    # quote(..., safe="") plus the explicit "." -> "%2E" replacement means
    # even a value made entirely of dots is sent as a literal segment
    # rather than resolved as a relative path.
    #
    # USERNAME_PATTERN does less than that. It is ^[A-Za-z0-9_.-]{2,64}$,
    # so it narrows the character set - "../users/x" and anything with a
    # space, "?", "#" or "%" fails it - but it permits dots freely.
    # Constructing ManageUsersParams(action="get", name=v) accepts "..",
    # "...", "..-" and ".env"; only a bare "." fails, and only because of
    # the two-character floor. Reusing the same pattern as NewUser.name
    # here keeps one definition of what a username may look like and turns
    # an obviously wrong value into a named parameter error instead of a
    # 404, but it is not what makes the endpoint safe.
    name: str | None = Field(default=None, pattern=USERNAME_PATTERN)
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
        # Reason: Gramps Web API can emit JSON nulls for optional fields.
        # .get() returns None for null values, not the default, so coerce null
        # to placeholder to avoid "TypeError: unsupported format string passed
        # to NoneType.__format__" crashes in the f-string formatting.
        name = user.get("name") or "-"
        email = user.get("email") or "-"
        full_name = user.get("full_name") or "-"
        # Reason: role is nullable in the API, so coerce to "-" when null or
        # absent, then only call _role_name for valid integer role IDs.
        role = user.get("role")
        role_str = _role_name(role) if isinstance(role, int) else "-"
        rows.append(f"{name:<20} {email:<30} {full_name:<25} {role_str}")
    return "\n".join(rows)


async def _existing_usernames(client, tree_id: str) -> set[str]:
    """
    Fetch the set of usernames already registered on the instance.

    Args:
        client (GrampsWebAPIClient): Client to use.
        tree_id (str): Family tree identifier.

    Returns:
        set[str]: Existing usernames.

    Raises:
        GrampsAPIError: If the call fails. A 403 here is rewritten to the
            tailored owner/admin-rights message, since this is the first
            network call the "create" action makes and a non-owner account
            hits it before any per-user POST.
    """
    # Reason: one list call up front, rather than reading a 409 back off each
    # POST. _format_http_error flattens every status into prose, so "already
    # exists" and a real server fault would otherwise be indistinguishable.
    try:
        result = await client.make_api_call(
            api_call=ApiCalls.GET_USERS, params=None, tree_id=tree_id
        )
    except GrampsAPIError as e:
        message = str(e)
        if "Permission denied" in message:
            raise GrampsAPIError(PERMISSION_MESSAGE) from e
        raise
    if not isinstance(result, list):
        return set()
    # Reason: same null-name defense as _format_user_rows - .get(..., "")
    # only supplies the default when the key is absent, not when the API
    # emits an explicit JSON null for "name".
    return {user.get("name") or "" for user in result}


async def _create_one(client, tree_id: str, user: NewUser) -> tuple[str, str]:
    """
    Create a single account with a generated password.

    Args:
        client (GrampsWebAPIClient): Client to use.
        tree_id (str): Family tree identifier.
        user (NewUser): Account to create.

    Returns:
        tuple[str, str]: ("created", password), ("skipped", reason), or
            ("failed", reason). This never raises: a per-user failure -
            expected (GrampsAPIError) or not (cancellation, a bug in URL
            building, anything else) - must not abort the batch and discard
            the passwords already issued to earlier users in it.
    """
    password = secrets.token_urlsafe(PASSWORD_BYTES)
    try:
        body = UserCreateBody(
            email=user.email,
            full_name=user.full_name or user.name,
            password=password,
            role=ROLE_IDS[user.role],
        )
        await client.make_api_call(
            api_call=ApiCalls.POST_USER,
            params=body,
            tree_id=tree_id,
            name=user.name,
        )
    except GrampsAPIError as e:
        message = str(e)
        if "Permission denied" in message:
            return "failed", PERMISSION_MESSAGE
        # Reason: 409 is the acknowledged create-time race (or a username
        # that differs only in case from an existing one, which the
        # pre-check's exact-match set does not catch) - report it the same
        # way as a pre-check hit, not as a generic HTTP failure.
        if "status 409" in message:
            return "skipped", "already exists"
        return "failed", message
    except Exception as e:
        # Reason: deliberately broad - see docstring, this must never raise.
        return "failed", f"unexpected error: {e}"
    return "created", password


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

        elif params.action == "create":
            if not params.users:
                raise ValueError("users is required for action 'create'")

            existing = await _existing_usernames(client, tree_id)
            rows: list[str] = []
            counts = {"created": 0, "skipped": 0, "failed": 0}
            aborted_after: int | None = None

            # Reason: sequential on purpose. Parallel writes against one
            # Gramps Web worker invite rate-limiting and interleave partial
            # failures that are hard to read back.
            for index, user in enumerate(params.users):
                try:
                    if user.name in existing:
                        status, detail = "skipped", "already exists"
                    else:
                        status, detail = await _create_one(client, tree_id, user)
                except Exception as e:
                    # Reason: _create_one already turns every failure it can
                    # anticipate into a ("failed"/"skipped", reason) tuple
                    # and never raises. This is a last-resort guard for
                    # anything that still escapes it (e.g. a cancellation on
                    # client disconnect) so the passwords already generated
                    # for earlier users in this batch are still returned
                    # instead of discarded by the outer error handler.
                    aborted_after = index
                    rows.append(f"{user.name:<20} aborted: {e}")
                    break
                counts[status] += 1
                if status == "created":
                    rows.append(
                        f"{user.name:<20} {user.email:<30} {user.role:<12} {detail}"
                    )
                else:
                    rows.append(f"{user.name:<20} {status}: {detail}")

            header = (
                f"Created {counts['created']}, skipped {counts['skipped']}, "
                f"failed {counts['failed']}"
            )
            formatted = header + "\n\n" + "\n".join(rows)
            if aborted_after is not None:
                formatted += (
                    f"\n\nABORTED after {aborted_after} of {len(params.users)} "
                    "users due to an unexpected error. Rows above for "
                    "already-processed users are complete; any passwords "
                    "shown above are the only copy - capture them now."
                )

        else:
            raise ValueError(f"Unsupported action: {params.action}")

        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, f"manage_users({arguments.get('action')})")
