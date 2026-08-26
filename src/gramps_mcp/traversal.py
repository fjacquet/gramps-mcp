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
Breadth-first traversal of the Gramps family graph.

Pure graph logic: this module fetches people and follows family links. It
formats nothing - rendering lives in handlers/traversal_handler.py.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from .models.api_calls import ApiCalls
from .utils import escape_gql_literal

logger = logging.getLogger(__name__)

VISIT_CAP = 500
MAX_CONCURRENT_FETCHES = 8

# Reason: the Gramps child reference type that continues a lineage. Every
# other value - Adopted, Stepchild, Foster, Sponsored, None, Unknown, or a
# custom string - names a relationship that is real but not biological.
BIRTH_RELATION = "Birth"


@dataclass(frozen=True)
class Link:
    """
    One step from a person to a relative, with how they are related.

    Attributes:
        handle (str): The relative's handle.
        relation (str | None): The Gramps child reference type when it is
            anything other than a birth link, verbatim - "Adopted",
            "Stepchild", a custom string. None for a birth link.
        expand (bool): Whether the walk continues through this relative.
        secondary_family (bool): True when the link comes from a parent
            family beyond the first, which Gramps treats as the main one.
    """

    handle: str
    relation: str | None = None
    expand: bool = True
    secondary_family: bool = False


@dataclass
class TraversalResult:
    """Outcome of one breadth-first walk of the family graph."""

    root: str
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: dict[str, list[Link]] = field(default_factory=dict)
    truncated_by_cap: bool = False
    unexplored: int = 0
    failed: dict[str, str] = field(default_factory=dict)
    visit_cap: int = VISIT_CAP


async def resolve_person_handle(client, tree_id: str, gramps_id: str) -> str | None:
    """
    Look up a person's handle from their Gramps ID.

    Args:
        client: A GrampsWebAPIClient.
        tree_id (str): Family tree identifier.
        gramps_id (str): The Gramps ID to resolve, for example "I0001".

    Returns:
        str | None: The handle, or None when no person matches.
    """
    # Reason: escape for the GQL string literal - see escape_gql_literal,
    # without it a crafted gramps_id closes the literal early and resolves
    # to an arbitrary person instead of the one requested.
    escaped = escape_gql_literal(gramps_id)
    people = await client.make_api_call(
        api_call=ApiCalls.GET_PEOPLE,
        params={"gql": f'gramps_id = "{escaped}"', "pagesize": 1, "page": 1},
        tree_id=tree_id,
    )
    if not people:
        return None
    return people[0].get("handle")


async def _fetch_person(client, tree_id: str, handle: str, extend: str) -> dict:
    """
    Fetch one person with their profile and their extended families.

    Args:
        client: A GrampsWebAPIClient.
        tree_id (str): Family tree identifier.
        handle (str): Person handle.
        extend (str): "parent_family_list" or "family_list".

    Returns:
        dict: The raw person payload.
    """
    return await client.make_api_call(
        api_call=ApiCalls.GET_PERSON,
        params={"profile": "self", "extend": extend},
        tree_id=tree_id,
        handle=handle,
    )


async def _fetch_level(
    client, tree_id: str, handles: list[str], extend: str
) -> dict[str, dict | Exception]:
    """
    Fetch one generation concurrently.

    Args:
        client: A GrampsWebAPIClient.
        tree_id (str): Family tree identifier.
        handles (list[str]): Handles making up this generation.
        extend (str): "parent_family_list" or "family_list".

    Returns:
        dict[str, dict | Exception]: Payload or the exception, per handle.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def _bounded(handle: str):
        async with semaphore:
            return await _fetch_person(client, tree_id, handle, extend)

    # Reason: return_exceptions keeps one server error from discarding the
    # hundreds of fetches that succeeded alongside it.
    payloads: list[dict | Exception] = await asyncio.gather(
        *(_bounded(handle) for handle in handles), return_exceptions=True
    )
    return dict(zip(handles, payloads, strict=True))


def _relation(raw: str | None) -> str | None:
    """
    Normalise one Gramps child reference type into a link annotation.

    Args:
        raw (str | None): The frel or mrel value, or None when the payload
            carries no child reference entry.

    Returns:
        str | None: None for a birth link - which Gramps also expresses by
        omitting the value - and the verbatim string otherwise, custom
        types included.
    """
    # Reason: the raw object fields are not localised, unlike the profile
    # fields alongside them - verified against the live server, where
    # locale=fr turns profile.relationship into "Maries" while frel stays
    # "Birth". Comparing to the English constant is therefore safe.
    if raw is None or raw == BIRTH_RELATION:
        return None
    return raw


def _subject_child_ref(family: dict, subject: str | None) -> dict:
    """
    Find the subject's own entry in a family's child reference list.

    Args:
        family (dict): An extended family object.
        subject (str | None): Handle of the person the walk is centred on.

    Returns:
        dict: The matching child reference, or an empty dict when the
        family carries none - which the export does whenever both
        relationships are Birth.
    """
    for child_ref in family.get("child_ref_list", []) or []:
        if child_ref.get("ref") == subject:
            return child_ref
    return {}


def _parents_of(payload: dict) -> list[Link]:
    """
    Read a person's parent links from an extended parent_family_list.

    Args:
        payload (dict): A person payload fetched with extend=parent_family_list.

    Returns:
        list[Link]: Father then mother, per family, skipping empty slots.
        Each parent carries its own relationship: Gramps records frel and
        mrel separately, so a child can be the birth child of one parent
        and the stepchild of the other.
    """
    subject = payload.get("handle")
    links: list[Link] = []
    families = (payload.get("extended") or {}).get("parent_families", []) or []
    for index, family in enumerate(families):
        child_ref = _subject_child_ref(family, subject)
        slots = (
            ("father_handle", child_ref.get("frel")),
            ("mother_handle", child_ref.get("mrel")),
        )
        for key, raw in slots:
            handle = family.get(key)
            if not handle:
                continue
            relation = _relation(raw)
            links.append(
                Link(
                    handle=handle,
                    relation=relation,
                    expand=relation is None,
                    # Reason: Gramps treats the first parent family as the
                    # main one - the one its own reports and charts follow.
                    secondary_family=index > 0,
                )
            )
    return links


def _children_of(payload: dict) -> list[Link]:
    """
    Read a person's child links from an extended family_list.

    Args:
        payload (dict): A person payload fetched with extend=family_list.

    Returns:
        list[Link]: Child links across all families, in family order, each
        annotated with the relationship binding the subject to that child.
    """
    subject = payload.get("handle")
    links: list[Link] = []
    for family in (payload.get("extended") or {}).get("families", []) or []:
        is_father = family.get("father_handle") == subject
        is_mother = family.get("mother_handle") == subject
        for child_ref in family.get("child_ref_list", []) or []:
            handle = child_ref.get("ref")
            if not handle:
                continue
            frel = _relation(child_ref.get("frel"))
            mrel = _relation(child_ref.get("mrel"))
            if is_father:
                relation = frel
            elif is_mother:
                relation = mrel
            else:
                # Reason: the payload does not say which parent the subject
                # is, so neither side can be ruled out. Report a non-birth
                # relationship rather than default to a birth link that
                # nothing in the data vouches for.
                relation = frel or mrel
            links.append(
                Link(handle=handle, relation=relation, expand=relation is None)
            )
    return links


async def _walk(
    client,
    tree_id: str,
    start_handle: str,
    max_generations: int,
    visit_cap: int,
    extend: str,
    successors,
) -> TraversalResult:
    """
    Walk the family graph breadth-first from one person.

    Args:
        client: A GrampsWebAPIClient.
        tree_id (str): Family tree identifier.
        start_handle (str): Handle of the subject.
        max_generations (int): Generations to fetch, the subject counting as one.
        visit_cap (int): Hard ceiling on people fetched.
        extend (str): "parent_family_list" or "family_list".
        successors (Callable[[dict], list[Link]]): Reads the next
            generation's links out of a person payload.

    Returns:
        TraversalResult: Nodes, edges, and what the walk could not reach.
    """
    result = TraversalResult(root=start_handle, visit_cap=visit_cap)
    seen: set[str] = {start_handle}
    level = [start_handle]
    # Reason: handles fetched for their name only, reached solely through a
    # non-birth link. Empty at the root: the subject is always expanded.
    terminal: set[str] = set()
    # Reason: a failed fetch is recorded in result.failed and never enters
    # result.nodes, so len(result.nodes) alone understates how many fetches
    # were actually attempted. A level with many failures would then leave
    # the cap check unmoved and the walk would keep issuing requests well
    # past visit_cap. attempted counts every fetch issued, success or not,
    # and is what the cap is enforced against.
    attempted = 0

    for iteration in range(max_generations):
        if not level:
            break
        if attempted + len(level) > visit_cap:
            # Reason: the previous iteration already recorded edges pointing
            # at these handles, but they were never fetched - drop those
            # dangling references so the renderer does not print a phantom
            # generation of "[unavailable: not fetched]" lines for handles
            # the cap refused to reach. The tail is counted once, below;
            # clearing level here keeps the cap break from double-counting
            # the generation it just refused to fetch.
            refused = set(level)
            for handle, links in result.edges.items():
                result.edges[handle] = [
                    link for link in links if link.handle not in refused
                ]
            result.truncated_by_cap = True
            result.unexplored += len(level)
            level = []
            break

        is_last_iteration = iteration == max_generations - 1
        attempted += len(level)
        payloads = await _fetch_level(client, tree_id, level, extend)
        next_level: list[str] = []
        next_terminal: set[str] = set()
        for handle, payload in payloads.items():
            if isinstance(payload, Exception):
                logger.warning(f"Traversal could not fetch {handle}: {payload}")
                result.failed[handle] = str(payload)
                continue
            result.nodes[handle] = payload.get("profile") or {
                "handle": handle,
                "gramps_id": payload.get("gramps_id", "?"),
                "name_display": "?",
            }
            # Reason: a person reached only through a non-birth link is
            # fetched - the renderer needs a name, not a bare handle - but
            # the lineage stops there, so their own relatives are never read.
            links = [] if handle in terminal else successors(payload)
            if links and not is_last_iteration:
                result.edges[handle] = links
            for link in links:
                # Reason: promotion. The same person can be reached by a
                # birth link and a non-birth one - an adoptive father who is
                # also the birth father. The birth link wins, whichever
                # order the two arrive in, or a real lineage is dropped.
                if link.expand:
                    next_terminal.discard(link.handle)
                if link.handle in seen:
                    continue
                seen.add(link.handle)
                next_level.append(link.handle)
                if not link.expand:
                    next_terminal.add(link.handle)
        level = next_level
        terminal = next_terminal

    result.unexplored += len(level)
    return result


async def walk_ancestors(
    client,
    tree_id: str,
    start_handle: str,
    max_generations: int,
    visit_cap: int = VISIT_CAP,
) -> TraversalResult:
    """
    Walk up the family graph from one person.

    Args:
        client: A GrampsWebAPIClient.
        tree_id (str): Family tree identifier.
        start_handle (str): Handle of the subject.
        max_generations (int): Generations to fetch, the subject counting as one.
        visit_cap (int): Hard ceiling on people fetched.

    Returns:
        TraversalResult: The ancestry reached.
    """
    return await _walk(
        client,
        tree_id,
        start_handle,
        max_generations,
        visit_cap,
        "parent_family_list",
        _parents_of,
    )


async def walk_descendants(
    client,
    tree_id: str,
    start_handle: str,
    max_generations: int,
    visit_cap: int = VISIT_CAP,
) -> TraversalResult:
    """
    Walk down the family graph from one person.

    Args:
        client: A GrampsWebAPIClient.
        tree_id (str): Family tree identifier.
        start_handle (str): Handle of the subject.
        max_generations (int): Generations to fetch, the subject counting as one.
        visit_cap (int): Hard ceiling on people fetched.

    Returns:
        TraversalResult: The descendancy reached.
    """
    return await _walk(
        client,
        tree_id,
        start_handle,
        max_generations,
        visit_cap,
        "family_list",
        _children_of,
    )
