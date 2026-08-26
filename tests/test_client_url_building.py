"""
URL construction must keep a caller-supplied value inside its path segment.

The value that fills a {handle} placeholder is composed by an LLM, which
reads free text out of the tree and can be induced to craft one. These
tests pin that no such value can move the request to a different endpoint.
Pure string building - no server, no transport.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient


class TestUrlParameterEncoding:
    @pytest.mark.parametrize(
        "crafted",
        [
            "../users/someuser",
            "../metadata/",
            "..%2fusers",
            ".",
            "..",
            "a/../../../",
            "abc?keys=x",
            "abc#frag",
            "//evil.example.com/steal",
        ],
    )
    def test_a_crafted_handle_cannot_leave_its_endpoint(self, crafted):
        # Reason: str.replace plus urljoin resolved ".." and treated "?" as
        # a query separator, so delete_type(handle="../users/x") issued a
        # DELETE against /api/users/x while reporting it deleted a person.
        client = GrampsWebAPIClient()
        url = client._build_url_with_substitution(
            "default", "people/{handle}", {"handle": crafted}
        )
        assert "/api/people/" in url
        assert "/api/users" not in url
        assert "/api/metadata" not in url
        assert "?" not in url
        assert "#" not in url
        # Reason: the whole crafted value must sit in the single segment
        # after /api/people/, so nothing after that prefix may be a slash.
        tail = url.split("/api/people/", 1)[1]
        assert "/" not in tail

    def test_an_ordinary_handle_is_unchanged(self):
        client = GrampsWebAPIClient()
        url = client._build_url_with_substitution(
            "default", "people/{handle}", {"handle": "103bcbfa97824cbb051f1c7a28b"}
        )
        assert url.endswith("/api/people/103bcbfa97824cbb051f1c7a28b")

    def test_the_api_prefix_survives_an_endpoint_with_a_leading_slash(self):
        # Reason: urljoin discards the base path when the second argument
        # starts with "/", silently dropping the /api prefix.
        client = GrampsWebAPIClient()
        assert "/api/people/" in client._build_url("default", "/people/x")
