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

from ..traversal import Link, TraversalResult

INDENT = "  "

POLICY_FOOTER = (
    "**Non-birth links**: a relationship other than birth (Adopted, "
    "Stepchild, Foster, Sponsored, None, Unknown, or a custom type) is "
    "reported but its line is not followed."
)

SECONDARY_FAMILY_FOOTER = (
    "**Other parents families**: Gramps designates the first parent family "
    "as the main one; a parent from any other is marked."
)


def _markers(link: Link | None, followed: bool) -> str:
    """
    Render the bracketed annotations qualifying one link, if any.

    Args:
        link (Link | None): The link leading to this person, None at the root.
        followed (bool): Whether the finished walk read this person's own
            relatives - which a birth link from some other path can make
            true even when this link alone would have stopped here.

    Returns:
        str: For example " [Adopted, line not followed]", or "" when the
        link is an unremarkable birth link inside the main parent family.
    """
    if link is None:
        return ""
    parts = []
    if link.relation is not None:
        # Reason: the marker reports what the walk actually did, not what
        # the link predicted at discovery time. Naming the relationship
        # without saying the walk stopped would let the silence beyond read
        # as "no relatives recorded"; claiming it stopped while the line is
        # rendered underneath misattributes that whole branch. Only the
        # finished walk knows which of the two happened.
        parts.append(
            link.relation if followed else f"{link.relation}, line not followed"
        )
    if link.secondary_family:
        parts.append("other parents family")
    return f" [{'; '.join(parts)}]" if parts else ""


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
    line = f"{profile.get('name_display') or '?'} ({profile.get('gramps_id', '?')})"
    for part in (
        _format_event(profile.get("birth"), "b."),
        _format_event(profile.get("death"), "d."),
    ):
        if part:
            line += f", {part}"
    return line


def _walk_lines(
    result: TraversalResult,
    handle: str,
    depth: int,
    seen: set[str],
    lines: list[str],
    link: Link | None = None,
) -> int:
    """
    Append the markdown lines for one subtree, depth-first for readability.

    Args:
        result (TraversalResult): The walk to render.
        handle (str): Handle of the person to render at this position.
        depth (int): Current generation, zero for the root.
        seen (set[str]): Handles already rendered somewhere above.
        lines (list[str]): Accumulator, mutated in place.
        link (Link | None): The link that led here, None at the root.

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
        # Reason: the markers describe the path that reached this position,
        # so they belong on the repeat too. A person who is the birth child
        # of one parent and the adopted child of another would otherwise
        # render unmarked under the adoptive one.
        lines.append(
            f"{pad}- {_format_person(profile)}"
            f"{_markers(link, bool(result.edges.get(handle)))}"
            " [already listed above]"
        )
        return depth + 1
    seen.add(handle)
    children = result.edges.get(handle, [])
    lines.append(f"{pad}- {_format_person(profile)}{_markers(link, bool(children))}")
    deepest = depth + 1
    for child in children:
        deepest = max(
            deepest, _walk_lines(result, child.handle, depth + 1, seen, lines, child)
        )
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
    every_link = [link for links in result.edges.values() for link in links]
    # Reason: each marker explains itself in the output. The usage guide
    # documents both, but it is a separate resource a client may never have
    # loaded, and an unexplained bracket is a question with no answer.
    # Reason: the policy footer is only true when the policy actually bit.
    # A non-birth relative whose line a birth link elsewhere reopened is
    # marked with the bare relationship, which explains itself.
    if any(
        link.relation is not None and not result.edges.get(link.handle)
        for link in every_link
    ):
        text += f"\n{POLICY_FOOTER}\n"
    if any(link.secondary_family for link in every_link):
        text += f"\n{SECONDARY_FAMILY_FOOTER}\n"
    if result.truncated_by_cap:
        text += (
            f"\n**Truncated**: visit cap of {result.visit_cap} reached, "
            f"{result.unexplored} branches unexplored. Lower max_generations "
            "or start from a closer person.\n"
        )
    return text
