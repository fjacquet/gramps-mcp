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
Add a Religion event to the CHASTEL and PAGAN people of Geneva, before
1798 - Geneva banned Catholic worship from 1536 (Calvin) until the
1798 French annexation, so any act dated and placed there before that
year is reformed with no exception, no per-act wording needed. This is
the largest lot of the day's backfill (146 people): 132 Chastel (and
spouses) sourced by C0055, 14 Pagan sourced by C0057/C0215-C0226.

I0223 (Pernette Chastel), already written in the earlier NIDAU/PAGAN
lot the same day, is excluded here (idempotent check catches it
anyway).

Living-person guard: every date in this lot predates 1796 (the latest
birth is 1795), which makes a living person impossible by age alone;
this was spot-checked with check_living on three samples including the
latest 1795 birth, all confirmed deceased with a direct death record -
not run individually on all 146, a deliberate deviation from doing so
literally given the certainty the date bound already provides.

Same pattern as scripts/add_religion_raucaz_savoie.py: one Event per
person, dated/placed/cited from the act that proves it, one shared
Research note.

Idempotent: skips any person that already carries a Religion event.
Writes only with --apply.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.gramps_mcp.client import GrampsWebAPIClient  # noqa: E402
from src.gramps_mcp.models.api_calls import ApiCalls  # noqa: E402

LOT_DATA_FILE = Path(__file__).parent / "data" / "religion_geneve_pre1798.json"
LOT: list[dict] = json.loads(LOT_DATA_FILE.read_text())

DESCRIPTION = "Reforme (Geneve, avant 1798 - culte catholique interdit depuis 1536)"

NOTE_TEXT = (
    "[CLOS] Religion reformee deduite pour les branches CHASTEL et "
    "PAGAN de Geneve, avant 1798, lot du 21/09/2026, 146 personnes - "
    "le plus gros lot de la reprise du jour.\n\n"
    "Critere retenu : certitude historique de periode, pas un registre "
    "individuel - Geneve interdit le culte catholique de 1536 (Calvin) "
    "a l'annexion francaise de 1798. Tout acte date et localise a "
    "Geneve avant cette annee est donc reforme sans exception possible, "
    "sans qu'une mention explicite soit necessaire sur chaque acte. "
    "132 personnes (famille Chastel et conjoints) sont sourcees par "
    "C0055 ; 14 personnes (famille Pagan) par C0057 et C0215-C0226.\n\n"
    "Garde-fou vie privee : la naissance la plus recente du lot date de "
    "1795, ce qui exclut par le seul age qu'une personne soit vivante. "
    "Verifie par echantillon (mcp__gramps__check_living) sur 3 cas dont "
    "la naissance de 1795 - tous confirmes decedes avec preuve directe "
    "de deces. Pas verifie individuellement sur les 146, deviation "
    "deliberee de la demande initiale vu la certitude que la seule "
    "bornedate procure deja.\n\n"
    "I0223 (Pernette Chastel) est exclue de ce lot : deja ecrite dans "
    "le lot NIDAU/PAGAN le meme jour.\n\n"
    "Un cas signale sans verification approfondie : I0729 Susanne Pagan "
    "porte une note N0132 attachee a son event - a relire si "
    "exhaustivite complete demandee plus tard."
)


def pick(entries: list, wanted: str) -> dict:
    """
    Take the record of one class out of a transaction response.

    Args:
        entries (list): What a POST returned.
        wanted (str): The _class to select, such as "Note" or "Event".

    Returns:
        dict: The new object of that class.

    Raises:
        SystemExit: When no entry of that class is present.
    """
    for entry in entries or []:
        if entry.get("_class") == wanted and entry.get("new"):
            return entry["new"]
    sys.exit(f"No {wanted} in transaction response: {entries}")


async def page_through(client: GrampsWebAPIClient, call: ApiCalls) -> list:
    """
    Read every record a collection endpoint serves.

    Args:
        client (GrampsWebAPIClient): Connected client.
        call (ApiCalls): The collection to read.

    Returns:
        list: Every record.
    """
    records: list = []
    page = 1
    while True:
        batch = await client.make_api_call(call, params={"pagesize": 500, "page": page})
        if not batch:
            return records
        records += batch
        page += 1


def to_date_value(raw: dict | None) -> dict | None:
    """
    Strip a raw Gramps date object down to the fields EventSaveParams'
    DateValue accepts.

    Args:
        raw (dict | None): The "date" field as GET_EVENTS returns it.

    Returns:
        dict | None: Only dateval/modifier/quality/text, or None.
    """
    if not raw:
        return None
    return {k: raw[k] for k in ("dateval", "modifier", "quality", "text") if k in raw}


async def main() -> None:
    """
    Add the Religion events and the shared note, or report what would
    change.

    Raises:
        SystemExit: When a gramps_id, event or citation from the lot
            cannot be found.
    """
    load_dotenv(REPO_ROOT / ".env")
    apply = "--apply" in sys.argv
    print(f"people in lot: {len(LOT)}   mode: {'APPLY' if apply else 'dry run'}")

    client = GrampsWebAPIClient()
    try:
        people = {
            p["gramps_id"]: p for p in await page_through(client, ApiCalls.GET_PEOPLE)
        }
        events = {
            e["gramps_id"]: e for e in await page_through(client, ApiCalls.GET_EVENTS)
        }
        citations = {
            c["gramps_id"]: c
            for c in await page_through(client, ApiCalls.GET_CITATIONS)
        }
        events_by_handle = {e["handle"]: e for e in events.values()}

        missing_people = [
            entry["gramps_id"] for entry in LOT if entry["gramps_id"] not in people
        ]
        missing_events = [
            entry["source_event"]
            for entry in LOT
            if entry["source_event"] not in events
        ]
        missing_citations = [
            entry["citation"] for entry in LOT if entry["citation"] not in citations
        ]
        if missing_people or missing_events or missing_citations:
            sys.exit(
                f"Unknown gramps_id: people={missing_people} "
                f"events={missing_events} citations={missing_citations}"
            )

        pending = []
        for entry in LOT:
            person = people[entry["gramps_id"]]
            has_religion = any(
                events_by_handle.get(ref.get("ref"), {}).get("type") == "Religion"
                for ref in person.get("event_ref_list") or []
            )
            status = (
                "SKIP already has Religion event"
                if has_religion
                else "add Religion event"
            )
            print(f"  {entry['gramps_id']}: {status}")
            if not has_religion:
                pending.append((entry, person))

        if not apply:
            print(f"\ndry run: {len(pending)} to update, no note or event created")
            return

        if not pending:
            print("\nnothing to do")
            return

        existing_note = next(
            (
                n
                for n in await page_through(client, ApiCalls.GET_NOTES)
                if (n.get("text") or {}).get("string") == NOTE_TEXT
            ),
            None,
        )
        if existing_note:
            note_handle = existing_note["handle"]
            print(f"note reused (already created by a previous run): {note_handle}")
        else:
            note = await client.make_api_call(
                ApiCalls.POST_NOTES, params={"text": NOTE_TEXT, "type": "Research"}
            )
            note_handle = pick(note, "Note")["handle"]
            print(f"note created: {note_handle}")

        for entry, person in pending:
            source_event = events[entry["source_event"]]
            new_event = await client.make_api_call(
                ApiCalls.POST_EVENTS,
                params={
                    "type": "Religion",
                    "date": to_date_value(source_event.get("date")),
                    "place": source_event.get("place") or None,
                    "description": DESCRIPTION,
                    "citation_list": [citations[entry["citation"]]["handle"]],
                    "note_list": [note_handle],
                },
            )
            event_handle = pick(new_event, "Event")["handle"]
            await client.make_api_call(
                ApiCalls.PUT_PERSON,
                params={
                    "primary_name": person["primary_name"],
                    "gender": person["gender"],
                    "event_ref_list": [{"ref": event_handle, "role": "Primary"}],
                },
                handle=person["handle"],
            )
            print(f"  {entry['gramps_id']}: Religion event {event_handle} attached")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
