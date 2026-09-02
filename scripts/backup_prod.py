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
Back up the live Gramps Web tree into ./backup: XML plus media archive.

Read-only against the configured server. Produces two files the local test
stack is seeded from:

    backup/tree-<YYYY-MM-DD>.gramps.gz   Gramps XML, lossless, no media
    backup/media-<YYYY-MM-DD>.zip        every media file

The XML carries only <object> references, so the media archive is not
optional - without it the local tree has dead file references.

Both outputs are validated before they are kept: an expired token or a
truncated download otherwise leaves a file that passes for a good backup.
Run from the repo root:

    uv run python scripts/backup_prod.py
"""

import asyncio
import gzip
import os
import sys
import zipfile
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = REPO_ROOT / "backup"
# Reason: this script talks to the server named in .env - the live tree -
# and never to the test stack, so it reads that file explicitly rather
# than inheriting whatever the shell happens to export.
load_dotenv(REPO_ROOT / ".env")
TIMEOUT = httpx.Timeout(600.0, connect=30.0)

# Reason: the archive is built server-side and can take minutes on a large
# tree; poll rather than assume the first response carries the filename.
ARCHIVE_POLL_SECONDS = 5
ARCHIVE_POLL_ATTEMPTS = 60


def api_base() -> str:
    """
    Return the REST base URL, adding the /api suffix GRAMPS_API_URL lacks.

    Returns:
        str: Base URL every call below is built on.

    Raises:
        SystemExit: When GRAMPS_API_URL is not configured.
    """
    url = os.environ.get("GRAMPS_API_URL", "").rstrip("/")
    if not url:
        sys.exit("GRAMPS_API_URL is not set. Run from the repo root with .env loaded.")
    return f"{url}/api"


async def get_token(client: httpx.AsyncClient) -> str:
    """
    Exchange the configured credentials for a bearer token.

    Args:
        client (httpx.AsyncClient): Client used for the request.

    Returns:
        str: The access token.

    Raises:
        SystemExit: When the server refuses the credentials or returns a
            body without an access token.
    """
    response = await client.post(
        f"{api_base()}/token/",
        json={
            "username": os.environ.get("GRAMPS_USERNAME", ""),
            "password": os.environ.get("GRAMPS_PASSWORD", ""),
        },
    )
    if response.status_code != 200:
        sys.exit(f"Token request failed: HTTP {response.status_code} {response.text}")
    token = response.json().get("access_token")
    if not token:
        sys.exit("Token response carried no access_token.")
    return token


async def download_xml(client: httpx.AsyncClient, headers: dict, target: Path) -> None:
    """
    Download the Gramps XML export and keep it only if it is valid gzip.

    Args:
        client (httpx.AsyncClient): Client used for the request.
        headers (dict): Authorization header.
        target (Path): Where to write the export.

    Returns:
        None

    Raises:
        SystemExit: When the download fails or the body is not gzip.
    """
    response = await client.get(
        f"{api_base()}/exporters/gramps/file", headers=headers, timeout=TIMEOUT
    )
    if response.status_code != 200:
        sys.exit(
            f"XML export failed: HTTP {response.status_code} {response.text[:200]}"
        )

    # Reason: a token that expired mid-run returns a JSON error with HTTP
    # 200 in some deployments. Decompressing one member proves the body is
    # really the export and not an error page, before it replaces any
    # earlier backup.
    staging = target.with_suffix(target.suffix + ".part")
    staging.write_bytes(response.content)
    try:
        with gzip.open(staging, "rb") as handle:
            head = handle.read(200)
    except OSError:
        staging.unlink(missing_ok=True)
        sys.exit("XML export is not gzip - refusing to keep it.")
    if b"<database" not in head and b"<?xml" not in head:
        staging.unlink(missing_ok=True)
        sys.exit(f"XML export does not look like Gramps XML: {head[:80]!r}")
    staging.replace(target)
    print(f"XML   {target.name}  {target.stat().st_size:,} bytes")


async def wait_for_archive(
    client: httpx.AsyncClient, headers: dict, task_id: str
) -> str:
    """
    Poll a media-export task until it finishes and return its filename.

    Args:
        client (httpx.AsyncClient): Client used for the requests.
        headers (dict): Authorization header.
        task_id (str): Identifier returned by POST /media/archive/.

    Returns:
        str: Name of the archive the task produced.

    Raises:
        SystemExit: When the task fails, never finishes, or finishes
            without naming a file.
    """
    for _ in range(ARCHIVE_POLL_ATTEMPTS):
        response = await client.get(
            f"{api_base()}/tasks/{task_id}", headers=headers, timeout=TIMEOUT
        )
        if response.status_code != 200:
            sys.exit(
                f"Task poll failed: HTTP {response.status_code} {response.text[:200]}"
            )
        task = response.json()
        state = task.get("state")
        if state == "SUCCESS":
            result = task.get("result_object") or {}
            filename = result.get("file_name") or result.get("filename")
            if not filename:
                sys.exit(f"Media export finished without a filename: {result}")
            return str(filename)
        if state in ("FAILURE", "REVOKED"):
            sys.exit(f"Media export task {state}: {task.get('result')}")
        # Reason: PROGRESS carries current/total, so the wait is legible
        # rather than a silent hang on a tree with over a thousand files.
        progress = task.get("result_object") or {}
        if "current" in progress:
            done, total = progress["current"], progress.get("total", "?")
            print(f"      media export {done}/{total}", end="\r")
        await asyncio.sleep(ARCHIVE_POLL_SECONDS)
    sys.exit("Media export task never finished.")


async def download_media(
    client: httpx.AsyncClient, headers: dict, target: Path
) -> None:
    """
    Ask the server to build a media archive, then download it.

    Args:
        client (httpx.AsyncClient): Client used for the requests.
        headers (dict): Authorization header.
        target (Path): Where to write the archive.

    Returns:
        None

    Raises:
        SystemExit: When the archive cannot be built or is not a valid zip.
    """
    response = await client.post(
        f"{api_base()}/media/archive/", headers=headers, timeout=TIMEOUT
    )
    if response.status_code not in (200, 201, 202):
        sys.exit(
            f"Media archive request failed: HTTP {response.status_code} "
            f"{response.text[:200]}"
        )

    payload = response.json() if response.content else {}
    task_id = payload.get("task", {}).get("id")
    if not task_id:
        sys.exit(f"Media archive response carried no task id: {payload}")

    filename = await wait_for_archive(client, headers, task_id)

    archive = await client.get(
        f"{api_base()}/media/archive/{filename}", headers=headers, timeout=TIMEOUT
    )
    if archive.status_code != 200:
        sys.exit(
            f"Media archive download failed: HTTP {archive.status_code} "
            f"{archive.text[:200]}"
        )

    staging = target.with_suffix(target.suffix + ".part")
    staging.write_bytes(archive.content)
    if not zipfile.is_zipfile(staging):
        staging.unlink(missing_ok=True)
        sys.exit("Media archive is not a zip - refusing to keep it.")
    with zipfile.ZipFile(staging) as bundle:
        count = len(bundle.namelist())
    staging.replace(target)
    print(f"MEDIA {target.name}  {target.stat().st_size:,} bytes, {count} files")


async def main() -> None:
    """
    Write both backup files into ./backup, named by today's date.

    Returns:
        None
    """
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = date.today().isoformat()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        headers = {"Authorization": f"Bearer {await get_token(client)}"}
        await download_xml(client, headers, BACKUP_DIR / f"tree-{stamp}.gramps.gz")
        await download_media(client, headers, BACKUP_DIR / f"media-{stamp}.zip")


if __name__ == "__main__":
    asyncio.run(main())
