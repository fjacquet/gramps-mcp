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
Add a Religion event to the Polish-nobility POTOCKI/BRANICKI/DZIALYNSKI
people whose burial or death act is documented in this tree - Polish
Catholic magnates, one with an explicit named Catholic church (I1081,
crypt of the Potocki, church of Saint-Martin de Krzeszowice).

Recon deliberately cut the earlier ~30-40 estimate down to 16: the
Zamoyski branch and several later/peripheral Potocki generations had
no citation attached to their events, or an empty place, and were
excluded rather than guessed. Same pattern as
scripts/add_religion_raucaz_savoie.py: one Event per person, dated/
placed/cited from the act that proves it, one shared Research note.

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
        "gramps_id": "I1814",
        "event_handle": "10464541d23433e34072a671a126",
        "citation": "C1668",
        "evidence": "Wladyslaw Grzegorz Branicki: deces 27/08/1843, Warszawa",
    },
    {
        "gramps_id": "I1071",
        "event_handle": "104076eae21e5db141b027bb1324",
        "citation": "C0730",
        "evidence": "Roza Potocka: deces 30/10/1862, Paris",
    },
    {
        "gramps_id": "I1070",
        "event_handle": "104076ea46d05dc803d4d29d7660",
        "citation": "C1889",
        "evidence": (
            "Antoni Norbert Potocki: deces 18/10/1850, Warszawa, comte, "
            "general de brigade, senateur"
        ),
    },
    {
        "gramps_id": "I1078",
        "event_handle": "1040772e79c5e128e41aa703a2d",
        "citation": "C1670",
        "evidence": "Eliza Branicka (ep. Krasinska): deces 15/05/1876, Krakow",
    },
    {
        "gramps_id": "I1079",
        "event_handle": "1040772f118059aed7c0d20c6d40",
        "citation": "C1671",
        "evidence": "Aleksander Branicki: deces 19/09/1877, Nice",
    },
    {
        "gramps_id": "I1081",
        "event_handle": "104645cffe2613d407a59569cee",
        "citation": "C1674",
        "evidence": (
            "Katarzyna Zofia Branicka: inhumee apres le 30/09/1907 dans la "
            "crypte des Potocki, EGLISE SAINT-MARTIN DE KRZESZOWICE - "
            "eglise catholique nommee explicitement"
        ),
    },
    {
        "gramps_id": "I1085",
        "event_handle": "104645cf5acc68bb26be2165b95e",
        "citation": "C1669",
        "evidence": (
            "Ksawery Franciszek Branicki: inhume en 1880, cimetiere du "
            "chateau de Montresor (Indre-et-Loire)"
        ),
    },
    {
        "gramps_id": "I1087",
        "event_handle": "10407735aeaf69e263b803c1d4c0",
        "citation": "C1672",
        "evidence": "Zofia Branicka (ep. Odescalchi): deces 18/08/1886, Bassano Romano",
    },
    {
        "gramps_id": "I1088",
        "event_handle": "1040776f73af41b394193aa37c32",
        "citation": "C1673",
        "evidence": "Konstanty Grzegorz Branicki: deces 14/07/1884, Paris",
    },
    {
        "gramps_id": "I1089",
        "event_handle": "104077388f776e3e86d2932a2251",
        "citation": "C1675",
        "evidence": "Wladyslaw Michal Branicki: deces 17/07/1884, Paris",
    },
    {
        "gramps_id": "I1064",
        "event_handle": "104076e5b88b1f04db8ff9b115d9",
        "citation": "C0333",
        "evidence": "Przemyslaw Potocki: deces 23/11/1847, Warszawa",
    },
    {
        "gramps_id": "I1076",
        "event_handle": "1040772d74403400d1492a4de5fe",
        "citation": "C1891",
        "evidence": (
            "Wlodzimierz Stanislaw Potocki: deces 20/03/1820, Paris, ne a Tulczyn"
        ),
    },
    {
        "gramps_id": "I1084",
        "event_handle": "10407733b2a21ae09255bdcbf206",
        "citation": "C1888",
        "evidence": (
            "Roza Potocka (1802-1862): deces 27/10/1862, Warszawa, nee a Tulczyn"
        ),
    },
    {
        "gramps_id": "I1979",
        "event_handle": "1043aec9ec17160258358fd08178",
        "citation": "C1811",
        "evidence": (
            "Ksawery Franciszek Szymon Dzialynski: deces 13/03/1819, "
            "Konarzewo (Wielkopolskie)"
        ),
    },
    {
        "gramps_id": "I1092",
        "event_handle": "1043aecad22540a3c65f6467788d",
        "citation": "C1810",
        "evidence": (
            "Adam Tytus Dzialynski: inhume en 1861 a Kornik (siege "
            "familial des Dzialynski)"
        ),
    },
    {
        "gramps_id": "I1097",
        "event_handle": "10407789cce168fd826a568ec891",
        "citation": "C1816",
        "evidence": "Jan Kanty Dzialynski: deces 30/03/1880, Kornik (Wielkopolskie)",
    },
]

DESCRIPTION = "Catholique (noblesse polonaise)"

NOTE_TEXT = (
    "[CLOS] Religion catholique deduite pour la branche POTOCKI/BRANICKI/"
    "DZIALYNSKI (noblesse polonaise), lot du 21/09/2026.\n\n"
    "Critere retenu : contexte historique bien etabli (magnats polonais "
    "catholiques) et/ou mention explicite. La preuve la plus forte du "
    "lot est directe : Katarzyna Zofia Branicka (I1081) inhumee dans la "
    "crypte des Potocki, EGLISE SAINT-MARTIN DE KRZESZOWICE, nommee "
    "explicitement. Le volume final (16) est volontairement sous "
    "l'estimation initiale (~30-40) : la branche Zamoyski entiere et "
    "plusieurs generations Potocki plus tardives/peripheriques ont ete "
    "exclues, faute de citation attachee a un event date/localise - "
    "qualite du sourcage privilegiee au volume.\n\n"
    "Personnes et preuves :\n" + "\n".join(f"- {entry['evidence']}" for entry in LOT)
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
        SystemExit: When a gramps_id, event handle or citation from the
            lot cannot be found.
    """
    load_dotenv(REPO_ROOT / ".env")
    apply = "--apply" in sys.argv
    print(f"people in lot: {len(LOT)}   mode: {'APPLY' if apply else 'dry run'}")

    client = GrampsWebAPIClient()
    try:
        people = {
            p["gramps_id"]: p for p in await page_through(client, ApiCalls.GET_PEOPLE)
        }
        events_by_handle = {
            e["handle"]: e for e in await page_through(client, ApiCalls.GET_EVENTS)
        }
        citations = {
            c["gramps_id"]: c
            for c in await page_through(client, ApiCalls.GET_CITATIONS)
        }

        missing_people = [
            entry["gramps_id"] for entry in LOT if entry["gramps_id"] not in people
        ]
        missing_events = [
            entry["event_handle"]
            for entry in LOT
            if entry["event_handle"] not in events_by_handle
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
            source_event = events_by_handle[entry["event_handle"]]
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
