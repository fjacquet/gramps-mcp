"""
Backup pair selection - the only part of seeding that is pure.

Seeding the XML without its media archive leaves every media object
pointing at a file that is not there, which surfaces much later as
puzzling test failures rather than as a seeding error. The selection
therefore refuses a date that has only one half.
"""

import pytest

from scripts.seed_test_tree import newest_backup_pair


def _pair(directory, stamp, xml=True, media=True):
    """Write one or both halves of a backup for the given date stamp."""
    if xml:
        (directory / f"tree-{stamp}.gramps.gz").write_bytes(b"x")
    if media:
        (directory / f"media-{stamp}.zip").write_bytes(b"x")


class TestNewestBackupPair:
    """Which backup the seed script restores."""

    def test_the_newest_complete_pair_wins(self, tmp_path):
        _pair(tmp_path, "2026-08-01")
        _pair(tmp_path, "2026-09-02")
        xml, media = newest_backup_pair(tmp_path)
        assert xml.name == "tree-2026-09-02.gramps.gz"
        assert media.name == "media-2026-09-02.zip"

    def test_a_date_missing_its_media_archive_is_not_used(self, tmp_path):
        _pair(tmp_path, "2026-08-01")
        _pair(tmp_path, "2026-09-02", media=False)
        xml, media = newest_backup_pair(tmp_path)
        assert xml.name == "tree-2026-08-01.gramps.gz"
        assert media.name == "media-2026-08-01.zip"

    def test_a_date_missing_its_xml_is_not_used(self, tmp_path):
        _pair(tmp_path, "2026-08-01")
        _pair(tmp_path, "2026-09-02", xml=False)
        xml, _ = newest_backup_pair(tmp_path)
        assert xml.name == "tree-2026-08-01.gramps.gz"

    def test_an_empty_directory_names_the_backup_script(self, tmp_path):
        with pytest.raises(FileNotFoundError) as exc:
            newest_backup_pair(tmp_path)
        assert "backup_prod.py" in str(exc.value)

    def test_a_directory_of_halves_only_names_the_backup_script(self, tmp_path):
        _pair(tmp_path, "2026-09-02", media=False)
        with pytest.raises(FileNotFoundError) as exc:
            newest_backup_pair(tmp_path)
        assert "backup_prod.py" in str(exc.value)
