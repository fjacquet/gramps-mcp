# Design: quality improvements, lot 1 — correctness and stability

Date: 2026-08-13
Status: implemented, three of four defects fixed, one falsified and dropped, open as pull request #8
Branch: `fix/quality-lot1-correctness`

## Context

A full review of `src/gramps_mcp` (62 files, ~9000 lines) produced 20 findings.
None is a regression from recent work; all predate it. The findings span five
independent areas — handlers, tools, `merge.py`, Pydantic models and
`client.py` — which is too much for one spec.

The work is therefore split into four lots by the nature of the defect. Each
lot gets its own spec, plan, branch and pull request. This document covers
**lot 1 only**.

| Lot | Theme |
|---|---|
| 1 | Correctness and stability: crashes, wrong endpoints, shared-client teardown |
| 2 | Data fidelity: date rendering, `merge.py` replace-vs-union, parameter models |
| 3 | Ergonomics: result totals, error messages, sort handling |
| 4 | Test debt: uncovered paths, guards, the misleading docstring in `tests/test_user_tools.py` |

## Scope

Four defects, each with its twin occurrences.

| Defect | Files |
|---|---|
| `with_client` closes the process-wide HTTP pool | `tools/search_basic.py:69`; the manual `finally` blocks in `tools/data_management.py:145,263,395,459` and `tools/sourced_event.py:125` |
| Crash when a save produces no change | **(dropped — falsified during testing)** |
| Collection endpoint used where the item endpoint is meant | `handlers/person_handler.py:159`, `handlers/family_handler.py:194` |
| One dead handle discards an entire person detail | `handlers/person_detail_handler.py:264` and 277-288 |

Explicitly out of scope, each belonging to a later lot: date rendering,
`merge.py`, the Pydantic parameter models, search result totals, and the 422
error messages.

## The defects

### 1. The shared HTTP pool is torn down mid-flight

`with_client`'s `finally` calls `client.close()`, which delegates to
`AuthManager.close()` — and `AuthManager` is a process-wide singleton owning a
single `httpx.AsyncClient`. Two tool calls running concurrently, which is
normal for this server, means the first to finish closes the connection pool
out from under the second's in-flight request. It also fires on every nested
call: `get_type_tool` calling `find_type_tool` closes the pool, and the caller
then rebuilds it and re-authenticates.

**Decision: stop closing the client.** Remove the `close()` call from
`with_client` and from the manual `finally` blocks. The singleton keeps its
client for the lifetime of the process, which is what it was evidently built
for — its `client` property already recreates the client on demand when it is
closed or when the event loop changes.

Two alternatives were considered and rejected. Reference counting adds
concurrent state to a singleton that already has some, and still destroys the
pool between bursts, paying reconnection cost for no benefit. A client per call
gives isolation but loses connection reuse on a server that chains calls, and
does nothing for the nested-call case.

The consequence to accept and document: nothing closes the pool explicitly at
shutdown. For a long-running server that is the normal arrangement, and the
process exit releases the sockets.

### 2. A save that changes nothing reports a failure

`_format_save_response` reads `entity_data.get("handle", "N/A")` at
`data_management.py:159`, *before* its `try` block at 162. `_extract_entity_data`
returns `None` for a falsy response (line 67-68). A Gramps PUT that produces no
actual change was assumed to return `[]`, which would cause updating an entity
with data identical to what is stored to raise `AttributeError: 'NoneType'
object has no attribute 'get'`. Similarly, `sourced_event.py:69` would do
`source_data["handle"]` on the same `None`, raising `TypeError`.

**Would-be fix (had the premise been true):** handle the `None` case before
dereferencing, and report the no-change outcome as the success it is.

**Outcome:** The premise was verified against the live Gramps Web server during
testing. A PUT with unchanged place data does not return `[]` or any other falsy
value. Instead, it returns a fully populated response: `{'new': {...}, 'old':
{...}, 'type': 'update'}`. Consequently, `_extract_entity_data` never returns
`None` on this code path, and the described `AttributeError` cannot occur. The
defect is theoretical rather than real. Per the testing plan, this task has been
dropped rather than worked around: no code changes were made to
`data_management.py` or `sourced_event.py` for this defect.

### 3. Collection endpoint used where the item endpoint is meant

`person_handler.py:159` and `family_handler.py:194` call `ApiCalls.GET_MEDIA`
(`media/`, the collection) passing `handle=media_handle`.
`_build_url_with_substitution` silently drops keyword arguments with no
matching placeholder, so the handle is ignored, the whole media collection is
fetched, and the `list` that comes back makes the following `.get()` raise an
`AttributeError` that a bare `except Exception: continue` swallows.

Two consequences: the "Attached media" line never appears in `find_person` or
the family view, and every media reference triggers a full collection download.

Fix: use `ApiCalls.GET_MEDIA_ITEM` (`media/{handle}`), as
`handlers/citation_handler.py:105` and `handlers/media_handler.py:48` already
do correctly.

### 4. One dead handle discards an entire person detail

The media loop at `person_detail_handler.py:264-273` and the note loop at
277-288 make unguarded `make_api_call`s, and the function has no `try/except`
of its own. A single dangling or private media or note handle returns 404,
raising `GrampsAPIError`, which discards the whole person detail — relations,
timeline, citations — leaving only `Error: Record not found.`.
`handlers/family_detail_handler.py:196,211` wraps the equivalent calls and
degrades gracefully.

Fix: adopt the `family_detail_handler` pattern. Also guard
`note_data.get("text", {}).get("string", "")` at line 284, which raises when
`text` is JSON null — the same null-versus-absent bug class already fixed in
`tools/user_tools.py`.

## Testing

The project forbids mocks, fixtures and test clients: tests run against the
live Gramps Web server. Each defect gets one test, written first and observed
failing before the fix.

| Defect | Test |
|---|---|
| Shared pool | Two tool calls launched concurrently with `asyncio.gather`; both must succeed. Fails today because the first to finish closes the second's pool. |
| No-change save | **(dropped — defect falsified during testing)** |
| Media endpoint | A person carrying a media object must render its "Attached media" line. |
| Dead handle | Attach a media object to a person, delete the media, request the person detail; it must degrade without losing the rest. |

**Premise for the no-change test (verified):** A Gramps PUT with unchanged data
returns `{'new': {...}, 'old': {...}, 'type': 'update'}`, not `[]` as
originally assumed. The defect is theoretical; the premise check determined that
Gramps returns a fully populated response, so the task was dropped rather than
worked around.

Tests that write to the tree must clean up in a `finally` block, as
`tests/test_user_tools.py::test_create_then_delete` already does.

Live tests need a URL override from the macOS host, because `.env` targets
`host.docker.internal`, which only resolves inside the container:

```
GRAMPS_API_URL=http://localhost:80 uv run pytest ...
```

## Integration

Branch `fix/quality-lot1-correctness`. One atomic commit per defect, each
carrying its fix and its test together, so a single correction can be read or
reverted on its own. One pull request for the lot, reviewed before merge. No
release tag — the four lots ship together as one version.

## Accepted risk

The tests write to a real genealogy tree: creating and deleting a media object,
saving an entity twice. Every test cleans up after itself, but the target is
the repository owner's live data rather than a scratch database. The
person-detail resilience test deliberately writes a referentially inconsistent
record — a person carrying a media reference to a handle that does not exist —
which `CLAUDE.md` warns can crash the XML export or backup if left behind; the
test removes it in a `finally` block, but if a run is killed outright, a
leftover can be identified by grepping for surnames beginning with "Pytest".
