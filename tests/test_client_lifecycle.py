"""
Integration tests for HTTP client lifecycle against the real Gramps API.
"""

import asyncio

import pytest

from src.gramps_mcp.auth import AuthManager
from src.gramps_mcp.tools.records_tools import get_facts_tool
from src.gramps_mcp.tools.user_tools import manage_users_tool

pytestmark = pytest.mark.integration


class TestSharedClientLifecycle:
    """The AuthManager singleton owns one client for the process lifetime."""

    @pytest.mark.asyncio
    async def test_pool_survives_a_tool_call(self):
        # Reason: a tool call must not close the pool other calls are using.
        # Read _client directly - the public `client` property recreates a
        # closed client on access, which would mask the very bug under test.
        await get_facts_tool({})
        auth = AuthManager()
        assert auth._client is not None
        assert not auth._client.is_closed

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls_all_succeed(self):
        results = await asyncio.gather(
            get_facts_tool({}),
            manage_users_tool({"action": "list"}),
            get_facts_tool({}),
            manage_users_tool({"action": "list"}),
        )
        for result in results:
            assert "error" not in result[0].text.lower()
