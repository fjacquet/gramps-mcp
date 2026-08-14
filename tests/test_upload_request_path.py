"""
The media upload must inherit the shared request path's error handling.

No server is needed: only httpx's transport is replaced. The responses are
real httpx.Response objects and every assertion reads what the client returns
or raises.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.gramps_mcp.client import GrampsAPIError, GrampsWebAPIClient


class TestUploadSharedRequestPath:
    """upload_media_file must behave like every other call."""

    @pytest.mark.asyncio
    async def test_connect_error_becomes_gramps_api_error(self):
        """An unreachable server must not leak httpx.ConnectError."""
        client = GrampsWebAPIClient()
        with (
            patch.object(client.auth_manager, "get_token", AsyncMock(return_value="t")),
            # Reason: AuthManager.get_headers is synchronous, so the stub is
            # synchronous too - an async stub would hand the client a
            # coroutine where it expects a header mapping.
            patch.object(client.auth_manager, "get_headers", return_value={}),
            patch.object(
                client.auth_manager.client,
                "request",
                AsyncMock(side_effect=httpx.ConnectError("no route")),
            ),
        ):
            with pytest.raises(GrampsAPIError) as excinfo:
                await client.upload_media_file(b"bytes", "image/jpeg")

        assert "Cannot connect to Gramps API" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_timeout_becomes_gramps_api_error(self):
        """A slow server must not leak httpx.TimeoutException."""
        client = GrampsWebAPIClient()
        with (
            patch.object(client.auth_manager, "get_token", AsyncMock(return_value="t")),
            patch.object(client.auth_manager, "get_headers", return_value={}),
            patch.object(
                client.auth_manager.client,
                "request",
                AsyncMock(side_effect=httpx.TimeoutException("too slow")),
            ),
        ):
            with pytest.raises(GrampsAPIError) as excinfo:
                await client.upload_media_file(b"bytes", "image/jpeg")

        assert "Request timeout" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_401_refreshes_the_token_and_retries(self):
        """A stale token must be refreshed once, not surfaced to the caller."""
        request = httpx.Request("POST", "http://example.invalid/api/media/")
        unauthorised = httpx.Response(401, request=request)
        created = httpx.Response(
            200, json=[{"new": {"handle": "abc123"}}], request=request
        )
        client = GrampsWebAPIClient()
        with (
            patch.object(client.auth_manager, "get_token", AsyncMock(return_value="t")),
            patch.object(client.auth_manager, "get_headers", return_value={}),
            patch.object(
                client.auth_manager, "authenticate", AsyncMock()
            ) as authenticate,
            patch.object(
                client.auth_manager.client,
                "request",
                AsyncMock(side_effect=[unauthorised, created]),
            ),
        ):
            result = await client.upload_media_file(b"bytes", "image/jpeg")

        assert authenticate.await_count == 1
        assert result == [{"new": {"handle": "abc123"}}]

    @pytest.mark.asyncio
    async def test_uploaded_bytes_reach_the_server(self):
        """The file bytes must survive the shared request path, including the
        401 retry - a retry that dropped them would upload an empty file."""
        request = httpx.Request("POST", "http://example.invalid/api/media/")
        # Reason: a real transport, so the request the client builds is a real
        # httpx.Request whose body is read back out of the response object it
        # produced, not out of a mock's recorded call arguments.
        seen: list[bytes] = []
        responses = [
            httpx.Response(401, request=request),
            httpx.Response(200, json=[{"new": {"handle": "abc123"}}]),
        ]

        async def handler(sent: httpx.Request) -> httpx.Response:
            seen.append(sent.content)
            return responses[len(seen) - 1]

        client = GrampsWebAPIClient()
        with (
            patch.object(client.auth_manager, "get_token", AsyncMock(return_value="t")),
            patch.object(client.auth_manager, "get_headers", return_value={}),
            patch.object(client.auth_manager, "authenticate", AsyncMock()),
            # Reason: only the transport is swapped, so the request the client
            # builds is a real httpx.Request carrying a real body.
            patch.object(
                client.auth_manager.client, "_transport", httpx.MockTransport(handler)
            ),
        ):
            result = await client.upload_media_file(b"real bytes", "image/jpeg")

        assert result == [{"new": {"handle": "abc123"}}]
        assert seen == [b"real bytes", b"real bytes"]

    @pytest.mark.asyncio
    async def test_mime_type_is_sent_as_content_type(self):
        """The upload's own Content-Type must override the JSON default that
        _get_headers builds."""
        seen: list[str | None] = []

        async def handler(sent: httpx.Request) -> httpx.Response:
            seen.append(sent.headers.get("content-type"))
            return httpx.Response(200, json=[{"new": {"handle": "abc123"}}])

        client = GrampsWebAPIClient()
        with (
            patch.object(client.auth_manager, "get_token", AsyncMock(return_value="t")),
            patch.object(
                client.auth_manager,
                "get_headers",
                return_value={
                    "Authorization": "Bearer t",
                    "Content-Type": "application/json",
                },
            ),
            patch.object(
                client.auth_manager.client, "_transport", httpx.MockTransport(handler)
            ),
        ):
            await client.upload_media_file(b"bytes", "image/tiff")

        assert seen == ["image/tiff"]
