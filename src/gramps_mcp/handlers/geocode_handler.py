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
Markdown rendering for a single place resolution.

No I/O: everything here operates on an already-resolved (or already-failed)
`genealogy.geo.registry.resolve_place` result. Three rules are pinned by
tests and must not be collapsed into each other:

1. A provider failure and "no match found" are different answers and must
   render differently - an unreachable gazetteer is not the same claim as
   "nothing there matched".
2. An ambiguous resolution (`ResolvedPlace.ambiguous`) is stated
   prominently, never silently resolved. This repo's own history: "Le
   Rocher" (Cher) matched Saint-Antoine-du-Rocher (Indre-et-Loire) on the
   region alone, and "le rocher" is a genuine alias of that commune - the
   label alone is no protection.
3. The output never implies a write happened, even when the decision is
   'ecrire' (score says the match is solid). It always names `create_place`
   as the next step, because this tool only proposes.
"""

from ..genealogy.domain import ResolvedPlace


def _format_chain(resolved: ResolvedPlace) -> str | None:
    """
    Render the administrative chain as a single top-down line.

    Args:
        resolved (ResolvedPlace): The resolution, with `chains[0].levels`
            holding the parent hierarchy (top-down, country first) when the
            resolver found one.

    Returns:
        str | None: For example "France > Cher > Bourges", or None when the
        resolver returned no administrative chain at all (a bare worldwide
        fallback with no country segment).
    """
    # Reason: map_nominatim (genealogy/geo/nominatim.py) always returns
    # `chains=[DatedChain(levels=[])]` on a fallback with no administrative
    # hierarchy - never an empty `chains` list. Checking `not resolved.chains`
    # alone is therefore never true in practice, and `names` (which always
    # gets `resolved.name` appended below) is never empty either - `if not
    # names: return None` was dead code that let an empty-levels chain
    # through and rendered a one-element "hierarchy" naming nothing but the
    # place itself. Checking `resolved.chains[0].levels` directly is what
    # actually detects "no chain".
    if not resolved.chains or not resolved.chains[0].levels:
        return None
    names = [level.name for level in resolved.chains[0].levels]
    names.append(resolved.name)
    return " > ".join(names)


def _format_action(action: str) -> str:
    """
    Render the next-step line for one decided action.

    Every branch names `create_place` and phrases the resolution as a
    proposal - `decide_action` returning 'ecrire' means the score cleared
    the bar for a solid match, not that anything was written. This handler
    has no write path at all.

    Args:
        action (str): One of 'ecrire', 'proposition', 'indecidable', as
            produced by `genealogy.geo.registry.decide_action`.

    Returns:
        str: A markdown paragraph naming `create_place` as the next step.
    """
    if action == "ecrire":
        return (
            "**Solid match** - nothing has been written. Pass these details "
            "to `create_place` to record it, and still check the QID "
            "against the nearest identified ancestor first - this tool "
            "supplies a candidate, it does not replace that check."
        )
    if action == "proposition":
        return (
            "**Proposal to review** - this is not an established fact. If "
            "you confirm it, pass the details to `create_place` to record "
            "it."
        )
    return (
        "**Could not be decided** confidently. Nothing has been written; "
        "review manually before calling `create_place`."
    )


def format_place_resolution(
    resolved: ResolvedPlace | None,
    action: str,
    confiance: str,
    query: str,
    error: str | None = None,
) -> str:
    """
    Render one geocode_place result as markdown.

    Args:
        resolved (ResolvedPlace | None): The resolver's output, or None when
            no gazetteer produced a candidate (or when a provider failed -
            see `error`).
        action (str): 'ecrire' | 'proposition' | 'indecidable', from
            `decide_action`.
        confiance (str): 'haute' | 'moyenne' | 'basse', from `confiance_of`.
        query (str): The original free-text query, echoed back so the
            reader can see what was asked for.
        error (str | None): The exception message from a failed gazetteer
            call (`httpx.HTTPError`). When set, this is reported as a
            provider failure - a different answer from "no match found",
            never conflated with it.

    Returns:
        str: Markdown ready to hand back as tool output.
    """
    # Reason: a provider failure and "no match" are different claims. This
    # branch returns before touching the "no match" wording below, so the
    # two paths can never bleed into each other.
    if error is not None:
        return (
            f'**Gazetteer unreachable** for "{query}": {error}. No '
            "resolution was attempted - this is not a claim that no match "
            "exists, only that the lookup itself failed.\n"
        )

    if resolved is None:
        return f'## No match\n\nNo gazetteer returned a candidate for "{query}".\n'

    sections = [f"## Resolved: {resolved.name}"]

    # Reason: ambiguity must be stated prominently, immediately after the
    # headline, before any other detail - a reader skimming past the
    # coordinates and code must still hit this line.
    if resolved.ambiguous:
        sections.append(
            "**Ambiguous match** - more than one candidate scored close "
            "together. This is not a resolved fact; review it manually "
            "before doing anything with it."
        )

    chain = _format_chain(resolved)
    if chain:
        sections.append(f"**Administrative chain**: {chain}")

    if resolved.lat is not None and resolved.long is not None:
        sections.append(f"**Coordinates**: {resolved.lat}, {resolved.long}")

    if resolved.code:
        sections.append(f"**Code**: {resolved.code}")

    sections.append(
        f"**Score**: {resolved.score:.2f} (confidence: {confiance}, "
        f"source: {resolved.source})"
    )

    sections.append(_format_action(action))

    return "\n\n".join(sections) + "\n"
