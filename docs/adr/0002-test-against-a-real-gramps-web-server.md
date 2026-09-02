# 2. Test against a real Gramps Web server, with no mocks

Date: 2025-09-11

## Status

Accepted, and narrowed by
[ADR 0010](0010-run-the-tests-against-a-local-stack.md): the no-mocks rule
below stands unchanged, but the live server the suite talks to is now a
local stack seeded from a backup, not the production tree. The costs
recorded under Consequences - writes to a real genealogy database,
leftover `Pytest`-prefixed objects, credentials for a full run - no longer
apply.

## Context

`gramps-mcp` is almost entirely translation: it turns MCP tool arguments
into Gramps Web REST calls and turns the responses back into text. Very
little of the codebase is logic that exists independently of the API's actual
behaviour. A mocked test of a translation layer asserts that the code sends
what the test author believed the API expects, which is precisely the
assumption most likely to be wrong.

The rule appears in `CLAUDE.md` at the initial commit (d27134a, 2025-09-11),
line 26, and in `CONTRIBUTING.md` at the same commit. No spec or commit
argues for it; it was stated as a premise rather than concluded from a
deliberation, so the justification above is reconstruction from what the
codebase is, not a record of what was said.

## Decision

Tests exercise a live Gramps Web instance configured through `.env`. No
mocks, no fixtures, no test clients. Tests are written before the code
(red-green-refactor) and each fix carries a test observed failing without it.

The boundary the rule does not cross is pure logic with no API in it.
`merge.py` was extracted into a pure module (3d7c8cc) explicitly so its
tests would need no server, and the design spec for that work states that
this "complies with the project's no-mocks policy; there is nothing to mock."

Lot 4 of the quality work (2026-08-13) added `pytestmark =
pytest.mark.integration` to every module that needs the server, making
`uv run pytest -m "not integration"` a real selector. The marker had been
declared in `pytest.ini` since the initial commit and used by nothing. The
default `uv run pytest` was deliberately left selecting everything, so that
a green result cannot be read as proof of the server path when the server
was never contacted.

## Consequences

Bugs found by this suite are real bugs. Several of the quality lots exist
because a live call returned something the code did not expect - a null
`text` on a note, a nullable `role`, a `409` on a create race. None of those
would have appeared against a mock built from the same assumptions as the
code.

The costs are substantial and are being paid now. Most of the suite cannot
run offline at all; a full run takes minutes and needs credentials. Tests
write to a real genealogy database, and the lot 4 spec records that a run
killed outright leaves `Pytest`-prefixed objects behind for someone to clean
up. Live runs from the macOS host need a `GRAMPS_API_URL` override because
`.env` targets `host.docker.internal`. Three offline failures in
`test_parameter_alignment.py` (a `media_path` mismatch) are carried as
known, and `tree_stats` fails with a permission error even for the
`.env` owner account.

The rule as written is also already violated. `tests/test_client_merge.py`
and `tests/test_http_error_detail.py` both import `unittest.mock` and patch
the transport seam, and CI runs both of them - the workflow's explicit file
list is `test_merge.py`, `test_config.py`, `test_client_merge.py`,
`test_utils.py`, `test_http_error_detail.py`. The defensible version of the
rule is "no mocking of the Gramps API's semantics; stubbing the HTTP
transport to construct a response httpx itself would produce is allowed",
which is what those two files actually do. That version has not been written
down, so the rule on the books forbids two files the project's own CI
depends on. This tension is unresolved.

## Update, 2026-08-13

The three known offline failures no longer exist. Branch
`fix/quality-lot5a-test-structure` split `tests/test_parameter_alignment.py`
into the `test_alignment_*` modules and the `media_path` mismatch went with
it; `uv run pytest -m "not integration"` is green at 134 passed. Nothing is
carried as a known offline failure now, so a red offline run is a
regression and should be read as one.

The rest of this section still holds: the suite is still mostly
server-bound, live runs from the macOS host still need the `GRAMPS_API_URL`
override, `tree_stats` still fails on permissions for the `.env` owner
account, and the tension over `unittest.mock` in `test_client_merge.py` and
`test_http_error_detail.py` is still unresolved.
