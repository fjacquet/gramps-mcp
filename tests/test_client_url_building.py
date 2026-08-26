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


def _assert_confined_to_people_endpoint(value: str, *, anchored: bool = False) -> None:
    """
    Assert value carries the people endpoint and none of the escape
    surfaces a crafted handle could otherwise reach.

    Shared by the constructed URL string and the wire request's raw_path -
    the two representations a crafted handle passes through before this
    test is satisfied. The endpoint-presence check differs between them:
    the constructed string carries a scheme and host before the path, so
    the endpoint can only be asserted present; the wire's raw_path is the
    path alone, so it can be asserted to start with the endpoint.

    Args:
        value (str): The constructed URL, or the wire request's raw_path.
        anchored (bool): True for the wire's raw_path, where the endpoint
            must be the very start of what is actually sent, not merely
            present somewhere in the value.
    """
    if anchored:
        assert value.startswith("/api/people/")
    else:
        assert "/api/people/" in value
    assert "/api/users" not in value
    assert "/api/metadata" not in value
    assert "?" not in value
    assert "#" not in value


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
        _assert_confined_to_people_endpoint(url)

        # Reason: the whole crafted value must remain one path segment on
        # the wire - the constructed string is not the exploitable surface,
        # httpx normalises dot segments when it builds the request. This
        # segment-boundary assertion is the actual point of the test and
        # stays here rather than moving into the shared helper: it only
        # applies to what is actually sent, not to the constructed string.
        sent = httpx.Request("GET", url).url.raw_path.decode()
        _assert_confined_to_people_endpoint(sent, anchored=True)
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
