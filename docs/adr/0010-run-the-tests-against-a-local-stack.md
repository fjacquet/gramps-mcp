# 10. Run the tests against a local Gramps Web stack

Date: 2026-09-02

## Status

Accepted. Amends [ADR 0002](0002-test-against-a-real-gramps-web-server.md),
which stands in full on the no-mocks rule and is narrowed only on *which*
real server the suite talks to.

## Context

ADR 0002 settled that tests exercise a live Gramps Web instance rather than
mocks, and that decision has paid for itself: several defects exist in the
changelog only because a real call returned something the code did not
expect. What it did not settle is which live instance. In practice the
answer was the production family tree - the one that is the point of the
whole project.

Its own Consequences section names the cost plainly: "Tests write to a real
genealogy database", and a run killed outright "leaves `Pytest`-prefixed
objects behind for someone to clean up". `tests/conftest.py` creates people,
families, events, sources and media on every module and deletes them
afterwards, which is correct until a teardown does not run.

The tree is irreplaceable in a way the code is not. It holds work that
exists nowhere else and records living people. A test suite that writes to
it trades a real risk for a convenience.

## Decision

The suite runs against a local Gramps Web stack, seeded from a backup of the
live tree, and cannot be pointed anywhere else.

- `docker-compose.test.yml` publishes Gramps Web on `127.0.0.1:5555` with
  `gramps_test_` volumes, SQLite, and no MCP container - the tests import
  the working tree, and an MCP container would run the published image.
- `scripts/backup_prod.py` takes both halves of a backup: the Gramps XML
  and the media archive the XML only references. It is the only thing left
  in the repository that talks to the live server.
- `scripts/seed_test_tree.py` restores that backup through
  `POST /importers/gramps/file/restore`, which replaces the tree's contents,
  so re-seeding is idempotent and also clears whatever a failed teardown
  left behind.
- `tests/conftest.py` applies `tests/local_stack.py` at import time and
  refuses any host outside an explicit allowlist. pytest no longer reads
  `.env`. The refusal is covered by its own test, because a passing local
  run demonstrates nothing about a guard.

The seed uses a copy of the production data rather than a synthetic tree.
Several tests assert on a populated tree - ancestors over three
generations, a transaction history, media counts - and a hand-built fixture
would have to grow into a second family tree to satisfy them.

CI is unchanged: it runs `-m "not integration"`, which needs no server.

## Consequences

The live tree is now unreachable from pytest, and a failed teardown costs
nothing. Running the full suite is a local operation with no credentials
beyond the ones in `tests/local_stack.py`, which guard a loopback-bound
container holding throwaway data.

Seeding it took finding three things the API does not do as documented:
`create_owner` answers 401 on this image, so the first account is created
with the container's own CLI; the restore and the media upload both answer
202 with a Celery task, so both must be polled to completion; and `/token/`
is capped at one request per second, which the suite exceeds on its own -
`AuthManager` now waits out a 429 rather than reporting it as a failure.

Two settings the tests had been inheriting from `.env`, or not at all, are
now explicit: the media import root, so the `media_path` tests can read
their own fixture in `tests/sample/`, and the tree id, which is a UUID
minted when the stack's volumes are created and which the seed script
records for `local_stack.tree_id()` to read back.

The test account is created with the admin role, where the live account has
the owner role. That is a deliberate divergence: `get_tree_info` reads
`/trees/<id>`, which an owner is refused, so an owner-role test account
would leave that test permanently red for a reason unrelated to the code.
`tree_stats` therefore passes locally and fails against production.

The backup is a point-in-time copy and will drift from the live tree. It is
gitignored - real data on living people, in a public repository - so each
contributor takes their own, and a test that comes to depend on data added
after the last backup will fail until it is refreshed.
