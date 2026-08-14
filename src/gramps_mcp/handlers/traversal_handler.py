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
Markdown rendering for breadth-first traversal results.

No I/O: everything here operates on an in-memory TraversalResult.
"""

from ..traversal import TraversalResult

INDENT = "  "


def _format_event(event: dict | None, prefix: str) -> str:
    """
    Render one birth or death as a compact suffix.

    Args:
        event (dict | None): The profile's birth or death object.
        prefix (str): "b." or "d.".

    Returns:
        str: For example "b. 1948 Lyon", or "" when there is no date.
    """
    if not event or not event.get("date"):
        return ""
    place = event.get("place_name") or ""
    # Reason: place_name only, never the full hierarchy the API also
    # returns - token economy is the point of this whole change.
    return f"{prefix} {event['date']} {place}".rstrip()


def _format_person(profile: dict) -> str:
    """
    Render one person as a single line without indentation or bullet.

    Args:
        profile (dict): A profile=self payload for one person.

    Returns:
        str: For example "JACQUET, Yvan (I0042), b. 1948 Lyon, d. 2011".
    """
    line = f"{profile.get('name_display', '?')} ({profile.get('gramps_id', '?')})"
    for part in (
        _format_event(profile.get("birth"), "b."),
        _format_event(profile.get("death"), "d."),
    ):
        if part:
            line += f", {part}"
    return line


def _walk_lines(
    result: TraversalResult, handle: str, depth: int, seen: set[str], lines: list[str]
) -> int:
    """
    Append the markdown lines for one subtree, depth-first for readability.

    Args:
        result (TraversalResult): The walk to render.
        handle (str): Handle of the person to render at this position.
        depth (int): Current generation, zero for the root.
        seen (set[str]): Handles already rendered somewhere above.
        lines (list[str]): Accumulator, mutated in place.

    Returns:
        int: The deepest generation reached under this handle, one-based.
    """
    pad = INDENT * depth
    if handle in result.failed:
        lines.append(f"{pad}- (handle {handle}) [unavailable: {result.failed[handle]}]")
        return depth + 1
    profile = result.nodes.get(handle)
    if profile is None:
        lines.append(f"{pad}- (handle {handle}) [unavailable: not fetched]")
        return depth + 1
    if handle in seen:
        lines.append(f"{pad}- {_format_person(profile)} [already listed above]")
        return depth + 1
    seen.add(handle)
    lines.append(f"{pad}- {_format_person(profile)}")
    deepest = depth + 1
    for child in result.edges.get(handle, []):
        deepest = max(deepest, _walk_lines(result, child, depth + 1, seen, lines))
    return deepest


def format_traversal(result: TraversalResult, direction: str) -> str:
    """
    Render a traversal result as an indented markdown tree.

    Args:
        result (TraversalResult): The walk to render.
        direction (str): "ancestors" or "descendants", used in the heading.

    Returns:
        str: Markdown ready to hand back as tool output.
    """
    lines: list[str] = []
    generations = _walk_lines(result, result.root, 0, set(), lines)
    root_profile = result.nodes.get(result.root, {})
    header = (
        f"# {direction.capitalize()} of "
        f"{root_profile.get('name_display', '?')} "
        f"({root_profile.get('gramps_id', '?')}) - "
        f"{generations} generations, {len(result.nodes)} people"
    )
    text = header + "\n\n" + "\n".join(lines) + "\n"
    if result.truncated_by_cap:
        text += (
            f"\n**Truncated**: visit cap of {result.visit_cap} reached, "
            f"{result.unexplored} branches unexplored. Lower max_generations "
            "or start from a nearer ancestor.\n"
        )
    return text
