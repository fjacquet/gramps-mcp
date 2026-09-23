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
Add a Religion event to the living members of the JACQUET branch, on
the tree owner's own direct testimony rather than an archival act -
the one deliberate exception to every other lot written the same day,
all of which required a citation and excluded every living person
found.

Scope and sourcing were confirmed explicitly with the tree owner
(Frederic Jacquet, 21/09/2026): the whole living JACQUET branch, one
shared note carrying the testimony in place of a citation - there is
no act to cite for a currently-held belief.

The living branch was found by listing all 107 JACQUET-surname people,
excluding the 8 that already carry a Religion event from earlier lots
the same day, then running check_living on the remaining 99 (delegated
recon, same day). 14 came back living; I0100 was dropped despite that
result - its estimated dates (1887-1916) are far too wide to be a real
living person, almost certainly Gramps's default inference from a
missing death date rather than genuine confidence, so it is treated as
deceased-unknown, not living, and is out of scope for this lot (and was
not covered by any dated-act lot either, since no acte exists for it
in this corpus).

Same event-modeling pattern as scripts/add_religion_raucaz_savoie.py
(one Event per person, type "Religion"), but with no date, no place
and an empty citation_list - a testimony has none of the three, unlike
every prior lot's archival acts.

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

LOT_GRAMPS_IDS = [
    "I0213",
    "I1821",
    "I0001",
    "I0000",
    "I0212",
    "I0211",
    "I0210",
    "I0155",
    "I0154",
    "I0105",
    "I0104",
    "I0103",
    "I2409",
]

DESCRIPTION = "Catholique (temoignage direct de Frederic Jacquet)"

NOTE_TEXT = (
    "[CLOS] Religion catholique pour la branche JACQUET vivante, lot "
    "du 21/09/2026 - temoignage direct de Frederic Jacquet (proprietaire "
    "de l'arbre), pas un acte d'archive.\n\n"
    "Exception deliberee a la regle du jour : chaque autre lot ecrit "
    "le 21/09/2026 exigeait une citation d'acte et excluait "
    "systematiquement toute personne vivante trouvee (I0001 lui-meme, "
    "I0018, plusieurs Puyobro, Castries...). Ici, le proprietaire de "
    "l'arbre confirme explicitement la confession de sa propre branche "
    "vivante - source valide mais differente, documentee comme telle.\n\n"
    "Perimetre : les 14 personnes JACQUET trouvees vivantes par "
    "check_living sur les 99 JACQUET sans event Religion (8 des 107 "
    "JACQUET totaux avaient deja un event Religion d'un lot anterieur "
    "le meme jour). I0100 est exclue malgre un resultat 'vivant' de "
    "l'outil : son estimation (1887-1916) est bien trop large pour etre "
    "une vraie personne vivante, presque certainement l'inference par "
    "defaut de Gramps en l'absence de date de deces plutot qu'une "
    "confiance reelle."
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


async def main() -> None:
    """
    Add the Religion events and the shared note, or report what would
    change.

    Raises:
        SystemExit: When a gramps_id from the lot cannot be found.
    """
    load_dotenv(REPO_ROOT / ".env")
    apply = "--apply" in sys.argv
    mode = "APPLY" if apply else "dry run"
    print(f"people in lot: {len(LOT_GRAMPS_IDS)}   mode: {mode}")

    client = GrampsWebAPIClient()
    try:
        people = {
            p["gramps_id"]: p for p in await page_through(client, ApiCalls.GET_PEOPLE)
        }
        events_by_handle = {
            e["handle"]: e for e in await page_through(client, ApiCalls.GET_EVENTS)
        }

        missing_people = [gid for gid in LOT_GRAMPS_IDS if gid not in people]
        if missing_people:
            sys.exit(f"Unknown gramps_id: {missing_people}")

        pending = []
        for gramps_id in LOT_GRAMPS_IDS:
            person = people[gramps_id]
            has_religion = any(
                events_by_handle.get(ref.get("ref"), {}).get("type") == "Religion"
                for ref in person.get("event_ref_list") or []
            )
            status = (
                "SKIP already has Religion event"
                if has_religion
                else "add Religion event"
            )
            print(f"  {gramps_id}: {status}")
            if not has_religion:
                pending.append(person)

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

        for person in pending:
            new_event = await client.make_api_call(
                ApiCalls.POST_EVENTS,
                params={
                    "type": "Religion",
                    "description": DESCRIPTION,
                    "citation_list": [],
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
            print(f"  {person['gramps_id']}: Religion event {event_handle} attached")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
