# BFS traversal for get_ancestors / get_descendants

Date: 2026-08-14
Upstream issue: cabout-me/gramps-mcp#6
Status: approved, not yet implemented

## Problem

`get_ancestors_tool` and `get_descendants_tool` (`src/gramps_mcp/tools/analysis.py`)
do not read the family graph. They ask Gramps Web to render a full HTML report
(`ancestors_report` / `descend_report`), poll a Celery task with exponential
backoff until it completes, download the HTML file, and run it through
`html_to_markdown`.

That costs a server-side report job and several round trips before a single
name is known, and it returns report layout - headings, numbering schemes,
place hierarchies - that an LLM pays for in tokens and does not need.

## Solution

Walk the graph directly, breadth-first, one level at a time, and format the
result ourselves.

A live probe against the production tree confirms the walk needs exactly one
request per person. `GET /people/?gql=...&profile=self&extend=parent_family_list`
returns, in one response:

- `profile`: `name_display`, `gramps_id`, `sex`, and `birth`/`death` objects
  carrying `date` and `place_name`
- `extended.parent_families`: the full family objects, including
  `father_handle`, `mother_handle` and `child_ref_list`

So no separate family fetch is needed. Descendants use `extend=family_list`
and follow `child_ref_list[].ref` instead.

GQL has no `in` or `or` operator (only `=`, `!=`, `~`, comparisons, and the
`any`/`all` list qualifiers), so a whole generation cannot be fetched in one
query. Concurrency within a level is what buys the speed instead.

## Architecture

### `src/gramps_mcp/traversal.py` (new)

Pure graph logic. Knows dicts and handles; formats nothing.

```python
async def walk_ancestors(client, tree_id, start_handle, max_generations, visit_cap) -> TraversalResult
async def walk_descendants(client, tree_id, start_handle, max_generations, visit_cap) -> TraversalResult
```

`TraversalResult` is a dataclass:

| field | meaning |
|-------|---------|
| `nodes` | `dict[handle, profile]` for every person reached |
| `edges` | `dict[handle, list[handle]]`, successors in walk direction: parents for an ancestor walk, children for a descendant walk |
| `root` | handle of the subject |
| `truncated_by_cap` | the visit cap stopped the walk |
| `unexplored` | number of handles queued but never fetched |
| `revisited` | handles reached more than once (cycles, cousin marriages) |
| `failed` | `dict[handle, str]` for nodes whose fetch raised |

All fetching goes through one private helper:

```python
async def _fetch_level(client, tree_id, handles, extend_field) -> dict[handle, dict]
```

It issues the level's requests with `asyncio.gather(..., return_exceptions=True)`
behind an `asyncio.Semaphore(8)`.

### `src/gramps_mcp/handlers/traversal_handler.py` (new)

Renders a `TraversalResult` to markdown. No I/O, fully testable offline.

### `src/gramps_mcp/tools/analysis.py` (modified)

Both tools shrink to: validate arguments, call `walk_*`, hand the result to the
handler. The report path is deleted from this module: `_wait_for_task_completion`,
the `ReportFileParams` calls, the task polling, and the `html_to_markdown` call.

`ReportFileParams`, the `ApiCalls` report entries and `html_to_markdown` itself
stay - they describe real API endpoints and cost nothing to keep.

## Output format

```markdown
# Ancestors of JACQUET, Frederic (I0001) - 3 generations, 6 people

- JACQUET, Frederic (I0001), b. 10 Aug 1976 Bourges
  - JACQUET, Yvan (I0042), b. 1948 Lyon, d. 2011
    - JACQUET, Joseph (I0107), b. 1912
    - RIPPERT, Marie (I0108), b. 1915, d. 1998
  - MARIAUD, Odile (I0129)
```

Rules:

- one line per person, indented two spaces per generation
- `NAME, Given (gramps_id)` always; the gramps_id is what lets the assistant
  chain a `get_type` call on any line
- `b.` / `d.` only when the date exists; place reduced to `place_name`, never
  the full hierarchy - token economy is the point of the issue
- a person already shown elsewhere in the tree is rendered
  `NAME, Given (I0123) [already listed above]` and not expanded again

## Error handling and limits

- Unknown `gramps_id`: the GQL lookup returns an empty list, the tool returns
  `Error: no person found with gramps_id X`. Matches today's behaviour, which
  the existing live tests assert on.
- Visit cap: 500 people. On reaching it the walk stops and the output ends with
  `**Truncated**: visit cap of 500 reached, N branches unexplored. Lower
  max_generations or start from a nearer ancestor.` The cap is never silent.
- `max_generations` keeps its default of 5 and gains an upper bound of 20 in
  `AncestorsParams` / `DescendantsParams`, which have no bound today.
- A failed fetch for one person does not abort the walk. That node renders as
  `(handle 103bce...) [unavailable: <reason>]` - the handle, not the gramps_id,
  because the gramps_id only arrives with the fetch that just failed; all the
  walk has is the handle it read out of the family object. The branch stops
  there. On a 500-person walk a single server error must not discard 499
  successful fetches.
- Errors still surface through the existing `_format_error_response`.

## Testing

Written test-first, in this order.

1. `tests/test_traversal_handler.py` - offline, pure. Hand-built
   `TraversalResult` objects in, markdown out. Covers indentation per
   generation, omission of absent dates, the already-listed marker, the
   unavailable marker, and the truncation footer.
2. `tests/test_traversal.py` - offline. Patches `GrampsWebAPIClient._make_request`
   (the transport seam, as `tests/test_client_merge.py` does) over a synthetic
   tree. Covers: depth respected, cycle not re-expanded, cap triggered, one
   node failing in isolation. Assertions read the returned `TraversalResult`,
   never the mock's call arguments.
3. `tests/test_analysis.py` - live, `integration`-marked, extended: the
   ancestry of `I0001` contains the known father and mother, and
   `max_generations=1` returns strictly fewer lines than `max_generations=3`.

### Performance gate

The issue claims speed. Before the report path is deleted, both
implementations are timed against the same subject on the live tree. If BFS is
not measurably faster, the design has failed and the report path stays. The
measurement happens first; the deletion is a separate commit that cites it.

## Out of scope

- Flattening the `arguments` wrapper in the HTTP inputSchema (upstream #23) -
  a client contract change, tracked separately.
- Any change to `get_relationship`, `get_timeline`, or `check_living`.
