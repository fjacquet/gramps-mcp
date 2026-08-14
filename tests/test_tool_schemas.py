"""
Unit tests for the tool schemas published over the streamable-http transport.

These introspect the registered FastMCP tools in-process and need no server.
"""

import warnings

import pytest

from src.gramps_mcp.server import app
from src.gramps_mcp.tool_registry import TOOL_REGISTRY


def _input_schema(tool) -> dict:
    """
    Read a tool's JSON input schema across MCP SDK attribute spellings.

    Args:
        tool: A tool object returned by app.list_tools().

    Returns:
        dict: The tool's JSON schema.
    """
    schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
    assert schema is not None, f"no input schema on tool {tool.name}"
    return schema


@pytest.fixture
async def http_tools():
    """
    List the tools as the streamable-http transport publishes them.

    Returns:
        list: Tool objects from app.list_tools().
    """
    # Reason: pydantic warns that the handler function default is not JSON
    # serializable while building the schema. That warning is itself a
    # symptom of the leak under test; silence it so the assertion is what
    # reports the problem.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return await app.list_tools()


class TestToolInputSchemas:
    async def test_every_registered_tool_is_published(self, http_tools):
        assert {tool.name for tool in http_tools} == set(TOOL_REGISTRY)

    async def test_no_tool_exposes_a_handler_parameter(self, http_tools):
        # Reason: registering the handler via a default kwarg made FastMCP
        # publish it as a caller-supplied string on all 27 tools. A client
        # that sends handler="..." overwrites the bound callable with a
        # string and the call dies (upstream issue #30).
        leaking = [
            tool.name
            for tool in http_tools
            if "handler" in _input_schema(tool).get("properties", {})
        ]
        assert leaking == []

    async def test_arguments_is_the_only_published_property(self, http_tools):
        for tool in http_tools:
            properties = set(_input_schema(tool).get("properties", {}))
            assert properties == {"arguments"}, (
                f"{tool.name} publishes unexpected properties: "
                f"{sorted(properties - {'arguments'})}"
            )

    async def test_arguments_is_required(self, http_tools):
        for tool in http_tools:
            assert _input_schema(tool).get("required") == ["arguments"]
