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

"""
Markdown rendering for the deterministic quality-audit results.

No I/O: everything here operates on an in-memory list of Anomaly objects,
already produced by `genealogy.rules.check_person` and
`genealogy.rules.check_family`.
"""

from ..genealogy.domain import Anomaly

# Reason: the rules engine (genealogy/rules.py) emits only these three
# French severities. An anomaly carrying any other value (in practice, only
# the tool's own tests do this) sorts after all three known ones, rather
# than raising - rendering must never fail just because a caller handed the
# renderer a severity the engine does not itself produce.
_SEVERITY_ORDER = {"haute": 0, "moyenne": 1, "basse": 2}


def _severity_rank(severity: str) -> int:
    """Rank a severity for sorting, highest first. Unknown values sort last."""
    return _SEVERITY_ORDER.get(severity, len(_SEVERITY_ORDER))


def _format_anomaly(anomaly: Anomaly) -> str:
    """
    Render one anomaly as a single markdown bullet.

    Args:
        anomaly (Anomaly): One anomaly from check_person or check_family.

    Returns:
        str: For example "- **R1** I0001: Naissance postérieure au déces.".
    """
    return f"- **{anomaly.rule}** {anomaly.gramps_id}: {anomaly.message}"


def format_anomalies(
    anomalies: list[Anomaly],
    skipped: int,
    partial: bool,
    error: str | None,
) -> str:
    """
    Render the full audit_quality result as markdown.

    Order: a partial-scan warning first when the scan did not complete, then
    the count of skipped records when non-zero, then the anomalies
    themselves grouped by severity with the highest severity first. A clean
    result (no anomalies) renders an explicit "no anomalies" line rather
    than an empty string - an empty answer reads exactly like a broken one.

    Args:
        anomalies (list[Anomaly]): Findings from check_person and
            check_family, already collected across the tree.
        skipped (int): Records the collector could not parse.
        partial (bool): Whether the tree scan stopped early.
        error (str | None): The error that stopped the scan, when `partial`.

    Returns:
        str: Markdown ready to hand back as tool output.
    """
    sections: list[str] = []

    # Reason: a partial scan must be stated before any finding - a caller
    # who reads "no anomalies" over half a tree has been told a clean bill
    # of health that was never established.
    if partial:
        sections.append(
            f"**Partial scan**: {error or 'unknown error'}. Results below "
            "cover only what was read before the scan stopped."
        )

    if skipped:
        sections.append(f"{skipped} record(s) were unreadable and skipped.")

    if not anomalies:
        sections.append("## Anomalies\n\nNone found - the tree is clean.")
        return "\n\n".join(sections) + "\n"

    ordered = sorted(anomalies, key=lambda a: _severity_rank(a.severity))

    grouped: dict[str, list[Anomaly]] = {}
    for anomaly in ordered:
        grouped.setdefault(anomaly.severity, []).append(anomaly)

    for severity, group in grouped.items():
        lines = "\n".join(_format_anomaly(a) for a in group)
        sections.append(f"## {severity} ({len(group)})\n\n{lines}")

    return "\n\n".join(sections) + "\n"
