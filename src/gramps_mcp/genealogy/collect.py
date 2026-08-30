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

"""Fetch the tree and convert every record to facts."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..client import GrampsWebAPIClient
from ..models.api_calls import ApiCalls
from .domain import FamilyFacts, PersonFacts
from .facts import _LIST_PARAMS, family_from_json, person_from_json

logger = logging.getLogger(__name__)


@dataclass
class CollectResult:
    """One pass over the tree, with what it could not read stated explicitly."""

    people: list[PersonFacts] = field(default_factory=list)
    families: dict[str, FamilyFacts] = field(default_factory=dict)
    skipped: int = 0
    partial: bool = False
    error: str | None = None


async def collect_tree(
    client: GrampsWebAPIClient, tree_id: str, limit: int | None = None
) -> CollectResult:
    """Fetch every person and family, converted to facts.

    Args:
        client (GrampsWebAPIClient): Client to issue the reads with.
        tree_id (str): Family tree identifier.
        limit (int | None): Stop after this many people, for a cheap probe.

    Returns:
        CollectResult: The facts, plus how many records were unreadable and
            whether the pass completed.
    """
    out = CollectResult()

    # Reason: a partial scan that renders like a complete one is the failure
    # that matters here - "no duplicates found" over half a tree reads as a
    # clean bill of health. Every early exit leaves partial=True/error set.
    try:
        raw_people = await client.make_api_call(
            api_call=ApiCalls.GET_PEOPLE, params=dict(_LIST_PARAMS), tree_id=tree_id
        )
        for raw in raw_people[:limit] if limit else raw_people:
            try:
                person = person_from_json(raw)
                # Reason: person_from_json defaults every field via dict.get,
                # so it never raises on a malformed record - it silently
                # returns an empty-shell PersonFacts instead. A record
                # missing either identifier is not a real person entry;
                # count it as unreadable rather than let it through. This
                # must mirror the family check below: the next task keys a
                # dict on `.handle` (`by_handle = {p.handle: p for p in
                # collected.people}`), and two people with handle="" would
                # collapse into one entry there, naming the wrong person in
                # a merge proposal.
                if not person.gramps_id or not person.handle:
                    raise ValueError("record has no gramps_id/handle")
                out.people.append(person)
            except Exception:
                out.skipped += 1
                logger.debug("unreadable person record: %s", raw.get("handle"))

        raw_families = await client.make_api_call(
            api_call=ApiCalls.GET_FAMILIES, params=dict(_LIST_PARAMS), tree_id=tree_id
        )
        for raw in raw_families:
            try:
                family = family_from_json(raw)
                if not family.gramps_id or not family.handle:
                    raise ValueError("record has no gramps_id/handle")
                out.families[family.handle] = family
            except Exception:
                out.skipped += 1
                logger.debug("unreadable family record: %s", raw.get("handle"))
    except Exception as exc:
        out.partial = True
        out.error = str(exc)

    return out
