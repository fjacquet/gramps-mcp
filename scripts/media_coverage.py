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
Where each person's images are, and which people have none at all.

The tree holds far more media than the person records show: a register
scan is attached to the citation that quotes it, a postcard to the place
it depicts. Both are one hop away from the person and neither appears in
the person's own media_list. Counting only media_list therefore reports
a famine that does not exist, and counting every reachable image reports
a wealth the reader may never see.

So the coverage of a person is three separate numbers, never a total.
"""

from __future__ import annotations

import asyncio
import csv
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tests import local_stack  # noqa: E402

PAGE_SIZE = 500
TIMEOUT = 120.0


def index_media_holders(records: list[dict]) -> set[str]:
    """
    Collect the handles of records that carry at least one media object.

    Args:
        records (list[dict]): Citations, places or any record with a media_list.

    Returns:
        set[str]: Handle of every record holding one or more media objects.
    """
    return {r["handle"] for r in records if r.get("media_list")}


def person_coverage(
    person: dict,
    events_by_handle: dict[str, dict],
    citations_with_media: set[str],
    places_with_media: set[str],
) -> dict:
    """
    Count the images reachable from one person, by the path that reaches them.

    Args:
        person (dict): Raw person record, with event_ref_list and media_list.
        events_by_handle (dict[str, dict]): Every event, keyed by handle.
        citations_with_media (set[str]): Handles of citations holding media.
        places_with_media (set[str]): Handles of places holding media.

    Returns:
        dict: gramps_id, handle, and the direct, citation and place counts.
    """
    direct = len(person.get("media_list") or [])
    via_citation = 0
    via_place = 0
    for ref in person.get("event_ref_list") or []:
        event = events_by_handle.get(ref.get("ref"))
        if event is None:
            continue
        via_citation += sum(
            1 for c in event.get("citation_list") or [] if c in citations_with_media
        )
        # Reason: an event's place is a single handle, not a list, and an
        # event with no place carries the empty string rather than None.
        place = event.get("place")
        if place and place in places_with_media:
            via_place += 1
    return {
        "gramps_id": person.get("gramps_id", ""),
        "handle": person.get("handle", ""),
        "direct": direct,
        "via_citation": via_citation,
        "via_place": via_place,
    }


def is_uncovered(row: dict) -> bool:
    """
    Say whether a person has no image reachable by any path.

    Args:
        row (dict): A person_coverage row.

    Returns:
        bool: True when direct, citation and place counts are all zero.
    """
    return not (row["direct"] or row["via_citation"] or row["via_place"])


def needs_surfacing(row: dict) -> bool:
    """
    Say whether a person has an image nearby but none on their own record.

    Args:
        row (dict): A person_coverage row.

    Returns:
        bool: True when the person holds no media but an event reaches one.
    """
    return row["direct"] == 0 and bool(row["via_citation"] or row["via_place"])


def has_document_nearby(row: dict) -> bool:
    """
    Say whether a person could carry a document scan they do not yet hold.

    Args:
        row (dict): A person_coverage row.

    Returns:
        bool: True when the person holds no media but a citation on one of
            their events carries a scan.

    Notes:
        Place media are excluded on purpose. They are commune and region
        illustrations taken from Wikimedia, so copying one onto a person
        would assert that a stock photograph depicts the person.
    """
    return row["direct"] == 0 and row["via_citation"] > 0


def summarise(rows: list[dict]) -> dict[str, int]:
    """
    Fold the per-person rows into the three headline numbers.

    Args:
        rows (list[dict]): One person_coverage row per person.

    Returns:
        dict[str, int]: Totals for people, covered, surfacing and uncovered.
    """
    return {
        "people": len(rows),
        "own_media": sum(1 for r in rows if r["direct"]),
        "document_nearby": sum(1 for r in rows if has_document_nearby(r)),
        "place_photo_only": sum(
            1 for r in rows if needs_surfacing(r) and not has_document_nearby(r)
        ),
        "uncovered": sum(1 for r in rows if is_uncovered(r)),
    }


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


async def fetch_all(
    client: httpx.AsyncClient, base: str, headers: dict, kind: str, **extra: object
) -> list[dict]:
    """
    Read every record of one type, following the pagination.

    Args:
        client (httpx.AsyncClient): Client used for the requests.
        base (str): REST base URL ending in /api.
        headers (dict): Authorization header.
        kind (str): Collection name, such as "people" or "citations".
        **extra (object): Extra query parameters, such as profile or backlinks.

    Returns:
        list[dict]: Every record of that type.

    Raises:
        SystemExit: When the server answers anything but HTTP 200.
    """
    records: list[dict] = []
    page = 1
    while True:
        # Reason: pages start at 1 - page=0 answers HTTP 422.
        response = await client.get(
            f"{base}/{kind}/",
            params={"pagesize": PAGE_SIZE, "page": page, **extra},
            headers=headers,
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            sys.exit(f"{kind} read failed: HTTP {response.status_code}")
        batch = response.json()
        if not batch:
            return records
        records += batch
        page += 1


async def main() -> None:
    """
    Report where the tree's images sit and write the uncovered people to CSV.

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

        people = await fetch_all(client, base, headers, "people", profile="self")
        events = await fetch_all(client, base, headers, "events")
        citations = await fetch_all(client, base, headers, "citations")
        places = await fetch_all(client, base, headers, "places")

    events_by_handle = {e["handle"]: e for e in events}
    rows = [
        person_coverage(
            person,
            events_by_handle,
            index_media_holders(citations),
            index_media_holders(places),
        )
        for person in people
    ]
    for row, person in zip(rows, people, strict=True):
        profile = person.get("profile") or {}
        row["name"] = (
            f"{profile.get('name_given', '')} {profile.get('name_surname', '')}".strip()
        )

    totals = summarise(rows)
    print(f"people                       : {totals['people']}")
    print(f"  carry their own media      : {totals['own_media']}")
    print(f"  document scan one hop away : {totals['document_nearby']}")
    print(f"  only a commune photograph  : {totals['place_photo_only']}")
    print(f"  no image by any path       : {totals['uncovered']}")

    out = REPO_ROOT / "media_coverage.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["gramps_id", "name", "direct", "via_citation", "via_place"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["gramps_id"]))
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    asyncio.run(main())
