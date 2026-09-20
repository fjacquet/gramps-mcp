"""
The shared httpx client must identify itself with a User-Agent string.

https://gramps.discourse.group/t/gramps-web-api-client-authors-please-send-a-user-agent/10006
asks every Gramps Web API client to send tool name + version, so a server
admin can attribute an error to this tool rather than seeing an anonymous
httpx default. No network call is made here: constructing the client is
pure local config, so this stays an offline unit test.
"""

import pytest

from src.gramps_mcp import __version__
from src.gramps_mcp.auth import USER_AGENT, AuthManager


@pytest.fixture(autouse=True)
def isolated_auth_manager():
    AuthManager.reset_instance()
    yield
    AuthManager.reset_instance()


def test_shared_client_identifies_itself_with_a_user_agent():
    manager = AuthManager()
    client = manager.client

    assert client.headers["User-Agent"] == USER_AGENT
    assert client.headers["User-Agent"] == (
        f"gramps-mcp/{__version__} (+https://github.com/fjacquet/gramps-mcp)"
    )
    assert "python-httpx" not in client.headers["User-Agent"]
