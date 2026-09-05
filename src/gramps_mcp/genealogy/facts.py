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

"""Build normalized PersonFacts / FamilyFacts from the Gramps Web API.

Pure mappers only: `person_from_json` and `family_from_json`. One list call
per page uses `profile=all&extend=event_ref_list`, so vital dates (raw, with
sortval) and citation counts arrive together.

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/gramps/facts.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.

Only the source file's lines 1-87 were copied. The source's `class
FactsFetcher` (I/O layer bound to `GrampsClient`, source lines 88-128) was
deliberately not copied: this repo has no `GrampsClient`, and the I/O side is
the MCP server's own concern (see Task 7).
"""

from __future__ import annotations

import logging

from .domain import (
    EventFact,
    FamilyFacts,
    PersonFacts,
)

logger = logging.getLogger(__name__)

_SEX = {0: "F", 1: "M", 2: "U"}
_LIST_PARAMS = {"profile": "all", "extend": "event_ref_list", "sort": "gramps_id"}


def _event_from_raw(raw: dict) -> EventFact:
    date = raw.get("date") or {}
    return EventFact(
        type=raw.get("type", ""),
        sortval=date.get("sortval", 0) or 0,
        year=date.get("year"),
        modifier=date.get("modifier", 0) or 0,
        quality=date.get("quality", 0) or 0,
        dateval=date.get("dateval") or [],
        has_citation=bool(raw.get("citation_list")),
    )


def _first_primary(raw: dict, events: list[EventFact], kind: str) -> EventFact | None:
    """Find the person's own event of one type, ignoring the ref indexes.

    Args:
        raw (dict): The raw person record.
        events (list[EventFact]): `extended.events`, positionally aligned
            with `event_ref_list` - the API renders one per reference, in
            order.
        kind (str): "Birth" or "Death".

    Returns:
        EventFact | None: The first event of that type the person holds
        as Primary. Roles other than Primary are skipped: a witness at
        someone else's death carries that event in their own list, and
        reading it as their death would kill them decades early.
    """
    for ref, event in zip(raw.get("event_ref_list") or [], events):
        if event.type == kind and (ref or {}).get("role") == "Primary":
            return event
    return None


def person_from_json(raw: dict) -> PersonFacts:
    """Map one raw person (profile=all & extend=event_ref_list) to PersonFacts."""
    name = raw.get("primary_name") or {}
    surnames = name.get("surname_list") or [{}]
    surname = surnames[0].get("surname", "") if surnames else ""
    given = name.get("first_name", "")
    events = [_event_from_raw(e) for e in (raw.get("extended") or {}).get("events", [])]

    bi, di = raw.get("birth_ref_index", -1), raw.get("death_ref_index", -1)
    birth = events[bi] if 0 <= bi < len(events) else None
    death = events[di] if 0 <= di < len(events) else None
    # Reason: both indexes are stored on the Gramps Person and only ever
    # written by the Gramps UIs. A person created through the REST API
    # comes back with -1 for both, even when its event_ref_list holds one
    # Primary Death - so trusting the index alone hides the birth and
    # death of every person this server itself created, and with them
    # every date rule that would have caught a duplicate.
    if birth is None:
        birth = _first_primary(raw, events, "Birth")
    if death is None:
        death = _first_primary(raw, events, "Death")

    profile = raw.get("profile") or {}
    prof_cites = sum(
        (profile.get(k) or {}).get("citations", 0) for k in ("birth", "death")
    )
    has_cite = (
        bool(raw.get("citation_list"))
        or prof_cites > 0
        or any(e.has_citation for e in events)
    )

    # Le lieu ne vit que dans le profile (chaînes lisibles), pas dans extended.events.
    # On le surimpose donc sur la naissance et le décès, seuls événements que le profile
    # décrit. Aucune requête supplémentaire : profile=all est déjà demandé.
    for fact, cle in ((birth, "birth"), (death, "death")):
        if fact is not None:
            bloc = profile.get(cle) or {}
            fact.place = bloc.get("place") or ""
            fact.place_name = bloc.get("place_name") or ""

    return PersonFacts(
        gramps_id=raw.get("gramps_id", ""),
        handle=raw.get("handle", ""),
        name=f"{given} {surname}".strip(),
        surname=surname,
        given=given,
        sex=_SEX.get(raw.get("gender", 2), "U"),
        birth=birth,
        death=death,
        events=events,
        has_any_citation=has_cite,
        parent_family_handles=list(raw.get("parent_family_list") or []),
        family_handles=list(raw.get("family_list") or []),
    )


def family_from_json(raw: dict) -> FamilyFacts:
    """Map one raw family (extend=event_ref_list) to FamilyFacts."""
    events = [_event_from_raw(e) for e in (raw.get("extended") or {}).get("events", [])]
    marriage = next((e for e in events if e.type == "Marriage"), None)
    return FamilyFacts(
        gramps_id=raw.get("gramps_id", ""),
        handle=raw.get("handle", ""),
        father_handle=raw.get("father_handle"),
        mother_handle=raw.get("mother_handle"),
        child_handles=[
            c["ref"] for c in (raw.get("child_ref_list") or []) if "ref" in c
        ],
        marriage=marriage,
    )
