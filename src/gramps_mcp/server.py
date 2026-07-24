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
MCP server main entry point with HTTP transport.

This module provides the FastAPI application and MCP server setup with
all genealogy tools for Gramps Web API integration.
"""

import asyncio
import logging
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server
from mcp.types import Tool
from pydantic import BaseModel, Field

from . import __version__
from .config import get_settings

# Import all parameter models
from .models.parameters.citation_params import CitationData
from .models.parameters.event_params import EventSaveParams
from .models.parameters.facts_params import FactsParams
from .models.parameters.family_params import FamilySaveParams
from .models.parameters.media_params import MediaSaveParams
from .models.parameters.note_params import NoteSaveParams
from .models.parameters.people_params import PersonData
from .models.parameters.place_params import PlaceSaveParams
from .models.parameters.repository_params import RepositoryData
from .models.parameters.simple_params import (
    SimpleFindParams,
    SimpleGetParams,
    SimpleSearchParams,
)
from .models.parameters.source_params import SourceSaveParams
from .models.parameters.tag_params import ManageTagsParams
from .models.parameters.transactions_params import TransactionHistoryParams

# Import all tool functions
from .tools import (
    create_citation_tool,
    create_event_tool,
    create_family_tool,
    create_media_tool,
    create_note_tool,
    create_person_tool,
    create_place_tool,
    create_repository_tool,
    create_source_tool,
    find_anything_tool,
    get_ancestors_tool,
    get_descendants_tool,
    get_recent_changes_tool,
    get_tree_info_tool,
)
from .tools.records_tools import get_facts_tool, manage_tags_tool
from .tools.relationship_tools import (
    check_living_tool,
    get_relationship_tool,
    get_timeline_tool,
)
from .tools.search_basic import find_type_tool
from .tools.search_details import get_type_tool


# Simple analysis models for tools that use direct dict access
class TreeInfoParams(BaseModel):
    include_statistics: bool = Field(True, description="Include statistics")


class DescendantsParams(BaseModel):
    gramps_id: str = Field(..., description="Person ID")
    max_generations: int | None = Field(
        5,
        description=(
            "Max generations to retrieve (default: 5, use higher values "
            "carefully as they can overflow context)"
        ),
    )


class AncestorsParams(BaseModel):
    gramps_id: str = Field(..., description="Person ID")
    max_generations: int | None = Field(
        5,
        description=(
            "Max generations to retrieve (default: 5, use higher values "
            "carefully as they can overflow context)"
        ),
    )


class RelationshipQueryParams(BaseModel):
    person1: str = Field(..., description="Handle or gramps_id of the first person")
    person2: str = Field(..., description="Handle or gramps_id of the second person")
    all_relationships: bool = Field(
        False,
        description=(
            "If true, return all possible relationships; if false, only "
            "the most direct one"
        ),
    )
    depth: int | None = Field(
        None, ge=1, description="Search depth in generations (API default: 15)"
    )


class LivingStatusParams(BaseModel):
    person: str = Field(
        ..., description="Handle or gramps_id of the person to evaluate"
    )
    average_generation_gap: int | None = Field(None, ge=1)
    max_age_probably_alive: int | None = Field(None, ge=1)
    max_sibling_age_difference: int | None = Field(None, ge=0)
    include_dates: bool = Field(
        True, description="Also fetch estimated birth/death dates"
    )


class TimelineQueryParams(BaseModel):
    scope: str = Field(
        ...,
        description=(
            "One of: 'person', 'family', 'people', 'families' - whose timeline to build"
        ),
    )
    target: str | None = Field(
        None,
        description=(
            "Handle or gramps_id of the person/family (required when scope "
            "is 'person' or 'family'; optional anchor for scope 'people')"
        ),
    )
    dates: str | None = Field(
        None, description="Date range filter, e.g. '1900/1/1-1950/1/1'"
    )
    handles: str | None = Field(
        None, description="Comma-delimited handles (scope 'people'/'families' only)"
    )
    events: str | None = Field(
        None, description="Comma-delimited event types to include"
    )
    event_classes: str | None = Field(
        None, description="Comma-delimited event classes to include"
    )
    ratings: bool | None = Field(
        None,
        description=(
            "Include citation count and confidence score (not used for scope 'person')"
        ),
    )
    precision: int | None = Field(
        None, ge=1, le=3, description="Date precision, 1-3 (scope 'people' only)"
    )
    discard_empty: bool | None = Field(
        None, description="Discard undated events (not used for scope 'person')"
    )
    first: bool | None = Field(
        None,
        description=(
            "Include events before the anchor's first event "
            "(scope 'person'/'people' only)"
        ),
    )
    last: bool | None = Field(
        None,
        description=(
            "Include events after the anchor's last event "
            "(scope 'person'/'people' only)"
        ),
    )
    page: int | None = Field(
        None, ge=0, description="Page number (not used for scope 'person')"
    )
    pagesize: int | None = Field(
        None, gt=0, description="Items per page (not used for scope 'person')"
    )


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Tool registry - single source of truth for all tools
TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    # Search & Retrieval Tools
    "find_type": {
        "description": (
            "Search any entity type using GQL - read gql://documentation "
            "resource first to understand syntax"
        ),
        "schema": SimpleFindParams,
        "handler": find_type_tool,
    },
    "find_anything": {
        "description": (
            "Text search across all record types - matches literal text "
            "within records, not logical combinations"
        ),
        "schema": SimpleSearchParams,
        "handler": find_anything_tool,
    },
    "get_type": {
        "description": "Get full details for person or family by handle or gramps_id",
        "schema": SimpleGetParams,
        "handler": get_type_tool,
    },
    # Data Management Tools
    "create_person": {
        "description": (
            "Create or update person information including family links "
            "and event associations"
        ),
        "schema": PersonData,
        "handler": create_person_tool,
    },
    "create_family": {
        "description": "Create or update family unit including member relationships",
        "schema": FamilySaveParams,
        "handler": create_family_tool,
    },
    "create_event": {
        "description": (
            "Create or update life event including person/place associations"
        ),
        "schema": EventSaveParams,
        "handler": create_event_tool,
    },
    "create_place": {
        "description": "Create or update geographic location",
        "schema": PlaceSaveParams,
        "handler": create_place_tool,
    },
    "create_source": {
        "description": "Create or update source document",
        "schema": SourceSaveParams,
        "handler": create_source_tool,
    },
    "create_citation": {
        "description": "Create or update citation including object associations",
        "schema": CitationData,
        "handler": create_citation_tool,
    },
    "create_note": {
        "description": "Create or update textual note including object associations",
        "schema": NoteSaveParams,
        "handler": create_note_tool,
    },
    "create_media": {
        "description": "Create or update media files including object associations",
        "schema": MediaSaveParams,
        "handler": create_media_tool,
    },
    "create_repository": {
        "description": "Create or update repository information",
        "schema": RepositoryData,
        "handler": create_repository_tool,
    },
    # Analysis Tools
    "tree_stats": {
        "description": (
            "Get information about a specific tree including statistics "
            "(counts of people, families, events, etc.)"
        ),
        "schema": TreeInfoParams,
        "handler": get_tree_info_tool,
    },
    "get_descendants": {
        "description": (
            "Find all descendants of a person - WARNING: Very token-heavy "
            "operation, minimize generations (default: 5)"
        ),
        "schema": DescendantsParams,
        "handler": get_descendants_tool,
    },
    "get_ancestors": {
        "description": (
            "Find all ancestors of a person - WARNING: Very token-heavy "
            "operation, minimize generations (default: 5)"
        ),
        "schema": AncestorsParams,
        "handler": get_ancestors_tool,
    },
    "recent_changes": {
        "description": "Get recent changes/modifications to the family tree",
        "schema": TransactionHistoryParams,
        "handler": get_recent_changes_tool,
    },
    "get_relationship": {
        "description": (
            "Calculate the relationship between two people (accepts handle "
            "or gramps_id for each)"
        ),
        "schema": RelationshipQueryParams,
        "handler": get_relationship_tool,
    },
    "check_living": {
        "description": (
            "Check whether a person is living and get estimated birth/death "
            "dates (accepts handle or gramps_id)"
        ),
        "schema": LivingStatusParams,
        "handler": check_living_tool,
    },
    "get_timeline": {
        "description": (
            "Build a chronological timeline for a person, family, or group "
            "(scope: person/family/people/families)"
        ),
        "schema": TimelineQueryParams,
        "handler": get_timeline_tool,
    },
    "manage_tags": {
        "description": (
            "List, get, or create/update tags (action: list/get/create - no delete)"
        ),
        "schema": ManageTagsParams,
        "handler": manage_tags_tool,
    },
    "get_facts": {
        "description": "Get interesting facts and statistics about the tree",
        "schema": FactsParams,
        "handler": get_facts_tool,
    },
}


# Create FastMCP app with stateless HTTP (no SSE)
app = FastMCP("gramps", stateless_http=True, json_response=True)


# ============================================================================
# Dynamic FastMCP Tool Registration
# ============================================================================


# Register all tools dynamically from the registry
def register_tools():
    """Register all tools from the registry with FastMCP."""
    for tool_name, tool_config in TOOL_REGISTRY.items():
        schema = tool_config["schema"]
        handler_func = tool_config["handler"]
        description = tool_config["description"]

        # Create the async handler function with proper schema annotation
        async def create_handler(arguments, handler=handler_func):
            return await handler(arguments.model_dump())

        # Set proper metadata
        create_handler.__name__ = tool_name
        create_handler.__doc__ = description
        create_handler.__annotations__ = {"arguments": schema}

        # Register with FastMCP
        app.tool(description=description)(create_handler)


register_tools()


# ============================================================================
# Resource Management
# ============================================================================


def load_resource(filename: str) -> str:
    """Load content from resources folder with error handling."""
    try:
        # Get the path to the resources directory relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        resource_path = os.path.join(current_dir, "resources", filename)

        with open(resource_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Resource file '{filename}' not found."
    except Exception as e:
        return f"Error loading resource '{filename}': {str(e)}"


@app.resource("gql://documentation")
def get_gql_documentation() -> str:
    """
    Complete GQL documentation, syntax, examples, and property
    reference for Gramps queries.
    """
    return load_resource("gql-documentation.md")


@app.resource("gramps://usage-guide")
def get_usage_guide() -> str:
    """
    IMPORTANT: Read this first before using ANY creation tools -
    explains proper genealogy workflow and tool usage order.
    """
    return load_resource("gramps-usage-guide.md")


# Add custom routes to the FastMCP app
@app.custom_route("/", ["GET"])
async def root(request):
    """Root endpoint with server information."""
    from starlette.responses import JSONResponse

    return JSONResponse(
        {
            "service": "Gramps MCP Server",
            "version": __version__,
            "description": "MCP server for Gramps Web API genealogy operations",
            "mcp_endpoint": "/mcp",
            "tools_count": len(TOOL_REGISTRY),
        }
    )


@app.custom_route("/health", ["GET"])
async def health_check(request):
    """Health check endpoint."""
    from starlette.responses import JSONResponse

    return JSONResponse(
        {
            "status": "healthy",
            "service": "Gramps MCP Server",
            "tools": len(TOOL_REGISTRY),
        }
    )


async def run_stdio_server():
    """Run the MCP server with stdio transport."""
    # Create a standard MCP server for stdio transport
    server = Server("gramps")

    @server.list_tools()
    async def handle_list_tools():
        """List all available tools."""
        return [
            Tool(
                name=tool_name,
                description=tool_config["description"],
                inputSchema=tool_config["schema"].model_json_schema(),
            )
            for tool_name, tool_config in TOOL_REGISTRY.items()
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict):
        """Handle tool calls."""
        if name in TOOL_REGISTRY:
            return await TOOL_REGISTRY[name]["handler"](arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

    # Run the server with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    # Determine transport type from command line arguments or environment
    transport_type = sys.argv[1] if len(sys.argv) > 1 else "streamable-http"

    if transport_type == "stdio":
        # Run with stdio transport for CLI usage
        asyncio.run(run_stdio_server())
    else:
        # Run the FastMCP server with streamable HTTP transport
        # Configure server settings
        settings = get_settings()
        app.settings.host = settings.gramps_mcp_host
        app.settings.port = settings.gramps_mcp_port

        # Run with streamable-http transport for production use
        app.run(transport="streamable-http")
