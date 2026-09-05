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

"""Duplicate detection by date collision.

Written for this repository - not part of the material copied from
fjacquet/crewai-custom-tools.

Name blocking is the wrong first instrument for this tree. Ten Marie
Jacquet and seven Silvain Villaudy are what a Berry parish looks like, so
grouping by name buries the real duplicates under homonyms - and it misses
the ones filed under two spellings entirely: the 1819 Breitenbach pair sat
under HADLER and STADLER, and no name rule will ever put those together.

A day-precise date is a much sharper key. A few hundred of them spread
over four centuries collide by chance only a handful of times, so two
people sharing one to the day is evidence, and two people sharing both a
birth and a death date is proof.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations

from .domain import EventFact, FamilyFacts, PersonFacts

_NEAR_SURNAME_DISTANCE = 2


@dataclass
class DateCollision:
    """Two people whose dates coincide, with why and how strongly."""

    a: str
    b: str
    tier: str  # "prouve" | "fort" | "a_verifier"
    reasons: list[str] = field(default_factory=list)


def _exact(event: EventFact | None) -> tuple[int, int, int] | None:
    """Return (year, month, day) only for a single, unqualified, day-precise date.

    Args:
        event (EventFact | None): The event to read, if the person has one.

    Returns:
        tuple[int, int, int] | None: The date, or None when it is absent,
        approximate, estimated, a range, or precise only to the month or
        year - none of which is evidence of anything.
    """
    if event is None:
        return None
    if event.modifier or event.quality:
        return None
    val = event.dateval
    if len(val) != 4:
        return None
    day, month, year = val[0], val[1], val[2]
    if not (day and month and year):
        return None
    return (int(year), int(month), int(day))


def _levenshtein(a: str, b: str) -> int:
    """Edit distance between two surnames, capped for speed.

    Args:
        a (str): First surname, already normalised.
        b (str): Second surname, already normalised.

    Returns:
        int: The distance, or a large sentinel when the lengths differ
        too much for the pair to be a spelling variant.
    """
    if a == b:
        return 0
    if abs(len(a) - len(b)) > _NEAR_SURNAME_DISTANCE:
        return _NEAR_SURNAME_DISTANCE + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            )
        previous = current
    return previous[-1]


def _key(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalpha())


def _siblings(a: PersonFacts, b: PersonFacts, families: dict[str, FamilyFacts]) -> bool:
    """Whether the two share a parent family, in either direction.

    Args:
        a (PersonFacts): One person.
        b (PersonFacts): The other.
        families (dict[str, FamilyFacts]): Families by handle, used when a
            person's own `parent_family_handles` is empty but the family
            lists them as a child - the link is stored on both sides and
            either one may be missing.

    Returns:
        bool: True when they are siblings, and so twins rather than
        duplicates if they share a birth date.
    """
    if set(a.parent_family_handles) & set(b.parent_family_handles):
        return True
    for family in families.values():
        children = set(family.child_handles)
        if a.handle in children and b.handle in children:
            return True
    return False


def find_date_collisions(
    people: list[PersonFacts], families: dict[str, FamilyFacts]
) -> list[DateCollision]:
    """Pair up people whose day-precise dates coincide.

    Args:
        people (list[PersonFacts]): Everyone in the tree.
        families (dict[str, FamilyFacts]): Families by handle, used only
            to recognise siblings.

    Returns:
        list[DateCollision]: One entry per colliding pair, strongest
        first. Siblings sharing a birth date are omitted: they are twins,
        which this tree records correctly and which would otherwise be
        re-reported on every run until the reader stops reading.
    """
    buckets: dict[tuple[str, tuple[int, int, int]], list[PersonFacts]] = defaultdict(
        list
    )
    for person in people:
        # Reason: births are bucketed apart from deaths. One person born
        # the day another died is a calendar coincidence, not a hint.
        for kind, event in (("naissance", person.birth), ("deces", person.death)):
            date = _exact(event)
            if date is not None:
                buckets[(kind, date)].append(person)

    reasons: dict[tuple[str, str], list[str]] = defaultdict(list)
    by_id: dict[str, PersonFacts] = {p.gramps_id: p for p in people}
    for (kind, date), members in buckets.items():
        if len(members) < 2:
            continue
        year, month, day = date
        for first, second in combinations(members, 2):
            left, right = sorted((first.gramps_id, second.gramps_id))
            reasons[(left, right)].append(f"meme {kind} {day:02d}/{month:02d}/{year}")

    found: list[DateCollision] = []
    for (left, right), why in reasons.items():
        a, b = by_id[left], by_id[right]
        if _siblings(a, b, families):
            continue
        same_name = (_key(a.given), _key(a.surname)) == (_key(b.given), _key(b.surname))
        if len(why) > 1 or same_name:
            tier = "prouve"
        elif _levenshtein(_key(a.surname), _key(b.surname)) <= _NEAR_SURNAME_DISTANCE:
            tier = "fort"
        else:
            tier = "a_verifier"
        found.append(DateCollision(a=left, b=right, tier=tier, reasons=sorted(why)))

    order = {"prouve": 0, "fort": 1, "a_verifier": 2}
    found.sort(key=lambda c: (order[c.tier], c.a, c.b))
    return found
