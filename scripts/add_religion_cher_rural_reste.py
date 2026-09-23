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
Add a Religion event to 52 people of five rural Cher communes -
Vasselay, Quantilly, Saint-Georges-sur-Moulon, Saint-Eloy-de-Gy,
Vignoux-sous-les-Aix - all before 1793, all confirmed part of the same
corpus as Saint-Martin-d'Auxigny (scripts/add_religion_jacquet_
villaudy_clavier.py, written earlier the same day): rural France,
only the Catholic parish register existed before the Revolution, no
alternative confession possible in this zone.

A sixth candidate commune from the same place-ranking pass,
Saint-Germain-du-Puy, was dropped entirely: all 8 of its events date
1900-1929, outside the pre-1793 window this lot relies on.

Two people already covered by earlier lots the same day (Francoise
Dubuisson I0889, Francois Jacquet I0952) are naturally excluded by
this script's own idempotent check. Gabriel Jacquet (I1495) was left
out: his only citation (C0655) is a derived Geneanet source the tree
itself flags "sans reproduction d'acte" - not enough on its own. Anne
Mabilat (I1116) was kept instead, because her burial event carries a
second, corroborating citation (C2196). Jeanne Desmouliere (I1118) and
Sylvain Bardin (I1470), excluded from an earlier lot for a flagged
citation, are included here via a different, reliable CGH-B record
(marriage 1732, C0632) that names her deceased first husband and
resolves the homonymy that earlier flag was about.

Same pattern as scripts/add_religion_raucaz_savoie.py: one Event per
person, dated/placed/cited from the act that proves it, one shared
Research note.

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

LOT_DATA_FILE = Path(__file__).parent / "data" / "religion_cher_rural_reste.json"
LOT: list[dict] = json.loads(LOT_DATA_FILE.read_text())

DESCRIPTION = "Catholique (registre paroissial rural du Cher, avant 1793)"

NOTE_TEXT = (
    "[CLOS] Religion catholique deduite pour 52 personnes de cinq "
    "communes rurales du Cher - Vasselay, Quantilly, Saint-Georges-sur-"
    "Moulon, Saint-Eloy-de-Gy, Vignoux-sous-les-Aix - lot du 21/09/2026, "
    "suite du lot Saint-Martin-d'Auxigny ecrit plus tot le meme jour.\n\n"
    "Meme critere : registre paroissial mono-confessionnel connu, avant "
    "1793, meme corpus rural francais sans alternative confessionnelle. "
    "Verifie commune par commune avant inclusion (hierarchie "
    "geographique dans les citations) plutot que suppose par nom.\n\n"
    "Une sixieme commune candidate du meme classement par volume, "
    "SAINT-GERMAIN-DU-PUY, a ete abandonnee entierement : ses 8 events "
    "datent tous de 1900-1929, hors de la fenetre pre-1793 sur laquelle "
    "repose ce lot.\n\n"
    "Deux personnes deja pourvues d'un event Religion par des lots "
    "ecrits plus tot le meme jour (Francoise Dubuisson I0889, Francois "
    "Jacquet I0952) sont exclues naturellement par le controle "
    "d'idempotence de ce script. Gabriel Jacquet (I1495) a ete laisse "
    "de cote : sa seule citation (C0655) est une source Geneanet "
    "derivee que l'arbre annote lui-meme 'reserves... sans reproduction "
    "d'acte' - insuffisant seul. Anne Mabilat (I1116) est gardee a la "
    "place : son event de sepulture porte une seconde citation "
    "corroborante (C2196). Jeanne Desmoulieres (I1118) et Sylvain "
    "Bardin (I1470), ecartes d'un lot precedent pour une citation "
    "flaguee, sont inclus ici via un acte different, un releve CGH-B "
    "fiable (mariage 1732, C0632) qui nomme explicitement son premier "
    "mari decede et resout l'homonymie qui motivait ce flag.\n\n"
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
