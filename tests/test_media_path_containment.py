"""
media_path must not read outside the configured import root.

The tool opens a local path named by the caller and uploads its bytes
into the tree, where the media API can read them back. Unconfined, that
turns any file the server process can open - including its own .env,
which holds owner-role credentials - into tree content.
"""

import os

import pytest

from src.gramps_mcp.tools.media_upload import resolve_media_path


class TestMediaPathContainment:
    def test_a_path_inside_the_root_resolves(self, tmp_path):
        target = tmp_path / "scan.jpg"
        target.write_bytes(b"x")
        assert resolve_media_path(str(target), str(tmp_path)) == str(target.resolve())

    def test_a_path_outside_the_root_is_refused(self, tmp_path):
        outside = tmp_path.parent / "outside.txt"
        outside.write_bytes(b"x")
        with pytest.raises(ValueError) as exc:
            resolve_media_path(str(outside), str(tmp_path))
        assert "import root" in str(exc.value)

    def test_a_traversal_out_of_the_root_is_refused(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_media_path(str(tmp_path / ".." / "etc" / "passwd"), str(tmp_path))

    def test_a_symlink_pointing_out_of_the_root_is_refused(self, tmp_path):
        # Reason: os.path.isfile follows symlinks, so a link inside the
        # root pointing at /app/.env passed the old check.
        outside = tmp_path.parent / "secret.txt"
        outside.write_bytes(b"x")
        link = tmp_path / "innocent.jpg"
        os.symlink(outside, link)
        with pytest.raises(ValueError):
            resolve_media_path(str(link), str(tmp_path))

    def test_a_missing_file_still_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_media_path(str(tmp_path / "absent.jpg"), str(tmp_path))
