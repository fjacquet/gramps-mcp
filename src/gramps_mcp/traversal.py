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

logger = logging.getLogger(__name__)

VISIT_CAP = 500
MAX_CONCURRENT_FETCHES = 8


@dataclass
class TraversalResult:
    """Outcome of one breadth-first walk of the family graph."""

    root: str
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: dict[str, list[str]] = field(default_factory=dict)
    truncated_by_cap: bool = False
    unexplored: int = 0
    revisited: set[str] = field(default_factory=set)
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
    people = await client.make_api_call(
        api_call=ApiCalls.GET_PEOPLE,
        params={"gql": f'gramps_id = "{gramps_id}"', "pagesize": 1, "page": 1},
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
    payloads = await asyncio.gather(
        *(_bounded(handle) for handle in handles), return_exceptions=True
    )
    return dict(zip(handles, payloads, strict=True))


def _parents_of(payload: dict) -> list[str]:
    """
    Read a person's parent handles from an extended parent_family_list.

    Args:
        payload (dict): A person payload fetched with extend=parent_family_list.

    Returns:
        list[str]: Father then mother, per family, skipping empty slots.
    """
    handles: list[str] = []
    for family in payload.get("extended", {}).get("parent_families", []) or []:
        for key in ("father_handle", "mother_handle"):
            handle = family.get(key)
            if handle:
                handles.append(handle)
    return handles


def _children_of(payload: dict) -> list[str]:
    """
    Read a person's child handles from an extended family_list.

    Args:
        payload (dict): A person payload fetched with extend=family_list.

    Returns:
        list[str]: Child handles across all families, in family order.
    """
    handles: list[str] = []
    for family in payload.get("extended", {}).get("families", []) or []:
        for child_ref in family.get("child_ref_list", []) or []:
            handle = child_ref.get("ref")
            if handle:
                handles.append(handle)
    return handles


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
        successors (Callable[[dict], list[str]]): Reads the next generation's
            handles out of a person payload.

    Returns:
        TraversalResult: Nodes, edges, and what the walk could not reach.
    """
    result = TraversalResult(root=start_handle, visit_cap=visit_cap)
    seen: set[str] = {start_handle}
    level = [start_handle]

    for iteration in range(max_generations):
        if not level:
            break
        if len(result.nodes) + len(level) > visit_cap:
            # Reason: the tail is counted once, below. Clearing level here
            # keeps the cap break from double-counting the generation it
            # just refused to fetch.
            result.truncated_by_cap = True
            result.unexplored += len(level)
            level = []
            break

        is_last_iteration = iteration == max_generations - 1
        payloads = await _fetch_level(client, tree_id, level, extend)
        next_level: list[str] = []
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
            children = successors(payload)
            if children and not is_last_iteration:
                result.edges[handle] = children
            for child in children:
                if child in seen:
                    result.revisited.add(child)
                    continue
                seen.add(child)
                next_level.append(child)
        level = next_level

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
