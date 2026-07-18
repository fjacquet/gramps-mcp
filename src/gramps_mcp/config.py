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
Configuration management for Gramps MCP Server.
"""

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, HttpUrl, ValidationError

# Load environment variables from .env file
load_dotenv()


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # Gramps Web API Configuration
    gramps_api_url: HttpUrl = Field(..., description="Base URL for Gramps Web API")
    gramps_username: str = Field(..., description="Username for Gramps Web API")
    gramps_password: str = Field(..., description="Password for Gramps Web API")
    gramps_tree_id: str = Field(..., description="Family tree identifier")

    # MCP HTTP Server Configuration
    gramps_mcp_host: str = Field(
        "0.0.0.0", description="Host/interface for the MCP HTTP server to bind to"
    )
    gramps_mcp_port: int = Field(
        8000, description="Port for the MCP HTTP server to listen on"
    )


def get_settings() -> Settings:
    """Get settings from environment variables."""
    try:
        return Settings(
            gramps_api_url=HttpUrl(os.environ["GRAMPS_API_URL"]),
            gramps_username=os.environ["GRAMPS_USERNAME"],
            gramps_password=os.environ["GRAMPS_PASSWORD"],
            gramps_tree_id=os.environ["GRAMPS_TREE_ID"],
            gramps_mcp_host=os.environ.get("GRAMPS_MCP_HOST", "0.0.0.0"),
            gramps_mcp_port=int(os.environ.get("GRAMPS_MCP_PORT", "8000")),
        )
    except KeyError as e:
        raise ValueError(f"Missing required environment variable: {e}")
    except ValidationError as e:
        raise ValueError(f"Invalid configuration: {e}")


def get_api_base_url(settings: Settings) -> str:
    """
    Build the Gramps Web API base URL from settings.

    Args:
        settings (Settings): Application settings.

    Returns:
        str: Base URL ending in "/api", without a trailing slash.
    """
    base_url = str(settings.gramps_api_url).rstrip("/")
    if not base_url.endswith("/api"):
        base_url += "/api"
    return base_url
