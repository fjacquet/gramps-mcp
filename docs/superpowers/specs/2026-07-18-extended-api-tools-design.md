# Extended API Tools: Relationships, Tags, Facts, Living Status, Timelines — Design

Date: 2026-07-18
Status: Approved

## Context

`src/gramps_mcp/models/parameters/` already contains fully-built Pydantic
models for several Gramps Web API domains that are never registered as MCP
tools: `relations_params.py`, `tag_params.py`, `facts_params.py`,
`living_params.py`, `timeline_params.py` (plus `PersonTimelineParams` in
`people_params.py` and `FamilyTimelineParams` in `family_params.py`). Only 16
of the domains the client already models are exposed in `TOOL_REGISTRY`
(`server.py`). This design wires up 5 of the unwired domains — relationship
calculation, tags, facts, living-status checking, and timelines — as 5 new
MCP tools. Reports, DNA-match parsing, and holidays are deliberately deferred
(higher complexity — reports involve async task polling and file downloads —
or lower genealogy value, per the user's explicit prioritization).

All endpoint shapes below are taken directly from the vendored OpenAPI spec
at `grampsweb-docs/apispec.yaml`, not from memory.

Decided with the user during brainstorming:
- **Tool granularity: consolidated (5 tools, not ~12).** Matches the
  project's existing convention (`create_person` handles create+update,
  `find_type` unifies 8 entity types) of few, parameter-rich tools over many
  narrow ones.
- **No delete operation for tags.** No existing tool in the project exposes
  deletion of any entity; `manage_tags` stays consistent with that and only
  supports list/get/create-or-update.
- **New shared utility, `resolve_person_handle`.** Three of the five new
  tools need to accept a person by either its internal `handle` or its
  human-facing `gramps_id` (e.g. "I0044"). The existing precedent for this
  (`get_type_tool` in `search_details.py`) resolves `gramps_id` → `handle` by
  calling `find_type_tool`, then regex-extracting the handle from its
  *already-markdown-formatted* text output (`re.search(r"\[([^\]]+)\]", ...)`)
  — fragile and indirect. The new tools instead call
  `client.make_api_call(ApiCalls.GET_PEOPLE, params={"gql": f'gramps_id="{gramps_id}"', "pagesize": 1}, tree_id=tree_id)`
  directly and read `result[0]["handle"]` from the raw JSON. This is a
  targeted improvement to code this work depends on, not a drive-by
  refactor — the existing `get_type_tool` regex path is left untouched since
  it's out of scope and working.
- **File organization:** two new files under `tools/`, since `tools/analysis.py`
  is already at 451/500 lines:
  - `tools/relationship_tools.py`: `get_relationship`, `check_living`,
    `get_timeline` (person/family-centric analysis, all three need
    `resolve_person_handle`)
  - `tools/records_tools.py`: `manage_tags`, `get_facts` (record management,
    no handle resolution needed for facts; tags use their own handle
    directly, no gramps_id resolution since tags aren't looked up by
    gramps_id)

Out of scope: Reports (`GET_REPORTS`/`POST_REPORT_FILE`/etc. — already
partially used internally by `get_descendants_tool`/`get_ancestors_tool` via
the async task-polling helper in `tools/analysis.py`, but not exposed as a
general-purpose "generate any report" tool), DNA-match parsing
(`POST_PARSERS_DNA_MATCH`, `GET_PERSON_DNA_MATCHES`), holidays
(`GET_HOLIDAYS`, `GET_HOLIDAYS_DATE`). A resolver for family handle-by-
gramps_id (needed only by `get_timeline`'s `family` scope) is in scope as
`resolve_family_handle`, mirroring `resolve_person_handle` against
`ApiCalls.GET_FAMILIES`.

## New shared utility

Added to `src/gramps_mcp/utils.py`:

```python
async def resolve_person_handle(client, tree_id: str, gramps_id: str) -> Optional[str]:
    """Look up a person's handle by gramps_id via a direct GQL search."""

async def resolve_family_handle(client, tree_id: str, gramps_id: str) -> Optional[str]:
    """Look up a family's handle by gramps_id via a direct GQL search."""
```

Each calls `client.make_api_call(ApiCalls.GET_PEOPLE` (or `GET_FAMILIES`),
`params={"gql": f'gramps_id="{gramps_id}"', "pagesize": 1}, tree_id=tree_id)`
and returns `result[0]["handle"]` if the result list is non-empty, else
`None`. Callers combine this with an already-provided `handle` argument: if
`handle` is given, use it as-is; else if `gramps_id` is given, resolve it;
else raise `ValueError`.

## The 5 tools

### 1. `get_relationship`

New wrapper params model in `server.py` (matching the existing
`DescendantsParams`/`AncestorsParams` pattern of small MCP-facing schemas
distinct from the client's internal parameter models):

```python
class RelationshipQueryParams(BaseModel):
    person1: str = Field(..., description="Handle or gramps_id of the first person")
    person2: str = Field(..., description="Handle or gramps_id of the second person")
    all_relationships: bool = Field(
        False,
        description="If true, return all possible relationships; if false, only the most direct one",
    )
    depth: Optional[int] = Field(None, ge=1, description="Search depth in generations (API default: 15)")
```

`tools/relationship_tools.py::get_relationship_tool`: resolves `person1`/
`person2` to handles (via `resolve_person_handle` if not already handle-shaped
— see "Handle-or-gramps_id detection" below), builds the existing
`RelationParams(handle1=..., handle2=..., depth=...)`, and calls
`ApiCalls.GET_RELATIONS` (single most direct relationship,
`Relationship` schema: `relationship_string`, `distance_common_origin`,
`distance_common_other`) when `all_relationships` is false, or
`ApiCalls.GET_RELATIONS_ALL` (`Relationships` schema: array of
`{relationship_string, common_ancestors: [handle, ...]}`) when true.

New `handlers/relationship_handler.py`:
- `format_relationship(data: Dict) -> str` for the single case — renders the
  `relationship_string`, and generation distances only when
  `distance_common_origin`/`distance_common_other` are not `-1` (per the
  spec, `-1` means "no common ancestor").
- `format_relationships(data: List[Dict], client, tree_id) -> str` for the
  all-relationships case — one bullet per entry, `relationship_string` plus
  common ancestors resolved to `gramps_id` via the existing
  `get_gramps_id_from_handle` utility (already used the same way in
  `tools/analysis.py`'s `_format_recent_changes`).

### 2. `manage_tags`

New model in `tag_params.py`:

```python
class ManageTagsParams(BaseModel):
    action: Literal["list", "get", "create"]
    handle: Optional[str] = Field(None, description="Tag handle (required for get; provide for update, omit for new tag on create)")
    name: Optional[str] = Field(None, description="Tag name (required for create)")
    color: Optional[str] = None
    priority: Optional[int] = None
    page: Optional[int] = Field(None, ge=0)
    pagesize: Optional[int] = Field(None, ge=1, le=100)
    sort: Optional[List[str]] = None
```

`tools/records_tools.py::manage_tags_tool` branches on `action`:
- `"list"`: builds `TagSearchParams(page=..., pagesize=..., sort=...)`, calls
  `ApiCalls.GET_TAGS` (returns `array of Tag`).
- `"get"`: requires `handle`; calls `ApiCalls.GET_TAG` (no params model —
  `api_mapping.py` already maps this to `None`, handle-only via URL
  substitution), returns a single `Tag`.
- `"create"`: builds `TagSaveParams(handle=..., name=..., color=..., priority=...)`;
  calls `ApiCalls.PUT_TAG` if `handle` is provided (update), else
  `ApiCalls.POST_TAGS` (new tag) — mirrors the existing
  create-vs-update-by-handle-presence convention already used by
  `create_person_tool` et al. in `tools/data_management.py`.

New `handlers/tag_handler.py`:
- `format_tag(data: Dict) -> str` — single tag: name, color, priority.
- `format_tags(data: List[Dict]) -> str` — bullet list for the list action.

### 3. `get_facts`

No new parameter model — `FactsParams` (already in `facts_params.py`, already
mapped in `api_mapping.py`) matches `GET_FACTS`'s query parameters exactly:
`gramps_id`, `handle`, `living` (`LivingProxy` enum), `person` (built-in
filter name), `private`, `rank`. `tools/records_tools.py::get_facts_tool`
validates arguments directly into `FactsParams` and calls `ApiCalls.GET_FACTS`
(returns `array of RecordFact`: `description`, `key`,
`objects: [RecordFactObject, ...]`).

New `handlers/facts_handler.py`:
- `format_facts(data: List[Dict], client, tree_id) -> str` — one bullet per
  fact (`description`), with associated object handles resolved to
  `gramps_id` via `get_gramps_id_from_handle` where the object's class is
  known (defensive: falls back to the raw handle if the object shape doesn't
  include what's expected, matching the defensive `.get()`-based style
  already used throughout `handlers/`).

### 4. `check_living`

New wrapper params model in `server.py`:

```python
class LivingStatusParams(BaseModel):
    person: str = Field(..., description="Handle or gramps_id of the person to evaluate")
    average_generation_gap: Optional[int] = Field(None, ge=1)
    max_age_probably_alive: Optional[int] = Field(None, ge=1)
    max_sibling_age_difference: Optional[int] = Field(None, ge=0)
    include_dates: bool = Field(True, description="Also fetch estimated birth/death dates")
```

`tools/relationship_tools.py::check_living_tool`: resolves `person` to a
handle, builds `LivingParams(handle=..., average_generation_gap=...,
max_age_probably_alive=..., max_sibling_age_difference=...)` (already exists,
already mapped to both calls), always calls `ApiCalls.GET_LIVING` (`Living`
schema: `living: bool`), and additionally calls `ApiCalls.GET_LIVING_DATES`
(`LivingDates` schema: `birth`, `death`, `explain`, `other: Person`) when
`include_dates` is true.

New `handlers/living_handler.py`:
- `format_living_status(living: Dict, dates: Optional[Dict]) -> str` —
  renders the living boolean plainly, and the estimated dates + explanation
  when provided.

### 5. `get_timeline`

New wrapper params model in `server.py`:

```python
class TimelineQueryParams(BaseModel):
    scope: Literal["person", "family", "people", "families"]
    handle: Optional[str] = Field(None, description="Handle for person/family scope")
    gramps_id: Optional[str] = Field(None, description="gramps_id for person/family scope (alternative to handle)")
    dates: Optional[str] = Field(None, description="Date range filter, e.g. '1900/1/1-1950/1/1'")
    handles: Optional[str] = Field(None, description="Comma-delimited handles, for people/families scope")
    events: Optional[str] = None
    event_classes: Optional[str] = None
    ratings: bool = False
    precision: int = Field(1, ge=1, le=3)
    discard_empty: bool = True
    page: int = Field(0, ge=0)
    pagesize: int = Field(20, gt=0)
```

`tools/relationship_tools.py::get_timeline_tool` maps `scope` to one of 4
existing (API-call, param-model) pairs:
- `"person"`: resolves `handle`/`gramps_id` via `resolve_person_handle`,
  builds `PersonTimelineParams` (from `people_params.py`), calls
  `ApiCalls.GET_PERSON_TIMELINE`.
- `"family"`: resolves via `resolve_family_handle`, builds
  `FamilyTimelineParams` (from `family_params.py`), calls
  `ApiCalls.GET_FAMILY_TIMELINE`.
- `"people"`: builds `PeopleTimelineParams` (from `timeline_params.py`,
  passing through `dates`/`handles`/`events`/etc.), calls
  `ApiCalls.GET_TIMELINES_PEOPLE`.
- `"families"`: builds `FamiliesTimelineParams`, calls
  `ApiCalls.GET_TIMELINES_FAMILIES`.

All four return `TimelineEventProfile`-shaped entries (`date`, `description`,
`label`, `age`, `citations`, `confidence`, `handle`, `gramps_id`) per the
spec — for the single-entity scopes the spec's schema ref is not wrapped in
`type: array` (likely a spec-authoring simplification), so the handler must
defensively accept either a single object or a list, matching the existing
"list-or-single" defensive pattern already used in `client.py`'s
`_extract_entity_data`-style code.

New `handlers/timeline_handler.py`:
- `format_timeline(data: Union[Dict, List[Dict]]) -> str` — normalizes to a
  list, then renders a chronological bullet list: date, description/label,
  age, and confidence/citation count when present.

## Handle-or-gramps_id detection

All three consumers of `resolve_person_handle` (and `get_timeline`'s family
scope) follow the same small rule, implemented once per tool (not extracted
into a shared decorator, to keep each tool's control flow readable — this
matches the project's existing style of inline resolution in
`get_type_tool` rather than a generic wrapper): if the caller passed
`handle` non-empty, use it as-is; if only `gramps_id` was passed, resolve it
via `resolve_person_handle`/`resolve_family_handle`; if neither, raise
`ValueError` with a clear message before making any API call.

For `get_relationship`, `person1`/`person2` are single fields accepting
either shape directly (not split `handle`/`gramps_id` pairs) — detection
uses the exact regex `^[A-Z]+[0-9]+$` (one or more uppercase letters
followed by one or more digits, nothing else): a full match means treat the
value as a `gramps_id` and resolve it; no match means treat it as an
already-valid handle. This matches observed `gramps_id` examples throughout
the codebase (`I0001`, `F0001`, `E0200`) and does not match observed handle
examples (`bb80c2b235b0a1b3f49`, `35WJQC1B7T7NPV8OLV` — mixed case and/or
leading digits). This keeps the tool's argument list short (2 fields instead
of 4) at the cost of a small heuristic; it is documented in the field
description so callers aren't surprised.

## Testing

Per project convention (`CLAUDE.md`: real APIs, no mocks), each tool gets an
integration test file requiring a live Gramps Web server:
`tests/test_relationship_tools.py`, `tests/test_records_tools.py` — these
join the existing pool of tests that fail offline by design and are **not**
added to the CI workflow's offline test list (`ci.yml` continues to run only
`test_merge.py`, `test_config.py`, `test_client_merge.py`, `test_utils.py`).
`resolve_person_handle`/`resolve_family_handle` are thin API wrappers (no
branching logic beyond "empty list vs not"), so they are exercised through
the tool tests rather than given standalone unit tests.

## Registration and documentation

- `server.py`: `TOOL_REGISTRY` gains 5 entries (16 → 21); imports the 2 new
  tool modules and the new wrapper param classes
  (`RelationshipQueryParams`, `LivingStatusParams`, `TimelineQueryParams`)
  alongside the existing `DescendantsParams`/`AncestorsParams`-style classes
  already defined in that file.
- `README.md`: the "16 Genealogy Tools" section gains a new subsection for
  these 5 tools; the Architecture tree gains the 2 new `tools/` files and the
  3 new `handlers/` files (`relationship_handler.py`, `tag_handler.py`,
  `facts_handler.py`, `living_handler.py`, `timeline_handler.py` — 5 new
  handler files total, one per tool except `get_relationship` and
  `check_living`/`get_timeline` which live together in
  `relationship_tools.py` but still get separate handler files matching the
  project's one-handler-per-concern convention).
- No changes needed to the root `/` or `/health` endpoints or their tests —
  both already compute tool count via `len(TOOL_REGISTRY)` (from the prior
  code-quality cleanup), so they update automatically.

## Verification

- `uv run ruff check src/`, `uv run ruff format --check src/ tests/`,
  `uv run mypy src/gramps_mcp --ignore-missing-imports` all clean.
- The 4 existing offline tests still pass unchanged.
- The new integration tests pass against a live Gramps Web server (manual
  verification by the user/implementer, matching how the existing 31
  server-dependent tests are validated today — not part of automated CI).
- `uv run python -c "from src.gramps_mcp.server import TOOL_REGISTRY; print(len(TOOL_REGISTRY))"` → `21`.

## Risks

- The `TimelineEventProfile` array-vs-single-object ambiguity in the vendored
  spec (noted above) means the person/family single-scope timeline handler
  must be defensive; if the live API's actual shape differs from both
  guesses, this will surface as a test failure against the real server, not
  a silent misformat, since the handler will raise if `.get()` calls hit
  something wholly unexpected — acceptable per the project's existing error
  handling (`_format_error_response` returns a clear error to the caller
  rather than crashing the server).
- `manage_tags`'s single `action`-multiplexed schema is a new pattern for
  this codebase (existing tools consolidate by *entity type*, e.g.
  `find_type`, not by *action* within one entity type). This is called out
  explicitly rather than silently introduced, since it's the one place this
  design deviates from strict precedent — justified here because a
  dedicated 3-tool split (`find_tags`/`get_tag`/`create_tag`) was rejected in
  favor of 1 tool during brainstorming to keep the total tool count at 5.
