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
Add a Religion event to the PAGAN people whose baptism, birth or death
act is explicitly reformed - the Nidau parish register (canton of
Berne, reformed since 1528) or a named reformed Geneva temple
(Saint-Gervais). Stops before Jean-Pierre Pagan (I0090), who converts
to Catholicism, and before the generations N0314 itself flags as not
established (I0217, I0225) or otherwise disputed by identity (I1198,
I1333 - see that note's own homonymy caveats).

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
        "gramps_id": "I0092",
        "source_event": "E0117",
        "citation": "C2318",
        "evidence": (
            "Laurent Philippe Pagan: deces 05/11/1958, culte au temple de "
            "Saint-Gervais (Journal de Geneve, 07/11/1958)"
        ),
    },
    {
        "gramps_id": "I0223",
        "source_event": "E0282",
        "citation": "C0056",
        "evidence": (
            "Pernette Chastel: bapteme 05/01/1770 au Temple de "
            "Saint-Gervais, Geneve, famille chassee de Montbeliard pour "
            "calvinisme (N0094)"
        ),
    },
    {
        "gramps_id": "I1212",
        "source_event": "E2476",
        "citation": "C1901",
        "evidence": (
            "Johan Jacob Pagan: bapteme 12/01/1716, registre paroissial "
            "reforme de Nidau"
        ),
    },
    {
        "gramps_id": "I1211",
        "source_event": "E1573",
        "citation": "C0435",
        "evidence": (
            "Rudolff Pagan: naissance 13/08/1752 a Nidau, fils de Johan "
            "Jacob Pagan I1212, meme corpus reforme"
        ),
    },
    {
        "gramps_id": "I1217",
        "source_event": "E1575",
        "citation": "C0437",
        "evidence": (
            "Johann Emanuel Pagan: naissance 24/06/1764 a Nidau, fils de "
            "Johan Jacob Pagan I1212, meme corpus reforme"
        ),
    },
    {
        "gramps_id": "I1218",
        "source_event": "E1576",
        "citation": "C0438",
        "evidence": (
            "Catharina Elisabeth Pagan: naissance 23/10/1767 a Nidau, "
            "fille de Johan Jacob Pagan I1212, meme corpus reforme"
        ),
    },
    {
        "gramps_id": "I1350",
        "source_event": "E1642",
        "citation": "C0503",
        "evidence": (
            "Johann Rodolph Pagan: bapteme 12/02/1719, registre "
            "paroissial reforme de Nidau"
        ),
    },
    {
        "gramps_id": "I1454",
        "source_event": "E1716",
        "citation": "C0579",
        "evidence": (
            "Anna Dorothea Pagan: naissance 27/10/1721, registre "
            "paroissial reforme de Nidau"
        ),
    },
]

DESCRIPTION = "Reforme (registre paroissial reforme de Nidau, ou temple de Geneve)"

NOTE_TEXT = (
    "[CLOS] Religion reformee deduite pour la branche PAGAN (Nidau, "
    "canton de Berne, et Geneve), lot du 21/09/2026.\n\n"
    "Critere retenu : registre paroissial reforme connu (canton de Berne, "
    "reforme depuis 1528 ; K Nidau) et/ou mention explicite (temple, "
    "culte protestant, famille chassee de Montbeliard pour calvinisme). "
    "Arrete avant Jean-Pierre PAGAN (I0090), converti catholique, mort "
    "en 2019 - voir N0314. Exclus de ce lot pour identite non tranchee : "
    "I1198 Johan Jacob Pagan dit 'V.D.M.' (pasteur, acte de 1772 - la "
    "preuve la plus explicite du dossier, mais identite a rapprocher de "
    "Samuel Pagan I1196, non tranchee, voir N0198) et son epouse I1199 "
    "Janette Dupan ; I1333 Abraham Pagan (trois mariages concurrents, "
    "voir N0213/N0246) ; I0217 Louis Charles Pagan et I0225 Ami Pagan, "
    "explicitement non etablis par N0314 elle-meme.\n\n"
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
