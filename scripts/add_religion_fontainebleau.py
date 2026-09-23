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
Add a Religion event to 3 BRAUD/PAGAN people baptised at the
Fontainebleau evangelical church - a small French Protestant minority
pocket, found while checking Fontainebleau, Magescq and Les Roches for
the day's religion backfill.

Direct proof: Louise Marguerite Germaine Pagan (I0278), baptised
17/04/1881 at the "Eglise evangelique libre de Fontainebleau", act
signed "A. Racine BRAUD, PASTEUR". Her aunts Mary Fanny (I0266) and
Matilda Braud (I0268) were baptised 16/09/1849 at the "Chapelle
evangelique de Fontainebleau" - a named Protestant place of worship.
Robert Yvan Lennox Pagan (I0279, Louise's brother) was excluded: only
a civil birth record exists for him, no baptism of his own found.

Magescq (Landes) and Les Roches (a Saint-Martin-d'Auxigny hamlet, but
all its events postdate 1793) yielded nothing - civil acts only, no
religious wording.

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
        "gramps_id": "I0278",
        "source_event": "E0271",
        "citation": "C0031",
        "evidence": (
            "Louise Marguerite Germaine Pagan: bapteme 17/04/1881, "
            "Eglise evangelique libre de Fontainebleau, acte signe "
            "'A. Racine BRAUD, PASTEUR'"
        ),
    },
    {
        "gramps_id": "I0266",
        "source_event": "E0269",
        "citation": "C0030",
        "evidence": (
            "Mary Fanny Braud: bapteme 16/09/1849, Chapelle evangelique "
            "de Fontainebleau"
        ),
    },
    {
        "gramps_id": "I0268",
        "source_event": "E0270",
        "citation": "C0034",
        "evidence": (
            "Matilda Braud: bapteme 16/09/1849, meme Chapelle "
            "evangelique de Fontainebleau que sa soeur"
        ),
    },
]

DESCRIPTION = "Reforme evangelique (Eglise/Chapelle evangelique de Fontainebleau)"

NOTE_TEXT = (
    "[CLOS] Religion reformee evangelique pour 3 personnes BRAUD/PAGAN "
    "baptisees a Fontainebleau (Seine-et-Marne), lot du 21/09/2026 - "
    "une poche protestante minoritaire francaise, trouvee en verifiant "
    "Fontainebleau/Magescq/Les Roches.\n\n"
    "Preuve directe : Louise Marguerite Germaine Pagan (I0278), "
    "bapteme 17/04/1881 a l'Eglise evangelique libre de Fontainebleau, "
    "acte signe 'A. Racine BRAUD, PASTEUR'. Ses tantes Mary Fanny "
    "(I0266) et Matilda Braud (I0268), baptisees le 16/09/1849 a la "
    "Chapelle evangelique de Fontainebleau - lieu de culte protestant "
    "nomme explicitement.\n\n"
    "Exclu : Robert Yvan Lennox Pagan (I0279, frere de Louise) - "
    "seulement un acte civil de naissance trouve, aucun bapteme propre "
    "pour lui personnellement. Magescq (Landes) et Les Roches (hameau "
    "de Saint-Martin-d'Auxigny, mais tous ses actes posterieurs a 1793) "
    "verifies aussi le meme jour : actes civils uniquement, rien a "
    "ecrire.\n\n"
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
