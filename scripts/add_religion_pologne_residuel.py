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
Add a Religion event to 27 more people of the Polish Catholic nobility
network (Trzecieski, Potocki, Zamoyski, Wodzicki, Dzialynski) at
Krakow, Rymanow and Kornik - a continuation of scripts/
add_religion_potocki_branicki.py and scripts/add_religion_warszawa.py
written earlier the same day.

Six of the Krakow-area people (I2117, I2119-I2122, I2246) are anchored
at "Krakow par. Mariacka" - a named Catholic parish, stronger proof
than the network argument alone. Two people already covered by an
earlier lot the same day (I2043, I1982, via
scripts/add_religion_france_residuel_divers.py) are naturally
excluded by this script's idempotent check if that script ran first.

Excluded: I1078, I1101, I2250, I1044, I1092, I1097 (already had a
Religion event from earlier lots); I2116 and I2118, apparent duplicate
person records with no date or event at all - a data-quality issue to
merge, outside this recon's scope, not a religion question.

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
        "gramps_id": "I1038",
        "nom": "Elzbieta Antonina Trzecieska",
        "source_event": "E1316",
        "citation": "C0325",
    },
    {
        "gramps_id": "I1046",
        "nom": "Jan Wojciech Trzecieski",
        "source_event": "E1332",
        "citation": "C0326",
    },
    {
        "gramps_id": "I1053",
        "nom": "Krystyna Jakobina Maria Trzecieska",
        "source_event": "E1345",
        "citation": "C0326",
    },
    {
        "gramps_id": "I1032",
        "nom": "Aleksander Klemens Antoni Potocki",
        "source_event": "E1348",
        "citation": "C0324",
    },
    {
        "gramps_id": "I1033",
        "nom": "Jan Nepomucen Potocki",
        "source_event": "E1349",
        "citation": "C0328",
    },
    {
        "gramps_id": "I1034",
        "nom": "Roza Maria Alfonsyna Wodzicka",
        "source_event": "E1349",
        "citation": "C0328",
    },
    {
        "gramps_id": "I1994",
        "nom": "Konstancja Katarzyna Szajer",
        "source_event": "E2271",
        "citation": "C1838",
    },
    {
        "gramps_id": "I1063",
        "nom": "Dominik Kazimierz Potocki",
        "source_event": "E2280",
        "citation": "C1842",
    },
    {
        "gramps_id": "I1998",
        "nom": "Helena Maria Jozefa Badeni",
        "source_event": "E2280",
        "citation": "C1842",
    },
    {
        "gramps_id": "I1999",
        "nom": "Cecylia Maria Jadwiga Potocka",
        "source_event": "E2283",
        "citation": "C1844",
    },
    {
        "gramps_id": "I2000",
        "nom": "Anna Gabriela Maria Potocka",
        "source_event": "E2285",
        "citation": "C1845",
    },
    {
        "gramps_id": "I2043",
        "nom": "Andrzej Artur Zamoyski",
        "source_event": "E2358",
        "citation": "C1892",
    },
    {
        "gramps_id": "I2046",
        "nom": "Cecilia Zamoyska",
        "source_event": "E2362",
        "citation": "C1895",
    },
    {
        "gramps_id": "I2113",
        "nom": "Jozef Wincenty Dionizy Wodzicki",
        "source_event": "E2542",
        "citation": "C1941",
    },
    {
        "gramps_id": "I2114",
        "nom": "Petronela Jablonowska",
        "source_event": "E2562",
        "citation": "C1948",
    },
    {
        "gramps_id": "I2247",
        "nom": "Tekla Wodzicka h. wl.",
        "source_event": "E2556",
        "citation": "C1945",
    },
    {
        "gramps_id": "I2246",
        "nom": "Elzbieta Wodzicka h. wl.",
        "source_event": "E2552",
        "citation": "C1944",
    },
    {
        "gramps_id": "I2117",
        "nom": "Aleksander Tomasz Wodzicki",
        "source_event": "E2571",
        "citation": "C1951",
    },
    {
        "gramps_id": "I2119",
        "nom": "Aleksander Adam Ignacy Wodzicki",
        "source_event": "E2575",
        "citation": "C1954",
    },
    {
        "gramps_id": "I2120",
        "nom": "Franciszek Kanty Stanislaw Wodzicki",
        "source_event": "E2573",
        "citation": "C1952",
    },
    {
        "gramps_id": "I2121",
        "nom": "Wladyslaw Ignacy Napoleon Wodzicki",
        "source_event": "E2574",
        "citation": "C1953",
    },
    {
        "gramps_id": "I2122",
        "nom": "Henryk Franciszek Ksawery Wodzicki",
        "source_event": "E2576",
        "citation": "C1955",
    },
    {
        "gramps_id": "I2251",
        "nom": "Emilia Monika Petronela Anna Wodzicka",
        "source_event": "E2569",
        "citation": "C1950",
    },
    {
        "gramps_id": "I1041",
        "nom": "Jadwiga Maria Potocka",
        "source_event": "E2263",
        "citation": "C1831",
    },
    {
        "gramps_id": "I1042",
        "nom": "Teresa Jadwiga Maria Potocka",
        "source_event": "E2264",
        "citation": "C1832",
    },
    {
        "gramps_id": "I1037",
        "nom": "Anna Zofia Dzialynska",
        "source_event": "E1361",
        "citation": "C0335",
    },
    {
        "gramps_id": "I1982",
        "nom": "Klaudia Teofila Dzialynska",
        "source_event": "E2235",
        "citation": "C1813",
    },
]

DESCRIPTION = "Catholique (noblesse polonaise, Krakow/Rymanow/Kornik)"

NOTE_TEXT = (
    "[CLOS] Religion catholique pour 27 personnes du reseau POTOCKI/"
    "ZAMOYSKI/WODZICKI/DZIALYNSKI/TRZECIESKI a Krakow, Rymanow et "
    "Kornik, lot du 21/09/2026 - suite des lots POTOCKI/BRANICKI et "
    "WARSZAWA ecrits plus tot le meme jour.\n\n"
    "Six personnes (I2117, I2119, I2120, I2121, I2122, I2246) sont "
    "ancrees a 'Krakow par. Mariacka' - une paroisse catholique nommee "
    "explicitement, preuve plus forte que l'argument de reseau seul. "
    "Les autres reposent sur la meme base deja acceptee : noblesse "
    "polonaise catholique, reseau familial bien documente.\n\n"
    "Exclus (deja pourvus d'un event Religion par des lots anterieurs) "
    ": I1078, I1101, I2250, I1044, I1092, I1097. Exclus aussi : I2116 "
    "et I2118, des doublons apparents sans aucune date ni evenement - "
    "un probleme de qualite de donnees a fusionner, hors sujet de ce "
    "lot.\n\n"
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
