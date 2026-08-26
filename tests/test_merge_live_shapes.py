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
Check merge_put_data against the shapes the live Gramps server returns.

The offline merge tests use hand-written records. This module fetches a
real person and a real place and asserts that a partial update of the
shape the usage guide tells the assistant to send preserves everything
the server actually stores. Read-only: it issues GETs and never writes.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.merge import merge_put_data
from src.gramps_mcp.models.api_calls import ApiCalls

pytestmark = pytest.mark.integration


class TestMergeAgainstLiveShapes:
    async def test_a_partial_name_update_preserves_every_stored_sub_key(self):
        client = GrampsWebAPIClient()
        people = await client.make_api_call(
            api_call=ApiCalls.GET_PEOPLE, params={"pagesize": 1, "page": 1}
        )
        stored = people[0]
        assert stored.get("primary_name"), "fixture person has no primary_name"

        merged = merge_put_data(
            stored, {"primary_name": {"first_name": "TestFirstName"}}
        )

        assert merged["primary_name"]["first_name"] == "TestFirstName"
        for key, value in stored["primary_name"].items():
            if key == "first_name":
                continue
            assert merged["primary_name"][key] == value, (
                f"sub-key {key} was lost by a partial update"
            )

    async def test_a_partial_place_name_update_preserves_lang_and_date(self):
        client = GrampsWebAPIClient()
        places = await client.make_api_call(
            api_call=ApiCalls.GET_PLACES, params={"pagesize": 1, "page": 1}
        )
        stored = places[0]
        if not isinstance(stored.get("name"), dict):
            pytest.skip("fixture place has no structured name object")

        merged = merge_put_data(stored, {"name": {"value": "TestPlaceName"}})

        assert merged["name"]["value"] == "TestPlaceName"
        for key, value in stored["name"].items():
            if key == "value":
                continue
            assert merged["name"][key] == value, f"sub-key {key} was lost"
