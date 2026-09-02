"""
The token endpoint is rate limited; authentication must wait, not fail.

Gramps Web caps /token/ at one request per second
(gramps_webapi/api/resources/token.py). Anything that authenticates
several clients in quick succession - the integration suite does exactly
that - gets an HTTP 429 that used to surface to the caller as
"Authentication failed: HTTP 429", an error about nothing being wrong.

Only the transport is replaced here. AuthManager's own retry, token
parsing and expiry handling all run for real, and the assertions read
what authenticate() returns.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.gramps_mcp.auth import AuthManager


def _response(status: int, payload: dict | None = None) -> httpx.Response:
    """Build a real httpx.Response bound to a request, as httpx would."""
    return httpx.Response(
        status_code=status,
        json=payload if payload is not None else {},
        request=httpx.Request("POST", "http://localhost/api/token/"),
    )


# Reason: a JWT with no exp claim. authenticate() decodes it without
# verifying the signature, so any well-formed token works here.
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LW93bmVyIn0.c2lnbmF0dXJl"


@pytest.fixture(autouse=True)
def isolated_auth_manager():
    """
    Give each test its own AuthManager and leave none behind.

    Reason: AuthManager is a process-wide singleton. Without this, the
    fake token minted below survives into every later test in the same
    run, and the integration tests then present it to the real server,
    which refuses it with "Signature verification failed".
    """
    AuthManager.reset_instance()
    yield
    AuthManager.reset_instance()


class TestTokenRateLimit:
    """What authenticate() does with HTTP 429."""

    @pytest.mark.asyncio
    async def test_a_rate_limited_request_is_retried_and_succeeds(self, monkeypatch):
        monkeypatch.setattr("src.gramps_mcp.auth.RATE_LIMIT_RETRY_SECONDS", 0.01)
        manager = AuthManager()
        post = AsyncMock(
            side_effect=[
                _response(429, {"code": 429, "status": "Too Many Requests"}),
                _response(200, {"access_token": TOKEN}),
            ]
        )
        with patch.object(
            type(manager), "client", property(lambda _self: post_client(post))
        ):
            token = await manager.authenticate()
        assert token == TOKEN

    @pytest.mark.asyncio
    async def test_an_endless_rate_limit_still_reports_the_status(self, monkeypatch):
        monkeypatch.setattr("src.gramps_mcp.auth.RATE_LIMIT_RETRY_SECONDS", 0.01)
        manager = AuthManager()
        post = AsyncMock(return_value=_response(429, {"code": 429}))
        with patch.object(
            type(manager), "client", property(lambda _self: post_client(post))
        ):
            with pytest.raises(ValueError) as exc:
                await manager.authenticate()
        assert "429" in str(exc.value)

    @pytest.mark.asyncio
    async def test_a_wrong_password_is_not_retried(self, monkeypatch):
        monkeypatch.setattr("src.gramps_mcp.auth.RATE_LIMIT_RETRY_SECONDS", 0.01)
        manager = AuthManager()
        post = AsyncMock(return_value=_response(403, {}))
        with patch.object(
            type(manager), "client", property(lambda _self: post_client(post))
        ):
            with pytest.raises(ValueError) as exc:
                await manager.authenticate()
        assert "Invalid username or password" in str(exc.value)


class _Client:
    """Minimal stand-in exposing the one method authenticate() calls."""

    def __init__(self, post):
        self.post = post


def post_client(post):
    """Wrap a mock post callable in an object shaped like httpx.AsyncClient."""
    return _Client(post)
