# Quality Lot 4 — Test Debt and Leftovers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close what the three previous quality lots left behind: coverage they deferred, one claim of coverage that was never true, and four small code defects each found while fixing something else.

**Architecture:** Nothing structural. Five items are tests or test infrastructure; four are one-to-five-line code changes in files that already carry the correct pattern elsewhere. The one genuine design change replaces a narrow refusal with escaping, and is gated behind a live check.

**Tech Stack:** Python 3.13, httpx, pydantic v2, MCP Python SDK 2.0, pytest + pytest-asyncio, uv, ruff.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-08-13-quality-lot4-test-debt-design.md`.
- Every command runs through uv: `uv run pytest`, `uv run git commit`.
- No mocks, no fixtures, no test clients.
- Live tests need a URL override from the macOS host, because `.env` targets `host.docker.internal`, which only resolves inside the container: `GRAMPS_API_URL=http://localhost:80 uv run pytest ...`. Never edit `.env`, never commit the override.
- **Do not use `git stash`.** Read a file as it is on main with `git show main:<path>`. Do not check out main either.
- **Every test must pass a revert-check before its commit:** remove the fix, run the test, confirm it fails, restore the fix, confirm it passes — and **revert each independent half separately**. Record both observations in the report. Five times across the previous lots a fix shipped with a test that claimed to cover it and did not; once, reverting two halves together credited two detectors where there was one, and the defect that slipped through was a Critical found only at the final review.
- Where a case genuinely cannot be reached without a mock, say so and remove the claim rather than writing a test that appears to cover it. That outcome is expected for Task 2.
- Never create a file longer than 500 lines. No emojis anywhere. Google-style docstrings on every function. Pre-commit hooks enforce the first two.
- One atomic commit per item.
- Branch `fix/quality-lot4-test-debt`, which already exists and holds the spec commit.
- Do NOT merge the pull request, create a tag, publish a release, or bump a version. This lot ends the series and a release follows, but that is the owner's action.

---

### Task 1: Make the `integration` marker real, and derive the offline list from it

`pytest.ini:10` declares the marker and documents `-m "not integration"` as the
way to deselect server-dependent tests. No test carries it, so that command
selects everything. Meanwhile `CLAUDE.md:44-46` lists offline-safe test files by
hand, and that list has now diverged twice: it names five files, and there are
at least eight.

**Files:**
- Modify: every test module under `tests/` that needs the live server
- Modify: `CLAUDE.md:44-46`

**Interfaces:**
- Consumes: nothing.
- Produces: `-m "not integration"` selects only server-free tests. Later tasks may use it.

- [ ] **Step 1: Establish which files are genuinely offline**

Do not trust any existing list, including this plan's. Determine it empirically
by running each test file with an unreachable API and seeing which pass:

```bash
for f in tests/test_*.py; do
  if GRAMPS_API_URL=http://127.0.0.1:9 uv run pytest "$f" -q >/dev/null 2>&1; then
    echo "OFFLINE $f"
  else
    echo "SERVER  $f"
  fi
done
```

Record the full output in your report. A file that passes against a dead
endpoint touches no server. Note that a file can pass for the wrong reason — if
it contains only skipped tests, for example — so sanity-check any surprise
against the file's contents before classifying it.

- [ ] **Step 2: Mark the server-dependent modules**

In each file classified `SERVER`, add immediately after the imports:

```python
pytestmark = pytest.mark.integration
```

Ensure `import pytest` is present in each. Do not mark individual tests; module
level is enough and is far less to maintain.

- [ ] **Step 3: Verify the marker selects correctly**

```bash
GRAMPS_API_URL=http://127.0.0.1:9 uv run pytest -m "not integration" -q
```

Expected: every selected test passes against a dead endpoint, and the count
matches the number of tests in the files you classified `OFFLINE`. If anything
fails, that file was misclassified — fix the classification, not the test.

Then confirm the default is unchanged:

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest --collect-only -q | tail -1
```

Expected: the same total as before your change. `uv run pytest` must still run
everything.

- [ ] **Step 4: Replace the hand-written list in `CLAUDE.md`**

`CLAUDE.md:44-46` currently enumerates the offline files. Replace that
enumeration with the marker command, keeping the surrounding sentence's meaning
and the file's voice:

```
  offline: `uv run pytest -m "not integration"`.
```

Keep whatever the surrounding lines say about most tests needing a live server —
that is still true. Only the enumeration goes.

- [ ] **Step 5: Commit**

```bash
rtk git add pytest.ini tests/ CLAUDE.md
uv run git commit -m "test: apply the integration marker so the offline suite is selectable"
```

---

### Task 2: Correct the docstring that claims coverage it does not provide

`tests/test_user_tools.py:264-267` says the test "also proves the fix for the
mid-batch-abort finding". It does not: the test drives a 409, which the code
caught before that fix existed, so it would pass with the fix reverted.

**Files:**
- Modify: `tests/test_user_tools.py:264-267`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing.

- [ ] **Step 1: Read what the claim refers to**

Read `src/gramps_mcp/tools/user_tools.py`, the `create` branch of
`manage_users_tool` and its helper `_create_one`. The fix in question makes a
mid-batch failure return the rows already accumulated instead of discarding
them, so a batch that fails partway still reports the passwords already issued.

- [ ] **Step 2: Try to reach the case**

The 409 path does not exercise it, because that is a skip rather than a
failure. What would: a batch where one entry fails for a reason other than
"already exists", after at least one entry succeeded.

Probe whether such a failure is reachable against the live server. Candidates
worth trying, in order:

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio, uuid
from src.gramps_mcp.tools.user_tools import manage_users_tool
suffix = uuid.uuid4().hex[:8]
users = [
    {'name': f'pytest_a{suffix}', 'email': f'a{suffix}@example.org'},
    {'name': f'pytest_b{suffix}', 'email': f'a{suffix}@example.org'},
]
print(asyncio.run(manage_users_tool({'action': 'create', 'users': users}))[0].text)
"
```

The second entry reuses the first's e-mail address. If Gramps requires unique
e-mails, the first succeeds and the second fails, which is exactly the shape
needed. Delete any account created, through `ApiCalls.DELETE_USER` on the
client, before continuing.

If that does not produce a failure, try another route of your choosing and
report what you tried.

- [ ] **Step 3a: If the case is reachable, write the test**

Add a test that creates such a batch, asserts the successful entry's row and
its password are present in the output alongside the failure, and cleans up
every account it created in a `finally` block. Then correct the docstring at
264-267 to describe only what its own test proves, and let the new test carry
the mid-batch claim.

Revert-check it: remove the row-preserving behaviour, confirm the new test
fails, restore it, confirm it passes.

- [ ] **Step 3b: If the case is not reachable without a mock, remove the claim**

Delete the sentence claiming the test proves the mid-batch fix. Replace it with
one stating what the test actually covers — that a duplicate name is skipped
rather than failing the batch. Add a brief note that the mid-batch-abort path
has no automated coverage, and why.

This is an acceptable and expected outcome. Do not write a test that appears to
cover the case in order to keep the sentence.

- [ ] **Step 4: Confirm the tree is clean**

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.tools.user_tools import manage_users_tool
print(asyncio.run(manage_users_tool({'action': 'list'}))[0].text)
"
```

Expected: exactly the two real accounts, neither starting with `pytest_`.

- [ ] **Step 5: Commit**

```bash
rtk git add tests/test_user_tools.py
uv run git commit -m "test: make the mid-batch coverage claim match what the test proves"
```

---

### Task 3: Cover the note loop and its null-`text` guard

Lot 1 guarded both the media and note loops in `person_detail_handler` and
added a guard for a `text` field that is present but null. Only the media path
got a test.

**Files:**
- Modify: `tests/test_person_detail_resilience.py`

**Interfaces:**
- Consumes: `format_person_detail` from `src.gramps_mcp.handlers.person_detail_handler`.
- Produces: nothing.

- [ ] **Step 1: Read the existing media test**

`tests/test_person_detail_resilience.py` already creates a person carrying a
fabricated media handle that resolves to nothing, and asserts the detail
degrades to a placeholder line rather than being lost. The note case has the
same shape: a person carrying a `note_list` entry that is a handle no note has.

- [ ] **Step 2: Write the failing test**

Add a test creating a person whose `note_list` holds a fabricated handle,
asserting the detail still renders — the surname is present, the output does
not read as an error — and that the degraded note line naming the handle
appears. Follow the media test's structure exactly, including cleanup of the
person in a `finally` block.

Read the guard in `src/gramps_mcp/handlers/person_detail_handler.py` first to
get the exact placeholder string it emits, and assert that string rather than
inventing one.

- [ ] **Step 3: Run it to verify it fails**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_person_detail_resilience.py -v`

Expected: FAIL only if you first remove the note guard — this test covers
already-working behaviour, so run the revert-check now rather than after:
remove the `try/except` around the note loop, confirm the new test fails,
restore it, confirm it passes. Report both observations.

- [ ] **Step 4: Cover the null-`text` case**

Determine whether a note with a null `text` can be created through this client.
`NoteSaveParams` declares `text` as `str | dict`, so passing `None` is rejected
before any request — the same wall an earlier lot hit.

If it cannot be created, say so in your report and do not write the test. The
guard remains justified by data created outside this server, and that reasoning
belongs in a comment beside the guard if it is not already there.

- [ ] **Step 5: Confirm the tree is clean**

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.tools.search_basic import find_anything_tool
print(asyncio.run(find_anything_tool({'query': 'Pytest'}))[0].text[:300])
"
```

Expected: no `Pytest*` object.

- [ ] **Step 6: Commit**

```bash
rtk git add tests/test_person_detail_resilience.py
uv run git commit -m "test: cover the dangling note reference in person detail"
```

---

### Task 4: Make `test_handle_still_works` test a handle

`tests/test_get_type_resolution.py:56-58` calls `get_type_tool` with a
`gramps_id`, identically to the test above it and with a weaker assertion. The
handle path it names is untested, as are the fallthrough cases.

**Files:**
- Modify: `tests/test_get_type_resolution.py:56-58`

**Interfaces:**
- Consumes: `get_type_tool` from `src.gramps_mcp.tools.search_details`.
- Produces: nothing.

- [ ] **Step 1: Obtain a real handle**

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.tools.search_details import _resolve_gramps_id
print(asyncio.run(_resolve_gramps_id('person', 'I0076')))
"
```

Record the handle. The test should fetch it this way rather than hardcoding it,
so it survives a tree rebuild.

- [ ] **Step 2: Rewrite the test**

Replace the body so it resolves `I0076` to a handle, then calls
`get_type_tool({"type": "person", "handle": <that handle>})` and asserts the
record comes back — the identifier appears in the output and it does not read
as an error.

- [ ] **Step 3: Add the fallthrough cases**

Add two tests: `get_type_tool({"type": "person"})` with neither handle nor
identifier, and `get_type_tool({"type": "banana", "gramps_id": "I0076"})` with
an unsupported type. Both must produce a message naming what was wrong, and
neither may contain the string "not yet implemented".

- [ ] **Step 4: Run and revert-check**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_get_type_resolution.py -v`

Then verify the rewritten handle test discriminates: temporarily break the
handle branch of `get_type_tool` — for instance by making it ignore the
supplied handle — confirm the test fails, restore it, confirm it passes. Report
both observations.

- [ ] **Step 5: Commit**

```bash
rtk git add tests/test_get_type_resolution.py
uv run git commit -m "test: exercise the handle path and the fallthrough cases"
```

---

### Task 5: Escape the identifier instead of refusing it

`tools/search_details.py:130-134` rejects an identifier containing a double
quote or backslash. That closes a real hole — a crafted identifier previously
resolved to an unrelated record — but refusing is blunt for a value that could
legitimately contain either character.

**Files:**
- Modify: `src/gramps_mcp/tools/search_details.py:121-134` and the filter at :141
- Modify: `tests/test_get_type_resolution.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: nothing.

- [ ] **Step 1: Verify escaping works before changing anything**

GQL string literals follow GraphQL rules: a literal double quote is `\"` and a
literal backslash is `\\`. Confirm the server honours that:

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
async def m():
    c = GrampsWebAPIClient(); t = get_settings().gramps_tree_id
    for raw, gql in [
        ('I0076', 'gramps_id=\"I0076\"'),
        ('x\" or gramps_id!=\"', 'gramps_id=\"x\\\\\" or gramps_id!=\\\\\"\"'),
    ]:
        try:
            r = await c.make_api_call(api_call=ApiCalls.GET_PEOPLE, params={'gql': gql, 'pagesize': 1}, tree_id=t)
            print(repr(raw), '->', len(r), 'result(s)')
        except Exception as e:
            print(repr(raw), '-> error:', str(e)[:120])
asyncio.run(m())
"
```

Expected: the plain identifier returns one result, and the escaped injection
returns zero — it is searched for literally and matches nothing.

**If the escaped form errors instead of returning zero results, stop.** Keep
the existing guard, record exactly what you observed, and report BLOCKED for
this task. The spec anticipates this: replacing a correct-but-narrow guard with
something that does not work would be worse.

- [ ] **Step 2: Write the failing test**

Add a test asserting that `get_type_tool` with the crafted identifier
`x" or gramps_id!="` reports that no record was found, naming the identifier,
rather than raising or returning someone else's record. Against the current
code this fails, because the guard raises instead.

Keep the existing test that a malformed identifier is handled, adjusting its
expectation to the new behaviour if it asserted the refusal.

- [ ] **Step 3: Replace the guard with escaping**

Delete the guard block at lines 130-134 and the `# Reason:` comment above it
that explains the refusal. In its place, escape the identifier where the filter
is built. The current line reads:

```python
    params = BaseGetMultipleParams(  # type: ignore[call-arg]
        gql=f'gramps_id="{gramps_id}"', pagesize=1
    )
```

Introduce the escaping just above it, with a comment explaining why the order
matters:

```python
    # Reason: escape for the GQL string literal - the backslash first, so the
    # backslashes introduced when escaping quotes are not escaped again.
    escaped = gramps_id.replace("\\", "\\\\").replace('"', '\\"')
    params = BaseGetMultipleParams(  # type: ignore[call-arg]
        gql=f'gramps_id="{escaped}"', pagesize=1
    )
```

Keep the `type: ignore` comment and its explanation exactly as they are.

- [ ] **Step 4: Run and revert-check**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_get_type_resolution.py -v`

Then revert only the escaping — restore the raw interpolation without the guard
— and confirm the crafted-identifier test fails by resolving to a real record.
That is the exact hole this closes, so seeing it reopen is the proof. Restore
and confirm. Report both observations.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/tools/search_details.py tests/test_get_type_resolution.py
uv run git commit -m "fix: escape the identifier for the GQL filter instead of refusing it"
```

---

### Task 6: Three small fixes, three commits

Each is independent and a few lines. They share a task because none warrants
its own review cycle, but each gets its own commit.

**Files:**
- Modify: `src/gramps_mcp/client.py:116-129` and `:333`
- Modify: `src/gramps_mcp/handlers/family_detail_handler.py:217`
- Modify: `tests/test_http_error_detail.py`

**Interfaces:**
- Consumes: `MAX_ERROR_DETAIL` from `src.gramps_mcp.client`, defined at line 42.
- Produces: nothing.

#### 6a: Bound the non-JSON 2xx body

`client.py:123` returns `{"error": "Invalid JSON response", "raw_content":
response.text}` with no limit — the one route by which more than the intended
fragment of a server response reaches the caller. Lot 3 bounded every other one
at `MAX_ERROR_DETAIL` because Gramps can echo the submitted payload, which
holds genealogy data about living people.

- [ ] **Step 6a.1: Write the failing test**

Add to `tests/test_http_error_detail.py` a test that calls the JSON-parsing
path with an oversized non-JSON body and asserts the returned `raw_content` is
bounded by `MAX_ERROR_DETAIL` and carries the truncation marker. Read how the
existing tests in that file construct real `httpx` objects and follow the same
shape — this file needs no server.

If the parsing path cannot be reached without a request, exercise it through
`_make_request` against a URL that returns non-JSON, and say in your report how
you produced it.

- [ ] **Step 6a.2: Run it to verify it fails**

Run: `uv run pytest tests/test_http_error_detail.py -v`
Expected: FAIL — the body comes back whole.

- [ ] **Step 6a.3: Implement**

Truncate `response.text` to `MAX_ERROR_DETAIL` with the same `"..."` marker the
error path uses, and add a `# Reason:` comment saying why the bound exists,
matching the one at line 42.

- [ ] **Step 6a.4: Run, revert-check, commit**

Run the file again, expect PASS. Then remove the truncation, confirm the test
fails, restore it, confirm it passes, and report both.

```bash
rtk git add src/gramps_mcp/client.py tests/test_http_error_detail.py
uv run git commit -m "fix: bound the non-JSON response body like every other path"
```

#### 6b: Route `upload_media_file` through the error formatting

`client.py:333` calls `response.raise_for_status()` directly, so a failed media
upload raises a raw `httpx.HTTPStatusError` that never reaches
`_format_http_error`. Media upload failures gain none of lot 3's improvement
and their message has a different shape from every other tool's.

- [ ] **Step 6b.1: Implement**

Wrap the call so a failure produces a `GrampsAPIError` carrying the formatted
message, matching what `_make_request` does at its own `raise_for_status`. Read
that handler first and mirror it rather than inventing a second form.

- [ ] **Step 6b.2: Verify**

Exercise it against a URL that will fail — for example by calling
`upload_media_file` with an empty body, or against an unreachable host — and
confirm the raised error is a `GrampsAPIError` whose message has the `Error`
shape rather than httpx's. Record the before and after output in your report.

If no automated test can produce the failure without a mock, say so and rely on
the recorded manual evidence, as an earlier lot did for the same class of path.

- [ ] **Step 6b.3: Commit**

```bash
rtk git add src/gramps_mcp/client.py
uv run git commit -m "fix: format media upload failures like every other error"
```

#### 6c: Align the twin handler's null-`text` treatment

`handlers/family_detail_handler.py:217` still does
`note_data.get("text", {}).get("string", "")`, the form lot 2 replaced in
`person_detail_handler` because it raises when the key is present but null. The
family view cannot crash — its own `except` catches it — but it silently
degrades a note to a placeholder where the person view renders it.

- [ ] **Step 6c.1: Implement**

Change it to the form its twin uses:

```python
                note_full_text = (note_data.get("text") or {}).get("string", "") or ""
```

Read `person_detail_handler` first and copy its exact expression, so the twins
match character for character.

- [ ] **Step 6c.2: Verify and commit**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_person_detail_resilience.py tests/test_search_details.py -q`
Expected: no new failures.

State in your report that this path has no dedicated test because a null-`text`
note cannot be created through this client, and that the change is justified by
parity with the tested twin.

```bash
rtk git add src/gramps_mcp/handlers/family_detail_handler.py
uv run git commit -m "fix: treat a null note text the same way in the family view"
```

---

### Task 7: Verification and pull request

- [ ] **Step 1: Run the whole suite**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest -q`
Expected: the new tests pass. Categorise every failure as new-from-this-branch or pre-existing, and check rather than assume — `git show main:<path>` reads a file as it is on main. A regression reported as pre-existing is the worst possible outcome of this task; it happened twice in this series.

Known pre-existing failures, not yours: three in `tests/test_parameter_alignment.py` about `media_path`, three in `tests/test_server.py`, and others in `test_analysis.py`, `test_data_management.py` and `test_search_basic.py` concerning live-tree state, media MIME types and the `tree_stats` permission gap.

- [ ] **Step 2: Confirm the marker still selects correctly**

Run: `GRAMPS_API_URL=http://127.0.0.1:9 uv run pytest -m "not integration" -q`
Expected: all selected tests pass against a dead endpoint. Any test added by this lot that needs the server must be in a marked module.

- [ ] **Step 3: Type check, lint and format**

Run: `uv run mypy src/gramps_mcp --ignore-missing-imports`
Run: `uv run ruff format src/gramps_mcp tests && uv run ruff check src/gramps_mcp tests`
Expected: no new errors; all checks pass.

- [ ] **Step 4: Confirm the tree is clean**

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.tools.search_basic import find_anything_tool
print(asyncio.run(find_anything_tool({'query': 'Pytest'}))[0].text[:400])
"
```

Expected: no `Pytest*` object. Also list the users and confirm no `pytest_*` account survives from Task 2.

- [ ] **Step 5: Commit any formatting changes**

```bash
rtk git add -A
uv run git commit -m "chore: format and lint quality lot 4"
```

Skip if ruff changed nothing. Do not create an empty commit.

- [ ] **Step 6: Push and open the pull request**

```bash
rtk git push -u origin fix/quality-lot4-test-debt
rtk gh pr create --repo fjacquet/gramps-mcp --title "fix: quality lot 4 - test debt and leftovers" --body "$(cat <<'BODY'
Closes what the three previous quality lots left behind. Last lot of the series.

- The `integration` marker is now applied, so `-m "not integration"` selects the server-free suite. `CLAUDE.md` derives the offline set from the marker instead of listing files by hand, a list that had diverged twice.
- A docstring claiming to prove the mid-batch-abort fix now matches what its test actually covers.
- The dangling note reference in the person detail is covered, alongside the media case that already was.
- `test_handle_still_works` exercises a handle, and the fallthrough cases have tests.
- The `gramps_id` is escaped for the GQL filter rather than refused, so an identifier containing a quote is searched for literally instead of rejected.
- The non-JSON response body is bounded like every other path.
- Media upload failures are formatted like every other error.
- The family view treats a null note text the way the person view does.

Behaviour changes: an identifier containing a quote is no longer refused, and a malformed non-JSON response body is truncated.

Spec: `docs/superpowers/specs/2026-08-13-quality-lot4-test-debt-design.md`

Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01PAZLxVasEXVDbriMRvGmDE
BODY
)"
```

**Do not merge, tag, or release.** This lot ends the series and a release follows, but both are the owner's action, and the merge uses a merge commit rather than a squash.

---

## Self-Review

**Spec coverage:** All nine spec sections have a task — the docstring (Task 2), the marker (Task 1), the note loop (Task 3), the handle path (Task 4), the `CLAUDE.md` list (Task 1, since it becomes derivable only once the marker exists), GQL escaping (Task 5), the unbounded body (6a), the upload bypass (6b), the twin handler (6c). The spec's testing requirements — revert-check per half, and the licence to remove an unprovable claim — are in Global Constraints and restated where they bite.

**Placeholders:** None. Task 2 branches on an empirical result rather than deferring a decision, and both branches are written out. Task 5 has an explicit stop condition with instructions for the blocked case. Task 6b permits manual evidence where an automated test needs a mock, and says what to record.

**Type consistency:** `MAX_ERROR_DETAIL` is defined at `client.py:42` and consumed in 6a. `_resolve_gramps_id` is used in Task 4 Step 1 with the signature it already has. `pytestmark` is standard pytest. No task references a name another task defines.

**Ordering note:** Task 1 should run first, because later tasks add tests whose modules may need the marker. Tasks 2 to 6 are independent of each other.
