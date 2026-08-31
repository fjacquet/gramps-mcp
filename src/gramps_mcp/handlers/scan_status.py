# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2026 cabout.me
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

"""Shared markdown preamble for the two collect_tree-backed detection tools.

`audit_handler.format_anomalies` and `duplicates_handler.format_duplicate_clusters`
both open with the same partial-scan warning and skipped-record count, since
both render a `CollectResult`. One source keeps the wording - delicate,
already corrected once - from drifting apart between the two.
"""


def scan_status_lines(partial: bool, error: str | None, skipped: int) -> list[str]:
    """
    Render the partial-scan warning and skipped-record count, if any apply.

    Order: a partial-scan warning first when the scan did not complete, then
    the count of skipped records when non-zero. A partial scan must be
    stated before any finding - a caller who reads "no anomalies" or "no
    duplicates" over half a tree has been told a clean bill of health that
    was never established.

    Args:
        partial (bool): Whether the tree scan stopped early.
        error (str | None): The error that stopped the scan, when `partial`.
        skipped (int): Records the collector could not parse.

    Returns:
        list[str]: Zero, one or two markdown lines to prepend to the
        caller's own sections, in the order they should appear.
    """
    lines: list[str] = []
    if partial:
        lines.append(
            f"**Partial scan**: {error or 'unknown error'}. Results below "
            "cover only what was read before the scan stopped."
        )
    if skipped:
        lines.append(f"{skipped} record(s) were unreadable and skipped.")
    return lines
