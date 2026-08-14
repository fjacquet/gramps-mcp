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

from mcp.server import MCPServer, Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from . import __version__
from .config import get_settings

# Reason: the registry is pure data and lives in its own module - it grew
# server.py to 497 of the 500 lines the pre-commit hook allows, and it gains
# a block every time a tool is added. Re-exported here because tests and
# workflow helpers import it from server.
from .tool_registry import TOOL_REGISTRY

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Create MCPServer app; stateless_http/json_response now live on .run(), not
# the constructor (mcp>=2.0.0)
app = MCPServer("gramps")


# ============================================================================
# Dynamic MCPServer Tool Registration
# ============================================================================


# Register all tools dynamically from the registry
def _make_tool_handler(handler, tool_name: str, schema, description: str):
    """
    Build the MCPServer-facing callable for one registry entry.

    Args:
        handler: The tool implementation taking a plain dict of arguments.
        tool_name (str): Name the tool is published under.
        schema: Pydantic model describing the tool's arguments.
        description (str): Tool description shown to clients.

    Returns:
        Callable: An async callable taking only `arguments`.
    """

    # Reason: handler is captured by closure rather than bound as a default
    # kwarg. FastMCP derives each tool's inputSchema from the signature, so
    # a `handler=...` default was published on all 27 tools as an optional
    # string - a client sending it replaced the bound callable with a string
    # and the call died (upstream issue #30).
    async def tool_handler(arguments):
        return await handler(arguments.model_dump())

    tool_handler.__name__ = tool_name
    tool_handler.__doc__ = description
    tool_handler.__annotations__ = {"arguments": schema}
    return tool_handler


def register_tools():
    """Register all tools from the registry with MCPServer."""
    for tool_name, tool_config in TOOL_REGISTRY.items():
        description = tool_config["description"]
        app.tool(description=description)(
            _make_tool_handler(
                tool_config["handler"],
                tool_name,
                tool_config["schema"],
                description,
            )
        )


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


async def handle_list_tools(
    ctx: Any, params: PaginatedRequestParams | None
) -> ListToolsResult:
    """List all available tools."""
    return ListToolsResult(
        tools=[
            Tool(
                name=tool_name,
                description=tool_config["description"],
                input_schema=tool_config["schema"].model_json_schema(),
            )
            for tool_name, tool_config in TOOL_REGISTRY.items()
        ]
    )


async def handle_call_tool(ctx: Any, params: CallToolRequestParams) -> CallToolResult:
    """Handle tool calls."""
    if params.name not in TOOL_REGISTRY:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Unknown tool: {params.name}")],
            is_error=True,
        )
    try:
        content = await TOOL_REGISTRY[params.name]["handler"](params.arguments or {})
        return CallToolResult(content=content, is_error=False)
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Tool error: {e}")],
            is_error=True,
        )


async def run_stdio_server():
    """Run the MCP server with stdio transport."""
    # Low-level Server: handlers are injected via the constructor in
    # mcp>=2.0.0 (the @server.list_tools()/@server.call_tool() decorators
    # were removed, not merely deprecated)
    server = Server(
        "gramps", on_list_tools=handle_list_tools, on_call_tool=handle_call_tool
    )

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
        # Run the MCPServer with streamable HTTP transport; transport
        # params live on .run() in mcp>=2.0.0, not the constructor
        settings = get_settings()
        app.run(
            transport="streamable-http",
            host=settings.gramps_mcp_host,
            port=settings.gramps_mcp_port,
            stateless_http=True,
            json_response=True,
        )
