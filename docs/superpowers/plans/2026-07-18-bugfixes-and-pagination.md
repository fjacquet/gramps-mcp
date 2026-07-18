# Bug Fixes and Search Pagination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 confirmed defects (note text StyledText slice crash, create_note double-validation crash over FastMCP transport, create_family silently dropping child_handles) and 2 silent pagination gaps in the universal `find_type`/`find_anything` tools, all found by direct triage of upstream `cabout-me/gramps-mcp` issues against this fork.

**Architecture:** Four independent, surgical fixes — no new modules, no architecture changes. Each fix stays local to the file(s) that own the bug; no changes to `client.py` or the shared `api_mapping.py`.

**Tech Stack:** Python, Pydantic v2, pytest-asyncio, live Gramps Web API for integration tests (no mocks).

## Global Constraints

- Tests run against a live Gramps Web server. Set `GRAMPS_API_URL=http://localhost:80` when running the new/changed tests in this plan (the `.env` default `http://host.docker.internal:80` only resolves inside Docker).
- No mocks, fixtures, or test clients — call the real tool functions against the real API, per this project's established TDD convention.
- Never reference real people/family names/dates/places from the live tree in test code or commit messages. Use fixture data created within the test itself (e.g. `"TestUpdate"` / `"PersonIssue9"`-style names, matching the existing convention in `tests/test_data_management.py`), or generic structural assertions.
- Follow Google-style docstrings, type hints, `ruff format`/`ruff check`, and the 16-line AGPL copyright header already present at the top of every touched file (do not remove or alter it).
- Do not touch `docker-compose.yml`, the `docker/` directory, or `.env` — out of scope, pre-existing unrelated work.
- Run `uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py -q` before committing as an offline sanity check (these do not require the live server); run the specific new/changed test classes against the live server as the primary verification for each task.

---

### Task 1: Fix note text StyledText slice crash in detail handlers (upstream #29/#30)

**Files:**
- Modify: `src/gramps_mcp/handlers/person_detail_handler.py:276-287`
- Modify: `src/gramps_mcp/handlers/family_detail_handler.py:206-222`
- Test: Create `tests/test_search_details.py`

**Interfaces:**
- Consumes: `format_person_detail(client, tree_id, handle) -> str` (existing, `person_detail_handler.py`), `format_family_detail(client, tree_id, handle) -> str` (existing, `family_detail_handler.py`), `get_person_tool(arguments: Dict) -> List[TextContent]` and `get_family_tool(arguments: Dict) -> List[TextContent]` (existing, `tools/search_details.py`), `create_person_tool`, `create_family_tool`, `create_note_tool` (existing, `tools/data_management.py`).
- Produces: no new public interfaces — this task only fixes an internal formatting bug.

The real Gramps Web API returns a note's `text` field as a StyledText dict
(`{"_class": "StyledText", "string": "..."}`), never a plain string. Both
handlers currently do `note_data.get("text", "")[:50]`, which raises
`unhashable type: slice` when `text` is a dict — the working reference
implementation is `handlers/note_handler.py:57`:
`note_data.get("text", {}).get("string")`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_search_details.py`:

```python
"""
Integration tests for detail retrieval tools using real Gramps Web API.

Tests get_person_tool and get_family_tool, including the case where the
person/family has an attached note (regression test for upstream issue
#29/#30: a StyledText note crashed detail formatting).
"""

import re

import pytest
from dotenv import load_dotenv

from src.gramps_mcp.tools.data_management import create_note_tool, create_person_tool
from src.gramps_mcp.tools.search_details import get_person_tool

load_dotenv()


def _extract_handle(text: str) -> str:
    match = re.search(r"\[([a-f0-9]+)\]", text)
    assert match, f"Could not extract handle from: {text}"
    return match.group(1)


class TestGetPersonToolWithNote:
    """Regression test for upstream issue #29/#30."""

    @pytest.mark.asyncio
    async def test_get_person_with_attached_note_does_not_crash(self):
        """A person with an attached note must format without error."""
        note_result = await create_note_tool(
            {
                "text": "Detail handler regression note for issue 29/30.",
                "type": "Research",
            }
        )
        note_text = note_result[0].text
        assert "Error:" not in note_text, f"Note creation failed: {note_text}"
        note_handle = _extract_handle(note_text)

        person_result = await create_person_tool(
            {
                "primary_name": {
                    "first_name": "NoteRegression",
                    "surname_list": [{"surname": "TestPerson", "primary": True}],
                },
                "gender": 1,
                "note_list": [note_handle],
            }
        )
        person_text = person_result[0].text
        assert "Error:" not in person_text, f"Person creation failed: {person_text}"
        person_handle = _extract_handle(person_text)

        detail_result = await get_person_tool({"person_handle": person_handle})
        detail_text = detail_result[0].text

        assert "Error:" not in detail_text, (
            f"get_person_tool crashed on attached note: {detail_text}"
        )
        assert "Detail handler regression note for issue 29/30." in detail_text, (
            f"Expected real note text in output but got: {detail_text}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_search_details.py -v`
Expected: FAIL — `get_person_tool` returns an `Error:` response because
`format_person_detail` raises `unhashable type: slice` internally (caught
by `get_person_tool`'s outer try/except and turned into an error string).

- [ ] **Step 3: Fix `person_detail_handler.py`**

Replace lines 276-287 of `src/gramps_mcp/handlers/person_detail_handler.py`:

```python
    # Attached notes section
    result += "\nAttached notes:\n"
    note_list = person_data.get("note_list", [])
    for note_handle in note_list:
        note_data = await client.make_api_call(
            ApiCalls.GET_NOTE, tree_id=tree_id, handle=note_handle
        )
        note_type = note_data.get("type", "")
        note_id = note_data.get("gramps_id", "")
        note_full_text = note_data.get("text", {}).get("string", "")
        note_text = note_full_text[:50]
        if len(note_full_text) > 50:
            note_text += "..."
        result += f"- {note_type}: {note_text} ({note_id})\n"
```

- [ ] **Step 4: Fix `family_detail_handler.py`**

Replace lines 206-222 of `src/gramps_mcp/handlers/family_detail_handler.py`:

```python
    # Attached notes section
    result += "\nAttached notes:\n"
    note_list = family_data.get("note_list", [])
    if note_list:
        for note_handle in note_list:
            try:
                note_data = await client.make_api_call(
                    ApiCalls.GET_NOTE, tree_id=tree_id, handle=note_handle
                )
                note_type = note_data.get("type", "")
                note_id = note_data.get("gramps_id", "")
                note_full_text = note_data.get("text", {}).get("string", "")
                note_text = note_full_text[:50]  # First 50 chars
                if len(note_full_text) > 50:
                    note_text += "..."
                result += f"- {note_type}: {note_text} ({note_id})\n"
            except Exception:
                result += f"- Note ({note_handle})\n"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_search_details.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
uv run git add src/gramps_mcp/handlers/person_detail_handler.py src/gramps_mcp/handlers/family_detail_handler.py tests/test_search_details.py
uv run git commit -m "fix: read note text as StyledText dict in detail handlers (#29/#30)"
```

---

### Task 2: Fix create_note double-validation crash over FastMCP transport (#27)

**Files:**
- Modify: `src/gramps_mcp/models/parameters/note_params.py:60-79`
- Test: `tests/test_data_management.py` (add to `TestCreateNoteTool`)

**Interfaces:**
- Consumes: `NoteSaveParams` (existing, `models/parameters/note_params.py`), `create_note_tool(arguments: Dict) -> List[TextContent]` (existing, `tools/data_management.py`).
- Produces: no new public interfaces — `NoteSaveParams.text` type widens from `str` to `str | dict[str, Any]`; nothing downstream depends on it being exactly `str`.

`server.py`'s generic `create_handler` calls `arguments.model_dump()` on the
`NoteSaveParams` schema instance built from the raw tool call — this already
runs `NoteSaveParams`'s overridden `model_dump()`, turning `text` into a
StyledText dict. `create_note_tool` then reconstructs
`NoteSaveParams(**params)` from that already-transformed dict, and
Pydantic rejects it because `text` is typed `str` but the value is now a
dict. The existing test in `TestCreateNoteTool` calls `create_note_tool`
directly with a hand-built dict, bypassing this path entirely, which is why
it didn't catch the bug.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_data_management.py`, inside `class TestCreateNoteTool:`
(after the existing `test_create_note_success` method):

```python
    @pytest.mark.asyncio
    async def test_create_note_via_fastmcp_transport(self):
        """Regression test for issue #27.

        server.py's create_handler calls arguments.model_dump() on the
        NoteSaveParams schema instance before create_note_tool ever sees
        the dict. This must not crash NoteSaveParams(**params) downstream.
        """
        from src.gramps_mcp.models.parameters.note_params import NoteSaveParams

        schema_instance = NoteSaveParams(
            text="Regression test note for FastMCP transport path.",
            type="Research",
        )
        transport_dict = schema_instance.model_dump()

        result = await create_note_tool(transport_dict)

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "Regression test note for FastMCP transport path." in text, (
            f"Expected note text in output but got: {text}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_data_management.py::TestCreateNoteTool::test_create_note_via_fastmcp_transport -v`
Expected: FAIL with a Pydantic `ValidationError` — `text` input should be a
valid string, `input_type=dict`.

- [ ] **Step 3: Fix `note_params.py`**

Replace lines 60-79 of `src/gramps_mcp/models/parameters/note_params.py`:

```python
class NoteSaveParams(BaseModel):
    """Parameters for creating or updating a note."""

    handle: str | None = Field(
        None,
        description="Note's handle (for updates; omit for new note)",
    )
    text: str | dict[str, Any] = Field(..., description="Note text content")
    type: str = Field(..., description="The type of note")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Convert to API format with StyledText structure."""
        data = super().model_dump(**kwargs)
        # Transform text string to StyledText format expected by API.
        # Reason: idempotent by design - the FastMCP transport path calls
        # model_dump() twice (once in server.py's generic dispatch, once
        # when client.py builds the API request body), so a dict here must
        # be left untouched rather than re-wrapped or rejected.
        if "text" in data and isinstance(data["text"], str):
            data["text"] = {
                "_class": "StyledText",
                "string": data["text"],
            }
        return data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_data_management.py::TestCreateNoteTool -v`
Expected: PASS (both the existing `test_create_note_success` and the new
`test_create_note_via_fastmcp_transport`)

- [ ] **Step 5: Commit**

```bash
uv run git add src/gramps_mcp/models/parameters/note_params.py tests/test_data_management.py
uv run git commit -m "fix: make NoteSaveParams.model_dump() idempotent for FastMCP transport (#27)"
```

---

### Task 3: Translate create_family's child_handles into child_ref_list (#24)

**Files:**
- Modify: `src/gramps_mcp/models/parameters/family_params.py:34-54`
- Modify: `src/gramps_mcp/tools/data_management.py:198-241` (`create_family_tool`)
- Test: `tests/test_data_management.py` (add to `TestCreateFamilyTool`)

**Interfaces:**
- Consumes: `FamilySaveParams` (existing, `models/parameters/family_params.py`), `create_family_tool(arguments: Dict) -> List[TextContent]` (existing, `tools/data_management.py`), `format_family` (existing, `handlers/family_handler.py`, already reads `child_ref_list` from the API response — used implicitly by `_format_save_response`).
- Produces: `FamilySaveParams.child_ref_list: Optional[List[dict]]` — new field, same shape as the existing `event_ref_list`.

The real Gramps Web `Family` schema has no `child_handles` field; it expects
`child_ref_list: [{"ref": <handle>}, ...]`. `FamilySaveParams` declares
`child_handles` with no translation anywhere, so the API silently drops it.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_data_management.py`, inside `class TestCreateFamilyTool:`
(after the existing `test_create_family_success` method):

```python
    @pytest.mark.asyncio
    async def test_create_family_with_child_handles(self):
        """Regression test for issue #24: child_handles must translate to
        child_ref_list so the API actually stores the child link."""
        import re

        child_result = await create_person_tool(
            {
                "primary_name": {
                    "first_name": "ChildHandles",
                    "surname_list": [{"surname": "RegressionChild", "primary": True}],
                },
                "gender": 0,
            }
        )
        child_text = child_result[0].text
        assert "Error:" not in child_text, f"Child creation failed: {child_text}"
        child_handle_match = re.search(r"\[([a-f0-9]+)\]", child_text)
        assert child_handle_match, f"Could not extract child handle: {child_text}"
        child_handle = child_handle_match.group(1)

        family_result = await create_family_tool({"child_handles": [child_handle]})

        family_text = family_result[0].text
        assert "Error:" not in family_text, (
            f"Expected success but got error: {family_text}"
        )
        assert "ChildHandles" in family_text and "RegressionChild" in family_text, (
            f"Expected child to appear in family details but got: {family_text}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_data_management.py::TestCreateFamilyTool::test_create_family_with_child_handles -v`
Expected: FAIL — the created family has no children section, or the
assertion on `"ChildHandles"`/`"RegressionChild"` fails because
`child_handles` was dropped before reaching the API.

- [ ] **Step 3: Add `child_ref_list` to `FamilySaveParams`**

In `src/gramps_mcp/models/parameters/family_params.py`, add a field right
after the existing `child_handles` field (after line 44):

```python
    child_ref_list: Optional[List[dict]] = Field(
        None,
        description=(
            "List of child references in API shape "
            "(translated internally from child_handles)"
        ),
    )
```

- [ ] **Step 4: Translate in `create_family_tool`**

In `src/gramps_mcp/tools/data_management.py`, inside `create_family_tool`,
immediately after `params = FamilySaveParams(**arguments)` (line 204), add:

```python
        # Reason: the real Gramps Web API has no child_handles field - it
        # expects child_ref_list entries. Translate here so the caller can
        # keep using the simpler child_handles shape.
        if params.child_handles:
            params.child_ref_list = [{"ref": h} for h in params.child_handles]
            params.child_handles = None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_data_management.py::TestCreateFamilyTool -v`
Expected: PASS (both the existing `test_create_family_success` and the new
`test_create_family_with_child_handles`)

- [ ] **Step 6: Commit**

```bash
uv run git add src/gramps_mcp/models/parameters/family_params.py src/gramps_mcp/tools/data_management.py tests/test_data_management.py
uv run git commit -m "fix: translate create_family child_handles into child_ref_list (#24)"
```

---

### Task 4: Fix pagination gaps in find_type and find_anything (#5)

**Files:**
- Modify: `src/gramps_mcp/models/parameters/simple_params.py:48-60`
- Modify: `src/gramps_mcp/tools/search_basic.py:369-388` (`find_type_tool`), `:392-398` (`find_anything_tool`)
- Test: `tests/test_search_basic.py` (add new test classes)

**Interfaces:**
- Consumes: `SimpleFindParams`, `SimpleSearchParams` (existing, `models/parameters/simple_params.py`), `find_type_tool`, `find_anything_tool` (existing, `tools/search_basic.py`), `SearchParams` (existing, `models/parameters/search_params.py`, already has `page`/`pagesize`), `BaseGetMultipleParams` (existing, already has `page`/`pagesize`, used by the entity-specific `find_*_tool`s that `find_type_tool` delegates to).
- Produces: `SimpleFindParams.page: Optional[int]`, `SimpleSearchParams.page: Optional[int]` — new fields.

Two separate silent gaps, both in the *universal* tools registered in
`TOOL_REGISTRY` (the entity-specific tools they delegate to already support
paging via `BaseGetMultipleParams`):

1. `SimpleFindParams` has no `page` field at all, and `find_type_tool` never
   builds one — there is no way to request page 2 through `find_type`.
2. `find_anything_tool` does `SearchParams(**arguments)` where `arguments`
   comes from `SimpleSearchParams` (`query`, `max_results`). `SearchParams`
   has `page`/`pagesize`, not `max_results` — Pydantic silently drops the
   unrecognized `max_results` kwarg, so `params.pagesize` is always `None`
   and `max_results` has never had any effect on `find_anything`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_search_basic.py`, after the existing `TestFindPersonTool`
class:

```python
class TestFindTypePagination:
    """Regression tests for issue #5: find_type page parameter."""

    @pytest.mark.asyncio
    async def test_find_type_accepts_page_parameter(self):
        """find_type must accept a page argument without raising."""
        result = await find_type_tool(
            {
                "type": "person",
                "gql": 'primary_name.first_name ~ "e"',
                "max_results": 2,
                "page": 2,
            }
        )

        print("\n--- FIND TYPE PAGE 2 RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
```

Add to `tests/test_search_basic.py`, after the existing
`TestFindAnythingTool` class (the class containing `test_find_anything`):

```python
class TestFindAnythingPagination:
    """Regression tests for issue #5: find_anything pagesize/page."""

    @pytest.mark.asyncio
    async def test_find_anything_respects_max_results(self):
        """max_results must actually limit the number of results shown.

        Uses a broad single-letter query that is expected to match far
        more than 2 records across a real family tree, to force the limit
        to matter rather than pass trivially on an already-small result set.
        """
        result = await find_anything_tool({"query": "e", "max_results": 2})

        print("\n--- FIND ANYTHING MAX_RESULTS RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )

        if "Found" in result[0].text and "No records found" not in result[0].text:
            result_count = result[0].text.count("• **")
            assert result_count <= 2, (
                f"Expected max 2 results, got {result_count}: {result[0].text}"
            )

    @pytest.mark.asyncio
    async def test_find_anything_accepts_page_parameter(self):
        """find_anything must accept a page argument without raising."""
        result = await find_anything_tool({"query": "e", "max_results": 2, "page": 2})

        print("\n--- FIND ANYTHING PAGE 2 RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_search_basic.py::TestFindTypePagination tests/test_search_basic.py::TestFindAnythingPagination -v`
Expected: `test_find_type_accepts_page_parameter` FAILs (or errors) because
`SimpleFindParams` rejects/ignores `page`; `test_find_anything_respects_max_results`
FAILs because `max_results` is silently dropped and the tree returns more
than 2 matches for a common letter; `test_find_anything_accepts_page_parameter`
FAILs the same way as the find_type case (via `SimpleSearchParams`).

- [ ] **Step 3: Add `page` fields to `simple_params.py`**

Replace lines 48-60 of `src/gramps_mcp/models/parameters/simple_params.py`:

```python
class SimpleFindParams(BaseModel):
    """Simplified parameters for type-based search."""

    type: EntityType = Field(description="Entity type to search")
    gql: str = Field(description="Gramps Query Language filter")
    max_results: int = Field(default=20, description="Maximum results to return")
    page: Optional[int] = Field(
        default=None, description="Page number for paging through results"
    )


class SimpleSearchParams(BaseModel):
    """Simplified parameters for full-text search."""

    query: str = Field(description="Plain text search query")
    max_results: int = Field(default=20, description="Maximum results to return")
    page: Optional[int] = Field(
        default=None, description="Page number for paging through results"
    )
```

- [ ] **Step 4: Thread `page` through `find_type_tool`**

Replace lines 369-388 of `src/gramps_mcp/tools/search_basic.py`:

```python
async def find_type_tool(arguments: Dict) -> List[TextContent]:
    """Universal type-based search tool."""
    entity_type = arguments.get("type")
    gql = arguments.get("gql")
    max_results = arguments.get("max_results", 20)
    page = arguments.get("page")

    # Get the string value from the enum if needed
    entity_type_str = getattr(entity_type, "value", entity_type)

    # Convert to parameters expected by existing tools
    params = {"gql": gql, "pagesize": max_results, "page": page}

    # Call the existing tool function directly
    tool_name = f"find_{entity_type_str}_tool"
    if tool_name in globals():
        return await globals()[tool_name](params)
    else:
        return [
            TextContent(type="text", text=f"Entity type '{entity_type}' not supported")
        ]
```

- [ ] **Step 5: Fix `find_anything_tool`'s parameter translation**

Replace lines 392-398 of `src/gramps_mcp/tools/search_basic.py`:

```python
@with_client
async def find_anything_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Full-text search across all entity types.
    """
    try:
        # Validate parameters - built explicitly rather than splatting
        # arguments, because SimpleSearchParams uses max_results while
        # SearchParams expects pagesize (splatting silently drops
        # max_results since Pydantic ignores unknown kwargs by default).
        params = SearchParams(
            query=arguments["query"],
            pagesize=arguments.get("max_results"),
            page=arguments.get("page"),
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_search_basic.py -v`
Expected: PASS for all tests in the file, including the pre-existing ones.

- [ ] **Step 7: Commit**

```bash
uv run git add src/gramps_mcp/models/parameters/simple_params.py src/gramps_mcp/tools/search_basic.py tests/test_search_basic.py
uv run git commit -m "fix: add page support to find_type and fix find_anything max_results (#5)"
```
