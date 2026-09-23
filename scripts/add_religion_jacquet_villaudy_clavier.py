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
Add a Religion event to the JACQUET/VILLAUDY/CLAVIER/LARPENT people of
Saint-Martin-d'Auxigny (Cher) whose birth, baptism, marriage or burial
act is dated before 1793 at the parish, church or cemetery place of
that commune. Before 1793 only the Catholic parish register existed in
this rural corpus - no alternative confession was possible - so the
"registre mono-confessionnel connu" criterion applies without needing
an explicit "Saints Sacrements"-style mention on every single act.

Built place-by-place (the three Saint-Martin-d'Auxigny place handles,
events filtered pre-1793), not person-by-person, because of volume -
95 candidates, the largest lot of this backfill. Same pattern as
scripts/add_religion_raucaz_savoie.py otherwise: one Event per person,
dated/placed/cited from the act that proves it, one shared Research
note.

Two corrections already folded in from the parallel Cœur/Bochetel
recon: I1764/I1766 (Arragepied) were dropped (their only citation,
C0190, is the same disqualified Ovaere-tree source that sank that
other lot); I1768/I1769 (Dubuisson/Cailbin) were kept but repointed
from their C0190-sourced birth to their C0620-sourced marriage
(E2077) instead.

Idempotent: skips any person that already carries a Religion event.
Writes only with --apply.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.gramps_mcp.client import GrampsWebAPIClient  # noqa: E402
from src.gramps_mcp.models.api_calls import ApiCalls  # noqa: E402

LOT_DATA_FILE = (
    Path(__file__).parent / "data" / "religion_jacquet_villaudy_clavier.json"
)
LOT: list[dict] = json.loads(LOT_DATA_FILE.read_text())

DESCRIPTION = "Catholique (registre paroissial de Saint-Martin-d'Auxigny, avant 1793)"

NOTE_TEXT = (
    "[CLOS] Religion catholique deduite pour la branche JACQUET/VILLAUDY/"
    "CLAVIER/LARPENT de Saint-Martin-d'Auxigny (Cher), lot du 21/09/2026, "
    "95 personnes.\n\n"
    "Critere retenu : registre paroissial mono-confessionnel connu. Avant "
    "1793 seul le registre catholique existait dans cette zone rurale du "
    "Cher, sans alternative confessionnelle possible - le critere "
    "s'applique donc a tout acte date/localise dans ce corpus avant "
    "cette date, sans exiger une mention explicite type 'Saints "
    "Sacrements' sur chaque acte individuellement (cette mention "
    "explicite reste attestee ailleurs dans l'arbre, ex. C2192, pour ce "
    "meme corpus).\n\n"
    "Corrections issues du recon parallele sur la chaine Coeur/Bochetel "
    "le meme jour : Andre et Marguerite ARRAGEPIED (I1764, I1766) "
    "retires de ce lot - leur seule citation, C0190, est la meme source "
    "Ovaere disqualifiee ('ne vaut pas preuve') qui a fait ecarter cette "
    "chaine entiere. Sylvain DUBUISSON (I1768) et Marie CAILBIN (I1769) "
    "gardes mais repointes de leur naissance (C0190) vers leur mariage "
    "(E2077, C0620, valide).\n\n"
    "Coupure de perimetre : limite aux trois lieux nommes "
    "'Saint-Martin-d'Auxigny' (municipalite/eglise/cimetiere) et a la "
    "fenetre pre-1793. D'autres personnes du meme corpus rattachees a "
    "d'autres paroisses voisines du Cher, ou datees apres 1793, ne sont "
    "pas couvertes ici.\n\n"
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
