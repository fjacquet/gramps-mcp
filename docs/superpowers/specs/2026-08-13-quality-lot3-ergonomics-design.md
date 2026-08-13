# Design: quality improvements, lot 3 — ergonomics

Date: 2026-08-13
Status: approved, not yet implemented
Branch: `fix/quality-lot3-ergonomics`

## Context

Third of four lots of quality work arising from a full review of
`src/gramps_mcp`. Lot 1 (correctness and stability) merged as pull request #8,
lot 2 (data fidelity) as pull request #9. Lot 4 covers test debt. No release
tag is cut until all four have landed.

Lot 1 fixed crashes. Lot 2 fixed silent wrongness in stored and displayed data.
Lot 3 concerns defects where the server works but misinforms the caller: a
count that is not the count, an error that withholds the one fact needed to fix
it, a parameter silently overridden, and a lookup that reports the tool
unimplemented when a record simply does not exist.

None of these corrupts data. All of them waste the caller's time, and three of
them do it by stating something untrue.

## Scope

Four defects plus a documentation repair.

| Defect | File |
|---|---|
| The reported total is the page size, not the match count | `tools/search_basic.py:176` |
| The error body is discarded, taking the offending field name with it | `client.py:146` |
| `sort` overwrites the caller's choice and mutates the caller's dict | `tools/analysis.py:379` |
| The handle is scraped out of formatted prose by regular expression | `tools/search_details.py:113` |
| Facts established during lots 1 and 2 are absent from `CLAUDE.md` | `CLAUDE.md` |

Out of scope, belonging to lot 4: the deferred test-debt items from both prior
ledgers, including the untested note-loop guard, the tests that pass whether or
not their fix exists, and `make_api_call` silently swallowing unknown keyword
arguments through `**url_params`.

## The defects

### 1. The reported total is the page size

`_search_entities` reads `total_count = len(results)` when the API returns a
bare list, which the entity endpoints always do. So a search capped at twenty
results reports "Found 20 people" whether the tree holds twenty matches or five
hundred, and the caller has no way to tell that the set was truncated.

The real count is in the `X-Total-Count` response header, which this code never
requests. `make_api_call` already supports `with_headers=True`, returning
`(data, headers)`.

A second consequence: the branch at `search_basic.py:186` that would announce
"Found 500 (showing 20)" can never execute, because `actual_total` and
`displayed_count` are by construction equal. It is dead code that looks alive.

`find_anything_tool` already does this correctly, which makes the inconsistency
visible to anyone comparing the two tools' output.

Fix: request the headers, read `X-Total-Count`, fall back to the result length
when the header is absent.

### 2. The error body is discarded

`_format_http_error` maps each status code to a fixed sentence and drops the
response body. Gramps returns a 422 naming the field it rejected; the caller
sees only `Invalid data provided.` This is the dominant failure mode of the
create and update tools, and the one message that could resolve it is thrown
away.

**Decision: append an extracted, truncated detail to the generic message.**
Read the message field from the JSON body when there is one, fall back to the
raw text, and truncate. The generic sentence stays, because it categorises the
failure; the detail follows it.

Returning the whole body was considered and rejected: Gramps can echo the
submitted payload, which would put genealogy data belonging to living people
into an error string that travels back to the calling model. Truncation bounds
that exposure without losing the field name, which appears early in these
messages.

This applies to every status code, not only 422 — a 400 or a 409 carries the
same kind of detail.

### 3. `sort` overwrites the caller's choice

`get_recent_changes_tool` sets `arguments["sort"] = "-id"` unconditionally,
though `TransactionHistoryParams` documents `sort` as a caller-supplied field.
So `recent_changes(sort="id")` silently returns descending order. The
assignment also mutates the dictionary the caller passed in, which is a side
effect no tool in this project otherwise has.

Fix: apply `-id` only as a default when the caller supplied nothing, and work
on a copy.

### 4. The handle is scraped out of prose

`get_type_tool` resolves a `gramps_id` by calling `find_type_tool`, which
returns text formatted for display, then searching that text for the first
bracketed substring with a regular expression. Two consequences:

The resolution is coupled to a display format. Any change to how search results
are rendered silently breaks lookup by identifier, with no test able to notice
because the rendering change would be the "fix".

When the identifier does not exist there is no bracket to match, `handle` stays
`None`, both branches fall through, and the function returns the literal string
`get_type_tool not yet implemented`. So asking for a person who is not in the
tree reports that the tool does not exist.

**Decision: query the API and read the structured response.** Call the client
directly with a GQL filter on `gramps_id` and take the `handle` field from the
returned object. An identifier that matches nothing gets a message saying so,
naming the identifier. The "not yet implemented" string is removed: it is
reachable today and it is false.

### 5. `CLAUDE.md` has lost facts this session established

An uncommitted modification to `CLAUDE.md` was lost during lot 2, most likely
to a subagent's `git stash` cycle. Independently, three facts were established
during lots 1 and 2 that the file does not record, and each was rediscovered
more than once at the cost of a round trip:

- Live tests need `GRAMPS_API_URL=http://localhost:80` from the macOS host,
  because `.env` targets `host.docker.internal`, which only resolves inside the
  container.
- The `.env` account holds owner rights but not enough for `tree_stats`, which
  returns "Permission denied" regardless of the caller.
- Subagents must not use `git stash`; comparing against `main` is done with
  `git show main:<path>`.

Fix: add them. This is the cheapest item in the lot and prevents the most
repeated waste.

## Testing

The project forbids mocks, fixtures and test clients. Each defect gets one
test, written first and observed failing.

Three need no server, which makes them the strongest tests in the lot:

| Defect | Test |
|---|---|
| Error detail | `_format_http_error` against constructed `httpx.HTTPStatusError` objects carrying a JSON body, a text body, and an oversized body. |
| Sort default | The tool's argument handling with and without a caller-supplied `sort`, asserting the caller's dict is not mutated. |
| Missing identifier | `get_type` with an identifier that cannot exist, asserting the message names it and does not contain "not yet implemented". |

Two need the live server:

| Defect | Test |
|---|---|
| Result total | A search whose match count exceeds the page size must report both numbers. The tree holds 908 people, so a `pagesize` below that produces the condition. |
| Identifier resolution | `get_type` with a real `gramps_id` must return that record. |

Constructing an `httpx.HTTPStatusError` in a test is not mocking: it is the
real exception type from the real library, built with a real response object.
No behaviour is stubbed.

Live tests need a URL override from the macOS host:

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest ...
```

## Integration

Branch `fix/quality-lot3-ergonomics`. One atomic commit per defect, each
carrying its fix and its test, so a single correction can be read or reverted
alone. One pull request. Merged with a merge commit, never squashed. No release
tag: lot 4 follows, and the version is cut once at the end.

## Accepted risk

Lower than lot 2. Nothing here makes a previously valid call fail.

Two visible behaviour changes: `recent_changes(sort="id")` now returns
ascending order as documented rather than descending, so anything that relied
on the override without knowing it will see a different order; and search
results now report the true match count, so a caller that treated the displayed
number as the total will see a larger one.

One exposure change: error messages now carry a fragment of the server's
response. It is truncated and follows a generic sentence, but a 422 echoing a
submitted field value could surface a name or a date from the tree in an error
string. That is the trade for knowing which field was wrong.
