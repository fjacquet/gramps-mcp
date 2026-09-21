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
Add a Religion event to 16 PAGAN people of Sutz-Lattrigen (canton of
Berne) - the same K Nidau parish register (confirmed by note N0189)
already used for scripts/add_religion_nidau_pagan.py written earlier
the same day: Nidau and Sutz share the same reformed register, so the
same certainty applies.

Excluded: the two Pagan-Dupan couples (I1196/I1197/I1198/I1199) - the
same unresolved homonymy already flagged in the Nidau lot (note N0198)
applies here too, not reopened.

Not the same corpus: Les Ponts-de-Martel (Neuchatel canton), Bienne
(bi-confessional, no direct proof found) and Hilterfingen (mixed
Kirchenbuch collection, ambiguous identity notes) were checked the
same recon and dropped - no candidates from them in this lot.

Same pattern as scripts/add_religion_raucaz_savoie.py: one Event per
person, dated/placed/cited from the act that proves it, one shared
Research note.

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
        "gramps_id": "I0339",
        "nom": "Abraham Pagan",
        "source_event": "E0467",
        "citation": "C0120",
    },
    {
        "gramps_id": "I0449",
        "nom": "Abraham Pagan",
        "source_event": "E0468",
        "citation": "C0121",
    },
    {
        "gramps_id": "I0450",
        "nom": "Abraham Pagan",
        "source_event": "E0471",
        "citation": "C0122",
    },
    {
        "gramps_id": "I0451",
        "nom": "Abraham Pagan",
        "source_event": "E0474",
        "citation": "C0123",
    },
    {
        "gramps_id": "I0707",
        "nom": "Emanuel Pagan",
        "source_event": "E0846",
        "citation": "C0210",
    },
    {
        "gramps_id": "I0708",
        "nom": "Viktor Pagan",
        "source_event": "E0847",
        "citation": "C0211",
    },
    {
        "gramps_id": "I0709",
        "nom": "Anna Iseli",
        "source_event": "E0847",
        "citation": "C0211",
    },
    {
        "gramps_id": "I0710",
        "nom": "Barbara Sorgen",
        "source_event": "E0849",
        "citation": "C0213",
    },
    {
        "gramps_id": "I0711",
        "nom": "Johann Gabriel Pagan",
        "source_event": "E0849",
        "citation": "C0213",
    },
    {
        "gramps_id": "I0435",
        "nom": "David Pagan",
        "source_event": "E0848",
        "citation": "C0212",
    },
    {
        "gramps_id": "I1200",
        "nom": "Abraham Pagan",
        "source_event": "E1568",
        "citation": "C0429",
    },
    {
        "gramps_id": "I1201",
        "nom": "Maria Abraham",
        "source_event": "E1568",
        "citation": "C0429",
    },
    {
        "gramps_id": "I1202",
        "nom": "Salome Pagan",
        "source_event": "E1569",
        "citation": "C0430",
    },
    {
        "gramps_id": "I1203",
        "nom": "Abraham Marin",
        "source_event": "E1569",
        "citation": "C0430",
    },
    {
        "gramps_id": "I1183",
        "nom": "Friedrich Pagan",
        "source_event": "E1688",
        "citation": "C0550",
    },
    {
        "gramps_id": "I1423",
        "nom": "Maria Gnagi",
        "source_event": "E1688",
        "citation": "C0550",
    },
]

DESCRIPTION = "Reforme (registre paroissial K Nidau, couvre Nidau et Sutz-Lattrigen)"

NOTE_TEXT = (
    "[CLOS] Religion reformee pour 16 personnes PAGAN de Sutz-Lattrigen "
    "(canton de Berne), lot du 21/09/2026 - suite du lot NIDAU/PAGAN "
    "ecrit plus tot le meme jour.\n\n"
    "Meme registre paroissial K Nidau que Nidau lui-meme (confirme par "
    "la note N0189 existante : Nidau et Sutz partagent le meme "
    "registre reforme) - meme certitude que le lot Nidau original.\n\n"
    "Exclus : les deux couples Pagan-Dupan (I1196/I1197/I1198/I1199) - "
    "meme homonymie non resolue deja signalee dans le lot Nidau (note "
    "N0198), pas rouverte ici.\n\n"
    "Pas le meme corpus (verifie et abandonne dans le meme recon) : Les "
    "Ponts-de-Martel (canton de Neuchatel, pas de preuve explicite), "
    "Bienne (bi-confessionnelle historiquement, aucune preuve directe) "
    "et Hilterfingen (collection mixte de registres, identites "
    "ambigues).\n\n"
    "Personnes (nom - gramps_id - citation) :\n"
    + "\n".join(
        f"- {entry['nom']} - {entry['gramps_id']} - {entry['citation']}"
        for entry in LOT
    )
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
