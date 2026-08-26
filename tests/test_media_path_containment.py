"""
media_path must not read outside the configured import root.

The tool opens a local path named by the caller and uploads its bytes
into the tree, where the media API can read them back. Unconfined, that
turns any file the server process can open - including its own .env,
which holds owner-role credentials - into tree content.
"""

import os

import pytest

from src.gramps_mcp.tools import media_upload
from src.gramps_mcp.tools.media_upload import resolve_media_path, upload_media_from_path


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

    def test_a_sibling_directory_sharing_the_root_s_prefix_is_refused(self, tmp_path):
        # Reason: root=".../root" and target=".../rootX/evil.txt" share the
        # string prefix ".../root" - the exact shape that defeats a check
        # built on str.startswith(root), which would see the target string
        # begin with the root string and wrongly call it contained.
        # "rootX" is a sibling directory, not a subdirectory of "root".
        # os.path.commonpath compares whole path components, not
        # characters, so it is not fooled by the shared prefix. This test
        # fails under startswith and passes under commonpath - see the
        # task-4 report for the verbatim proof of both.
        root = tmp_path / "root"
        root.mkdir()
        sibling = tmp_path / "rootX"
        sibling.mkdir()
        target = sibling / "evil.txt"
        target.write_bytes(b"x")
        with pytest.raises(ValueError):
            resolve_media_path(str(target), str(root))


class TestMediaSizeBound:
    @pytest.mark.asyncio
    async def test_the_read_is_capped_even_when_the_prior_stat_under_reports(
        self, tmp_path, monkeypatch
    ):
        """
        The upload must not trust os.path.getsize as the enforcement of
        MAX_MEDIA_BYTES: a stat and the later read are two different
        syscalls, so a file that grows between them would let a read based
        on the stat's size read past the limit (TOCTOU). This simulates
        that window directly - os.path.getsize is patched to report a size
        under the cap while the file on disk already exceeds it - so the
        only thing that can catch the oversize content is the bounded read
        itself, not the earlier stat.

        MAX_MEDIA_BYTES is monkeypatched down to a few bytes so the test
        does not need a 100 MB fixture.
        """
        monkeypatch.setattr(media_upload, "MAX_MEDIA_BYTES", 4)
        target = tmp_path / "scan.jpg"
        target.write_bytes(b"x" * 10)

        class FakeSettings:
            gramps_media_import_root = str(tmp_path)

        monkeypatch.setattr(media_upload, "get_settings", lambda: FakeSettings())
        # Reason: make the stat lie about the file's size, as it would if
        # the file grew after the stat but before the read, so this test
        # exercises only the bounded read's own enforcement.
        monkeypatch.setattr(media_upload.os.path, "getsize", lambda _path: 1)

        with pytest.raises(ValueError) as exc:
            await upload_media_from_path(None, str(target), "tree")
        assert "upload limit" in str(exc.value)
