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
    tier: str  # "prouve" | "parents_differents" | "fort" | "a_verifier"
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


def _parent_families(person: PersonFacts, families: dict[str, FamilyFacts]) -> set[str]:
    """Every family this person is recorded as a child of.

    Args:
        person (PersonFacts): The person to place.
        families (dict[str, FamilyFacts]): Families by handle. Read because
            the child link is stored on both sides and either side may be
            missing: a person's own `parent_family_handles` can be empty
            while the family lists them among its children.

    Returns:
        set[str]: Family handles, empty when the parentage is unrecorded.
    """
    found = set(person.parent_family_handles)
    for family in families.values():
        if person.handle in family.child_handles:
            found.add(family.handle)
    return found


def _siblings(a: PersonFacts, b: PersonFacts, families: dict[str, FamilyFacts]) -> bool:
    """Whether the two share a parent family, in either direction.

    Args:
        a (PersonFacts): One person.
        b (PersonFacts): The other.
        families (dict[str, FamilyFacts]): Families by handle.

    Returns:
        bool: True when they are siblings, and so twins rather than
        duplicates if they share a birth date.
    """
    return bool(_parent_families(a, families) & _parent_families(b, families))


def _parents_known_and_differ(
    a: PersonFacts, b: PersonFacts, families: dict[str, FamilyFacts]
) -> bool:
    """Whether both parentages are recorded and share no family.

    Args:
        a (PersonFacts): One person.
        b (PersonFacts): The other.
        families (dict[str, FamilyFacts]): Families by handle.

    Returns:
        bool: True only when both sides have a parent family recorded and
        none is shared. An unrecorded parentage contradicts nothing, so it
        returns False and leaves the pair's tier alone.
    """
    left = _parent_families(a, families)
    right = _parent_families(b, families)
    if not left or not right:
        return False
    return not (left & right)


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
        note: list[str] = []
        if len(why) > 1 or same_name:
            # Reason: a name and a date can both be copied onto the wrong
            # record; a parentage recorded on both sides cannot. Two people
            # documented as children of different couples are not one
            # person, however well their dates line up - so the pair still
            # deserves reporting, but never under "safe to merge".
            if _parents_known_and_differ(a, b, families):
                tier = "parents_differents"
                note = ["parents documentes differents"]
            else:
                tier = "prouve"
        elif _levenshtein(_key(a.surname), _key(b.surname)) <= _NEAR_SURNAME_DISTANCE:
            tier = "fort"
        else:
            tier = "a_verifier"
        found.append(
            DateCollision(a=left, b=right, tier=tier, reasons=sorted(why) + note)
        )

    order = {"prouve": 0, "parents_differents": 1, "fort": 2, "a_verifier": 3}
    found.sort(key=lambda c: (order[c.tier], c.a, c.b))
    return found
