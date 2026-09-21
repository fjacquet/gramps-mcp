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
Read-only aggregation: rank every place in the tree by how many events
it carries, so the religion backfill can target the largest clusters
first instead of checking 893 places one by one through GQL (which has
no "top places" aggregation). Also reports how many of a place's
events belong to a person who already has a Religion event, so an
already-covered cluster (Verrens-Arvey, Geneve, Nidau, Saint-Martin-
d'Auxigny, Bourges, Durmersheim...) does not look like unclaimed volume.

Writes nothing. Prints a ranked table to stdout.
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.gramps_mcp.client import GrampsWebAPIClient  # noqa: E402
from src.gramps_mcp.models.api_calls import ApiCalls  # noqa: E402


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


def year_of(event: dict) -> int | None:
    """
    Pull a usable year out of a raw Gramps event's date field.

    Args:
        event (dict): Raw event record.

    Returns:
        int | None: The year, or None if unavailable/zero.
    """
    date = event.get("date") or {}
    dateval = date.get("dateval") or []
    if len(dateval) >= 3 and dateval[2]:
        return dateval[2]
    return None


async def main() -> None:
    """Print the ranked place table."""
    load_dotenv(REPO_ROOT / ".env")
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 40

    client = GrampsWebAPIClient()
    try:
        places = {
            p["handle"]: p for p in await page_through(client, ApiCalls.GET_PLACES)
        }
        events = await page_through(client, ApiCalls.GET_EVENTS)
        people = await page_through(client, ApiCalls.GET_PEOPLE)

        events_by_handle = {e["handle"]: e for e in events}
        already_religious_event_handles = {
            ref.get("ref")
            for person in people
            for ref in (person.get("event_ref_list") or [])
            if events_by_handle.get(ref.get("ref"), {}).get("type") == "Religion"
        }
        already_covered_person = set()
        for person in people:
            for ref in person.get("event_ref_list") or []:
                if events_by_handle.get(ref.get("ref"), {}).get("type") == "Religion":
                    already_covered_person.add(person["handle"])
                    break

        person_by_event_handle: dict[str, set[str]] = defaultdict(set)
        for person in people:
            for ref in person.get("event_ref_list") or []:
                person_by_event_handle[ref.get("ref")].add(person["handle"])

        stats: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "years": [], "covered": 0}
        )
        for event in events:
            place_handle = event.get("place")
            if not place_handle:
                continue
            bucket = stats[place_handle]
            bucket["count"] += 1
            year = year_of(event)
            if year:
                bucket["years"].append(year)
            participants = person_by_event_handle.get(event["handle"], set())
            if participants & already_covered_person:
                bucket["covered"] += 1

        ranked = sorted(stats.items(), key=lambda kv: kv[1]["count"], reverse=True)

        print(f"{'place':50s} {'events':>7s} {'years':>15s} {'covered':>8s}")
        for place_handle, bucket in ranked[:top_n]:
            place = places.get(place_handle, {})
            title = (
                place.get("name", {}).get("value") or place.get("title") or place_handle
            )
            years = bucket["years"]
            year_range = f"{min(years)}-{max(years)}" if years else "?"
            print(
                f"{title[:50]:50s} {bucket['count']:>7d} {year_range:>15s} "
                f"{bucket['covered']:>8d}"
            )

        covered_count = len(already_covered_person)
        religious_count = len(already_religious_event_handles)
        print(f"\ntotal places with at least one event: {len(stats)}")
        print(f"already-covered people (have a Religion event): {covered_count}")
        print(f"already-religious event handles: {religious_count}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
