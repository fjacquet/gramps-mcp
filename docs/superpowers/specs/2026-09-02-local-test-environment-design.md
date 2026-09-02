# Local test environment

**Date:** 2026-09-02
**Status:** design, approved scope pending implementation plan

## Problem

Every integration test in this repository runs against the live family
tree. `tests/conftest.py` creates real people, families, events, sources
and media in it, then deletes them. A failed teardown leaves residue in
production data, and a test that writes where it should read corrupts
records that exist nowhere else. The tree is the product; it should not
also be the fixture.

`pytest -m "not integration"` (638 tests) is unaffected and stays
offline. The 157 integration tests, spread over 28 modules, are what
this design moves.

## Scope

In scope: a local Gramps Web stack on the developer's machine, seeded
from a backup of the live tree, that pytest targets by default and
cannot be made to leave.

Out of scope, decided:

- **CI stays offline.** GitHub Actions keeps running the
  `-m "not integration"` selection. No stack in CI.
- **The MCP image rebuild** that publishes the `create_media` fix is a
  separate step.
- **`.env` and `.env-local` are not modified.** `.env` remains the live
  server's configuration, read by the MCP container and by
  `scripts/backup_prod.py`, and by nothing else.
- **The 60 duplicate media records** found while taking the backup (see
  Measured facts) are a data defect in the live tree, not a test-
  environment concern.

## Measured facts

Established on 2026-09-02, not assumed:

| Fact | Value |
| --- | --- |
| XML backup | `backup/tree-2026-09-02.gramps.gz`, 796 066 bytes |
| Media backup | `backup/media-2026-09-02.zip`, 928 514 742 bytes, 1171 files |
| Media objects in the tree | 1231, `filemissing=0` |
| Distinct media checksums / paths | 1171 / 1171 |

The 60-record gap is 60 media objects pointing at a file another record
already references - the shape a retry after a failed `create_media`
leaves behind. The archive is therefore complete; a restored tree must
show 1231 objects resolving to 1171 files, and that is not a seeding
failure.

Endpoints verified against `docs/reference/openapi.json` (Gramps Web API
3.21.1):

- `POST /api/importers/{extension}/file/restore` - "Reset the tree to
  match an uploaded backup, replacing its contents", with a `dry_run`
  query parameter. Replacement semantics, so re-seeding is idempotent.
  `POST /api/importers/{extension}/file` is additive and would duplicate
  the whole tree on a second run - do not use it.
- `POST /api/users/{user_name}/create_owner/` - creates the first
  administrator on a fresh server, no prior authentication.
- `POST /api/media/archive/upload/zip` - restores the media archive.
- `POST /api/media/archive/` returns a Celery task id, not a filename;
  the caller polls `GET /api/tasks/{id}` until `state == "SUCCESS"`.
  `scripts/backup_prod.py` already implements this.

## Design

### 1. The stack

A new `docker-compose.test.yml`, derived from
`docker-compose-sqllite.yml` and reduced to `grampsweb`,
`grampsweb_celery` and `grampsweb_redis`.

- **No MCP container.** The tests import the working tree; an MCP
  container would run the published image instead, which is the trap
  already recorded in `CLAUDE.md`.
- **Published on `127.0.0.1:5555`,** not `:80`, so the stack cannot
  collide with an existing local Gramps Web or with anything else on
  port 80, and is not reachable off the machine.
- **Volumes prefixed `gramps_test_`,** distinct from those in
  `docker-compose-sqllite.yml`. `docker compose -f docker-compose.test.yml
  down -v` resets the test tree and destroys nothing else.
- SQLite backend, tree name `TestTree`.

### 2. Seeding - `scripts/seed_test_tree.py`

Against the local stack only. Its own guard: refuse to run if the target
URL is not in the allowlist of section 3, so the script can never
restore a backup over the live tree.

1. Wait for the container healthcheck.
2. `POST /api/users/<owner>/create_owner/` with the credentials
   `.env-test` declares. Skip when the user already exists.
3. Obtain a token.
4. Locate the newest `backup/tree-*.gramps.gz` and matching
   `backup/media-*.zip`. Missing or mismatched dates is an error naming
   `scripts/backup_prod.py`, never a silent partial seed.
5. `POST /api/importers/gramps/file/restore` with `dry_run=true`, report
   the changeset summary, then the real call.
6. `POST /api/media/archive/upload/zip` with the media archive.
7. Verify: media object count is 1231 and `filemissing` is 0. Print both.

`backup/` is gitignored - it holds real genealogy data on living people
and this repository is public.

### 3. Switching and the guard - root `tests/conftest.py`

`.env-test` is loaded **at conftest import time**, before
`src.gramps_mcp.config` is first touched. `get_settings()` is a cached
singleton; loading it from a fixture would arrive after some module has
already read the live configuration.

The guard compares the **host** of `GRAMPS_API_URL` against an explicit
list - `localhost`, `127.0.0.1`, `host.docker.internal`. Not a prefix or
substring test: this repository has already had a containment check
defeated by a shared prefix (`resolve_media_path`, see
`tests/test_media_path_containment.py`). Any other host aborts the
integration tests with a message naming the URL that was seen.

pytest stops reading `.env` entirely.

**Proof obligation:** a negative test that points `GRAMPS_API_URL` at a
non-local host and asserts the run is refused. A green local run
demonstrates nothing about the guard.

### 4. Suite impact - to be measured

Four consequences of restoring an XML export are unknown and must be
established by running the suite, not predicted:

- `gramps_id` values survive an XML round-trip; **handles need not**.
  Any test carrying a hardcoded handle breaks.
- `recent_changes` asserts on transaction history, which an import may
  collapse into a single bulk transaction
  (`tests/test_analysis.py` asserts 1-10 entries).
- `tree_stats` returns "Permission denied" against the live server for
  the owner-role account. On a server whose owner was created by
  `create_owner`, that may change in either direction.
- `test_analysis.py` walks the ancestors of `I0001` over three
  generations and expects substantial output.

The implementation plan must therefore include: run all 157 integration
tests against the seeded stack, record which fail and why, and resolve
each one - either a corrected test or a documented exception. That list
is a deliverable, not an assumption.

### 5. Documentation

`CLAUDE.md` currently states that most tests need the live server and
that failures offline are expected. That paragraph becomes wrong the day
this lands and must be rewritten in the same change, together with a
`README.md` note on starting and seeding the stack.

## Testing

- The guard's negative test (section 3), which is the only proof the
  live tree is unreachable from pytest.
- The offline selection stays green throughout: 638 tests, unchanged.
- The seeded stack's verification counts (section 2, step 7) are printed
  by the seed script on every run, so a partial restore is visible
  immediately rather than as a puzzling test failure later.
