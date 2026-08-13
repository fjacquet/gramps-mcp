# Design: quality improvements, lot 4 — test debt and leftovers

Date: 2026-08-13
Status: approved, not yet implemented
Branch: `fix/quality-lot4-test-debt`

## Context

Final lot of the quality work arising from a full review of `src/gramps_mcp`.
Lot 1 (correctness and stability) merged as pull request #8, lot 2 (data
fidelity) as #9, lot 3 (ergonomics) as #10.

The original decomposition planned a fourth lot for test debt and a fifth for
the code defects those lots deferred. Both turned out small enough that
splitting them would cost more ceremony than it bought, so they are merged
here. This is the last lot; the release tag follows its merge.

The theme is closing what the three previous lots left behind: coverage they
deferred, one claim of coverage that was never true, and four small code
defects each of which was found while fixing something else.

## Scope

Seven items, all known and bounded. No exploratory work.

### Test debt

| Item | Location |
|---|---|
| A docstring claiming coverage the test does not provide | `tests/test_user_tools.py:264-267` |
| The `integration` marker is declared but used by no test | `pytest.ini:10`, test modules |
| The note loop and its null-`text` guard are untested | `handlers/person_detail_handler.py` |
| `test_handle_still_works` tests no handle | `tests/test_get_type_resolution.py:56-58` |
| `CLAUDE.md` lists offline-safe test files by hand | `CLAUDE.md:44-46` |

### Code defects

| Item | Location |
|---|---|
| `gramps_id` is interpolated into a GQL filter unescaped | `tools/search_details.py:141` |
| A 2xx response with a non-JSON body returns it unbounded | `client.py:123` |
| `upload_media_file` bypasses the error formatting | `client.py:333` |
| A twin handler still treats a null `text` the old way | `handlers/family_detail_handler.py:217` |

## The items

### 1. A docstring claims coverage that does not exist

`tests/test_user_tools.py:264-267` states that the test "also proves the fix
for the mid-batch-abort finding". It does not. The test drives a 409, which the
code caught before that fix existed, so it would pass with the fix reverted.
The final review of that lot established this and it was never corrected.

The fix under it is real and was verified by other means. What is missing is a
test that fails without it.

**Decision: attempt the test first; delete the sentence if the case cannot be
reached without a mock.** A batch where one entry fails for a reason other than
"already exists" is what would exercise it. If no such failure can be produced
against a live server without stubbing, the honest outcome is to remove the
claim and say so, rather than write something that only appears to cover it.

### 2. The `integration` marker is declared but unused

`pytest.ini:10` declares the marker and documents `-m "not integration"` as the
way to deselect server-dependent tests. No test carries it, so that command
selects everything and the documented escape hatch does nothing.

Fix: apply `pytestmark = pytest.mark.integration` at module level to every test
file that needs the live server. Leave `uv run pytest` running everything —
a default that silently skipped the server tests would let someone read a green
result as proof the server path works.

### 3. The note loop and its null-`text` guard are untested

Lot 1 guarded the media and note loops in `person_detail_handler` and added a
null-`text` guard, but only the media path got a test. The note path and the
null guard have no coverage. The media test resolves a fabricated handle, and
the same shape works for a note.

### 4. `test_handle_still_works` tests no handle

`tests/test_get_type_resolution.py:56-58` calls `get_type_tool` with a
`gramps_id`, identically to the test above it, with a weaker assertion. Its
name claims the handle path is covered; that path is untested, as is the
fallthrough for an unsupported type or missing input.

Fix: make it pass a handle, and add the fallthrough cases.

### 5. `CLAUDE.md` lists offline-safe files by hand

`CLAUDE.md:44-46` enumerates the test files that run without a server. That
list already diverged once — lot 3 added a fifth offline file and the list was
only corrected because a reviewer noticed. Once item 2 lands, the marker makes
the list derivable.

Fix: replace the enumeration with the marker command.

### 6. `gramps_id` is interpolated into a GQL filter unescaped

`tools/search_details.py:141` builds `gql=f'gramps_id="{gramps_id}"'`. Lot 3
added a guard rejecting an identifier containing a double quote or backslash,
which closes the exploit — a crafted identifier previously resolved to a real,
unrelated person whose record was then presented as the answer — but rejecting
is a blunt instrument for a value that could legitimately contain either
character in some other genealogy system's identifiers.

**Decision: escape rather than reject.** Escape the double quote and the
backslash per the GQL string-literal rules, and drop the guard. Keep a test for
the crafted-identifier case, asserting it now resolves to nothing rather than
to a stranger.

If escaping proves not to work as documented against the live server, keep the
guard and record what was observed. The guard is correct-but-narrow; replacing
it with something that does not work would be worse.

### 7. A 2xx response with a non-JSON body returns it unbounded

`client.py:123` returns `{"error": "Invalid JSON response", "raw_content":
response.text}` with no limit. This is the one route by which more than the
intended fragment of a server response reaches the caller, and lot 3 bounded
every other one at 300 characters for a stated reason: Gramps can echo the
submitted payload, which holds genealogy data about living people.

Fix: apply the same bound and the same constant.

### 8. `upload_media_file` bypasses the error formatting

`client.py:333` calls `response.raise_for_status()` outside `_make_request`, so
a failed media upload raises a raw `httpx.HTTPStatusError` that never passes
through `_format_http_error`. Media upload failures therefore gain none of lot
3's improvement, and their message has a different shape from every other
tool's.

Fix: route it through the same formatting.

### 9. A twin handler still treats a null `text` the old way

`handlers/family_detail_handler.py:217` does
`note_data.get("text", {}).get("string", "")`, the form lot 2 replaced in its
twin because it raises when the key is present but null. The family view cannot
crash — its own `except` catches it — but it silently degrades a note to a
placeholder where the person view renders it.

Fix: apply the same treatment, so the twins agree.

## Testing

The project forbids mocks, fixtures and test clients. Each item that changes
behaviour gets a test, written first and observed failing.

**Every test must pass a revert-check before its commit: remove the fix, run
the test, confirm it fails, restore the fix, confirm it passes — and revert
each independent half separately.** Five times across the previous three lots a
fix shipped with a test that claimed to cover it and did not; once, reverting
two halves together credited two detectors where there was one, and the defect
that slipped through was a Critical found only at the final review. The
observations go in the implementer's report.

Where a case genuinely cannot be reached without a mock, say so and remove the
claim rather than writing a test that appears to cover it. That outcome is
acceptable and expected for item 1.

Live tests need a URL override from the macOS host, because `.env` targets
`host.docker.internal`, which only resolves inside the container:

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest ...
```

## Integration

Branch `fix/quality-lot4-test-debt`. One atomic commit per item. One pull
request, merged with a merge commit, never squashed.

**This lot ends the series, so the release tag follows its merge** — the first
since v1.6.0, covering all four lots.

## Accepted risk

Lower than the previous lots. Nothing here changes what a valid call does,
with two exceptions worth stating.

Replacing the identifier guard with escaping means an identifier containing a
quote stops being refused and starts being searched for literally. That is the
correct behaviour, but it is a change: a caller who relied on the refusal as a
signal will now get an empty result instead of an error.

Bounding the non-JSON 2xx body truncates a payload that was previously returned
whole. Any caller depending on the full text of a malformed response will see
less. Given the path exists to report a parsing failure, that is a reasonable
trade for not carrying unbounded personal data back to the model.

Tests that write to the tree write to a real genealogy database. As in the
earlier lots, a run killed outright can leave a `Pytest`-prefixed object behind.
