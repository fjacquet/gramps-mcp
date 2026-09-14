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
Attach the validated Wikimedia portraits to the people they depict.

Follows the iconography convention the tree already uses (citations
C1542, C1666, C1667): one citation for the whole lot, whose page names
every file with its licence, its painter and an explicit identity
verdict, and which hangs on the media objects rather than on the people
- it records where a file came from, not what it proves. The media
description is written in French, as the reader sees it.

The identity verdicts below are human judgements, not computed: each was
read off the Commons file page and weighed against the tree's dates.
That is why the lot is spelled out here rather than read from a CSV.

Idempotent by checksum: Gramps stores each file's md5, so a rerun after
a partial failure reuses what is already uploaded instead of duplicating
it. Writes only with --apply.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.gramps_mcp.client import GrampsWebAPIClient  # noqa: E402
from src.gramps_mcp.models.api_calls import ApiCalls  # noqa: E402

SOURCE_GRAMPS_ID = "S0191"
USER_AGENT = "gramps-mcp portrait fetch (https://github.com/fjacquet/gramps-mcp)"
COMMONS_FILE_URL = "https://commons.wikimedia.org/wiki/Special:FilePath/{name}"

PORTRAITS = [
    {
        "gramps_id": "I1078",
        "file": "Elzibeta Branicka, Countess Krasinka and herr children 1853.jpg",
        "desc": (
            "Portrait de groupe : Eliza Branicka, comtesse Krasińska, avec ses "
            "enfants, par Franz Xaver Winterhalter, 1853 - domaine public, "
            "Wikimedia Commons"
        ),
    },
    {
        "gramps_id": "I1081",
        "file": "Winterhalter Katarzyna Potocka.png",
        "desc": (
            "Portrait de Katarzyna Potocka née Branicka par Franz Xaver "
            "Winterhalter, 1854 - domaine public, Wikimedia Commons"
        ),
    },
    {
        "gramps_id": "I1087",
        "file": "Clarot Alexander - portret Zofii Branickiej.jpg",
        "desc": (
            "Portrait de Zofia Branicka par Alexander Clarot, 1837, aquarelle "
            "et crayon sur bristol, Musée national de Varsovie - domaine "
            "public, Wikimedia Commons"
        ),
    },
    {
        "gramps_id": "I1979",
        "file": "Ksawery Działyński.JPG",
        "desc": (
            "Portrait de Ksawery Działyński par Antoni Brodowski d'après "
            "Marcello Bacciarelli, vers 1812 - domaine public, Wikimedia "
            "Commons"
        ),
    },
    {
        "gramps_id": "I1814",
        "file": "Браницкий.jpg",
        "desc": (
            "Portrait de Władysław Grzegorz Branicki (1783-1843), estampe "
            "d'auteur inconnu, première moitié du XIXe siècle, fonds New York "
            "Public Library - domaine public, Wikimedia Commons"
        ),
    },
]

CITATION_NOTE = (
    "ICONOGRAPHIE - ne prouve aucune filiation. Cinq fichiers "
    "Wikimedia Commons telecharges le 14/09/2026, identite verifiee "
    "sur les dates Wikidata puis sur la page du fichier:"
    "\n"
    '1. "Elzibeta Branicka, Countess Krasinka and herr children '
    '1853.jpg" - DOMAINE PUBLIC (PD-old-100), peintre Franz Xaver '
    "Winterhalter, 1853. IDENTITE CERTAINE: Wikidata Q9252846 porte "
    "1820-1876, identiques a I1078. A NOTER: portrait de GROUPE, "
    "Eliza avec ses enfants, et non portrait d'elle seule; elle y "
    "figure sous son nom d'epouse Krasinska."
    "\n"
    '2. "Winterhalter Katarzyna Potocka.png" - DOMAINE PUBLIC '
    "(PD-Art, PD-old-100), Winterhalter, 1854. IDENTITE CERTAINE: "
    'le titre du fichier dit lui-meme "nee Branicka", et Wikidata '
    "Q6375196 porte 1825-1907, identiques a I1081. Elle y figure "
    "sous son nom d'epouse Potocka."
    "\n"
    '3. "Clarot Alexander - portret Zofii Branickiej.jpg" - DOMAINE '
    "PUBLIC (PD-old-70), Alexander Clarot, 1837, aquarelle et "
    "crayon sur bristol, Musee national de Varsovie. IDENTITE "
    "CERTAINE: Wikidata Q97497657 porte 1821-1886, identiques a "
    'I1087, et la categorie Commons "Zofia Odescalchi" correspond a '
    "son nom d'epouse. PIEGE ECARTE: le premier resultat Wikidata "
    'pour "Zofia Branicka" est Q8073362, une autre femme nee en '
    "1790. Elle n'a pas ete retenue."
    "\n"
    '4. "Ksawery Dzialynski.JPG" - DOMAINE PUBLIC (PD-Art, '
    "PD-old-100), Antoni Brodowski d'apres Marcello Bacciarelli, "
    "vers 1812. IDENTITE CERTAINE: Wikidata Q11750339 porte "
    "1756-1819, identiques a I1979."
    "\n"
    '5. "Branicki.jpg" (nom de fichier en cyrillique) - DOMAINE '
    "PUBLIC (PD Old), auteur inconnu, premiere moitie du 19e "
    "siecle, fonds New York Public Library. IDENTITE CERTAINE MAIS "
    "SUPPORT INCERTAIN, c'est la piece la plus faible du lot: la "
    'description du fichier nomme explicitement "Count Wladyslaw '
    'Grzegorz Branicki (1783-1843)", dates identiques a I1814, mais '
    "il s'agit vraisemblablement d'une estampe et non d'une "
    "peinture, et aucun auteur n'est donne. A NE PAS CONFONDRE avec "
    "son fils Wladyslaw Michal Branicki (1826-1884), I1089, qui "
    "porte deja O0762, le portrait par Amerling."
    "\n"
    'NON RETENU: "Maria Potocka" (I1077, nee 1805) a quatre '
    "homonymes sur Wikidata dont aucun ne correspond a ses dates; "
    "aucune image ne lui a ete attribuee. Les branches Coeur et de "
    "Harlay n'ont pas de dates assez precises pour trancher et "
    "restent sans portrait."
)


def fetch_file(name: str) -> tuple[bytes, str, str]:
    """
    Download one Commons file.

    Args:
        name (str): Commons filename, without the "File:" prefix.

    Returns:
        tuple[bytes, str, str]: The bytes, the md5 Gramps stores as the
            checksum, and the MIME type it was served as.

    Raises:
        SystemExit: When the download fails.
    """
    response = httpx.get(
        COMMONS_FILE_URL.format(name=name),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=120,
    )
    if response.status_code != 200:
        sys.exit(f"Download of {name} failed: HTTP {response.status_code}")
    mime = response.headers.get("content-type", "application/octet-stream")
    return (
        response.content,
        hashlib.md5(response.content).hexdigest(),
        mime.split(";")[0].strip(),
    )


def pick(entries: list, wanted: str) -> dict:
    """
    Take the record of one class out of a transaction response.

    Args:
        entries (list): What a POST returned.
        wanted (str): The _class to select, such as "Media".

    Returns:
        dict: The new object of that class.

    Raises:
        SystemExit: When no entry of that class is present.

    Notes:
        Selecting by position is wrong: POST_FAMILIES, for one, returns
        the father's Person update before the family itself.
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
    Attach every portrait of the lot, or report what would be attached.

    Raises:
        SystemExit: When the source or a person cannot be found.
    """
    load_dotenv(REPO_ROOT / ".env")
    apply = "--apply" in sys.argv
    print(f"portraits: {len(PORTRAITS)}   mode: {'APPLY' if apply else 'dry run'}")

    client = GrampsWebAPIClient()
    try:
        sources = await page_through(client, ApiCalls.GET_SOURCES)
        source = next((s for s in sources if s["gramps_id"] == SOURCE_GRAMPS_ID), None)
        if source is None:
            sys.exit(f"Source {SOURCE_GRAMPS_ID} not found.")
        print(f'source {SOURCE_GRAMPS_ID}: "{source.get("title", "")}"')

        people = {
            p["gramps_id"]: p for p in await page_through(client, ApiCalls.GET_PEOPLE)
        }
        missing = [p["gramps_id"] for p in PORTRAITS if p["gramps_id"] not in people]
        if missing:
            sys.exit(f"Unknown gramps_id: {missing}")

        known = {
            m["checksum"]: m["handle"]
            for m in await page_through(client, ApiCalls.GET_MEDIA)
            if m.get("checksum")
        }
        print(f"media already in the tree: {len(known)}")

        downloaded = []
        for entry in PORTRAITS:
            content, checksum, mime = fetch_file(entry["file"])
            reused = known.get(checksum)
            downloaded.append((entry, content, checksum, mime, reused))
            person = people[entry["gramps_id"]]
            held = {r.get("ref") for r in (person.get("media_list") or [])}
            state = "reuse " + reused if reused else f"upload {len(content)} bytes"
            already = " ALREADY ON PERSON" if reused and reused in held else ""
            print(f"  {entry['gramps_id']}: {state}{already}")

        if not apply:
            print("\ndry run: no citation created, nothing attached")
            return

        citation = await client.make_api_call(
            ApiCalls.POST_CITATIONS,
            params={"source_handle": source["handle"], "page": CITATION_NOTE},
        )
        citation_handle = pick(citation, "Citation")["handle"]
        print(f"citation created: {citation_handle}")

        for entry, content, checksum, mime, reused in downloaded:
            if reused:
                media_handle = reused
            else:
                uploaded = await client.upload_media_file(content, mime)
                media_handle = pick(uploaded, "Media")["handle"]
            await client.make_api_call(
                ApiCalls.PUT_MEDIA_ITEM,
                params={"desc": entry["desc"], "citation_list": [citation_handle]},
                handle=media_handle,
            )
            person = people[entry["gramps_id"]]
            await client.make_api_call(
                ApiCalls.PUT_PERSON,
                params={
                    "primary_name": person["primary_name"],
                    "gender": person["gender"],
                    "media_list": [{"ref": media_handle}],
                },
                handle=person["handle"],
            )
            print(f"  {entry['gramps_id']}: media {media_handle} attached")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
