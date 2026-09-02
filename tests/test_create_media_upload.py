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
create_media must not choke on the media object its own upload returns.

The create branch used to echo the freshly uploaded record back into the
follow-up PUT. Filtering that record to MediaSaveParams' top-level fields
kept `date`, whose value is a raw Gramps Date carrying `_class`,
`calendar`, `format`, `newyear` and `sortval` - five keys DateValue
refuses under extra="forbid". Every upload therefore ended in a
validation error *after* the media record had already been created, so
the caller saw a failure for a record that existed.

Only the transport is replaced here; the tool, its parameter models and
the client's own validation all run for real, and the assertions read the
text the tool returns.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.tools import data_management, media_upload

# Reason: the `date` sub-object is the raw Gramps serialisation, not the
# four fields DateValue declares. It is the whole point of this fixture -
# trimming it here would test nothing.
RAW_MEDIA_OBJECT = {
    "_class": "Media",
    "handle": "a1b2c3d4e5f6a7b8c9d0",
    "gramps_id": "O0042",
    "path": "a1b2c3d4e5f6.jpg",
    "mime": "image/jpeg",
    "desc": "",
    "checksum": "9e107d9d372bb6826bd81d3542a419d6",
    "date": {
        "_class": "Date",
        "calendar": 0,
        "dateval": [0, 0, 0, False],
        "format": None,
        "modifier": 0,
        "newyear": 0,
        "quality": 0,
        "sortval": 0,
        "text": "",
    },
    "change": 1756800000,
    "private": False,
    "tag_list": [],
    "citation_list": [],
    "note_list": [],
    "attribute_list": [],
    "thumb": None,
}


class FakeSettings:
    """Settings stub: import root points at the test's own directory."""

    gramps_tree_id = "test_tree"

    def __init__(self, import_root: str) -> None:
        """
        Record the directory media_path values must resolve inside.

        Args:
            import_root (str): The test's own temporary directory.
        """
        self.gramps_media_import_root = import_root


async def _fake_transport(method: str, url: str, **kwargs: object) -> object:
    """Answer every request with the raw record the real server returns."""
    if method == "POST":
        return [{"new": dict(RAW_MEDIA_OBJECT)}]
    return dict(RAW_MEDIA_OBJECT)


@pytest.fixture
def staged_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Write a file inside a patched import root and return its path."""
    settings = FakeSettings(str(tmp_path))
    monkeypatch.setattr(media_upload, "get_settings", lambda: settings)
    monkeypatch.setattr(data_management, "get_settings", lambda: settings)
    scan = tmp_path / "acte-1878.jpg"
    scan.write_bytes(b"jpeg bytes")
    return str(scan)


class TestCreateMediaUpload:
    """The create branch of create_media_tool, transport stubbed."""

    @pytest.mark.asyncio
    async def test_uploading_a_file_reports_success(self, staged_scan):
        with patch.object(
            GrampsWebAPIClient,
            "_make_request",
            new=AsyncMock(side_effect=_fake_transport),
        ):
            result = await data_management.create_media_tool(
                {"desc": "Acte de naissance 1878", "media_path": staged_scan}
            )

        text = result[0].text
        assert "Extra inputs are not permitted" not in text
        assert "Successfully created media" in text

    @pytest.mark.asyncio
    async def test_the_servers_own_date_object_is_never_revalidated(self, staged_scan):
        """
        The five keys below are exactly what the raw Date carries beyond
        DateValue's declared fields. Naming them keeps this test tied to the
        defect rather than to a generic "no error" check.
        """
        with patch.object(
            GrampsWebAPIClient,
            "_make_request",
            new=AsyncMock(side_effect=_fake_transport),
        ):
            result = await data_management.create_media_tool(
                {"desc": "Acte de naissance 1878", "media_path": staged_scan}
            )

        text = result[0].text
        for server_field in ("_class", "calendar", "newyear", "sortval", "format"):
            assert f"date.{server_field}" not in text
