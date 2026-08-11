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

from pydantic import BaseModel, Field

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
