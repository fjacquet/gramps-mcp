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
Add a Religion event to the RAUCAZ-de-Savoie people whose baptism,
marriage or death act names the parish of Verrens (Verrens-Arvey), a
single-confession Catholic parish in this period - no alternative
confession attested anywhere in this corpus.

First slice of a tree-wide religion backfill. Superseded plan: an
earlier version of this script wrote a person Attribute instead.
Gramps's own libgedcom.py maps EventType.RELIGION to the GEDCOM tag
RELI (PERSONALCONSTANTEVENTS, both import and export), so "Religion" is
a *standard* Gramps event type, not a custom one, and it carries its
own date/place/citation/note the way any other event does - unlike a
person Attribute, which is flat. That makes the event the GEDCOM-
faithful choice here, confirmed 2026-09-21 against gramps-project/gramps
master (libgedcom.py, exportgedcom.py).

Each new Religion event copies the date, place and citation of the act
that proves it (same pattern as any other sourced event in this tree),
so the evidence travels with the fact instead of living only in a
note. One shared Research note documents the lot's criterion and its
one exclusion, and is attached to every new event.

Excludes Jean RAUCAZ x Antoinette FRAIX-BURNET (1827 marriage, explicit
"benediction donnee par le R.P. Gabriel, capucin") - strong evidence but
unresolved homonymy between several Jean/Claude RAUCAZ of different
generations (see N0158). Needs identification via the genealogiste skill
before any event is written for either spouse.

Idempotent: skips any person that already carries a Religion event.
Writes only with --apply.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.gramps_mcp.client import GrampsWebAPIClient  # noqa: E402
from src.gramps_mcp.models.api_calls import ApiCalls  # noqa: E402

LOT = [
    {
        "gramps_id": "I0075",
        "source_event": "E0093",
        "citation": "C0040",
        "evidence": "Joseph Raucaz: bapteme 08/04/1799, paroisse de Verrens",
    },
    {
        "gramps_id": "I0035",
        "source_event": "E0112",
        "citation": "C0038",
        "evidence": "Pierre Joseph Raucaz: bapteme 11/04/1850, paroisse de Verrens",
    },
    {
        "gramps_id": "I0283",
        "source_event": "E0960",
        "citation": "C0261",
        "evidence": (
            "Claude Joseph Raucaz: mariage 16/04/1793, registre paroissial "
            "de Verrens, celebrant Portier cure"
        ),
    },
    {
        "gramps_id": "I0284",
        "source_event": "E0960",
        "citation": "C0261",
        "evidence": (
            "Josephte Portier: meme mariage 16/04/1793 que I0283, "
            "celebrant Portier cure"
        ),
    },
    {
        "gramps_id": "I2591",
        "source_event": "E3223",
        "citation": "C2316",
        "evidence": (
            "Jeanne-Andrianne-Francoise Raucaz: bapteme 30/11/1848, paroisse de Verrens"
        ),
    },
    {
        "gramps_id": "I2592",
        "source_event": "E3223",
        "citation": "C2316",
        "evidence": (
            "Joseph Raucaz (pere): nomme dans le meme acte de bapteme du "
            "30/11/1848 que sa fille I2591"
        ),
    },
    {
        "gramps_id": "I2593",
        "source_event": "E3223",
        "citation": "C2316",
        "evidence": (
            "Francoise Neydet (mere): nommee dans le meme acte de bapteme "
            "du 30/11/1848 que sa fille I2591"
        ),
    },
    {
        "gramps_id": "I0741",
        "source_event": "E0879",
        "citation": "C0234",
        "evidence": (
            "Jean Joseph Raucaz: bapteme 23/09/1788 a Verrens, meme "
            "paroisse que le reste du lot, aucune confession alternative "
            "attestee"
        ),
    },
    {
        "gramps_id": "I0789",
        "source_event": "E0956",
        "citation": "C0253",
        "evidence": "Francois Raucaz: bapteme 08/08/1748 a Verrens-Arvey",
    },
]

DESCRIPTION = "Catholique (deduit du registre paroissial de Verrens)"

NOTE_TEXT = (
    "[CLOS] Religion catholique deduite pour la branche RAUCAZ de "
    "Verrens-Arvey (Savoie), lot du 21/09/2026.\n\n"
    "Critere retenu : registre paroissial de Verrens-Arvey (Savoie) et/ou "
    "mention explicite (cure, benediction donnee par un pretre) dans "
    "l'acte primaire. Aucune confession alternative attestee dans cette "
    "paroisse a cette epoque. Modelise en Event de type Religion (type "
    "Gramps standard, mappe vers la balise GEDCOM RELI par "
    "libgedcom.PERSONALCONSTANTEVENTS), pas en attribut - l'event porte "
    "sa propre date/lieu/citation, l'attribut Gramps n'en a pas.\n\n"
    "Personnes et preuves :\n"
    + "\n".join(f"- {entry['evidence']}" for entry in LOT)
    + "\n\n"
    "Exclu de ce lot : Jean RAUCAZ x Antoinette FRAIX-BURNET (mariage "
    "1827, benediction donnee par le R.P. Gabriel, capucin) - preuve "
    "explicite excellente mais risque d'homonymie non resolu entre "
    "plusieurs Jean/Claude RAUCAZ de generations differentes (voir "
    "N0158) - a traiter separement apres identification certaine."
)


def to_date_value(raw: dict | None) -> dict | None:
    """
    Strip a raw Gramps date object down to the fields EventSaveParams'
    DateValue accepts.

    Args:
        raw (dict | None): The "date" field as GET_EVENTS returns it -
            carries extra keys (calendar, sortval, year, ...) that a
            strict model rejects.

    Returns:
        dict | None: Only dateval/modifier/quality/text, or None.
    """
    if not raw:
        return None
    return {k: raw[k] for k in ("dateval", "modifier", "quality", "text") if k in raw}


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


async def main() -> None:
    """
    Add the Religion events and the shared note, or report what would
    change.

    Raises:
        SystemExit: When a gramps_id or event gramps_id from the lot
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
                    "place": source_event.get("place"),
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
