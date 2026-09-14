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
Find the ancestors for whom a painted portrait exists, and refuse the rest.

The tree's noble branches - Potocki, Branicki, Zamoyski, Dzialynski,
Bochetel, Coeur - are the only people in it notable enough to have been
painted. Wikidata knows most of them; Commons holds the paintings.

Two traps. Homonyms: the first hit for "Zofia Branicka" is a woman born
in 1790, while the one in this tree was born in 1821 and is filed under
her married name, so a match needs both years to agree. Licence: an 1853
painting is public domain, the photograph of it on Commons may not be,
and only the file page says which - an unreadable licence is a refusal.

This script proposes and never writes. Every row is for a human to judge.
"""

from __future__ import annotations

import asyncio
import csv
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tests import local_stack  # noqa: E402

PAGE_SIZE = 500
TIMEOUT = 60.0

# Reason: Wikimedia asks for one request per second and a real User-Agent;
# the same courtesy genealogy/rate_limit.py encodes for Nominatim.
REQUEST_INTERVAL = 1.0
USER_AGENT = "gramps-mcp portrait lookup (https://github.com/fjacquet/gramps-mcp)"

# Reason: a portrait hunt must never reach a living person. Anyone whose
# death is unrecorded, or recent enough that a child of theirs may live,
# is left out - the same boundary that rules out LinkedIn.
DEATH_YEAR_CEILING = date.today().year - 100

NOBLE_SURNAMES = {
    "Bochetel",
    "Branicka",
    "Branicki",
    "Cœur",
    "Działyńska",
    "Działyński",
    "Potocka",
    "Potocki",
    "Zamoyska",
    "Zamoyski",
    "de Harlay",
    "de Léodepart",
}


def year_of(value: str) -> int | None:
    """
    Read the year out of a Gramps date string.

    Args:
        value (str): Date as the profile serves it, possibly qualified
            ("vers 1780") or empty.

    Returns:
        int | None: The four-digit year, or None when the string holds none.
    """
    match = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", value or "")
    return int(match.group(1)) if match else None


def classify(
    tree_birth: str, tree_death: str, wd_birth: int | None, wd_death: int | None
) -> str:
    """
    Judge how firmly a Wikidata entity corresponds to a person in the tree.

    Args:
        tree_birth (str): Birth date held by the tree.
        tree_death (str): Death date held by the tree.
        wd_birth (int | None): Birth year held by Wikidata.
        wd_death (int | None): Death year held by Wikidata.

    Returns:
        str: "match" when both years are known on both sides and agree,
            "homonym" when what is known agrees but something is missing,
            "none" when any known pair disagrees or nothing is known.
    """
    birth = year_of(tree_birth)
    death = year_of(tree_death)
    if birth is None and death is None:
        return "none"
    for mine, theirs in ((birth, wd_birth), (death, wd_death)):
        if mine is not None and theirs is not None and mine != theirs:
            return "none"
    if None not in (birth, death, wd_birth, wd_death):
        return "match"
    return "homonym"


def name_variants(given: str, surname: str) -> list[str]:
    """
    Spell a person's name the several ways Wikidata may have filed it.

    Args:
        given (str): Every forename the tree records, space separated.
        surname (str): The surname.

    Returns:
        list[str]: The full name first, then the same with forenames
            dropped from the right, down to the first one alone. Wikidata
            files a noble under the forenames they were known by, rarely
            all: "Stanislaw Kostka Franciszek Zamoyski" finds nothing,
            "Stanislaw Kostka Zamoyski" finds the man and his dates.
    """
    parts = [p for p in (given or "").split() if p]
    if not parts:
        return [surname.strip()] if surname.strip() else []
    return [
        " ".join(parts[:count] + [surname]).strip()
        for count in range(len(parts), 0, -1)
    ]


def is_safely_dead(profile: dict) -> bool:
    """
    Say whether a person is long enough dead to be researched publicly.

    Args:
        profile (dict): Person profile, carrying a "death" date string.

    Returns:
        bool: True when a death year is recorded and old enough.
    """
    death = year_of(profile.get("death") or "")
    return death is not None and death <= DEATH_YEAR_CEILING


def target() -> tuple[str, str, str]:
    """
    Return the base URL and credentials for the requested target.

    Returns:
        tuple[str, str, str]: Base URL ending in /api, username, password.

    Raises:
        SystemExit: When --prod is given but .env is not configured.
    """
    if "--prod" in sys.argv:
        load_dotenv(REPO_ROOT / ".env")
        url = os.environ.get("GRAMPS_API_URL", "").rstrip("/")
        if not url:
            sys.exit("GRAMPS_API_URL is not set in .env.")
        return (
            f"{url}/api",
            os.environ["GRAMPS_USERNAME"],
            os.environ["GRAMPS_PASSWORD"],
        )
    return (
        f"{local_stack.API_URL.rstrip('/')}/api",
        local_stack.USERNAME,
        local_stack.PASSWORD,
    )


async def fetch_people(client: httpx.AsyncClient, base: str, headers: dict) -> list:
    """
    Read every person, with the profile that carries their dates.

    Args:
        client (httpx.AsyncClient): Client used for the requests.
        base (str): REST base URL ending in /api.
        headers (dict): Authorization header.

    Returns:
        list: Every person record in the tree.

    Raises:
        SystemExit: When the server answers anything but HTTP 200.
    """
    people: list = []
    page = 1
    while True:
        response = await client.get(
            f"{base}/people/",
            params={"pagesize": PAGE_SIZE, "page": page, "profile": "self"},
            headers=headers,
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            sys.exit(f"People read failed: HTTP {response.status_code}")
        batch = response.json()
        if not batch:
            return people
        people += batch
        page += 1


def shortlist(people: list) -> list[dict]:
    """
    Keep the people worth looking up: noble, imageless and long dead.

    Args:
        people (list): Every person record in the tree.

    Returns:
        list[dict]: One entry per person, with gramps_id, name and dates.
    """
    wanted = []
    for person in people:
        profile = person.get("profile") or {}
        if profile.get("name_surname") not in NOBLE_SURNAMES:
            continue
        if person.get("media_list"):
            continue
        dates = {
            "birth": (profile.get("birth") or {}).get("date", ""),
            "death": (profile.get("death") or {}).get("date", ""),
        }
        if not is_safely_dead(dates):
            continue
        wanted.append(
            {
                "gramps_id": person.get("gramps_id", ""),
                "given": profile.get("name_given", ""),
                "surname": profile.get("name_surname", ""),
                **dates,
            }
        )
    return wanted


def _throttle(last: list[float]) -> None:
    """
    Hold the caller to one Wikimedia request per second.

    Args:
        last (list[float]): Single-element list holding the last call time.
    """
    wait = REQUEST_INTERVAL - (time.monotonic() - last[0])
    if wait > 0:
        time.sleep(wait)
    last[0] = time.monotonic()


def search_wikidata(client: httpx.Client, name: str, last: list[float]) -> list[dict]:
    """
    Look a name up in Wikidata.

    Args:
        client (httpx.Client): Client used for the request.
        name (str): Given name and surname, as the tree spells them.
        last (list[float]): Throttle state.

    Returns:
        list[dict]: Search hits, each with at least an "id".
    """
    _throttle(last)
    response = client.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities",
            "search": name,
            "language": "pl",
            "uselang": "fr",
            "type": "item",
            "limit": 8,
            "format": "json",
        },
    )
    if response.status_code != 200:
        return []
    return response.json().get("search", [])


def read_entity(client: httpx.Client, qid: str, last: list[float]) -> dict | None:
    """
    Read the dates and the image filename of one Wikidata entity.

    Args:
        client (httpx.Client): Client used for the request.
        qid (str): Entity identifier, such as "Q9252846".
        last (list[float]): Throttle state.

    Returns:
        dict | None: Label, birth and death years and image filename, or
            None when the entity is not a human.
    """
    _throttle(last)
    response = client.get(
        f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    )
    if response.status_code != 200:
        return None
    entity = response.json()["entities"][qid]
    claims = entity.get("claims", {})

    def first(prop: str):
        snaks = claims.get(prop) or []
        for snak in snaks:
            datavalue = snak["mainsnak"].get("datavalue")
            if datavalue:
                return datavalue["value"]
        return None

    kinds = {
        s["mainsnak"]["datavalue"]["value"]["id"]
        for s in claims.get("P31", [])
        if s["mainsnak"].get("datavalue")
    }
    if "Q5" not in kinds:
        return None
    birth, death = first("P569"), first("P570")
    labels = entity.get("labels", {})
    return {
        "qid": qid,
        "label": (labels.get("pl") or labels.get("fr") or labels.get("en") or {}).get(
            "value", ""
        ),
        "birth": int(birth["time"][1:5]) if birth else None,
        "death": int(death["time"][1:5]) if death else None,
        "image": first("P18"),
    }


def read_licence(client: httpx.Client, filename: str, last: list[float]) -> dict:
    """
    Read the licence and credit that Commons records for one file.

    Args:
        client (httpx.Client): Client used for the request.
        filename (str): Commons filename, without the "File:" prefix.
        last (list[float]): Throttle state.

    Returns:
        dict: licence, artist and credit, each empty when unreadable. An
            empty licence is a refusal, not a detail: the painting may be
            public domain while the photograph of it is not.
    """
    _throttle(last)
    response = client.get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query",
            "titles": f"File:{filename}",
            "prop": "imageinfo",
            "iiprop": "extmetadata|url",
            "format": "json",
        },
    )
    blank = {"licence": "", "artist": "", "credit": "", "url": ""}
    if response.status_code != 200:
        return blank
    pages = response.json().get("query", {}).get("pages", {})
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}

        def value(key: str) -> str:
            raw = (meta.get(key) or {}).get("value", "")
            return re.sub(r"<[^>]+>", "", raw).strip()

        return {
            "licence": value("LicenseShortName"),
            "artist": value("Artist"),
            "credit": value("Credit"),
            "url": info.get("descriptionurl", ""),
        }
    return blank


def best_candidate(
    client: httpx.Client, person: dict, last: list[float]
) -> tuple[str, dict | None]:
    """
    Pick the firmest Wikidata entity for one person, if any.

    Args:
        client (httpx.Client): Client used for the requests.
        person (dict): Shortlist entry, with given, surname and dates.
        last (list[float]): Throttle state.

    Returns:
        tuple[str, dict | None]: The verdict and the entity behind it. A
            match beats a homonym; entities that disagree are discarded.
    """
    best: tuple[str, dict | None] = ("none", None)
    seen: set[str] = set()
    for name in name_variants(person["given"], person["surname"]):
        for hit in search_wikidata(client, name, last):
            if hit["id"] in seen:
                continue
            seen.add(hit["id"])
            entity = read_entity(client, hit["id"], last)
            if entity is None:
                continue
            verdict = classify(
                person["birth"], person["death"], entity["birth"], entity["death"]
            )
            if verdict == "match":
                return verdict, entity
            if verdict == "homonym" and best[0] == "none":
                best = (verdict, entity)
    return best


async def main() -> None:
    """
    Report the portrait candidates, with their licences, and write nothing.

    Raises:
        SystemExit: When authentication fails.
    """
    base, username, password = target()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{base}/token/", json={"username": username, "password": password}
        )
        if response.status_code != 200:
            sys.exit(f"Authentication failed: HTTP {response.status_code}")
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        people = await fetch_people(client, base, headers)

    wanted = shortlist(people)
    print(f"people to look up: {len(wanted)}")

    rows = []
    last = [0.0]
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as web:
        for person in wanted:
            verdict, entity = best_candidate(web, person, last)
            licence = {"licence": "", "artist": "", "credit": "", "url": ""}
            if entity and entity.get("image"):
                licence = read_licence(web, entity["image"], last)
            rows.append(
                {
                    "gramps_id": person["gramps_id"],
                    "name": f"{person['given']} {person['surname']}".strip(),
                    "tree_birth": person["birth"],
                    "tree_death": person["death"],
                    "verdict": verdict,
                    "qid": (entity or {}).get("qid", ""),
                    "wd_label": (entity or {}).get("label", ""),
                    "wd_birth": (entity or {}).get("birth", "") or "",
                    "wd_death": (entity or {}).get("death", "") or "",
                    "image": (entity or {}).get("image", "") or "",
                    **licence,
                }
            )
            flag = "OK " if verdict == "match" and licence["licence"] else "   "
            print(f"{flag}{person['gramps_id']:6s} {rows[-1]['name']:34s} {verdict}")

    counted = {
        v: sum(1 for r in rows if r["verdict"] == v) for v in ("match", "homonym")
    }
    usable = [
        r for r in rows if r["verdict"] == "match" and r["image"] and r["licence"]
    ]
    print(f"\nmatch: {counted['match']}   homonym: {counted['homonym']}")
    print(f"match with an image and a readable licence: {len(usable)}")

    out = Path(os.environ.get("PORTRAIT_OUT", REPO_ROOT / "portrait_candidates.csv"))
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"written: {out}")


if __name__ == "__main__":
    asyncio.run(main())
