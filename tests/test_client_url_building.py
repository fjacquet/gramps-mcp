"""
URL construction must keep a caller-supplied value inside its path segment.

The value that fills a {handle} placeholder is composed by an LLM, which
reads free text out of the tree and can be induced to craft one. These
tests pin that no such value can move the request to a different endpoint.
Pure string building - no server, no transport.
"""

import httpx
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
        # Reason: the whole crafted value must remain one path segment on
        # the wire - the constructed string is not the exploitable surface,
        # httpx normalises dot segments when it builds the request.
        sent = httpx.Request("GET", url).url.raw_path.decode()
        assert sent.startswith("/api/people/")
        assert "/api/users" not in sent
        assert "/api/metadata" not in sent
        assert "?" not in sent
        assert "#" not in sent
        assert "/" not in sent.split("/api/people/", 1)[1]

    def test_an_ordinary_handle_is_unchanged(self):
        client = GrampsWebAPIClient()
        url = client._build_url_with_substitution(
            "default", "people/{handle}", {"handle": "103bcbfa97824cbb051f1c7a28b"}
        )
        assert url.endswith("/api/people/103bcbfa97824cbb051f1c7a28b")
        # Reason: assert the raw_path ends with the hex handle unmodified,
        # so we know the encoding did not damage the normal path.
        sent = httpx.Request("GET", url).url.raw_path.decode()
        assert sent.endswith("/api/people/103bcbfa97824cbb051f1c7a28b")

    def test_the_api_prefix_survives_an_endpoint_with_a_leading_slash(self):
        # Reason: urljoin discards the base path when the second argument
        # starts with "/", silently dropping the /api prefix.
        client = GrampsWebAPIClient()
        assert "/api/people/" in client._build_url("default", "/people/x")
