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
Pydantic models for citation-related operations.

API calls supported in this category:
- GET_CITATIONS: Get information about multiple citations
- POST_CITATIONS: Add a new citation to the database
- GET_CITATION: Get information about a specific citation
- PUT_CITATION: Update the citation
- DELETE_CITATION: Delete the citation
"""

from pydantic import Field

from .base_params import BaseDataModel, BaseGetMultipleParams
from .date_params import DateValue


class GetCitationsParams(BaseGetMultipleParams):
    """Parameters for GET /citations endpoint."""

    dates: str | None = Field(
        None, description="A date filter that operates on the citation date."
    )


class CitationData(BaseDataModel):
    """Model for creating or updating a citation via POST/PUT endpoints."""

    date: DateValue | None = Field(None, description="Citation date")
    page: str | None = Field(None, description="Page or location within the source")
    source_handle: str = Field(..., description="Handle of the source being cited")
    media_path: str | None = Field(
        None,
        description=(
            "Local file path to upload as media and attach to this citation "
            "(alternative to referencing an existing media handle via "
            "media_list; the resulting ref is appended to media_list, not "
            "replacing any existing entries)"
        ),
    )
