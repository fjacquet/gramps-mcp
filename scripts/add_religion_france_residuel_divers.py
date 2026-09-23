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
Add a Religion event to 9 people found while checking a batch of small
residual places one by one (Paris, Poitiers, Tours-sur-Marne, Eglise
de Verrens, Le Castellard-Melan, Castries, Vienne, Kurtuvenai) - no
blanket "France/Europe is Catholic" assumption, each place checked on
its own evidence.

Notable: Anna Catharina Pagan (I0355) is catholic in Vienna, Austria
(named parish "Wiener Neustadt-Hauptpfarre") - a DIFFERENT confession
than the Pagan branch of Geneva already written the same day
(scripts/add_religion_geneve_pre1798.py, reformed). Same surname, same
family network at a distance, opposite confession - proof that local
evidence overrides a surname's usual pattern.

Three people (I0076, I1015, I1014) are the same Verrens-Arvey/RAUCAZ
corpus already written (scripts/add_religion_raucaz_savoie.py), simply
found via a different place record ("Eglise de Verrens" rather than
"Verrens-Arvey"). The rest extend the already-validated Polish
Catholic nobility network (Zamoyski, Dzialynski, Plater-Zyberk).

Places checked and dropped entirely, no candidates: Paris (I0274,
Messerli/Epinaut couple - no religious evidence), Poitiers (Jacques
Coeur already covered, nothing else), Tours-sur-Marne (100% civil
acts), Le Castellard-Melan (100% civil acts, same verdict as Mariaud
the same day), Castries (2 of 4 people living, the other 2 have no
religious evidence). Two living people were caught and must never be
touched: I0001 and I0018, both confirmed via check_living.

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
        "gramps_id": "I0355",
        "source_event": "E0391",
        "citation": "C0105",
        "description": (
            "Catholique (Vienne, Autriche - paroisse Wiener "
            "Neustadt-Hauptpfarre, diocese de Vienne)"
        ),
        "evidence": (
            "Anna Catharina Pagan: registre catholique nomme "
            "explicitement (Parish Wiener Neustadt-Hauptpfarre) - "
            "confession opposee a la branche Pagan de Geneve, "
            "preuve locale prime sur le patronyme"
        ),
    },
    {
        "gramps_id": "I2043",
        "source_event": "E2356",
        "citation": "C1892",
        "description": "Catholique (noblesse polonaise, reseau Zamoyski)",
        "evidence": (
            "Andrzej Artur Zamoyski: reseau Zamoyski deja valide (lot Warszawa)"
        ),
    },
    {
        "gramps_id": "I1982",
        "source_event": "E2237",
        "citation": "C1813",
        "description": "Catholique (noblesse polonaise, reseau Dzialynski)",
        "evidence": (
            "Klaudia Teofila Dzialynska: fille de Ksawery Franciszek "
            "Szymon Dzialynski (I1979, deja couvert)"
        ),
    },
    {
        "gramps_id": "I2019",
        "source_event": "E2322",
        "citation": "C1863",
        "description": "Catholique (noblesse polonaise, reseau Plater-Zyberk)",
        "evidence": (
            "Stefan Plater-Zyberk: reseau Plater-Zyberk deja valide (lot Warszawa)"
        ),
    },
    {
        "gramps_id": "I2020",
        "source_event": "E2324",
        "citation": "C1864",
        "description": "Catholique (noblesse polonaise, reseau Plater-Zyberk)",
        "evidence": "Ludwik Michal Tomasz Plater-Zyberk: meme reseau",
    },
    {
        "gramps_id": "I2021",
        "source_event": "E2326",
        "citation": "C1865",
        "description": "Catholique (noblesse polonaise, reseau Plater-Zyberk)",
        "evidence": "Teresa Maria Antonina Plater-Zyberk: meme reseau",
    },
    {
        "gramps_id": "I0076",
        "source_event": "E0096",
        "citation": "C0043",
        "description": "Catholique (Eglise de Verrens, Verrens-Arvey, Savoie)",
        "evidence": "Gasparde Josephte Grange: meme corpus RAUCAZ deja ecrit",
    },
    {
        "gramps_id": "I1015",
        "source_event": "E1281",
        "citation": "C0313",
        "description": "Catholique (Eglise de Verrens, Verrens-Arvey, Savoie)",
        "evidence": "Joseph Lerse: meme corpus RAUCAZ",
    },
    {
        "gramps_id": "I1014",
        "source_event": "E1281",
        "citation": "C0313",
        "description": "Catholique (Eglise de Verrens, Verrens-Arvey, Savoie)",
        "evidence": "Peronne Raucaz: meme corpus RAUCAZ",
    },
]

NOTE_TEXT = (
    "[CLOS] Religion catholique pour 9 personnes trouvees en verifiant "
    "individuellement un lot de petits lieux residuels (Paris, "
    "Poitiers, Tours-sur-Marne, Eglise de Verrens, Le Castellard-Melan, "
    "Castries, Vienne, Kurtuvenai), lot du 21/09/2026 - aucune "
    "supposition globale 'France/Europe = catholique', chaque lieu "
    "verifie sur sa propre preuve.\n\n"
    "A noter : Anna Catharina Pagan (I0355) est catholique a Vienne "
    "(Autriche), paroisse nommee explicitement 'Wiener Neustadt-"
    "Hauptpfarre' - confession OPPOSEE a la branche Pagan de Geneve "
    "deja ecrite le meme jour (reforme) - meme patronyme, meme reseau "
    "familial eloigne, confession differente : la preuve locale prime "
    "toujours sur le patronyme.\n\n"
    "I0076, I1015, I1014 sont le meme corpus Verrens-Arvey/RAUCAZ deja "
    "ecrit, trouves via une fiche de lieu differente ('Eglise de "
    "Verrens'). Le reste etend le reseau noblesse polonaise catholique "
    "deja valide (Zamoyski, Dzialynski, Plater-Zyberk).\n\n"
    "Lieux verifies et abandonnes entierement, aucun candidat : Paris "
    "(reste), Poitiers (reste), Tours-sur-Marne (actes 100% civils), "
    "Le Castellard-Melan (actes 100% civils, meme verdict que Mariaud "
    "le meme jour), Castries (2 personnes vivantes, 2 sans preuve "
    "religieuse). Deux personnes vivantes reperees et JAMAIS a "
    "toucher, confirmees via check_living : I0001 et I0018.\n\n"
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
                    "description": entry["description"],
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
