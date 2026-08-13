"""
Unit tests for HTTP error formatting. These construct real httpx objects and
need no server.
"""

import httpx

from src.gramps_mcp.client import MAX_ERROR_DETAIL, GrampsWebAPIClient

# Reason: imported (not hardcoded) so this test breaks loudly if the source
# constant changes without the test being updated to match.
MAX_DETAIL = MAX_ERROR_DETAIL


def _error_with(status_code: int, **response_kwargs) -> httpx.HTTPStatusError:
    """
    Build a real HTTPStatusError carrying the given response.

    Args:
        status_code (int): HTTP status to simulate.
        **response_kwargs: Passed to httpx.Response, for example json= or text=.

    Returns:
        httpx.HTTPStatusError: The exception httpx itself would raise.
    """
    request = httpx.Request("POST", "http://example.org/api/places/")
    response = httpx.Response(status_code, request=request, **response_kwargs)
    return httpx.HTTPStatusError("error", request=request, response=response)


class TestErrorDetail:
    """The server's explanation must survive."""

    def test_json_message_is_appended(self):
        client = GrampsWebAPIClient()
        error = _error_with(422, json={"message": "'place_type' is required"})

        formatted = client._format_http_error(error)

        assert "Invalid data provided" in formatted
        assert "place_type" in formatted

    def test_plain_text_body_is_appended(self):
        client = GrampsWebAPIClient()
        error = _error_with(422, text="place_type missing")

        formatted = client._format_http_error(error)

        assert "place_type" in formatted

    def test_long_body_is_truncated(self):
        client = GrampsWebAPIClient()
        error = _error_with(422, text="x" * 5000)

        formatted = client._format_http_error(error)

        # The body must actually have been included (not silently dropped)...
        assert "x" * 50 in formatted
        # ...cut off with a visible marker rather than just happening to be
        # short...
        assert formatted.endswith("...")
        # ...and cut exactly at MAX_DETAIL, not some other round number, so
        # the assertion is pinned to the source constant rather than to an
        # arbitrary length like 1000.
        expected = f"Invalid data provided. {'x' * MAX_DETAIL}..."
        assert formatted == expected

    def test_empty_body_keeps_the_generic_message(self):
        client = GrampsWebAPIClient()
        error = _error_with(422, text="")

        formatted = client._format_http_error(error)

        assert formatted == "Invalid data provided."

    def test_detail_is_added_for_other_statuses_too(self):
        client = GrampsWebAPIClient()
        error = _error_with(409, json={"message": "user already exists"})

        formatted = client._format_http_error(error)

        assert "already exists" in formatted

    def test_unparseable_body_does_not_raise(self):
        client = GrampsWebAPIClient()
        error = _error_with(500, content=b"\xff\xfe not valid utf-8")

        formatted = client._format_http_error(error)

        assert "Server error" in formatted

    def test_json_list_body_does_not_raise(self):
        client = GrampsWebAPIClient()
        error = _error_with(422, json=["place_type", "is required"])

        formatted = client._format_http_error(error)

        assert "place_type" in formatted

    def test_message_key_wins_over_error_and_detail(self):
        client = GrampsWebAPIClient()
        error = _error_with(
            422,
            json={
                "message": "'place_type' is required",
                "error": "should not appear",
                "detail": "should not appear either",
            },
        )

        formatted = client._format_http_error(error)

        assert "place_type" in formatted
        assert "should not appear" not in formatted
