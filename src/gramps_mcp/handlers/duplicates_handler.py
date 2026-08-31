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
Markdown rendering for duplicate-detection results.

No I/O: everything here operates on an in-memory list of MergeCluster and
MergePair objects, already produced by `genealogy.duplicates.etager` and
`genealogy.merge_plan.plan_fusions`.
"""

from ..genealogy.domain import MergeCluster, MergePair, PersonFacts
from ..genealogy.duplicates import MAX_BLOC


def _name(person: PersonFacts | None, gramps_id: str) -> str:
    """
    Render a short label for a person, falling back to the id alone.

    Args:
        person (PersonFacts | None): The person's facts, if still on hand.
        gramps_id (str): Its gramps_id, always available.

    Returns:
        str: For example "Jean Jacquet (I0001)", or "(I0001)" when the
        facts are not in the lookup handed to the renderer.
    """
    if person is None:
        return f"({gramps_id})"
    return f"{person.name} ({gramps_id})"


def _format_cluster(
    cluster: MergeCluster, people_by_handle: dict[str, PersonFacts]
) -> str:
    """
    Render one proved cluster: the phoenix, why it was chosen, and each titanic.

    Args:
        cluster (MergeCluster): One `tier == "auto"` cluster from `plan_fusions`.
        people_by_handle (dict[str, PersonFacts]): Facts keyed by handle, for
            naming the people involved.

    Returns:
        str: A markdown bullet list, one cluster.
    """
    phoenix = people_by_handle.get(cluster.phoenix_handle)
    lines = [
        f"- **{_name(phoenix, cluster.phoenix_gramps_id)}** survives "
        "(highest completeness score)."
    ]
    for handle, gramps_id in zip(
        cluster.titanic_handles, cluster.titanic_gramps_ids, strict=True
    ):
        titanic = people_by_handle.get(handle)
        lines.append(f"  - merges into it: {_name(titanic, gramps_id)}")
    if cluster.gender_patch is not None:
        sex = "M" if cluster.gender_patch == 1 else "F"
        lines.append(
            f"  - **Apply gender patch before merging**: set the phoenix's "
            f"gender to {sex} - `Person.merge()` does not carry it over."
        )
    return "\n".join(lines)


def _format_arbitration_pair(pair: MergePair) -> str:
    """
    Render one pair needing human review, never as an established match.

    Args:
        pair (MergePair): A `tier == "arbitrage"` pair.

    Returns:
        str: A single markdown bullet.
    """
    blocs = ", ".join(pair.blocs)
    return f"- {pair.gramps_id_a} <-> {pair.gramps_id_b} (blocked on {blocs})"


def format_duplicate_clusters(
    clusters: list[MergeCluster],
    arbitration_pairs: list[MergePair],
    people_by_handle: dict[str, PersonFacts],
    skipped: int,
    partial: bool,
    error: str | None,
    ignored: int = 0,
) -> str:
    """
    Render the full find_duplicates result as markdown.

    Order: a partial-scan warning first when the scan did not complete, then
    the count of skipped records and ignored blocking keys when non-zero,
    then the proved clusters (each naming its phoenix and titanics), and
    finally the pairs still needing human arbitration under their own
    heading. The two groups are never merged under one heading - a pair the
    rules could not prove must never read like a pair the rules proved.

    Args:
        clusters (list[MergeCluster]): Proved clusters (`tier == "auto"`
            pairs only), from `plan_fusions`.
        arbitration_pairs (list[MergePair]): Pairs with `tier == "arbitrage"`,
            carried separately because `plan_fusions` drops them.
        people_by_handle (dict[str, PersonFacts]): Facts keyed by handle.
        skipped (int): Records the collector could not parse.
        partial (bool): Whether the tree scan stopped early.
        error (str | None): The error that stopped the scan, when `partial`.
        ignored (int): Blocking keys dropped by `etager` for covering more
            than `MAX_BLOC` people (`duplicates.candidate_pairs`'s second
            return value). Every pair that would only have been found
            through one of those keys is silently absent from both sections
            below - render the count so a narrowed scan does not read as a
            full one.

    Returns:
        str: Markdown ready to hand back as tool output.
    """
    sections: list[str] = []

    # Reason: a partial scan must be stated before any finding - a caller who
    # reads "no duplicates" over half a tree has been told a clean bill of
    # health that was never established.
    if partial:
        sections.append(
            f"**Partial scan**: {error or 'unknown error'}. Results below "
            "cover only what was read before the scan stopped."
        )

    if skipped:
        sections.append(f"{skipped} record(s) were unreadable and skipped.")

    if ignored:
        sections.append(
            f"{ignored} blocking key(s) covered more than {MAX_BLOC} people "
            "and were skipped - pairs findable only through one of those "
            "keys are missing from both sections below."
        )

    if clusters:
        cluster_lines = "\n".join(
            _format_cluster(cluster, people_by_handle) for cluster in clusters
        )
        sections.append(
            f"## Proved duplicates ({len(clusters)} cluster(s))\n\n{cluster_lines}"
        )
    else:
        sections.append("## Proved duplicates\n\nNone found.")

    if arbitration_pairs:
        pair_lines = "\n".join(_format_arbitration_pair(p) for p in arbitration_pairs)
        sections.append(
            f"## Needs human arbitration ({len(arbitration_pairs)} pair(s))\n\n"
            "These pairs share enough to be worth a look, but the rules did "
            "not prove them - review each one before merging.\n\n"
            f"{pair_lines}"
        )

    return "\n\n".join(sections) + "\n"
