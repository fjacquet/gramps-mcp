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
Add a Religion event to 22 Warszawa members of the Polish-nobility
POTOCKI/ZAMOYSKI/PLATER-ZYBERK/JELSKA/SAPIEHA network, a continuation
of scripts/add_religion_potocki_branicki.py written earlier the same
day.

That earlier lot's recon reported the Zamoyski branch and several
later Potocki generations had "no citation attached" and excluded
them. A place-ranking pass later the same day showed 33 events at
Warszawa with only 10 already covered - meaning citations DO exist for
most of them, contradicting the earlier report. Re-checked directly:
the citations are there. This lot corrects that miss.

Strongest proof in the lot: Karolina Wodzicka (I2250) died at the
named Catholic parish "Warszawa sw. Krzyza" (Sainte-Croix). The other
21 rest on the same basis already accepted for the Potocki/Branicki
lot: Polish Catholic nobility, well-documented family network. Five
people close to the modern era (I1044 d.1994, I2022 d.1977, I2017
d.1964, I1103 d.1940, I2007 d.1939) were individually checked with
check_living - all confirmed deceased with a direct death record.

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
        "gramps_id": "I1044",
        "nom": "Ignacy Potocki",
        "source_event": "E1328",
        "citation": "C0324",
    },
    {
        "gramps_id": "I1035",
        "nom": "Maria Helena Szajer",
        "source_event": "E1358",
        "citation": "C0331",
    },
    {
        "gramps_id": "I1065",
        "nom": "Teresa Sapieha",
        "source_event": "E1378",
        "citation": "C0334",
    },
    {
        "gramps_id": "I1100",
        "nom": "Andrzej Przemyslaw Zamoyski",
        "source_event": "E1444",
        "citation": "C0344",
    },
    {
        "gramps_id": "I1101",
        "nom": "Roza Maria Elzbieta Zamoyska",
        "source_event": "E1446",
        "citation": "C0344",
    },
    {
        "gramps_id": "I1103",
        "nom": "Adam Michal Ludwik Zamoyski",
        "source_event": "E1451",
        "citation": "C0344",
    },
    {
        "gramps_id": "I1104",
        "nom": "Teresa Maria Elzbieta Zamoyska",
        "source_event": "E1452",
        "citation": "C0344",
    },
    {
        "gramps_id": "I2007",
        "nom": "Ludwik Wiktor Plater-Zyberk",
        "source_event": "E2298",
        "citation": "C1851",
    },
    {
        "gramps_id": "I1099",
        "nom": "Stanislaw Kostka Jan Zamoyski",
        "source_event": "E2292",
        "citation": "C1848",
    },
    {
        "gramps_id": "I1066",
        "nom": "Roza Maria Ewa Potocka",
        "source_event": "E2292",
        "citation": "C1848",
    },
    {
        "gramps_id": "I2017",
        "nom": "Elzbieta Roza Plater-Zyberk",
        "source_event": "E2319",
        "citation": "C1861",
    },
    {
        "gramps_id": "I2022",
        "nom": "Antoni Wojciech Piotr Plater-Zyberk",
        "source_event": "E2330",
        "citation": "C1866",
    },
    {
        "gramps_id": "I2044",
        "nom": "Zofia Andzheevna Zamoyska",
        "source_event": "E2359",
        "citation": "C1893",
    },
    {
        "gramps_id": "I2047",
        "nom": "Rosa Constance Eva Zamoyska",
        "source_event": "E2364",
        "citation": "C1896",
    },
    {
        "gramps_id": "I2048",
        "nom": "Zdzislaw Zamoyski",
        "source_event": "E2366",
        "citation": "C1897",
    },
    {
        "gramps_id": "I2209",
        "nom": "Izabela Jelska",
        "source_event": "E2499",
        "citation": "C1919",
    },
    {
        "gramps_id": "I2225",
        "nom": "Karolina Jelska h. Pielesz",
        "source_event": "E2511",
        "citation": "C1925",
    },
    {
        "gramps_id": "I2228",
        "nom": "Amelia Potocka",
        "source_event": "E2518",
        "citation": "C1928",
    },
    {
        "gramps_id": "I2416",
        "nom": "Andrzej Hieronim Zamoyski",
        "source_event": "E2846",
        "citation": "C2113",
    },
    {
        "gramps_id": "I2417",
        "nom": "Konstancja Czartoryska",
        "source_event": "E2846",
        "citation": "C2113",
    },
    {
        "gramps_id": "I2041",
        "nom": "Stanislaw Kostka Franciszek Zamoyski",
        "source_event": "E2852",
        "citation": "C2115",
    },
    {
        "gramps_id": "I2250",
        "nom": "Karolina Ludwika Wodzicka",
        "source_event": "E2566",
        "citation": "C1949",
    },
]

DESCRIPTION = "Catholique (noblesse polonaise, Warszawa)"

NOTE_TEXT = (
    "[CLOS] Religion catholique pour 22 personnes du reseau POTOCKI/"
    "ZAMOYSKI/PLATER-ZYBERK/JELSKA/SAPIEHA a Warszawa, lot du 21/09/2026 "
    "- suite du lot POTOCKI/BRANICKI ecrit plus tot le meme jour.\n\n"
    "Ce lot corrige une erreur du recon precedent : il avait exclu la "
    "branche Zamoyski et plusieurs generations Potocki tardives pour "
    "'aucune citation attachee'. Un classement des lieux par volume "
    "d'events a montre 33 events a Warszawa dont seulement 10 deja "
    "couverts - verifie directement, les citations existent bel et "
    "bien pour la plupart de ces personnes.\n\n"
    "Preuve la plus forte : Karolina Wodzicka (I2250), decedee a la "
    "paroisse nommee explicitement 'Warszawa sw. Krzyza' (Sainte-"
    "Croix), eglise catholique. Les 21 autres reposent sur la meme base "
    "deja acceptee pour le lot Potocki/Branicki : noblesse polonaise "
    "catholique, reseau familial bien documente. Cinq personnes proches "
    "de l'epoque moderne (I1044 mort 1994, I2022 mort 1977, I2017 mort "
    "1964, I1103 mort 1940, I2007 mort 1939) verifiees individuellement "
    "via check_living - toutes confirmees decedees avec preuve directe.\n\n"
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
