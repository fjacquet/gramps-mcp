"""Concurrent get_token() must authenticate once, not once per caller."""

import asyncio

import pytest

from src.gramps_mcp.auth import AuthManager


class _FakeResponse:
    """Minimal stand-in for the token endpoint's httpx response."""

    def __init__(self, token: str) -> None:
        self._token = token

    def raise_for_status(self) -> None:
        """No-op: the fake transport never returns an error status."""

    def json(self) -> dict:
        """Return the token payload the real endpoint would return."""
        return {"access_token": self._token}


class _CountingClient:
    """Transport seam that counts token requests and yields the event loop."""

    def __init__(self) -> None:
        self.posts = 0

    async def post(self, url: str, json: dict) -> _FakeResponse:
        """Record the call, then suspend so a concurrent caller can interleave."""
        self.posts += 1
        await asyncio.sleep(0)
        return _FakeResponse(f"token-{self.posts}")


@pytest.mark.asyncio
async def test_concurrent_get_token_authenticates_once(monkeypatch):
    """Two callers racing on a cold manager share one authentication.

    Reason: collect_tree and traversal both issue their first two API calls
    through asyncio.gather. Without a lock each call sees no cached token and
    posts to /token/ simultaneously, and the Gramps auth endpoint rate-limits
    one of them.
    """
    AuthManager.reset_instance()
    manager = AuthManager()
    fake = _CountingClient()
    monkeypatch.setattr(type(manager), "client", property(lambda self: fake))

    first, second = await asyncio.gather(manager.get_token(), manager.get_token())

    assert fake.posts == 1
    assert first == second == "token-1"
    AuthManager.reset_instance()
