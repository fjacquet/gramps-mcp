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
Add a Religion event to 9 more people of the Polish Catholic nobility
network (Dzialynski, Zamoyski/Broel-Plater, Wodzicki, Dzieduszycki) at
Lwow, Poznan, Podzamcze and Olejow - the last extension of scripts/
add_religion_potocki_branicki.py, scripts/add_religion_warszawa.py and
scripts/add_religion_pologne_residuel.py written earlier the same day.

Strongest proof: Cecylia Dzialynska (I1096), baptised at the named
parish "Lwow, eglise Sainte-Marie-Madeleine". The rest rest on the
same already-accepted network basis.

Excluded: Aleksander Tomasz Wodzicki (I1987) - shares a name with
I2117 already covered in an earlier lot but with different dates, a
possible duplicate/homonym not resolved here, left alone rather than
risk a mix-up. Kazimierz Stanislaw Michal Wodzicki (I1984) - his only
event (occupation) carries no citation. Oleszyce yielded no new
candidate: its two people (I1033, I1035) already have a Religion event
from earlier lots. Poznan/Kornik/Podzamcze(remainder)/Kurtuvenai were
confirmed already fully covered by the place-ranking tool's own
covered/total counts, not re-queried individually.

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
        "gramps_id": "I1096",
        "nom": "Cecylia Dzialynska",
        "source_event": "E2234",
        "citation": "C1819",
    },
    {
        "gramps_id": "I1094",
        "nom": "Elzbieta Dzialynska (ep. Czartoryska)",
        "source_event": "E1432",
        "citation": "C1815",
    },
    {
        "gramps_id": "I1107",
        "nom": "Elzbieta Barbara Zamoyska (ep. Broel-Plater)",
        "source_event": "E1458",
        "citation": "C1858",
    },
    {
        "gramps_id": "I1986",
        "nom": "Kazimierz Aleksander Jozef Wodzicki",
        "source_event": "E2246",
        "citation": "C1824",
    },
    {
        "gramps_id": "I1988",
        "nom": "Antoni Kazimierz Wodzicki",
        "source_event": "E2251",
        "citation": "C1826",
    },
    {
        "gramps_id": "I1990",
        "nom": "Teresa Maria Magdalena Wodzicka",
        "source_event": "E2255",
        "citation": "C1828",
    },
    {
        "gramps_id": "I1989",
        "nom": "Jerzy Kornel Wodzicki",
        "source_event": "E2254",
        "citation": "C1827",
    },
    {
        "gramps_id": "I1991",
        "nom": "Maria Marta Wodzicka",
        "source_event": "E2259",
        "citation": "C1829",
    },
    {
        "gramps_id": "I2123",
        "nom": "Aleksander Stanislaw Dzieduszycki",
        "source_event": "E2578",
        "citation": "C1956",
    },
]

DESCRIPTION = "Catholique (noblesse polonaise, Lwow/Poznan/Podzamcze/Olejow)"

NOTE_TEXT = (
    "[CLOS] Religion catholique pour 9 dernieres personnes du reseau "
    "DZIALYNSKI/ZAMOYSKI-BROEL-PLATER/WODZICKI/DZIEDUSZYCKI a Lwow, "
    "Poznan, Podzamcze et Olejow, lot du 21/09/2026 - derniere "
    "extension des lots POTOCKI/BRANICKI, WARSZAWA et POLOGNE RESIDUEL "
    "ecrits plus tot le meme jour.\n\n"
    "Preuve la plus forte : Cecylia Dzialynska (I1096), baptisee a la "
    "paroisse nommee 'Lwow, eglise Sainte-Marie-Madeleine'. Le reste "
    "repose sur la meme base de reseau deja acceptee.\n\n"
    "Exclus : Aleksander Tomasz Wodzicki (I1987) - meme nom qu'un "
    "I2117 deja couvert par un lot anterieur mais avec des dates "
    "differentes, doublon/homonyme possible non resolu, laisse de cote "
    "plutot que de risquer une confusion. Kazimierz Stanislaw Michal "
    "Wodzicki (I1984) - son seul event (occupation) n'a aucune "
    "citation. Oleszyce n'a donne aucun nouveau candidat : ses deux "
    "personnes (I1033, I1035) ont deja un event Religion. Poznan/"
    "Kornik/Podzamcze(reste)/Kurtuvenai confirmes deja entierement "
    "couverts via le comptage couvert/total de l'outil de classement, "
    "pas re-interroges individuellement.\n\n"
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
