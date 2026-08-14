# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Offline tests for resolve_target_handle, the gramps_id to handle lookup.

Both defects covered here could destroy the wrong production record, so they
are exercised at the transport seam (_make_request) - the same seam
tests/test_client_merge.py uses - rather than above the client, so the bytes
that would actually leave for the server are what gets asserted on.
"""

from unittest.mock import AsyncMock, patch

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.tools.destructive import delete_type_tool
from src.gramps_mcp.utils import escape_gql_literal


def test_escape_gql_literal_neutralises_a_literal_break_out():
    """A crafted value must become an inert literal, not GQL syntax."""
    escaped = escape_gql_literal('X" or gramps_id!="X')
    assert escaped == 'X\\" or gramps_id!=\\"X'
    # Every quote in the result is preceded by a backslash, so the literal
    # `"{escaped}"` cannot be closed early.
    for index, char in enumerate(escaped):
        if char == '"':
            assert escaped[index - 1] == "\\"


def test_escape_gql_literal_escapes_the_backslash_first():
    """A backslash must not survive to escape the quote that follows it."""
    assert escape_gql_literal('a\\"b') == 'a\\\\\\"b'


class TestGqlInjection:
    async def test_a_crafted_gramps_id_cannot_break_out_of_the_gql_literal(self):
        """
        `X" or gramps_id!="X` used to close the GQL string literal early,
        matching every record; with pagesize 1 delete_type then deleted an
        arbitrary one and reported the id the caller asked for.
        """
        with patch.object(
            GrampsWebAPIClient, "_make_request", new_callable=AsyncMock
        ) as request:
            # Empty result set: the lookup must find nothing, which is the
            # correct outcome for an identifier that does not exist.
            request.return_value = []
            result = await delete_type_tool(
                {"type": "person", "gramps_id": 'X" or gramps_id!="X'}
            )

        assert "Error" in result[0].text
        assert "No person found" in result[0].text

        # Exactly one request was made - the lookup. Nothing was deleted.
        assert request.call_count == 1
        sent = request.call_args.kwargs["params"]
        assert sent["gql"] == 'gramps_id="X\\" or gramps_id!=\\"X"'
        assert request.call_args.kwargs["method"] == "GET"

    async def test_an_ordinary_gramps_id_is_still_looked_up_unchanged(self):
        """The escaping must not break the normal case."""
        with patch.object(
            GrampsWebAPIClient, "_make_request", new_callable=AsyncMock
        ) as request:
            request.side_effect = [
                [{"handle": "h1"}],
                {"handle": "h1", "gramps_id": "I0001", "backlinks": {}},
                {},
            ]
            result = await delete_type_tool({"type": "person", "gramps_id": "I0001"})

        assert "Deleted" in result[0].text
        assert request.call_args_list[0].kwargs["params"]["gql"] == 'gramps_id="I0001"'


class TestTagGrampsIdRefusal:
    async def test_a_tag_cannot_be_deleted_by_gramps_id(self):
        """
        Tags have no gramps_id, and TagSearchParams declares no gql field, so
        the filter used to be dropped by pydantic's extra="ignore" and the
        call became `GET tags/?pagesize=1` - deleting whichever tag the
        server happened to list first.
        """
        with patch.object(
            GrampsWebAPIClient, "_make_request", new_callable=AsyncMock
        ) as request:
            result = await delete_type_tool({"type": "tag", "gramps_id": "T0001"})

        text = result[0].text
        assert "Error" in text
        assert "no gramps_id" in text
        assert "handle" in text
        assert "manage_tags" in text
        # Nothing at all was sent: no tag was listed and none was deleted.
        assert request.call_count == 0

    async def test_a_tag_is_still_deletable_by_handle(self):
        """The refusal must be scoped to gramps_id, not to tags as a whole."""
        with patch.object(
            GrampsWebAPIClient, "_make_request", new_callable=AsyncMock
        ) as request:
            request.side_effect = [
                {"handle": "t1", "backlinks": {}},
                {},
            ]
            result = await delete_type_tool({"type": "tag", "handle": "t1"})

        assert "Deleted" in result[0].text
        assert request.call_args_list[-1].kwargs["method"] == "DELETE"
