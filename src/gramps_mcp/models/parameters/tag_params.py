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

from typing import Literal

from pydantic import BaseModel, Field

from .base_params import StrictModel


class TagSearchParams(BaseModel):
    """
    Parameters for listing tags.

    Unlike the other collection endpoints, this model does not inherit
    BaseGetMultipleParams: Gramps Web's tags endpoint supports neither a
    `gql` filter nor a `gramps_id` (tags have no gramps_id at all), so those
    fields would be a lie if declared.

    That made it the same trap issue #18 described. With pydantic's default
    extra="ignore", a caller passing gql= or gramps_id= had the filter
    silently dropped and got the first page of *every* tag back, believing
    it was filtered - which, on the lookup feeding delete_type, resolved to
    an arbitrary tag. Unknown keys are therefore refused here rather than
    ignored, so the mistake fails loudly at the model instead of quietly at
    the server.
    """

    model_config = {"extra": "forbid"}

    page: int | None = Field(None, description="Page number for pagination", ge=0)
    pagesize: int | None = Field(
        None, description="Number of results per page", ge=1, le=100
    )
    sort: list[str] | None = Field(None, description="Sort order for results")


class TagSaveParams(StrictModel):
    """Parameters for creating or updating a tag."""

    handle: str | None = Field(
        None, description="Tag's handle (for updates; omit for new tag)"
    )
    name: str = Field(description="Tag name", min_length=1)
    color: str | None = Field(None, description="Tag color")
    priority: int | None = Field(None, description="Tag priority")
    change: str | None = Field(None, description="Change timestamp")


class ManageTagsParams(StrictModel):
    """Parameters for the consolidated manage_tags tool (list/get/create-or-update)."""

    action: Literal["list", "get", "create"] = Field(
        ..., description="Which operation to perform"
    )
    handle: str | None = Field(
        None,
        description=(
            "Tag handle (required for 'get'; provide for update, omit for "
            "a new tag on 'create')"
        ),
    )
    name: str | None = Field(None, description="Tag name (required for 'create')")
    color: str | None = Field(None, description="Tag color")
    priority: int | None = Field(None, description="Tag priority")
    page: int | None = Field(None, ge=0, description="Page number (for 'list')")
    pagesize: int | None = Field(
        None, ge=1, le=100, description="Results per page (for 'list')"
    )
    sort: list[str] | None = Field(None, description="Sort order (for 'list')")
