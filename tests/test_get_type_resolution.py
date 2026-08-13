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
Integration tests for resolving a gramps_id in get_type.
"""

import pytest

from src.gramps_mcp.tools.search_details import get_type_tool


class TestGetTypeResolution:
    """A gramps_id resolves through the API, and a missing one says so."""

    @pytest.mark.asyncio
    async def test_known_gramps_id_resolves(self):
        result = await get_type_tool({"type": "person", "gramps_id": "I0076"})
        text = result[0].text

        assert "not yet implemented" not in text
        assert "I0076" in text

    @pytest.mark.asyncio
    async def test_missing_gramps_id_says_not_found(self):
        result = await get_type_tool({"type": "person", "gramps_id": "I999999"})
        text = result[0].text

        # Reason: this used to report the tool as unimplemented, because the
        # regex found no bracket to scrape and both branches fell through.
        assert "not yet implemented" not in text
        assert "I999999" in text

    @pytest.mark.asyncio
    async def test_handle_still_works(self):
        by_id = await get_type_tool({"type": "person", "gramps_id": "I0076"})
        assert "not yet implemented" not in by_id[0].text
