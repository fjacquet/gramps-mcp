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
Merge media records that hold the same file, keeping every citation.

A media object whose checksum another one already carries is a duplicate:
the same bytes stored twice, usually because an upload was retried after
an error that had in fact created the record. Deleting the extra would
break whatever cites it, so each is merged into a survivor -
POST /media/<phoenix>/merge/<titanic> - which unions the backlinks and
leaves no citation pointing at nothing.

Targets the local test stack unless --prod is given. Rehearse there
first: the local stack is a restorable copy, so a wrong decision costs a
re-seed rather than a tree.

    uv run python scripts/dedupe_media.py            # local, dry run
    uv run python scripts/dedupe_media.py --apply    # local, for real
    uv run python scripts/dedupe_media.py --prod --apply
"""

import argparse
import asyncio
import collections
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests import local_stack  # noqa: E402

TIMEOUT = httpx.Timeout(120.0, connect=30.0)
PAGE_SIZE = 100


def choose_keeper(group: list[dict]) -> dict:
    """
    Pick the record of a checksum group that the others merge into.

    Args:
        group (list[dict]): Media objects sharing one checksum.

    Returns:
        dict: The survivor - most backlinks first, then one carrying a
            description, then the lowest gramps_id.
    """

    # Reason: gramps_id is assigned in creation order, so the lowest is the
    # original and the rest are the retries that duplicated it. It is the
    # last tie-break, not the first: a later record that acquired the
    # citations is the one the tree actually uses.
    def rank(media: dict) -> tuple:
        backlinks = sum(len(v) for v in (media.get("backlinks") or {}).values())
        return (-backlinks, 0 if media.get("desc") else 1, media.get("gramps_id") or "")

    return sorted(group, key=rank)[0]


def plan_merges(media: list[dict]) -> list[tuple[dict, dict]]:
    """
    List every (survivor, absorbed) pair the tree needs.

    Args:
        media (list[dict]): Every media object in the tree.

    Returns:
        list[tuple[dict, dict]]: Pairs to merge, survivor first.
    """
    by_checksum: dict[str, list[dict]] = collections.defaultdict(list)
    for item in media:
        checksum = item.get("checksum")
        # Reason: an empty checksum is not evidence of identical content,
        # it is evidence the server never computed one. Grouping on it
        # would merge unrelated records.
        if checksum:
            by_checksum[checksum].append(item)

    plan = []
    for group in by_checksum.values():
        if len(group) < 2:
            continue
        keeper = choose_keeper(group)
        for item in group:
            if item["handle"] != keeper["handle"]:
                plan.append((keeper, item))
    return plan


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


async def fetch_media(
    client: httpx.AsyncClient, base: str, headers: dict
) -> list[dict]:
    """
    Read every media object, with its backlinks.

    Args:
        client (httpx.AsyncClient): Client used for the requests.
        base (str): REST base URL ending in /api.
        headers (dict): Authorization header.

    Returns:
        list[dict]: Every media object in the tree.
    """
    media: list[dict] = []
    page = 1
    while True:
        # Reason: pages start at 1 - page=0 answers HTTP 422.
        response = await client.get(
            f"{base}/media/",
            params={"pagesize": PAGE_SIZE, "page": page, "backlinks": 1},
            headers=headers,
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            sys.exit(f"Media read failed: HTTP {response.status_code}")
        batch = response.json()
        if not batch:
            return media
        media += batch
        page += 1


async def main() -> None:
    """
    Report the duplicate media, and merge them when --apply is given.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prod", action="store_true", help="target the server named in .env"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the merges instead of listing them",
    )
    args = parser.parse_args()

    base, username, password = target()
    print(f"target {base}{'  (LIVE TREE)' if args.prod else ''}")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        token_response = await client.post(
            f"{base}/token/", json={"username": username, "password": password}
        )
        if token_response.status_code != 200:
            sys.exit(f"Token request failed: HTTP {token_response.status_code}")
        headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}

        media = await fetch_media(client, base, headers)
        plan = plan_merges(media)
        print(f"media  {len(media)} objects, {len(plan)} duplicates to absorb")
        if not plan:
            return
        if not args.apply:
            for keeper, absorbed in plan[:10]:
                print(f"would merge {absorbed['gramps_id']} into {keeper['gramps_id']}")
            print(f"dry run - {len(plan)} merges not performed. Pass --apply.")
            return

        for index, (keeper, absorbed) in enumerate(plan, start=1):
            response = await client.post(
                f"{base}/media/{keeper['handle']}/merge/{absorbed['handle']}",
                headers=headers,
                timeout=TIMEOUT,
            )
            if response.status_code not in (200, 201):
                sys.exit(
                    f"Merge of {absorbed['gramps_id']} into {keeper['gramps_id']} "
                    f"failed: HTTP {response.status_code} {response.text[:200]}"
                )
            print(f"       merged {index}/{len(plan)}", end="\r")

        remaining = await fetch_media(client, base, headers)
        print(f"\nmedia  {len(remaining)} objects, {len(plan_merges(remaining))} left")


if __name__ == "__main__":
    asyncio.run(main())
