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
Pydantic model for the create_sourced_event composite tool.

Chains source + citation + event creation into one call, auto-wiring the
citation onto the event so callers never retype a handle between steps.
"""

from typing import Any

from pydantic import BaseModel, Field


class SourcedEventData(BaseModel):
    """Composite parameters for create_sourced_event."""

    # Source fields
    source_title: str = Field(..., description="Source document title", min_length=1)
    source_author: str | None = Field(None, description="Source author")
    source_pubinfo: str | None = Field(None, description="Source publication info")

    # Citation fields
    citation_page: str | None = Field(
        None, description="Page or location within the source"
    )
    citation_date: dict[str, Any] | None = Field(
        None,
        description=(
            "Citation date object with dateval array [day, month, year, "
            "False], quality (0=regular, 1=estimated, 2=calculated), and "
            "modifier (0=regular, 1=before, 2=after, 3=about, 4=range, "
            "5=span, 6=textonly, 7=from, 8=to)"
        ),
    )

    # Event fields
    event_type: str = Field(
        ..., description="Event type (Birth, Death, Marriage, etc.)"
    )
    event_date: dict[str, Any] | None = Field(None, description="Event date object")
    event_place: str | None = Field(None, description="Place handle")
    event_description: str | None = Field(None, description="Event description")

    # Attaches to the citation, matching this codebase's existing sourcing
    # convention (see TestCreateCitationTool)
    media_path: str | None = Field(
        None, description="Local file to upload and attach to the citation"
    )
    note_list: list[str] | None = Field(
        None, description="Note handles to attach to the citation"
    )
