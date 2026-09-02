# Local Test Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the integration test suite against a local Gramps Web stack seeded from a backup, and make the live tree unreachable from pytest.

**Architecture:** A reduced docker-compose stack (Gramps Web + Celery + Valkey, SQLite, loopback-only) replaces the live server as pytest's target. A tracked module, `tests/local_stack.py`, holds the stack's coordinates and a host allowlist; the root `tests/conftest.py` applies them to `os.environ` at import time and refuses any non-local host. A seed script restores `backup/tree-*.gramps.gz` and `backup/media-*.zip` into the stack.

**Tech Stack:** Python 3.13, uv, pytest, httpx, Docker Compose, Gramps Web API 3.21.1.

**Spec:** `docs/superpowers/specs/2026-09-02-local-test-environment-design.md`

## Global Constraints

- Every command runs from the repo root through uv: `uv run pytest`, `uv run python`, `uv run git commit`.
- No file over 500 lines, `tests/` included - enforced by pre-commit.
- Type hints throughout, Google-style docstrings on every function, no emoji.
- `uv run ruff check src tests scripts` and `uv run ruff format --check` must pass; `uv run mypy src/gramps_mcp --ignore-missing-imports` must stay clean.
- `uv run pytest -m "not integration"` must stay green at every commit. It is 638 tests before this plan starts.
- Never `git stash` or `git reset --hard`.
- The live server's coordinates stay in `.env`, which pytest must stop reading. Do not edit `.env` or `.env-local`.
- `backup/` is gitignored and must stay so: it holds real data on living people, this repository is public.
- The first commit of the day may need repeating: the copyright pre-commit hook rewrites a new Python file and aborts that commit. Re-run the same `git add` and `git commit`.

---

### Task 1: Local stack coordinates and the guard

The core of the change: after this task, `uv run pytest` targets the local stack and cannot be pointed at the live tree.

**Files:**
- Create: `tests/local_stack.py`
- Modify: `tests/conftest.py` (top of file, before the `src.gramps_mcp` imports on lines 16-29)
- Test: `tests/test_local_stack_guard.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `tests/local_stack.py` exporting `API_URL: str`, `USERNAME: str`, `PASSWORD: str`, `EMAIL: str`, `FULL_NAME: str`, `TREE_ID: str`, `ALLOWED_HOSTS: frozenset[str]`, `is_local(url: str) -> bool`, `assert_local(url: str) -> None` (raises `RuntimeError`), `apply_test_environment() -> None`. Tasks 3 and 4 import these.

- [ ] **Step 1: Write the failing tests**

```python
"""The guard that keeps pytest off the live tree."""

import os

import pytest

from tests import local_stack


class TestHostAllowlist:
    def test_the_configured_stack_url_is_local(self):
        assert local_stack.is_local(local_stack.API_URL)

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:5555",
            "http://127.0.0.1:5555",
            "http://host.docker.internal:5555",
        ],
    )
    def test_every_allowed_host_passes(self, url):
        assert local_stack.is_local(url)

    def test_a_remote_host_is_refused(self):
        assert not local_stack.is_local("https://gramps.example.com")

    def test_a_host_merely_starting_with_an_allowed_name_is_refused(self):
        # Reason: resolve_media_path was already defeated once in this repo
        # by a shared string prefix. The allowlist compares whole hostnames.
        assert not local_stack.is_local("https://localhost.evil.example")

    def test_userinfo_cannot_smuggle_an_allowed_host(self):
        assert not local_stack.is_local("https://localhost@gramps.example.com")

    def test_assert_local_names_the_url_it_refused(self):
        with pytest.raises(RuntimeError) as exc:
            local_stack.assert_local("https://gramps.example.com")
        assert "gramps.example.com" in str(exc.value)


class TestEnvironmentApplication:
    def test_the_live_settings_are_replaced_by_the_stack_settings(self, monkeypatch):
        monkeypatch.setenv("GRAMPS_API_URL", "https://gramps.example.com")
        monkeypatch.setenv("GRAMPS_USERNAME", "live")
        local_stack.apply_test_environment()
        assert os.environ["GRAMPS_API_URL"] == local_stack.API_URL
        assert os.environ["GRAMPS_USERNAME"] == local_stack.USERNAME

    def test_settings_read_the_stack_after_application(self, monkeypatch):
        monkeypatch.setenv("GRAMPS_API_URL", "https://gramps.example.com")
        local_stack.apply_test_environment()
        from src.gramps_mcp.config import get_settings

        assert str(get_settings().gramps_api_url).startswith(local_stack.API_URL)

    def test_an_override_pointing_off_the_machine_is_refused(self, monkeypatch):
        monkeypatch.setenv("GRAMPS_TEST_API_URL", "https://gramps.example.com")
        with pytest.raises(RuntimeError):
            local_stack.apply_test_environment()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_local_stack_guard.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'tests.local_stack'`.

- [ ] **Step 3: Write `tests/local_stack.py`**

```python
"""
Coordinates of the local Gramps Web stack the tests run against.

Single source of truth: the seed script creates the account named here
and pytest authenticates with it, so the two cannot drift. Values live in
a tracked module rather than a dotenv file because .gitignore swallows
.env-*, which would leave every contributor to recreate it by hand.

The password is a local-only credential for a stack published on the
loopback interface with throwaway data. It is not a secret.
"""

import os
from urllib.parse import urlparse

API_URL = "http://localhost:5555"
USERNAME = "test-owner"
PASSWORD = "test-only-not-a-secret"
EMAIL = "test-owner@example.invalid"
FULL_NAME = "Test Owner"
# Reason: _build_url ignores the tree id - the token selects the tree
# (client.py:73-85) - but Settings requires the variable to be non-empty.
TREE_ID = "TestTree"

ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "host.docker.internal"})


def is_local(url: str) -> bool:
    """
    Report whether a URL points at this machine.

    Args:
        url (str): The URL to classify.

    Returns:
        bool: True when the host is one of ALLOWED_HOSTS.
    """
    # Reason: urlparse().hostname returns the host alone - port stripped,
    # userinfo discarded, lowercased - so the comparison is against whole
    # hostnames rather than a substring of the URL.
    return urlparse(url).hostname in ALLOWED_HOSTS


def assert_local(url: str) -> None:
    """
    Refuse a URL that is not the local stack.

    Args:
        url (str): The URL to check.

    Returns:
        None

    Raises:
        RuntimeError: When the host is not in ALLOWED_HOSTS.
    """
    if not is_local(url):
        raise RuntimeError(
            f"Refusing to run against '{url}': not the local test stack. "
            f"Allowed hosts: {sorted(ALLOWED_HOSTS)}. Start the stack with "
            "docker compose -f docker-compose.test.yml up -d and seed it "
            "with uv run python scripts/seed_test_tree.py."
        )


def apply_test_environment() -> None:
    """
    Point the Gramps configuration at the local stack, or refuse.

    Returns:
        None

    Raises:
        RuntimeError: When GRAMPS_TEST_API_URL names a non-local host.
    """
    url = os.environ.get("GRAMPS_TEST_API_URL", API_URL)
    assert_local(url)
    os.environ["GRAMPS_API_URL"] = url
    os.environ["GRAMPS_USERNAME"] = USERNAME
    os.environ["GRAMPS_PASSWORD"] = PASSWORD
    os.environ["GRAMPS_TREE_ID"] = TREE_ID
```

- [ ] **Step 4: Wire it into `tests/conftest.py`**

Insert directly below the module docstring, above the existing imports:

```python
from tests.local_stack import apply_test_environment

# Reason: get_settings() reads os.environ on every call and caches
# nothing, and config.py's load_dotenv() does not override variables
# already set - so setting them here, before any test module is
# imported, is what keeps .env (the live server) out of the test run.
apply_test_environment()
```

The `src.gramps_mcp` imports that follow now trip ruff's E402. Append `# noqa: E402` to each of them rather than moving the call: the call must precede them.

Extend the docstring's first paragraph to say the records are created in the local stack, not in the live tree.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_local_stack_guard.py -q`
Expected: 11 passed (the host allowlist parametrisation counts as three).

- [ ] **Step 6: Verify the offline suite is unharmed**

Run: `uv run pytest -m "not integration" -q`
Expected: 649 passed (638 + the 11 new).

- [ ] **Step 7: Verify the guard actually bites**

Run: `GRAMPS_TEST_API_URL=https://gramps.example.com uv run pytest tests/test_analysis.py -q`
Expected: a collection error quoting "Refusing to run against 'https://gramps.example.com'". No network call. This is the proof obligation from the spec; a green local run does not replace it.

- [ ] **Step 8: Commit**

```bash
uv run git add tests/local_stack.py tests/test_local_stack_guard.py tests/conftest.py
uv run git commit -m "test: point pytest at a local stack and refuse any other host"
```

---

### Task 2: The test stack

**Files:**
- Create: `docker-compose.test.yml`

**Interfaces:**
- Consumes: `tests/local_stack.py` for the published port (5555) and tree name.
- Produces: a Gramps Web server on `http://localhost:5555` with an empty tree and no users.

- [ ] **Step 1: Write the compose file**

Copy `docker-compose-sqllite.yml` and change exactly these things:

- delete the `grampsweb_mcp` service entirely - the tests import the working tree, and an MCP container would run the published image instead;
- `ports: ["127.0.0.1:5555:5000"]` on `grampsweb`;
- `GRAMPSWEB_TREE: "TestTree"`;
- rename every volume to a `gramps_test_` prefix (`gramps_test_users`, `gramps_test_index`, `gramps_test_thumb_cache`, `gramps_test_cache`, `gramps_test_secret`, `gramps_test_db`, `gramps_test_media`, `gramps_test_tmp`), in both the service's `volumes:` list and the top-level `volumes:` block;
- `container_name: grampsweb_test` and `grampsweb_test_celery`, `grampsweb_test_redis`, with the Celery service's broker URLs pointing at `grampsweb_test_redis`.

Keep the two healthchecks and the `depends_on: condition: service_healthy` between `grampsweb` and `grampsweb_celery` verbatim: they are what stops two containers running `alembic upgrade head` against the same SQLite file.

- [ ] **Step 2: Start it**

Run: `docker compose -f docker-compose.test.yml up -d`
Then: `docker compose -f docker-compose.test.yml ps`
Expected: `grampsweb_test` healthy within about a minute.

- [ ] **Step 3: Verify it answers and has no owner yet**

Run: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:5555/api/metadata/`
Expected: `401` - the server is up and demands authentication. A `000` means the stack is not listening; a `200` means you are talking to something else on that port.

- [ ] **Step 4: Commit**

```bash
uv run git add docker-compose.test.yml
uv run git commit -m "chore(docker): add the loopback-only test stack"
```

---

### Task 3: Seeding the stack

**Files:**
- Create: `scripts/seed_test_tree.py`
- Test: `tests/test_seed_backup_selection.py`

**Interfaces:**
- Consumes: `local_stack.API_URL`, `USERNAME`, `PASSWORD`, `EMAIL`, `FULL_NAME`, `assert_local`.
- Produces: `newest_backup_pair(backup_dir: Path) -> tuple[Path, Path]` returning `(xml_gz, media_zip)` for the newest date that has both, raising `FileNotFoundError` otherwise. Task 4 runs the script.

- [ ] **Step 1: Write the failing test for the pure helper**

```python
"""Backup pair selection - the only part of seeding that is pure."""

import pytest

from scripts.seed_test_tree import newest_backup_pair


def _pair(directory, stamp, xml=True, media=True):
    if xml:
        (directory / f"tree-{stamp}.gramps.gz").write_bytes(b"x")
    if media:
        (directory / f"media-{stamp}.zip").write_bytes(b"x")


class TestNewestBackupPair:
    def test_the_newest_complete_pair_wins(self, tmp_path):
        _pair(tmp_path, "2026-08-01")
        _pair(tmp_path, "2026-09-02")
        xml, media = newest_backup_pair(tmp_path)
        assert xml.name == "tree-2026-09-02.gramps.gz"
        assert media.name == "media-2026-09-02.zip"

    def test_a_date_missing_its_media_archive_is_not_used(self, tmp_path):
        # Reason: seeding the XML without the media leaves 1231 dead file
        # references, which surfaces much later as puzzling test failures.
        _pair(tmp_path, "2026-08-01")
        _pair(tmp_path, "2026-09-02", media=False)
        xml, media = newest_backup_pair(tmp_path)
        assert xml.name == "tree-2026-08-01.gramps.gz"

    def test_an_empty_directory_names_the_backup_script(self, tmp_path):
        with pytest.raises(FileNotFoundError) as exc:
            newest_backup_pair(tmp_path)
        assert "backup_prod.py" in str(exc.value)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_seed_backup_selection.py -q`
Expected: `ModuleNotFoundError: No module named 'scripts.seed_test_tree'`.
`scripts/` has no `__init__.py` and needs none - it imports as an implicit
namespace package, the repo root being on `sys.path` under pytest.

- [ ] **Step 3: Write the script**

Model it on `scripts/backup_prod.py`: same `httpx.AsyncClient`, same `sys.exit` on every failure, same staged-then-validated discipline. It must contain, in this order:

1. `newest_backup_pair(backup_dir)` - glob `tree-*.gramps.gz`, extract the stamp, keep the newest stamp that also has `media-<stamp>.zip`; raise `FileNotFoundError("No complete backup in {dir}. Run uv run python scripts/backup_prod.py first.")`.
2. `assert_local(local_stack.API_URL)` before the first request - the script restores over whatever it targets, so this guard is what stops it destroying the live tree.
3. `wait_for_server(client)` - poll `GET /api/metadata/` until it answers anything (401 included), up to 60 times, 5 seconds apart; exit naming `docker compose -f docker-compose.test.yml up -d` on timeout.
4. `ensure_owner(client)` - `POST /api/users/{USERNAME}/create_owner/` with `{"email": EMAIL, "full_name": FULL_NAME, "password": PASSWORD}`. HTTP 201 means created; a 409 or 422 whose body mentions the user already exists is success too. Any other status exits.
5. `get_token(client)` - as in `backup_prod.py`, against `local_stack.API_URL`.
6. `restore(client, headers, xml_path)` - `POST /api/importers/gramps/file/restore?dry_run=true` with the gzip as the body, print the `to_add`/`to_update`/`to_delete` counts from the `RestoreSummary`, then the same call without `dry_run`. Use `/restore`, never `/api/importers/gramps/file`: the latter is additive and a second run would duplicate the whole tree.
7. `upload_media(client, headers, zip_path)` - `POST /api/media/archive/upload/zip` with the zip as the body.
8. `verify(client, headers)` - `GET /api/media/?pagesize=1&page=1` and the same with `&filemissing=1`, reading `X-Total-Count` from each. Print both. Expect 1231 and 0 for the 2026-09-02 backup; print a warning naming both numbers when they differ rather than exiting, since a later backup will legitimately change the first.

Note for whoever runs it: pages start at `page=1`; `page=0` returns HTTP 422.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_seed_backup_selection.py -q`
Expected: 3 passed.

- [ ] **Step 5: Seed the running stack**

Run: `uv run python scripts/seed_test_tree.py`
Expected: the dry-run summary, then `media objects: 1231` and `file missing: 0`.

- [ ] **Step 6: Confirm the live tree was not touched**

Run: `uv run python -c "import pathlib; print(pathlib.Path('.env').read_text().splitlines()[2])"`
Expected: the live URL, unchanged. The seed script never reads `.env`; this checks nothing rewrote it.

- [ ] **Step 7: Commit**

```bash
uv run git add scripts/seed_test_tree.py tests/test_seed_backup_selection.py
uv run git commit -m "feat(scripts): seed the local test stack from a backup"
```

---

### Task 4: Make the integration suite pass against the stack

The deliverable is the list of what broke and why. Do not predict it - run it.

**Files:**
- Modify: whichever test modules fail, one commit per module.

**Interfaces:**
- Consumes: a seeded stack from Task 3.
- Produces: an integration suite that passes, or documented exceptions.

- [ ] **Step 1: Run the whole integration selection**

Run: `uv run pytest -m integration -q 2>&1 | tail -40`
Record the failures. Expect trouble in at least these four places, all named in the spec: hardcoded handles (`gramps_id` survives an XML round-trip, handles need not), `recent_changes` asserting 1-10 transaction entries against a tree whose history is one bulk import, `tree_stats` behaving differently for an owner created by `create_owner`, and `test_analysis.py` walking `I0001`'s ancestors.

- [ ] **Step 2: Fix one module at a time**

For each failing module: read the failure, decide whether the test's assumption or the environment is wrong, fix the test, re-run that module alone, commit. A test that cannot hold against a restored tree gets a `pytest.mark.skip` carrying the reason in its own words - never a silent deletion, never a loosened assertion that no longer checks anything.

- [ ] **Step 3: Re-run everything**

Run: `uv run pytest -q`
Expected: all tests pass, or every skip carries a reason.

- [ ] **Step 4: Prove the offline selection still stands alone**

Run: `docker compose -f docker-compose.test.yml stop && uv run pytest -m "not integration" -q`
Expected: still green with the stack down. Then `docker compose -f docker-compose.test.yml start`.

---

### Task 5: Documentation

**Files:**
- Modify: `CLAUDE.md` (the "Testing & Reliability" section), `README.md`

- [ ] **Step 1: Rewrite the stale CLAUDE.md rules**

Three bullets are wrong the moment Task 1 lands and must be replaced, not appended to:

- "Most tests need a live Gramps Web server ... and fail with connection errors offline" - they now need the local stack.
- "The Gramps Web server is remote ... Live tests run from the macOS host against it with no env override" - pytest no longer reads `.env` at all.
- "`tree_stats` returns a permission error even for the owner-role account in `.env`" - re-check against the stack in Task 4 and rewrite with what was actually observed.

Add: how to start and seed the stack, that `backup/` is gitignored and holds real data, and that `scripts/backup_prod.py` is the only thing in the repo that still talks to the live tree.

- [ ] **Step 2: Add the README section**

Under the existing testing instructions: start the stack, seed it, run the suite. Three commands, in that order.

- [ ] **Step 3: Verify the docs build**

Run: `uv run --with mkdocs-material mkdocs build --strict`
Expected: no broken internal links.

- [ ] **Step 4: Commit**

```bash
uv run git add CLAUDE.md README.md
uv run git commit -m "docs: the test suite targets the local stack, not the live tree"
```
