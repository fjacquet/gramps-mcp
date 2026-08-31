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
from .scan_status import people_limit_phrase, scan_status_lines

# Reason: the rules engine (genealogy/rules.py) emits only these three
# French severities. An anomaly carrying any other value (in practice, only
# the tool's own tests do this) sorts after all three known ones, rather
# than raising - rendering must never fail just because a caller handed the
# renderer a severity the engine does not itself produce.
_SEVERITY_ORDER = {"haute": 0, "moyenne": 1, "basse": 2}

MAX_PER_SEVERITY = 50
"""Cap on bullets rendered per severity group.

Measured against the live tree (~1 736 people, 2026-08-31): a whole-tree
audit produced 1 403 anomalies - 1 392 of them `basse` (mostly D1 "no vital
date" and R9 "no citation") - rendering as 1 411 lines. That is too much to
hand an LLM caller under one heading. The cap is per severity, not global,
so a handful of `haute`/`moyenne` findings are never pushed out by a long
tail of `basse` ones.
"""


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
    severity: str | None = None,
    limit: int | None = None,
) -> str:
    """
    Render the full audit_quality result as markdown.

    Order: a partial-scan warning first when the scan did not complete, then
    the count of skipped records when non-zero, then the scope actually
    examined when the caller narrowed it (`severity` and/or `limit`), then
    the anomalies themselves grouped by severity with the highest severity
    first, each group capped at `MAX_PER_SEVERITY`. A clean result (no
    anomalies) renders an explicit "no anomalies" line rather than an empty
    string - an empty answer reads exactly like a broken one - and states
    the scope it was clean *within*, so a caller who filtered or limited the
    scan is never told the whole tree is clean when only a slice was read.

    Args:
        anomalies (list[Anomaly]): Findings from check_person and
            check_family, already collected across the tree (or the
            narrowed scope named by `severity`/`limit`).
        skipped (int): Records the collector could not parse.
        partial (bool): Whether the tree scan stopped early.
        error (str | None): The error that stopped the scan, when `partial`.
        severity (str | None): The severity filter the caller applied to
            `AuditQualityParams`, if any - echoed so "no anomalies" cannot
            be misread as "no anomalies at any severity".
        limit (int | None): The `AuditQualityParams.limit` the caller
            applied, if any - echoed so "no anomalies" cannot be misread as
            "the whole tree is clean" when only the first N people were
            examined.

    Returns:
        str: Markdown ready to hand back as tool output.
    """
    sections: list[str] = scan_status_lines(partial, error, skipped)

    scope_bits: list[str] = []
    if limit is not None:
        scope_bits.append(people_limit_phrase(limit))
    if severity is not None:
        scope_bits.append(f"severity={severity!r} only")
    scope_note = f"Scope: {', '.join(scope_bits)}." if scope_bits else None
    if scope_note:
        sections.append(scope_note)

    if not anomalies:
        clean_line = (
            f"## Anomalies\n\nNone found within this scope ({', '.join(scope_bits)})."
            if scope_bits
            else "## Anomalies\n\nNone found - the tree is clean."
        )
        sections.append(clean_line)
        return "\n\n".join(sections) + "\n"

    ordered = sorted(anomalies, key=lambda a: _severity_rank(a.severity))

    grouped: dict[str, list[Anomaly]] = {}
    for anomaly in ordered:
        grouped.setdefault(anomaly.severity, []).append(anomaly)

    for group_severity, group in grouped.items():
        shown = group[:MAX_PER_SEVERITY]
        lines = "\n".join(_format_anomaly(a) for a in shown)
        remaining = len(group) - len(shown)
        section = f"## {group_severity} ({len(group)})\n\n{lines}"
        if remaining:
            # Reason: `limit` (AuditQualityParams / collect.py) is a prefix
            # of the people fetched - `raw_people[:limit]`, no offset - and
            # `severity` only removes *other* severity groups, so neither
            # narrows which anomalies land within an already-capped group.
            # There is no combination of today's parameters that reaches
            # anomaly 51 within one severity group. Advising the caller to
            # "narrow and page through" here would be false and, for an LLM
            # caller that follows it literally, would understate a tree with
            # nearly 1 400 `basse` anomalies as one with 50.
            section += (
                f"\n\n...{remaining} more {group_severity}-severity anomal"
                f"{'y' if remaining == 1 else 'ies'} not shown (cap: "
                f"{MAX_PER_SEVERITY} per severity). There is currently no "
                "way to page through them: `limit` truncates the same "
                "people from the start of every scan (no offset), and "
                "`severity` only removes other severity groups, not "
                f"entries within `{group_severity}` itself."
            )
        sections.append(section)

    return "\n\n".join(sections) + "\n"
