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
Unit tests for the event place parameter. No server involved.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.event_params import EventSaveParams


class TestPlaceValidation:
    """place takes a handle, never a name."""

    def test_place_name_is_rejected(self):
        with pytest.raises(ValidationError):
            EventSaveParams(type="Birth", citation_list=[], place="Lyon")

    def test_place_name_with_spaces_is_rejected(self):
        with pytest.raises(ValidationError):
            EventSaveParams(type="Birth", citation_list=[], place="Saint-Germain")

    def test_handle_is_accepted(self):
        params = EventSaveParams(
            type="Birth", citation_list=[], place="103c4094f2414e2400974f979824"
        )

        assert params.place == "103c4094f2414e2400974f979824"

    def test_place_may_be_omitted(self):
        params = EventSaveParams(type="Birth", citation_list=[])

        assert params.place is None
