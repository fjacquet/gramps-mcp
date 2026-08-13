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
from src.gramps_mcp.models.parameters.place_params import PlaceSaveParams


class TestPlaceValidation:
    """place takes a handle, never a name."""

    def test_place_name_is_rejected(self):
        with pytest.raises(ValidationError):
            EventSaveParams(type="Birth", citation_list=[], place="Lyon")

    def test_place_name_with_spaces_is_rejected(self):
        with pytest.raises(ValidationError):
            EventSaveParams(type="Birth", citation_list=[], place="Saint-Germain")

    def test_rejection_message_carries_guidance(self):
        """The raised error must tell the caller what to do, not just fail.

        A bare Pydantic ``pattern=`` constraint raises a generic message
        that drops the field's description, leaving the caller with no clue
        how to fix the call. This asserts the actual guidance text is
        present in the raised error, not merely that a ValidationError was
        raised.
        """
        with pytest.raises(ValidationError) as exc_info:
            EventSaveParams(type="Birth", citation_list=[], place="Lyon")

        message = str(exc_info.value)
        assert "handle" in message
        assert "name" in message
        assert "find_type" in message
        assert "Lyon" in message

    def test_handle_is_accepted(self):
        params = EventSaveParams(
            type="Birth", citation_list=[], place="103c4094f2414e2400974f979824"
        )

        assert params.place == "103c4094f2414e2400974f979824"

    def test_place_may_be_omitted(self):
        params = EventSaveParams(type="Birth", citation_list=[])

        assert params.place is None

    def test_handle_with_trailing_newline_is_rejected(self):
        """re.match + a "$"-anchored pattern accepts a trailing newline,

        because "$" matches just before a final newline. A handle carrying
        one is not a valid handle and must be rejected the same as any
        other malformed value.
        """
        with pytest.raises(ValidationError):
            EventSaveParams(
                type="Birth",
                citation_list=[],
                place="103c4094f2414e2400974f979824\n",
            )


class TestPlaceListShapeValidation:
    """alt_names and media_list take PlaceName/MediaRef objects, not strings.

    Both fields moved from list[str] to list[dict[str, Any]] on this
    branch, so a caller following the old shape now hits a generic
    Pydantic dict-coercion error. These assert the refusal names the
    expected object shape instead.
    """

    def test_media_list_string_entry_is_rejected(self):
        with pytest.raises(ValidationError):
            PlaceSaveParams(
                name={"value": "Somewhere"},
                media_list=["103c4094f2414e2400974f979824"],
            )

    def test_media_list_rejection_message_carries_guidance(self):
        with pytest.raises(ValidationError) as exc_info:
            PlaceSaveParams(
                name={"value": "Somewhere"},
                media_list=["103c4094f2414e2400974f979824"],
            )

        message = str(exc_info.value)
        assert "ref" in message
        assert "103c4094f2414e2400974f979824" in message

    def test_alt_names_string_entry_is_rejected(self):
        with pytest.raises(ValidationError):
            PlaceSaveParams(name={"value": "Somewhere"}, alt_names=["Lugdunum"])

    def test_alt_names_rejection_message_carries_guidance(self):
        with pytest.raises(ValidationError) as exc_info:
            PlaceSaveParams(name={"value": "Somewhere"}, alt_names=["Lugdunum"])

        message = str(exc_info.value)
        assert "value" in message
        assert "Lugdunum" in message

    def test_media_list_with_ref_objects_is_accepted(self):
        params = PlaceSaveParams(
            name={"value": "Somewhere"},
            media_list=[{"ref": "103c4094f2414e2400974f979824"}],
        )

        assert params.media_list == [{"ref": "103c4094f2414e2400974f979824"}]

    def test_alt_names_with_value_objects_is_accepted(self):
        params = PlaceSaveParams(
            name={"value": "Somewhere"}, alt_names=[{"value": "Lugdunum"}]
        )

        assert params.alt_names == [{"value": "Lugdunum"}]
