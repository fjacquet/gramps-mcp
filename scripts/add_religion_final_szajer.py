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
Add a Religion event to Artur Benedykt Szajer (I1996) - the single
person left over after a final sweep of Montferrier-sur-Lez and the
remaining scraps of the Polish nobility network (Olejow, Lwow,
Podzamcze), the last extension of the day's religion backfill.

Baptised 1898 at the named parish "Lwow, paroisse Sainte-Marie-
Madeleine" - the same church already used as strong proof for Cecylia
Dzialynska (I1096) in an earlier lot the same day.

Montferrier-sur-Lez yielded nothing (civil acts and an unproven
derived Geneanet source only). Olejow and Podzamcze yielded no new
person - their remaining uncovered people were either already
excluded for cause (homonymy, no citation) or turned out to already
have a Religion event from the Warszawa lot.

Same pattern as scripts/add_religion_raucaz_savoie.py: one Event per
person, dated/placed/cited from the act that proves it.

Idempotent: skips the person if they already carry a Religion event.
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

GRAMPS_ID = "I1996"
SOURCE_EVENT = "E2276"
CITATION = "C1840"
DESCRIPTION = "Catholique (paroisse Sainte-Marie-Madeleine, Lwow)"

NOTE_TEXT = (
    "[CLOS] Religion catholique pour Artur Benedykt Szajer (I1996), "
    "lot du 21/09/2026 - dernier candidat trouve en balayant "
    "Montferrier-sur-Lez et les miettes restantes du reseau noble "
    "polonais (Olejow, Lwow, Podzamcze), cloture de la reprise du "
    "jour.\n\n"
    "Bapteme 1898 a la paroisse nommee 'Lwow, paroisse Sainte-Marie-"
    "Madeleine' - la meme eglise deja utilisee comme preuve forte pour "
    "Cecylia Dzialynska (I1096) dans un lot ecrit plus tot le meme "
    "jour.\n\n"
    "Montferrier-sur-Lez n'a rien donne (actes civils et une source "
    "Geneanet derivee non probante seulement). Olejow et Podzamcze "
    "n'ont donne aucune nouvelle personne - leurs restes non couverts "
    "etaient soit deja exclus pour cause (homonymie, aucune citation), "
    "soit deja pourvus d'un event Religion par le lot Warszawa."
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
    Add the Religion event, or report what would change.

    Raises:
        SystemExit: When the person, event or citation cannot be
            found.
    """
    load_dotenv(REPO_ROOT / ".env")
    apply = "--apply" in sys.argv
    print(f"mode: {'APPLY' if apply else 'dry run'}")

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

        if GRAMPS_ID not in people:
            sys.exit(f"Unknown gramps_id: {GRAMPS_ID}")
        if SOURCE_EVENT not in events:
            sys.exit(f"Unknown event: {SOURCE_EVENT}")
        if CITATION not in citations:
            sys.exit(f"Unknown citation: {CITATION}")

        person = people[GRAMPS_ID]
        has_religion = any(
            events_by_handle.get(ref.get("ref"), {}).get("type") == "Religion"
            for ref in person.get("event_ref_list") or []
        )
        if has_religion:
            print(f"  {GRAMPS_ID}: SKIP already has Religion event")
            return
        print(f"  {GRAMPS_ID}: add Religion event")

        if not apply:
            print("\ndry run: 1 to update, no note or event created")
            return

        note = await client.make_api_call(
            ApiCalls.POST_NOTES, params={"text": NOTE_TEXT, "type": "Research"}
        )
        note_handle = pick(note, "Note")["handle"]
        print(f"note created: {note_handle}")

        source_event = events[SOURCE_EVENT]
        new_event = await client.make_api_call(
            ApiCalls.POST_EVENTS,
            params={
                "type": "Religion",
                "date": to_date_value(source_event.get("date")),
                "place": source_event.get("place") or None,
                "description": DESCRIPTION,
                "citation_list": [citations[CITATION]["handle"]],
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
        print(f"  {GRAMPS_ID}: Religion event {event_handle} attached")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
