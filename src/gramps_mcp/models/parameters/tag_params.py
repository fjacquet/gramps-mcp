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
Pydantic models for tag-related operations.

API calls supported in this category:
- GET_TAGS: Get information about multiple tags
- POST_TAGS: Add a new tag to the database
- GET_TAG: Get information about a specific tag
- PUT_TAG: Update the tag
- DELETE_TAG: Delete the tag
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TagSearchParams(BaseModel):
    """Parameters for searching tags."""

    page: Optional[int] = Field(None, description="Page number for pagination", ge=0)
    pagesize: Optional[int] = Field(
        None, description="Number of results per page", ge=1, le=100
    )
    sort: Optional[List[str]] = Field(None, description="Sort order for results")


class TagSaveParams(BaseModel):
    """Parameters for creating or updating a tag."""

    handle: Optional[str] = Field(
        None, description="Tag's handle (for updates; omit for new tag)"
    )
    name: str = Field(description="Tag name", min_length=1)
    color: Optional[str] = Field(None, description="Tag color")
    priority: Optional[int] = Field(None, description="Tag priority")
    change: Optional[str] = Field(None, description="Change timestamp")


class ManageTagsParams(BaseModel):
    """Parameters for the consolidated manage_tags tool (list/get/create-or-update)."""

    action: Literal["list", "get", "create"] = Field(
        ..., description="Which operation to perform"
    )
    handle: Optional[str] = Field(
        None,
        description=(
            "Tag handle (required for 'get'; provide for update, omit for "
            "a new tag on 'create')"
        ),
    )
    name: Optional[str] = Field(None, description="Tag name (required for 'create')")
    color: Optional[str] = Field(None, description="Tag color")
    priority: Optional[int] = Field(None, description="Tag priority")
    page: Optional[int] = Field(None, ge=0, description="Page number (for 'list')")
    pagesize: Optional[int] = Field(
        None, ge=1, le=100, description="Results per page (for 'list')"
    )
    sort: Optional[List[str]] = Field(None, description="Sort order (for 'list')")
