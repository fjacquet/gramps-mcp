# Design: quality improvements, lot 5 - test structure and the shared request path

Date: 2026-08-13
Status: approved, not yet implemented
Branches: `fix/quality-lot5a-test-structure`, `fix/quality-lot5b-upload-request-path`

## Context

Fifth and final lot of the quality work arising from a full review of
`src/gramps_mcp`. Lots 1 to 4 shipped as pull requests #8 to #11 and were
released as v1.7.0; the documentation work that followed released as v1.7.1.

This lot closes the three items those releases left open, recorded in the
product requirements document and in `CLAUDE.md`:

- `tests/test_data_management.py` carries a chain of module-level globals that
  makes its tests dependent on execution order.
- `upload_media_file` bypasses the shared request path and so lacks its 401
  refresh-retry and its connection and timeout wrapping.
- The `check-file-length` pre-commit hook excludes `tests/`, so the 500-line
  rule is unenforced there and three test files exceed it.

The three are connected. `tests/test_data_management.py` is 1139 lines. Had the
limit applied, it would have been split long ago, and a split would have made
the chain of globals untenable. The unenforced rule is what let the defect grow.

## Scope

Two pull requests, sequential, split by the nature of the change rather than by
size. Lot 5a touches only `tests/` and `.pre-commit-config.yaml`. Lot 5b touches
`client.py`, which every tool depends on. A review that mixes them dilutes
attention where it matters most.

| Lot | Item | Location |
|---|---|---|
| 5a | The file-length hook exempts `tests/` | `.pre-commit-config.yaml:26` |
| 5a | A 1139-line module with an order-dependent global chain | `tests/test_data_management.py` |
| 5a | A 617-line module of independent checks | `tests/test_parameter_alignment.py` |
| 5a | An 800-line module holding a 665-line test | `tests/test_complete_workflow.py` |
| 5a | The no-fixtures rule reads wider than its intent | `CLAUDE.md` |
| 5b | The media upload bypasses the shared request path | `client.py:343-377` |

## Lot 5a: test structure

### 1. Extend the file-length hook first

Remove `exclude: ^tests/` from the `check-file-length` hook in
`.pre-commit-config.yaml:26`.

Doing this before the splits rather than after is deliberate: the hook then
refuses every subsequent commit until the three files comply, which makes the
splits obligatory rather than aspirational. The alternative ordering leaves an
opening for the hook change to land alone and the splits to be deferred.

Note that `pyproject.toml:30-33` exempts `tests/*` from ruff's E501 **with a
written reason** - long diagnostic strings that the formatter cannot wrap. That
exemption stays. Line length is cosmetic; file length says a module is doing too
much. They are different rules and the project should hold only one of them.

### 2. Split `tests/test_data_management.py`

1139 lines across ten classes. Split by domain:

| File | Classes | Approximate lines |
|---|---|---|
| `tests/test_create_sourcing.py` | `TestCreateRepositoryTool`, `TestCreateSourceTool`, `TestCreateCitationTool`, `TestCreateSourcedEventTool` | 420 |
| `tests/test_create_people.py` | `TestCreatePersonTool`, `TestCreateFamilyTool` | 396 |
| `tests/test_create_records.py` | `TestCreateNoteTool`, `TestCreateMediaTool`, `TestCreatePlaceTool`, `TestCreateEventTool` | 270 |

Every class must land carrying exactly the marker state it has now.

### 3. Replace the chain of globals with a fixture

`tests/test_data_management.py:32-33` declares module-level globals
(`test_repository_handle`, `test_source_handle`, and others). One test creates a
repository, extracts its handle from formatted output with a regular expression,
and assigns it to a global; a later test reads it and calls `pytest.fail` when
it is absent.

The chain lives entirely in the sourcing classes, so it moves to
`tests/test_create_sourcing.py` and is replaced there by a module-scoped pytest
fixture that creates a real repository and a real source against the live
server, yields their handles, and deletes them on teardown.

**The fixture returns handles structurally, read from the API response, rather
than scraped out of formatted prose.** Lot 3 removed exactly this pattern from
`tools/search_details.py`, on the grounds that a rendering change silently
breaks resolution with no test able to notice. The pattern survives in the
tests; this removes it there too.

**This is setup, not a stub.** Nothing about the API's behaviour is faked: the
fixture calls the real server and uses what it returns. `CLAUDE.md`'s
"no fixtures" wording is aimed at fake responses standing in for the server, and
must be clarified to say so - see item 5.

### 4. Split the remaining two files

`tests/test_parameter_alignment.py` is 617 lines of eleven independent checks
against a single class. A mechanical split by entity group suffices:

| File | Tests |
|---|---|
| `tests/test_alignment_sourcing.py` | repository, source, citation, media |
| `tests/test_alignment_records.py` | event, person, family, place, note |
| `tests/test_alignment_simple_params.py` | the simple-params, person-event-reference and remaining checks |

`tests/test_complete_workflow.py` is different and is the real work of this lot.
Its 800 lines hold three tests, of which
`test_all_entity_attributes_comprehensive` is 665 lines by itself. Splitting the
file by method therefore does not bring it under the limit - that one test
exceeds it alone.

It is composed of sequential blocks, each exercising one entity type. Break it
into one test per entity. The gain is larger than the line count: today its
failure reports that the comprehensive test failed, not which entity failed.

### 5. Clarify the fixtures rule

`CLAUDE.md` currently forbids fixtures without qualification. Amend it to state
what item 3 relies on: setup that creates real records against the real server
is permitted; what is forbidden is faking the API's behaviour. This is the same
class of correction already applied to the mocks wording, and for the same
reason - a rule that forbids what the repository does is a rule nobody can
follow.

## Lot 5b: the shared request path

`client.py:343-377` calls `self.auth_manager.client.request` directly. Compared
with `_make_request`, the upload path is missing:

| Behaviour | `_make_request` | `upload_media_file` |
|---|---|---|
| 401 | refreshes the token and retries once | surfaces the error |
| `HTTPStatusError` | formatted | formatted |
| `ConnectError` | wrapped in `GrampsAPIError` | escapes raw |
| `TimeoutException` | wrapped in `GrampsAPIError` | escapes raw |
| empty 2xx body | returns `{}` | returns an error dict |

So a token that expires mid-session makes a media upload fail where every other
tool recovers silently, and an unreachable server raises `httpx.ConnectError`
past a caller that catches `GrampsAPIError`.

**Decision: extend `_make_request` rather than duplicate its handling.** Add
`content: bytes | None = None`; when supplied, pass it to httpx in place of
`json_data`. Route `upload_media_file` through it. Existing callers are
unaffected: the parameter is optional and defaults to `None`.

Duplicating the error handling into `upload_media_file` was considered and
rejected. Duplication is what produced this defect - the function was written by
copying part of `_make_request` and omitting the rest. A second copy guarantees
the next divergence.

## Testing

The project tests against the real Gramps API. Each item that changes behaviour
gets a test, written first and observed failing.

**Every test passes a revert-check before its commit: remove the fix, run the
test, confirm it fails, restore the fix, confirm it passes - and revert each
independent half separately.** Six times across the previous four lots a fix
shipped with a test that claimed to cover it and did not.

For lot 5b the two cases that matter are the 401 retry and the `ConnectError`
conversion. Both are reachable offline by replacing the transport seam alone,
as `tests/test_http_error_detail.py` established: assertions read the output of
the code under test, never the stub's call arguments.

For the three splits, the only proof that no test was lost is the collection
count. Record it before and after each split and require equality:

```bash
uv run pytest --collect-only -q -m "not integration" | tail -3
uv run pytest --collect-only -q -m integration | tail -3
```

Live tests need a URL override from the macOS host, because `.env` targets
`host.docker.internal`, which resolves only inside the container:

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest ...
```

## Integration

Branch `fix/quality-lot5a-test-structure`, then
`fix/quality-lot5b-upload-request-path` off updated `main`. One atomic commit per
item. Two pull requests, each merged with a merge commit, never squashed.

The release tag follows the second merge, and the version bump must regenerate
`uv.lock` in the same commit: `uv.lock` pins the project's own version and CI
runs `uv sync --locked`.

## Accepted risk

Lot 5a is confined to tests and cannot change what the server does. Its risk is
silent loss - a test dropped during a split, or a marker that changes meaning in
its new home. The collection counts are the control.

Lot 5b changes the request path every tool uses. An optional parameter defaulting
to `None` cannot alter existing behaviour, but if a regression did occur it would
be total. **The full integration suite must run before merge, not only the
offline subset.**

Tests that write to the tree write to a real genealogy database. As in the
earlier lots, a run killed outright can leave a `Pytest`-prefixed object behind;
the new fixture's teardown is subject to the same limit.
