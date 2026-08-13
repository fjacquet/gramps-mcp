# Quality Lot 3 — Ergonomics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four defects where the Gramps MCP server works but tells the caller something untrue, and record three project facts that were rediscovered repeatedly during earlier lots.

**Architecture:** Every fix is local to the function that owns the defect. Two of them adopt a pattern that already exists and works elsewhere in the same file or module, rather than inventing one. Three of the five tests need no server, because the logic under test is pure or the exception under test can be constructed directly from the real library.

**Tech Stack:** Python 3.13, httpx, pydantic v2, MCP Python SDK 2.0, pytest + pytest-asyncio, uv, ruff.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-08-13-quality-lot3-ergonomics-design.md`.
- Every command runs through uv: `uv run pytest`, `uv run git commit`.
- No mocks, no fixtures, no test clients. Constructing a real `httpx.Response` and a real `httpx.HTTPStatusError` is not mocking — it is the library's own type built from real data, with no behaviour stubbed.
- Live tests need a URL override from the macOS host, because `.env` targets `host.docker.internal`, which only resolves inside the container: `GRAMPS_API_URL=http://localhost:80 uv run pytest ...`. Never edit `.env`, never commit the override.
- **Do not use `git stash`.** An uncommitted change was lost to a stash cycle earlier in this project. To compare a file against main, use `git show main:<path>`. Do not check out main either.
- Never create a file longer than 500 lines. A pre-commit hook enforces this.
- No emojis anywhere, including markdown. A pre-commit hook enforces this.
- Google-style docstrings on every function.
- **One atomic commit per defect**, each carrying its fix and its test together.
- Branch `fix/quality-lot3-ergonomics`, which already exists and holds the spec commit.
- No release tag. Lot 3 merges into `main` and waits for lot 4.
- Do NOT merge the pull request, create a tag, publish a release, or bump a version.

---

### Task 1: Report the real match count

`_search_entities` sets `total_count = len(results)` for a bare list, which the
entity endpoints always return. A search capped at twenty reports "Found 20
people" whether the tree holds twenty matches or five hundred. The real count
is in the `X-Total-Count` header, never requested.

A second symptom: the branch that would print "Found 500 (showing 20)" cannot
execute today, because both numbers are the same by construction.

**Files:**
- Modify: `src/gramps_mcp/tools/search_basic.py:169-190`
- Test: `tests/test_search_totals.py` (new)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: no new names. `_search_entities` keeps its signature.

- [ ] **Step 1: Read the pattern that already works**

`find_anything_tool` in the same file already does this correctly, at roughly
lines 425 and 434:

```python
            with_headers=True,
...
        total_count = int(headers.get("x-total-count", len(results)))
```

Read that whole call and copy its shape. Note the header key is lowercased —
httpx normalises header names, so `x-total-count` is correct and
`X-Total-Count` would also work through httpx's case-insensitive mapping, but
match the existing code.

- [ ] **Step 2: Write the failing test**

The live tree holds 908 people, so any `pagesize` below that produces the
condition. Create `tests/test_search_totals.py`:

```python
"""
Integration tests for search result totals against the real Gramps API.
"""

import pytest

from src.gramps_mcp.tools.search_basic import find_type_tool


class TestSearchTotals:
    """A truncated search must report the real match count."""

    @pytest.mark.asyncio
    async def test_truncated_search_reports_both_numbers(self):
        result = await find_type_tool(
            {"type": "person", "gql": 'gramps_id!=""', "max_results": 5}
        )
        text = result[0].text

        assert "error" not in text.lower()
        # Reason: with the page length used as the total, this read
        # "Found 5 people" and gave no hint the set was truncated.
        assert "showing" in text.lower()

    @pytest.mark.asyncio
    async def test_total_exceeds_displayed_count(self):
        result = await find_type_tool(
            {"type": "person", "gql": 'gramps_id!=""', "max_results": 5}
        )
        text = result[0].text

        import re

        found = re.search(r"Found (\d+)", text)
        showing = re.search(r"showing (\d+)", text)
        assert found is not None
        assert showing is not None
        assert int(found.group(1)) > int(showing.group(1))
```

Before running, confirm `find_type_tool`'s parameter names by reading its
schema — `grep -n "class SimpleFindParams" -A 15 src/gramps_mcp/models/parameters/simple_params.py`.
If the field is not `max_results`, or the GQL filter above is not valid syntax,
use what the schema and `src/gramps_mcp/resources/gql-documentation.md` actually
specify. A filter matching every person is all this test needs.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_search_totals.py -v`
Expected: FAIL — the output says "Found 5 people" with no "showing", because the total equals the page length.

- [ ] **Step 4: Implement**

In `src/gramps_mcp/tools/search_basic.py`, this call:

```python
        response = await client.make_api_call(
            api_call=api_call, params=params, tree_id=tree_id
        )

        # Extract results and count from response
        if isinstance(response, list):
            results = response
            total_count = len(results)
        else:
            results = response.get("data", [])
            total_count = response.get("total_count", len(results))
```

becomes:

```python
        response, headers = await client.make_api_call(
            api_call=api_call, params=params, tree_id=tree_id, with_headers=True
        )

        # Extract results and count from response
        if isinstance(response, list):
            results = response
            # Reason: entity endpoints return a bare list for the current page,
            # so the real match count is only in the header. Using the page
            # length made every truncated search claim to be complete.
            total_count = int(headers.get("x-total-count", len(results)))
        else:
            results = response.get("data", [])
            total_count = response.get("total_count", len(results))
```

Leave the formatting block below it untouched: its `actual_total > displayed_count`
branch becomes reachable on its own once the numbers can differ.

- [ ] **Step 5: Run the tests**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_search_totals.py -v`
Expected: PASS, 2 tests.

- [ ] **Step 6: Check the other callers of `_search_entities`**

Run: `grep -n "_search_entities" src/gramps_mcp/tools/search_basic.py`

Every caller goes through the same function, so all of them gain the fix at
once. Run their tests to confirm none depended on the old number:

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_search_basic.py -q`
Expected: no NEW failures. That file has pre-existing failures; determine for each whether it is one of them by reading the test, or with `git show main:tests/test_search_basic.py`.

- [ ] **Step 7: Commit**

```bash
rtk git add src/gramps_mcp/tools/search_basic.py tests/test_search_totals.py
uv run git commit -m "fix: report the real match count instead of the page length"
```

---

### Task 2: Keep the detail the server sent

`_format_http_error` maps each status code to a fixed sentence and drops the
response body. Gramps returns a 422 naming the field it rejected; the caller
sees only `Invalid data provided.` This is the dominant failure mode of the
create and update tools.

**Files:**
- Modify: `src/gramps_mcp/client.py:136-151`
- Test: `tests/test_http_error_detail.py` (new)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `GrampsWebAPIClient._format_http_error(error: httpx.HTTPStatusError) -> str`, unchanged signature, richer output.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_http_error_detail.py`:

```python
"""
Unit tests for HTTP error formatting. These construct real httpx objects and
need no server.
"""

import httpx

from src.gramps_mcp.client import GrampsWebAPIClient

MAX_DETAIL = 300


def _error_with(status_code: int, **response_kwargs) -> httpx.HTTPStatusError:
    """
    Build a real HTTPStatusError carrying the given response.

    Args:
        status_code (int): HTTP status to simulate.
        **response_kwargs: Passed to httpx.Response, for example json= or text=.

    Returns:
        httpx.HTTPStatusError: The exception httpx itself would raise.
    """
    request = httpx.Request("POST", "http://example.org/api/places/")
    response = httpx.Response(status_code, request=request, **response_kwargs)
    return httpx.HTTPStatusError("error", request=request, response=response)


class TestErrorDetail:
    """The server's explanation must survive."""

    def test_json_message_is_appended(self):
        client = GrampsWebAPIClient()
        error = _error_with(422, json={"message": "'place_type' is required"})

        formatted = client._format_http_error(error)

        assert "Invalid data provided" in formatted
        assert "place_type" in formatted

    def test_plain_text_body_is_appended(self):
        client = GrampsWebAPIClient()
        error = _error_with(422, text="place_type missing")

        formatted = client._format_http_error(error)

        assert "place_type" in formatted

    def test_long_body_is_truncated(self):
        client = GrampsWebAPIClient()
        error = _error_with(422, text="x" * 5000)

        formatted = client._format_http_error(error)

        assert len(formatted) < 1000

    def test_empty_body_keeps_the_generic_message(self):
        client = GrampsWebAPIClient()
        error = _error_with(422, text="")

        formatted = client._format_http_error(error)

        assert formatted == "Invalid data provided."

    def test_detail_is_added_for_other_statuses_too(self):
        client = GrampsWebAPIClient()
        error = _error_with(409, json={"message": "user already exists"})

        formatted = client._format_http_error(error)

        assert "already exists" in formatted

    def test_unparseable_body_does_not_raise(self):
        client = GrampsWebAPIClient()
        error = _error_with(500, content=b"\xff\xfe not valid utf-8")

        formatted = client._format_http_error(error)

        assert "Server error" in formatted
```

`GrampsWebAPIClient()` constructs without contacting anything — it only builds
configuration. Confirm that by reading its `__init__` before running; if it does
reach out, call `_format_http_error` as an unbound method instead:
`GrampsWebAPIClient._format_http_error(None, error)`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_http_error_detail.py -v`
Expected: FAIL on the detail assertions. `test_empty_body_keeps_the_generic_message` passes already.

- [ ] **Step 3: Implement**

In `src/gramps_mcp/client.py`, the method currently reads:

```python
    def _format_http_error(self, error: httpx.HTTPStatusError) -> str:
        """Convert HTTP error to user-friendly message."""
        status_code = error.response.status_code

        if status_code == 401:
            return "Authentication failed. Please check your credentials."
        elif status_code == 403:
            return "Permission denied for this operation."
        elif status_code == 404:
            return "Record not found."
        elif status_code == 422:
            return "Invalid data provided."
        elif status_code >= 500:
            return "Server error. Please try again later."
        else:
            return f"Request failed with status {status_code}"
```

Add a module-level constant near the top of the file, beside the other
constants:

```python
# Reason: the server's explanation names the offending field, which the generic
# message cannot. Truncated because Gramps can echo the submitted payload, and
# that payload holds genealogy data about living people.
MAX_ERROR_DETAIL = 300
```

Then replace the method with:

```python
    def _extract_error_detail(self, error: httpx.HTTPStatusError) -> str:
        """
        Pull the server's explanation out of an error response.

        Args:
            error (httpx.HTTPStatusError): The failed response.

        Returns:
            str: The explanation, truncated, or an empty string when the body
                carries nothing useful.
        """
        try:
            body = error.response.json()
        except Exception:
            body = None

        detail = ""
        if isinstance(body, dict):
            for key in ("message", "error", "detail"):
                value = body.get(key)
                if isinstance(value, str) and value.strip():
                    detail = value.strip()
                    break
            if not detail:
                detail = str(body)
        elif body is not None:
            detail = str(body)
        else:
            try:
                detail = error.response.text.strip()
            except Exception:
                detail = ""

        if len(detail) > MAX_ERROR_DETAIL:
            detail = detail[:MAX_ERROR_DETAIL] + "..."
        return detail

    def _format_http_error(self, error: httpx.HTTPStatusError) -> str:
        """
        Convert an HTTP error into a message that names the cause.

        Args:
            error (httpx.HTTPStatusError): The failed response.

        Returns:
            str: A generic sentence categorising the failure, followed by the
                server's own explanation when it sent one.
        """
        status_code = error.response.status_code

        if status_code == 401:
            summary = "Authentication failed. Please check your credentials."
        elif status_code == 403:
            summary = "Permission denied for this operation."
        elif status_code == 404:
            summary = "Record not found."
        elif status_code == 422:
            summary = "Invalid data provided."
        elif status_code >= 500:
            summary = "Server error. Please try again later."
        else:
            summary = f"Request failed with status {status_code}"

        detail = self._extract_error_detail(error)
        if detail:
            return f"{summary} {detail}"
        return summary
```

Note `test_empty_body_keeps_the_generic_message` asserts exact equality with
`"Invalid data provided."`, so the summary must be returned unchanged when
there is no detail — no trailing space.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_http_error_detail.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 5: Check nothing matched on the old exact strings**

Run: `grep -rn "Invalid data provided\|Permission denied for this operation\|Record not found" tests/ src/`

Several places compare against these sentences. A test asserting equality will
now fail when a detail is appended; a test asserting `in` will still pass.
Report every such site you find and whether it still passes, rather than
changing assertions to fit.

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_client.py tests/test_user_tools.py -q`
Expected: no NEW failures.

- [ ] **Step 6: Commit**

```bash
rtk git add src/gramps_mcp/client.py tests/test_http_error_detail.py
uv run git commit -m "fix: keep the server's explanation in the error message"
```

---

### Task 3: Stop overriding the caller's sort

`get_recent_changes_tool` sets `arguments["sort"] = "-id"` unconditionally,
though `TransactionHistoryParams` documents `sort` as caller-supplied and says
`'id'` sorts ascending. So `recent_changes(sort="id")` silently returns
descending. The assignment also mutates the caller's dictionary.

**Files:**
- Modify: `src/gramps_mcp/tools/analysis.py:376-380`
- Test: `tests/test_recent_changes_sort.py` (new)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: no new names.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_recent_changes_sort.py`:

```python
"""
Integration tests for recent_changes sort handling.
"""

import pytest

from src.gramps_mcp.tools.analysis import get_recent_changes_tool


class TestRecentChangesSort:
    """The caller's sort choice must survive, and their dict must not change."""

    @pytest.mark.asyncio
    async def test_caller_dict_is_not_mutated(self):
        arguments = {"pagesize": 2}

        await get_recent_changes_tool(arguments)

        # Reason: the tool used to write its default into the caller's dict.
        assert arguments == {"pagesize": 2}

    @pytest.mark.asyncio
    async def test_explicit_sort_is_preserved(self):
        arguments = {"pagesize": 2, "sort": "id"}

        await get_recent_changes_tool(arguments)

        assert arguments["sort"] == "id"

    @pytest.mark.asyncio
    async def test_default_is_still_most_recent_first(self):
        result = await get_recent_changes_tool({"pagesize": 2})

        assert "error" not in result[0].text.lower()
```

The first two tests pin the observable contract without depending on the
server's ordering. The third confirms the default path still works.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_recent_changes_sort.py -v`
Expected: `test_caller_dict_is_not_mutated` FAILS — the dict gains a `sort` key. `test_explicit_sort_is_preserved` FAILS — the value becomes `-id`.

- [ ] **Step 3: Implement**

In `src/gramps_mcp/tools/analysis.py`, this block:

```python
        # Validate parameters and ensure we get most recent changes first
        if not arguments:
            arguments = {}
        arguments["sort"] = "-id"
        params = TransactionHistoryParams(**arguments)
```

becomes:

```python
        # Reason: most recent first is a sensible default, but the schema
        # documents sort as the caller's to choose, and writing into the
        # caller's dict is a side effect no other tool here has.
        arguments = dict(arguments or {})
        arguments.setdefault("sort", "-id")
        params = TransactionHistoryParams(**arguments)
```

- [ ] **Step 4: Run the tests**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_recent_changes_sort.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/tools/analysis.py tests/test_recent_changes_sort.py
uv run git commit -m "fix: honour the caller's sort and stop mutating their arguments"
```

---

### Task 4: Resolve an identifier through the API, not through prose

`get_type_tool` resolves a `gramps_id` by calling `find_type_tool`, which
returns text formatted for display, then searching that text for the first
bracketed substring. The resolution is coupled to a display format, and when
the identifier does not exist the function falls through to the literal string
`get_type_tool not yet implemented` — so asking for an absent person reports
that the tool does not exist.

**Files:**
- Modify: `src/gramps_mcp/tools/search_details.py:96-125`
- Test: `tests/test_get_type_resolution.py` (new)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: no new public names.

- [ ] **Step 1: Establish how to query for a handle**

Read how `find_type_tool` builds its call for `type="person"` and for
`type="family"` — which `ApiCalls` member and which parameter model. Run:

```bash
grep -n "def find_type_tool" -A 40 src/gramps_mcp/tools/search_basic.py
```

Record in your report the exact enum member and parameter class for both entity
types. The implementation below refers to them; substitute the real names. Do
not invent them.

Then confirm the GQL filter syntax for an exact identifier match by reading
`src/gramps_mcp/resources/gql-documentation.md`, and verify it live:

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
async def m():
    c = GrampsWebAPIClient(); t = get_settings().gramps_tree_id
    r = await c.make_api_call(api_call=ApiCalls.GET_PEOPLE, params={'gql': 'gramps_id=\"I0076\"'}, tree_id=t)
    print(type(r), len(r) if isinstance(r, list) else r)
    if isinstance(r, list) and r:
        print(r[0].get('gramps_id'), r[0].get('handle'))
asyncio.run(m())
"
```

`I0076` is a real person in this tree. If the call errors, adjust the params to
what the parameter model requires and say so in your report.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_get_type_resolution.py`:

```python
"""
Integration tests for resolving a gramps_id in get_type.
"""

import pytest

from src.gramps_mcp.tools.search_details import get_type_tool


class TestGetTypeResolution:
    """A gramps_id resolves through the API, and a missing one says so."""

    @pytest.mark.asyncio
    async def test_known_gramps_id_resolves(self):
        result = await get_type_tool({"type": "person", "gramps_id": "I0076"})
        text = result[0].text

        assert "not yet implemented" not in text
        assert "I0076" in text

    @pytest.mark.asyncio
    async def test_missing_gramps_id_says_not_found(self):
        result = await get_type_tool({"type": "person", "gramps_id": "I999999"})
        text = result[0].text

        # Reason: this used to report the tool as unimplemented, because the
        # regex found no bracket to scrape and both branches fell through.
        assert "not yet implemented" not in text
        assert "I999999" in text

    @pytest.mark.asyncio
    async def test_handle_still_works(self):
        by_id = await get_type_tool({"type": "person", "gramps_id": "I0076"})
        assert "not yet implemented" not in by_id[0].text
```

If `I0076` is not present when you run this, pick another real identifier from
the tree and use it consistently, noting the substitution in your report.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_get_type_resolution.py -v`
Expected: `test_missing_gramps_id_says_not_found` FAILS with the "not yet implemented" string present.

- [ ] **Step 4: Implement**

In `src/gramps_mcp/tools/search_details.py`, replace the resolution block and
the fallthrough. The current code is:

```python
    # If gramps_id provided but no handle, find the handle first
    if gramps_id and not handle:
        from .search_basic import find_type_tool

        search_result = await find_type_tool(
            {"type": entity_type, "gql": f'gramps_id="{gramps_id}"', "max_results": 1}
        )

        # Extract handle from search result
        search_text = search_result[0].text
        import re

        handle_match = re.search(r"\[([^\]]+)\]", search_text)
        if handle_match:
            handle = handle_match.group(1)
```

Replace it with a structured lookup, using the enum members and parameter
classes you recorded in Step 1:

```python
    # If gramps_id provided but no handle, resolve it through the API
    if gramps_id and not handle:
        # Reason: this used to regex-scrape the handle out of text formatted
        # for display, so any change to the rendering silently broke lookup by
        # identifier. Read the structured record instead.
        handle = await _resolve_gramps_id(entity_type, gramps_id)
        if handle is None:
            return [
                TextContent(
                    type="text",
                    text=(
                        f"No {entity_type} found with gramps_id {gramps_id}. "
                        f"Check the identifier, or use find_type to search."
                    ),
                )
            ]
```

Add the helper above `get_type_tool`, decorated so it receives a client the
same way the other tools in this file do — check how `get_type_tool`'s
neighbours obtain theirs before choosing:

```python
async def _resolve_gramps_id(entity_type: str, gramps_id: str) -> str | None:
    """
    Look up an entity's handle from its user-facing identifier.

    Args:
        entity_type (str): "person" or "family".
        gramps_id (str): The identifier shown in the Gramps interface.

    Returns:
        str | None: The handle, or None when no record matches.
    """
    ...
```

Fill the body with a `make_api_call` using the enum member for that entity
type, a GQL filter of `f'gramps_id="{gramps_id}"'`, and a read of
`result[0]["handle"]` guarded for an empty list. Return `None` when nothing
matches or the entity type is unsupported.

Finally, replace the trailing:

```python
    return [TextContent(type="text", text="get_type_tool not yet implemented")]
```

with a message that describes the real situation — an unsupported entity type,
or a missing handle — naming the type it was given. The string "not yet
implemented" must not remain anywhere in this file.

- [ ] **Step 5: Run the tests**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_get_type_resolution.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 6: Confirm the old string is gone**

Run: `grep -rn "not yet implemented" src/`
Expected: no output.

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_search_details.py -q`
Expected: no NEW failures.

- [ ] **Step 7: Commit**

```bash
rtk git add src/gramps_mcp/tools/search_details.py tests/test_get_type_resolution.py
uv run git commit -m "fix: resolve a gramps_id through the API instead of scraping prose"
```

---

### Task 5: Record the facts that keep being rediscovered

Three facts established during lots 1 and 2 are absent from `CLAUDE.md`, and
each was rediscovered more than once at the cost of a round trip. An
uncommitted edit to that file was also lost during lot 2, most likely to a
subagent's `git stash`.

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing.
- Produces: no code.

- [ ] **Step 1: Add the three facts**

`CLAUDE.md` has a "Testing & Reliability (TDD Approach)" section that already
discusses which tests need a live server. Extend it, and add to the AI
behaviour rules, so the file states:

1. **The URL override.** Live tests need `GRAMPS_API_URL=http://localhost:80`
   when run from the macOS host, because `.env` targets
   `host.docker.internal`, which only resolves inside the container. `.env`
   must not be edited and the override must not be committed.
2. **The `tree_stats` permission gap.** The account in `.env` holds the owner
   role, but `tree_stats` returns "Permission denied for this operation."
   regardless. Treat a failure there as an environment fact, not a regression.
3. **No `git stash`.** Comparing against main is done with
   `git show main:<path>`. An uncommitted change was lost to a stash cycle
   during lot 2.

Write them in the file's existing voice — short imperative bullets, bold lead-in
where the surrounding bullets use one. Do not restructure the file or reword
sections you are not adding to.

- [ ] **Step 2: Verify the claims before writing them**

Do not take them on trust. Confirm each:

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.tools.analysis import get_tree_info_tool
print(asyncio.run(get_tree_info_tool({}))[0].text[:120])
"
```

Expected: a permission error, confirming fact 2. If it succeeds, the fact has
changed — say so and adjust the wording rather than recording something false.

For fact 1, `grep GRAMPS_API_URL .env` shows the configured host without
printing any secret.

- [ ] **Step 3: Commit**

```bash
rtk git add CLAUDE.md
uv run git commit -m "docs: record the test URL override, the tree_stats gap, and the stash ban"
```

---

### Task 6: Verification and pull request

- [ ] **Step 1: Run the whole suite**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest -q`
Expected: the new test files pass. Categorise every failure as new-from-this-branch or pre-existing, and check rather than assume — `git show main:<path>` reads a file as it is on main. Do not check out main and do not stash. A regression reported as pre-existing is the worst possible outcome of this task; it happened once already on the lot 2 branch.

Pay particular attention to tests that compare against the exact error sentences Task 2 changed. A test asserting equality with `"Invalid data provided."` will now fail when a detail is appended. Report any such test rather than silently adjusting it.

- [ ] **Step 2: Type check**

Run: `uv run mypy src/gramps_mcp --ignore-missing-imports`
Expected: no new errors in the files this branch touched.

- [ ] **Step 3: Lint and format**

Run: `uv run ruff format src/gramps_mcp tests && uv run ruff check src/gramps_mcp tests`
Expected: all checks pass.

- [ ] **Step 4: Confirm the tree is untouched**

This lot writes nothing to the genealogy tree, so nothing should have been
created. Confirm:

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.tools.search_basic import find_anything_tool
print(asyncio.run(find_anything_tool({'query': 'Pytest'}))[0].text[:400])
"
```

Expected: no `Pytest*` object. If any appears, it came from an earlier lot's test run — say so rather than assuming it is yours.

- [ ] **Step 5: Commit any formatting changes**

```bash
rtk git add -A
uv run git commit -m "chore: format and lint quality lot 3"
```

Skip this step if ruff changed nothing. Do not create an empty commit.

- [ ] **Step 6: Push and open the pull request**

```bash
rtk git push -u origin fix/quality-lot3-ergonomics
rtk gh pr create --repo fjacquet/gramps-mcp --title "fix: quality lot 3 - ergonomics" --body "$(cat <<'BODY'
Fixes four defects where the server works but tells the caller something untrue, and records three project facts that kept being rediscovered.

- Search results report the real match count from `X-Total-Count` instead of the page length, so a truncated search no longer claims to be complete. The "showing N" branch, previously unreachable, now works.
- HTTP errors carry the server's own explanation, truncated, after the generic sentence. A 422 now names the field it rejected instead of saying only "Invalid data provided."
- `recent_changes` honours a caller-supplied `sort` instead of overwriting it, and no longer mutates the caller's dictionary.
- `get_type` resolves a `gramps_id` through the API rather than scraping a handle out of formatted prose, and an absent identifier reports that it was not found rather than claiming the tool is unimplemented.
- `CLAUDE.md` records the live-test URL override, the `tree_stats` permission gap, and the ban on `git stash`.

Behaviour changes: `recent_changes(sort="id")` now returns ascending order as documented; search results report a larger, truthful total; error messages now include a bounded fragment of the server's response.

Spec: `docs/superpowers/specs/2026-08-13-quality-lot3-ergonomics-design.md`

Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01PAZLxVasEXVDbriMRvGmDE
BODY
)"
```

**Do not merge the pull request and do not tag a release.** Both are the repository owner's decision, and the merge must use a merge commit rather than a squash.

---

## Self-Review

**Spec coverage:** All five items in the spec's scope table have a task — result totals (Task 1), error detail (Task 2), sort handling (Task 3), identifier resolution (Task 4), `CLAUDE.md` facts (Task 5). The spec's testing table maps onto Tasks 1 to 4; its accepted-risk section about changed sort order, larger totals and error-message exposure is surfaced in Task 6 Step 1.

**Placeholders:** Task 4 Step 4 leaves the helper's body to be filled from values the implementer records in Step 1, rather than inventing enum members and parameter classes I have not verified. That is deliberate and bounded: Step 1 names exactly what to record, the surrounding code is given in full, and the step says not to invent names. Every other code step is complete.

**Type consistency:** `_format_http_error` keeps its signature and gains `_extract_error_detail` alongside it, used only there. `_resolve_gramps_id(entity_type: str, gramps_id: str) -> str | None` is introduced and consumed within Task 4. `MAX_ERROR_DETAIL` is introduced in Task 2 and used only in that file. No task references a name another task did not define.

**Ordering note:** All five tasks are independent and may be run in any order. Task 2 is the only one whose change can affect another task's test output, through the error strings, which is why Task 6 Step 1 calls that out specifically.
