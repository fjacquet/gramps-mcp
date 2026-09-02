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
Seed the local test stack from the newest backup in ./backup.

Restores both halves of a backup taken by scripts/backup_prod.py: the
Gramps XML, then the media archive the XML only references. Idempotent -
the importer's /restore endpoint replaces the tree's contents rather than
adding to them, so a second run does not duplicate anything.

Targets the local stack and refuses anything else. This script overwrites
whatever it is pointed at, so that guard is what stands between a rerun
and the destruction of the live tree.

    docker compose -f docker-compose.test.yml up -d
    uv run python scripts/seed_test_tree.py
"""

import asyncio
import re
import shlex
import subprocess
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests import local_stack  # noqa: E402

BACKUP_DIR = REPO_ROOT / "backup"
COMPOSE_FILE = REPO_ROOT / "docker-compose.test.yml"
# Reason: mirror the live account's role (owner, not admin) so the tests
# meet the same permission surface they meet in production - including
# whatever tree_stats does with it.
OWNER_ROLE = 4
TIMEOUT = httpx.Timeout(1800.0, connect=30.0)
STAMP = re.compile(r"^tree-(\d{4}-\d{2}-\d{2})\.gramps\.gz$")

WAIT_ATTEMPTS = 60
WAIT_SECONDS = 5
TASK_ATTEMPTS = 360
TASK_SECONDS = 5
TOKEN_ATTEMPTS = 12
TOKEN_RETRY_SECONDS = 15


def api(path: str) -> str:
    """
    Build a URL under the local stack's REST base.

    Args:
        path (str): Path below /api, without a leading slash.

    Returns:
        str: The absolute URL.
    """
    return f"{local_stack.API_URL.rstrip('/')}/api/{path}"


def newest_backup_pair(backup_dir: Path) -> tuple[Path, Path]:
    """
    Return the newest backup that has both an XML export and a media archive.

    Args:
        backup_dir (Path): Directory holding the backups.

    Returns:
        tuple[Path, Path]: The XML export and the media archive, in that
            order, for the newest date that has both.

    Raises:
        FileNotFoundError: When no date has both halves.
    """
    pairs = []
    for xml in backup_dir.glob("tree-*.gramps.gz"):
        match = STAMP.match(xml.name)
        if not match:
            continue
        media = backup_dir / f"media-{match.group(1)}.zip"
        # Reason: an XML restored without its media archive leaves every
        # media object pointing at a file that is not there. That surfaces
        # much later as puzzling test failures, so a half backup is
        # treated as no backup at all.
        if media.is_file():
            pairs.append((match.group(1), xml, media))
    if not pairs:
        raise FileNotFoundError(
            f"No complete backup in {backup_dir} - each one needs both "
            "tree-<date>.gramps.gz and media-<date>.zip. Run "
            "'uv run python scripts/backup_prod.py' first."
        )
    _, xml, media = max(pairs)
    return xml, media


async def wait_for_server(client: httpx.AsyncClient) -> None:
    """
    Block until the stack answers, whatever it answers.

    Args:
        client (httpx.AsyncClient): Client used for the requests.

    Returns:
        None

    Raises:
        SystemExit: When the stack never answers.
    """
    for _ in range(WAIT_ATTEMPTS):
        try:
            # Reason: 401 is a healthy answer here - the server is up and
            # demanding authentication. Only a connection error means it
            # is not listening yet.
            await client.get(api("metadata/"), timeout=10.0)
            return
        except httpx.TransportError:
            await asyncio.sleep(WAIT_SECONDS)
    sys.exit(
        f"{local_stack.API_URL} never answered. Start the stack with "
        "'docker compose -f docker-compose.test.yml up -d'."
    )


def create_owner() -> None:
    """
    Create the stack's owner account through the container's own CLI.

    Returns:
        None

    Raises:
        SystemExit: When the CLI call fails.
    """
    # Reason: POST /api/users/<name>/create_owner/ answers 401 on this
    # image - the first account cannot be made over the API at all - so it
    # is created with the same CLI the container's own entrypoint runs.
    # GRAMPSWEB_SECRET_KEY comes from the file that entrypoint writes, and
    # the CLI lives in /venv, not in the system interpreter.
    command = (
        "export GRAMPSWEB_SECRET_KEY=$(cat /app/secret/secret); cd /app/src && "
        "/venv/bin/python -m gramps_webapi --config /app/config/config.cfg user add "
        f"{shlex.quote(local_stack.USERNAME)} {shlex.quote(local_stack.PASSWORD)} "
        f"--fullname {shlex.quote(local_stack.FULL_NAME)} "
        f"--email {shlex.quote(local_stack.EMAIL)} --role {OWNER_ROLE}"
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "exec",
            "-T",
            "grampsweb",
            "sh",
            "-lc",
            command,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.exit(
            "Could not create the owner account:\n"
            f"{result.stdout[-500:]}{result.stderr[-500:]}"
        )
    print(f"owner  {local_stack.USERNAME} created")


async def get_token(client: httpx.AsyncClient) -> str:
    """
    Exchange the stack's credentials for a bearer token, creating the
    account first if it does not exist yet.

    Args:
        client (httpx.AsyncClient): Client used for the request.

    Returns:
        str: The access token.

    Raises:
        SystemExit: When the stack keeps refusing the credentials.
    """
    created = False
    for _ in range(TOKEN_ATTEMPTS):
        response = await client.post(
            api("token/"),
            json={"username": local_stack.USERNAME, "password": local_stack.PASSWORD},
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            if not token:
                sys.exit("Token response carried no access_token.")
            return str(token)
        # Reason: /token/ is rate limited, and this script asks for a token
        # once per run - so a 429 here is the limiter still holding a
        # window open from an earlier run, not a wrong password. Wait it
        # out rather than failing the whole seed.
        if response.status_code == 429:
            print("token  rate limited, waiting", end="\r")
            await asyncio.sleep(TOKEN_RETRY_SECONDS)
            continue
        if response.status_code in (401, 403) and not created:
            create_owner()
            created = True
            continue
        sys.exit(f"Token request failed: HTTP {response.status_code} {response.text}")
    sys.exit("Token request kept failing - the stack never issued one.")


async def run_task(
    client: httpx.AsyncClient, headers: dict, response: httpx.Response, label: str
) -> dict:
    """
    Resolve a response that may be a finished body or a queued Celery task.

    Args:
        client (httpx.AsyncClient): Client used for the polling.
        headers (dict): Authorization header.
        response (httpx.Response): The response to interpret.
        label (str): What the caller was doing, used in error messages.

    Returns:
        dict: The task's result, or the response body when it carried one.

    Raises:
        SystemExit: When the request or the task it started failed.
    """
    if response.status_code == 200:
        return dict(response.json() or {})
    if response.status_code != 202:
        sys.exit(f"{label} failed: HTTP {response.status_code} {response.text[:300]}")

    # Reason: the importer and the media upload both hand the work to
    # celery and answer 202 with a task id. Treating that as success would
    # race the next step against an import still running.
    task_id = (response.json() or {}).get("task", {}).get("id")
    if not task_id:
        sys.exit(f"{label} returned 202 without a task id: {response.text[:200]}")
    for _ in range(TASK_ATTEMPTS):
        poll = await client.get(
            api(f"tasks/{task_id}"), headers=headers, timeout=TIMEOUT
        )
        if poll.status_code != 200:
            sys.exit(f"{label} task poll failed: HTTP {poll.status_code}")
        task = poll.json()
        if task.get("state") == "SUCCESS":
            return dict(task.get("result_object") or {})
        if task.get("state") in ("FAILURE", "REVOKED"):
            sys.exit(f"{label} task {task['state']}: {str(task.get('result'))[:300]}")
        progress = task.get("result_object") or {}
        if "current" in progress:
            print(
                f"       {label} {progress['current']}/{progress.get('total', '?')}",
                end="\r",
            )
        await asyncio.sleep(TASK_SECONDS)
    sys.exit(f"{label} task never finished.")


async def restore_tree(client: httpx.AsyncClient, headers: dict, xml: Path) -> None:
    """
    Replace the stack's tree with the backup, after a dry run.

    Args:
        client (httpx.AsyncClient): Client used for the requests.
        headers (dict): Authorization header.
        xml (Path): The gzipped Gramps XML to restore.

    Returns:
        None

    Raises:
        SystemExit: When either call fails.
    """
    payload = xml.read_bytes()
    # Reason: /restore replaces the tree's contents; /file would add to
    # them, so a second run would duplicate every record in the tree.
    url = api("importers/gramps/file/restore")
    dry = await client.post(
        url,
        params={"dry_run": "true"},
        content=payload,
        headers=headers,
        timeout=TIMEOUT,
    )
    summary = await run_task(client, headers, dry, "restore dry run")
    for key in ("to_add", "to_update", "to_delete"):
        print(f"dry    {key}: {summary.get(key)}")

    real = await client.post(url, content=payload, headers=headers, timeout=TIMEOUT)
    await run_task(client, headers, real, "restore")
    print(f"XML    {xml.name} restored")


async def upload_media(client: httpx.AsyncClient, headers: dict, archive: Path) -> None:
    """
    Upload the media archive into the stack.

    Args:
        client (httpx.AsyncClient): Client used for the request.
        headers (dict): Authorization header.
        archive (Path): The media zip to upload.

    Returns:
        None

    Raises:
        SystemExit: When the upload fails.
    """
    response = await client.post(
        api("media/archive/upload/zip"),
        content=archive.read_bytes(),
        headers=headers,
        timeout=TIMEOUT,
    )
    await run_task(client, headers, response, "media upload")
    print(f"MEDIA  {archive.name} uploaded")


async def report_counts(client: httpx.AsyncClient, headers: dict) -> None:
    """
    Print how many media objects the seeded tree has, and how many lack files.

    Args:
        client (httpx.AsyncClient): Client used for the requests.
        headers (dict): Authorization header.

    Returns:
        None
    """
    # Reason: pages start at 1 - page=0 returns HTTP 422 - and the total
    # comes back in a header, so pagesize=1 is enough to read it.
    total = await client.get(
        api("media/"), params={"pagesize": 1, "page": 1}, headers=headers
    )
    missing = await client.get(
        api("media/"),
        params={"pagesize": 1, "page": 1, "filemissing": 1},
        headers=headers,
    )
    print(f"CHECK  media objects: {total.headers.get('X-Total-Count')}")
    print(f"CHECK  file missing:  {missing.headers.get('X-Total-Count')}")


async def main() -> None:
    """
    Seed the local stack, refusing any target that is not local.

    Returns:
        None
    """
    local_stack.assert_local(local_stack.API_URL)
    xml, media = newest_backup_pair(BACKUP_DIR)
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await wait_for_server(client)
        headers = {"Authorization": f"Bearer {await get_token(client)}"}
        await restore_tree(client, headers, xml)
        await upload_media(client, headers, media)
        await report_counts(client, headers)


if __name__ == "__main__":
    asyncio.run(main())
