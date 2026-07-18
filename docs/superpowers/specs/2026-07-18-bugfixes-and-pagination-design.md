# Bug Fixes and Search Pagination — Design

## Context

A triage of 10 upstream `cabout-me/gramps-mcp` issues against this fork
(v1.3.0) found 4 real, reproducible defects in code that still exists in
this fork, plus one real gap behind a "pagination" feature request that
turned out to be two separate silent bugs. `#4` (notes+GQL 500) and `#32`
(vague tree_stats error) are excluded: `#4` is a server-side Gramps Web bug,
not ours; `#32` is not reproducible from the information available.

The BFS-traversal request for `get_ancestors`/`get_descendants` (#6) and the
doc/naming requests (#23, #7, #8) are explicitly out of scope for this
round — #6 is an architecture change (replace vs. supplement the current
HTML-report-based tools) that deserves its own design pass, not a
bugfix batch.

## Bugs to fix

### 1. Note text StyledText slice crash (upstream #29/#30)

`person_detail_handler.py:284` and `family_detail_handler.py:217` both do:

```python
note_text = note_data.get("text", "")[:50]
```

The live API returns `text` as a StyledText dict
(`{"_class": "StyledText", "string": "..."}`), not a string — matching how
`note_handler.py:57` already reads it (`note_data.get("text", {}).get("string")`).
Slicing a dict raises `unhashable type: slice`. In `person_detail_handler.py`
this is unguarded and aborts the entire `get_type` (person) response, not
just the notes section; in `family_detail_handler.py` it's wrapped in a
per-note `try/except` so it degrades to `- Note (handle)` instead of
crashing, but still never shows real note text.

**Fix:** read `note_data.get("text", {}).get("string", "")` in both files,
matching the existing correct pattern in `note_handler.py`.

### 2. create_note double-validation crash over FastMCP transport (#27)

`NoteSaveParams.model_dump()` (`note_params.py:70`) overrides the base dump
to turn `text: str` into a StyledText dict. The real request path is:

1. `server.py`'s `create_handler` calls `arguments.model_dump()` on the
   `NoteSaveParams` schema instance built from the raw tool call — this
   already runs the override, turning `text` into a dict.
2. `create_note_tool` → `_handle_crud_operation` reconstructs
   `NoteSaveParams(**params)` from that dict. `text` is now a dict, but the
   field is typed `str` — Pydantic rejects it with a validation error.

This only breaks over the real FastMCP/HTTP transport (`server.py`'s
generic `arguments.model_dump()` step); the existing test in
`test_data_management.py::TestCreateNoteTool` calls `create_note_tool`
directly with a hand-built dict and never exercises this path, which is why
it wasn't caught earlier — same class of gap as the FastMCP
None-vs-absent bug found in the extended-api-tools final review.

**Fix:** widen `NoteSaveParams.text` to `str | dict[str, Any]` and make the
override idempotent (it already checks `isinstance(data["text"], str)`
before wrapping, so a dict passed back in is left alone). This makes
`model_dump()` safe to call twice on the same instance, which is what the
transport path actually does — no change to `server.py`'s generic
transport, no special-casing in `client.py`.

### 3. create_family ignores child_handles (#24)

`FamilySaveParams.child_handles: Optional[List[str]]` (`family_params.py:42`)
has no equivalent field in the real Gramps Web `Family` schema
(`grampsweb-docs/apispec.yaml:8055-8059`), which expects
`child_ref_list: [{"ref": <handle>, ...}]`. There is no translation
anywhere, so the field is simply dropped by the API.

**Fix:** add `child_ref_list: Optional[List[dict]]` to `FamilySaveParams`
(same shape as the existing `event_ref_list`), and in
`create_family_tool` (`tools/data_management.py`), after validating params,
translate `child_handles` into `child_ref_list` entries
(`{"ref": h} for h in params.child_handles`) and clear `child_handles` to
`None` so it isn't also sent to the API as an unrecognized field. Kept
local to `create_family_tool` — no changes to `client.py` or shared
parameter-mapping code, consistent with this project's established pattern
for tool-facing-vs-API-shape mismatches.

## Pagination gaps (#5)

Investigation found the "add pagination" request corresponds to two
concrete, separate bugs in the two *universal* tools actually registered in
`TOOL_REGISTRY` (`find_type`, `find_anything`) — the entity-specific search
tools they delegate to (`find_person_tool` etc.) already support
`page`/`pagesize` via `BaseGetMultipleParams` and are not affected.

### find_type: no page parameter at all

`SimpleFindParams` (`models/parameters/simple_params.py:48`) has
`max_results` but no `page` field, and `find_type_tool`
(`tools/search_basic.py:369`) only ever builds
`{"gql": gql, "pagesize": max_results}` — there is no way to request page 2
of results through this tool.

**Fix:** add `page: Optional[int]` to `SimpleFindParams`, and include
`"page": page` in the params dict `find_type_tool` builds.

### find_anything: max_results silently dropped, pagination never worked

`find_anything_tool` (`tools/search_basic.py:392`) does
`params = SearchParams(**arguments)` where `arguments` comes from
`SimpleSearchParams` (`query`, `max_results`). `SearchParams` has no
`max_results` field (it has `page`/`pagesize` instead), and Pydantic
silently drops unknown kwargs by default — so `max_results` has never had
any effect, `params.pagesize` is always `None`, and the tool always returns
whatever page size the raw Gramps Web API defaults to, with no way to
request a different page.

**Fix:** add `page: Optional[int]` to `SimpleSearchParams` alongside the
existing `max_results`, and in `find_anything_tool` build the `SearchParams`
explicitly (`SearchParams(query=arguments["query"], pagesize=arguments.get("max_results"), page=arguments.get("page"))`)
instead of splatting the raw dict, so both fields actually reach the API.

## Testing

TDD against the live Gramps Web server (`GRAMPS_API_URL=http://localhost:80`),
per project convention — no mocks, generic IDs only, no real
person/family/place names in test assertions or commits.

- Bug 1: new test exercising `format_person_detail`/`format_family_detail`
  against a person/family with an attached note (created within the test),
  asserting no crash and that real note text (not a placeholder) appears.
- Bug 2: new regression test in `TestCreateNoteTool` that reproduces the
  exact FastMCP path — build `NoteSaveParams(text=..., type=...)`, call
  `.model_dump()` on it (mirroring `server.py`'s `create_handler`), then
  pass that dict to `create_note_tool`, asserting success.
- Bug 3: extend `TestCreateFamilyTool` to create/update a family with
  `child_handles=[<a person handle created earlier in the test>]` and
  verify the child appears in the family's children when read back.
- Pagination: extend `tests/test_search_basic.py` with tests that request
  `page=2` (or a `max_results` small enough to force multiple pages) via
  `find_type` and `find_anything` and confirm the request round-trips
  without error and (where the tree has enough matching records) returns a
  distinct result set from page 1.

## Out of scope (explicitly deferred)

- **#6** BFS traversal for `get_ancestors`/`get_descendants` — architecture
  decision (replace the current HTML-report tools vs. add a new
  structured-output tool), needs its own design pass.
- **#23, #7, #8** — documentation/naming requests, no code defect.
- **#32** — not reproducible from available information.
- **#4** — confirmed to be a Gramps Web server-side bug, not fixable here.
