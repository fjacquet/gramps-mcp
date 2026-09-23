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
Add a Religion event to the KOCH/RUF/SCHLAGER people of Durmersheim and
Ottersdorf (grand-duchy of Baden, Germany), before civil registration
(1876) - each act is read from a named parish register (Kirchenbuch),
explicitly "katholische Gemeinde" or "katholische Pfarrgemeinde", never
deduced from the region alone (Baden is historically mixed
Catholic/Protestant). All five checked not living via check_living
before this script was written.

I2538 Franziska Schlager was found earlier the same day while
investigating the Algeria Bauer/Koch/Rippert branch (left pending
there, since her proof - a Baden parish register - was outside that
lot's scope) and is folded into this lot instead, where it belongs.

Leimersheim/Neupotz births in the same wider family were excluded: no
primary parish act was read for them directly (only passing mentions
in later Algerian civil records), and the Palatinate is a mixed
Catholic/Protestant region - no confession could be verified.

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
        "gramps_id": "I2531",
        "source_event": "E3165",
        "citation": "C2263",
        "confession": "Catholique",
        "evidence": (
            "Joseph Francois Koch: mariage 04/10/1824, Heiratsbuch, "
            "katholische Gemeinde de Durmersheim"
        ),
    },
    {
        "gramps_id": "I2537",
        "source_event": "E3143",
        "citation": "C2259",
        "confession": "Catholique",
        "evidence": (
            "Jean Koch: naissance 20/11/1836, Geburtenbuch, katholische "
            "Gemeinde de Durmersheim"
        ),
    },
    {
        "gramps_id": "I2532",
        "source_event": "E3163",
        "citation": "C2262",
        "confession": "Catholique",
        "evidence": (
            "Jeanne (Maria Johanna) Ruf: acte 1844, Heiratsbuch "
            "katholische Gemeinde de Durmersheim nommant aussi la "
            "Pfarrkirche d'Ottersdorf"
        ),
    },
    {
        "gramps_id": "I2538",
        "source_event": "E3159",
        "citation": "C2260",
        "confession": "Catholique",
        "evidence": (
            "Franziska (Francoise) Schlager: deces 27/11/1843, "
            "Sterbebuch, katholische Gemeinde de Durmersheim - trouve en "
            "cherchant la branche Algerie Bauer/Koch/Rippert, integre ici"
        ),
    },
    {
        "gramps_id": "I2549",
        "source_event": "E3160",
        "citation": "C2261",
        "confession": "Catholique",
        "evidence": (
            "Gertrud Koch: naissance 03/01/1848, Geburtenbuch, "
            "katholische Pfarrgemeinde de Durmersheim"
        ),
    },
]


def description_for(confession: str) -> str:
    """
    Build the Event description for a confession.

    Args:
        confession (str): "Catholique" or "Reforme".

    Returns:
        str: Description text.
    """
    return f"{confession} (registre paroissial de Durmersheim/Ottersdorf, Bade)"


NOTE_TEXT = (
    "[CLOS] Religion deduite pour la branche KOCH/RUF/SCHLAGER de "
    "Durmersheim et Ottersdorf (grand-duche de Bade), lot du 21/09/2026, "
    "5 personnes.\n\n"
    "Critere retenu : mention explicite lue dans le nom du registre "
    "paroissial cite (Kirchenbuch), jamais deduite de la region seule - "
    "le Bade et le Palatinat sont historiquement mixtes catholique/"
    "protestant. Les cinq personnes de ce lot sont toutes rattachees a "
    "un registre nomme explicitement 'katholische Gemeinde' ou "
    "'katholische Pfarrgemeinde'.\n\n"
    "I2538 Franziska Schlager avait ete trouvee plus tot le meme jour en "
    "enquetant sur la branche Algerie Bauer/Koch/Rippert (laissee en "
    "attente la-bas, sa preuve etant hors perimetre de ce lot) - "
    "integree ici, ou elle appartient.\n\n"
    "Exclus : les naissances a Leimersheim/Neupotz de la meme famille "
    "elargie - aucun acte paroissial primaire lu directement pour elles "
    "(seulement des mentions de passage dans des actes civils algeriens "
    "tardifs), et le Palatinat est une region mixte, confession non "
    "verifiable sans lecture directe.\n\n"
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
                    "description": description_for(entry["confession"]),
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
