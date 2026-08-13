# Quality Lot 1 — Correctness and Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four correctness defects in the Gramps MCP server: the process-wide HTTP pool being torn down mid-flight, a crash when a save produces no change, a collection endpoint used where the item endpoint is meant, and a single dead handle discarding an entire person detail.

**Architecture:** Each defect is fixed in place, in the file that owns it, following a pattern that already exists elsewhere in the codebase. Nothing is restructured and no new module is introduced. The shared-client fix removes code rather than adding it: the `AuthManager` singleton keeps its `httpx.AsyncClient` for the process lifetime, which its own `client` property was already written to support.

**Tech Stack:** Python 3.13, httpx, pydantic v2, MCP Python SDK 2.0, pytest + pytest-asyncio, uv, ruff.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-08-13-quality-lot1-correctness-design.md`.
- Every command runs through uv: `uv run pytest`, `uv run git commit`.
- No mocks, no fixtures, no test clients. Tests hit the live Gramps Web server.
- Live tests need a URL override from the macOS host, because `.env` targets `host.docker.internal`, which only resolves inside the container: `GRAMPS_API_URL=http://localhost:80 uv run pytest ...`. Never edit `.env`, never commit the override.
- Never create a file longer than 500 lines. A pre-commit hook enforces this.
- No emojis anywhere in the code. A pre-commit hook enforces this.
- Google-style docstrings on every function.
- **One atomic commit per defect**, each carrying its fix and its test together, so a single correction can be read or reverted on its own.
- Work happens on the branch `fix/quality-lot1-correctness`, which already exists and holds the spec commit.
- No release tag. Lot 1 merges into `main` and waits for lots 2 to 4.
- Tests that write to the tree must clean up in a `finally` block. The target is a real genealogy tree, not a scratch database.

---

### Task 1: Stop tearing down the shared HTTP pool

`with_client`'s `finally` calls `client.close()`, which delegates to
`AuthManager.close()` — and `AuthManager` is a process-wide singleton owning
one `httpx.AsyncClient`. Every tool call therefore closes the connection pool
that other in-flight calls are using, and every nested call forces the caller
to rebuild the pool and re-authenticate.

**Files:**
- Modify: `src/gramps_mcp/tools/search_basic.py:74-75`
- Modify: `src/gramps_mcp/tools/data_management.py:144-145, 262-263, 394-395, 458-459`
- Modify: `src/gramps_mcp/tools/sourced_event.py:124-125`
- Test: `tests/test_client_lifecycle.py` (new)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the invariant that `AuthManager()._client` stays open across tool calls. Later tasks' tests rely on tool calls no longer closing the pool.

- [ ] **Step 1: Write the failing test**

Create `tests/test_client_lifecycle.py`:

```python
"""
Integration tests for HTTP client lifecycle against the real Gramps API.
"""

import asyncio

import pytest

from src.gramps_mcp.auth import AuthManager
from src.gramps_mcp.tools.analysis import get_tree_info_tool
from src.gramps_mcp.tools.records_tools import get_facts_tool


class TestSharedClientLifecycle:
    """The AuthManager singleton owns one client for the process lifetime."""

    @pytest.mark.asyncio
    async def test_pool_survives_a_tool_call(self):
        # Reason: a tool call must not close the pool other calls are using.
        # Read _client directly - the public `client` property recreates a
        # closed client on access, which would mask the very bug under test.
        await get_facts_tool({})
        auth = AuthManager()
        assert auth._client is not None
        assert not auth._client.is_closed

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls_all_succeed(self):
        results = await asyncio.gather(
            get_facts_tool({}),
            get_tree_info_tool({}),
            get_facts_tool({}),
            get_tree_info_tool({}),
        )
        for result in results:
            assert "error" not in result[0].text.lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_client_lifecycle.py -v`
Expected: `test_pool_survives_a_tool_call` FAILS on `assert not auth._client.is_closed`. `test_concurrent_tool_calls_all_succeed` may pass or fail depending on timing — that is the point, it is a race. Do not tune it to fail reliably; the first test is the deterministic one.

- [ ] **Step 3: Remove the close from `with_client`**

In `src/gramps_mcp/tools/search_basic.py`, the decorator's wrapper currently reads:

```python
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        client = GrampsWebAPIClient()
        try:
            return await func(client, *args, **kwargs)
        finally:
            await client.close()

    return wrapper
```

Replace it with:

```python
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Reason: the client delegates to the process-wide AuthManager
        # singleton, so closing it here would tear the connection pool out
        # from under any other tool call in flight, and force a fresh
        # authentication on every nested call. The singleton owns the
        # client for the lifetime of the process.
        client = GrampsWebAPIClient()
        return await func(client, *args, **kwargs)

    return wrapper
```

Update the decorator's docstring: the line "Client is automatically closed after function execution." is now false. Replace it with "The client is owned by the AuthManager singleton and is not closed here."

- [ ] **Step 4: Remove the four manual closes in `data_management.py`**

Each of the four sites has this shape:

```python
        finally:
            await client.close()
```

Delete the `finally:` block at each of lines 144-145, 262-263, 394-395 and 458-459, promoting the `try:` body to run without it. Where removing the `finally` leaves a `try:` with no `except` and no `finally`, remove the now-pointless `try:` and dedent its body. Do not otherwise change the control flow: the outer `except Exception` that wraps each tool must stay.

- [ ] **Step 5: Remove the manual close in `sourced_event.py`**

Same treatment at `src/gramps_mcp/tools/sourced_event.py:124-125`.

- [ ] **Step 6: Confirm no close sites remain**

Run: `grep -rn "await client.close()" src/gramps_mcp/`
Expected: no output.

`AuthManager.close()` itself stays — it is the legitimate shutdown path and is used by tests. Do not delete it.

- [ ] **Step 7: Run the tests**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_client_lifecycle.py -v`
Expected: PASS, 2 tests.

Then run the tools suites that exercise these files:
Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_data_management.py tests/test_search_basic.py tests/test_user_tools.py -q`
Expected: no NEW failures. `tests/test_data_management.py` has pre-existing failures unrelated to this change; note which ones fail and confirm they failed before your change by checking the same test on `main` with `git show main:tests/test_data_management.py`.

- [ ] **Step 8: Commit**

```bash
rtk git add src/gramps_mcp/tools/search_basic.py src/gramps_mcp/tools/data_management.py src/gramps_mcp/tools/sourced_event.py tests/test_client_lifecycle.py
uv run git commit -m "fix: stop closing the shared HTTP pool on every tool call"
```

---

### Task 2: Use the media item endpoint, not the collection

`person_handler.py:159` and `family_handler.py:194` call `ApiCalls.GET_MEDIA`
(`media/`) passing `handle=media_handle`.
`_build_url_with_substitution` silently drops kwargs with no matching
placeholder, so the handle is ignored, the whole media collection is fetched,
and the `list` that comes back makes the next `.get()` raise an
`AttributeError` swallowed by `except Exception: continue`. The result is that
the "Attached media" line never appears, and every media reference downloads
the full collection.

**Files:**
- Modify: `src/gramps_mcp/handlers/person_handler.py:159`
- Modify: `src/gramps_mcp/handlers/family_handler.py:194`
- Test: `tests/test_media_refs.py` (new)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `format_person` output containing an `Attached media:` line for a person that has media.

- [ ] **Step 1: Write the failing test**

The live tree has 908 people on one page, of which 14 carry media, so the test
finds a subject rather than creating one — it writes nothing.

Create `tests/test_media_refs.py`:

```python
"""
Integration tests for media reference rendering against the real Gramps API.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.handlers.person_handler import format_person
from src.gramps_mcp.models.api_calls import ApiCalls


async def _find_person_with_media(client, tree_id: str) -> dict | None:
    """
    Find a person in the live tree that carries at least one media reference.

    Args:
        client (GrampsWebAPIClient): Client to query with.
        tree_id (str): Family tree identifier.

    Returns:
        dict | None: The first person carrying media, or None if the tree
            has none.
    """
    people = await client.make_api_call(
        api_call=ApiCalls.GET_PEOPLE, params={"pagesize": 200}, tree_id=tree_id
    )
    for person in people if isinstance(people, list) else []:
        if person.get("media_list"):
            return person
    return None


class TestMediaReferences:
    """A person's attached media must be resolved and displayed."""

    @pytest.mark.asyncio
    async def test_person_media_line_is_rendered(self):
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id

        person = await _find_person_with_media(client, tree_id)
        assert person is not None, (
            "the live tree has no person carrying media - this test needs one"
        )

        result = await format_person(client, tree_id, person["handle"])

        # Reason: with the collection endpoint the lookup raised and was
        # swallowed, so this line was never emitted.
        assert "Attached media:" in result
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_media_refs.py -v`
Expected: FAIL on `assert "Attached media:" in result`.

- [ ] **Step 3: Fix both handlers**

In `src/gramps_mcp/handlers/person_handler.py`, inside the `media_list` loop:

```python
                        media_data = await client.make_api_call(
                            api_call=ApiCalls.GET_MEDIA,
                            tree_id=tree_id,
                            handle=media_handle,
                        )
```

becomes:

```python
                        media_data = await client.make_api_call(
                            api_call=ApiCalls.GET_MEDIA_ITEM,
                            tree_id=tree_id,
                            handle=media_handle,
                        )
```

Apply the identical change in `src/gramps_mcp/handlers/family_handler.py` at
line 194. Both loops are otherwise correct and must not be touched.

- [ ] **Step 4: Run the test**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_media_refs.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/handlers/person_handler.py src/gramps_mcp/handlers/family_handler.py tests/test_media_refs.py
uv run git commit -m "fix: resolve media refs via the item endpoint, not the collection"
```

---

### Task 3: One dead handle must not discard the whole person detail

In `person_detail_handler.py`, the media loop (264-273) and the note loop
(277-288) make unguarded `make_api_call`s, and the function has no `try/except`
of its own. A single dangling or private handle returns 404, raising
`GrampsAPIError`, which discards the entire person detail — relations,
timeline, citations — leaving only `Error: Record not found.`.
`family_detail_handler.py:196,211` already wraps the equivalent calls and
degrades gracefully; this task adopts that pattern.

**Files:**
- Modify: `src/gramps_mcp/handlers/person_detail_handler.py:264-288`
- Test: `tests/test_person_detail_resilience.py` (new)

**Interfaces:**
- Consumes: `format_person_detail` from `src.gramps_mcp.handlers.person_detail_handler`.
- Produces: `format_person_detail` returning the full detail even when a media or note handle cannot be resolved.

- [ ] **Step 1: Write the failing test**

The test creates a person, attaches a media object, deletes the media so the
reference dangles, then asks for the detail. It cleans up in `finally`.

Create `tests/test_person_detail_resilience.py`:

```python
"""
Integration tests for person detail degradation against the real Gramps API.
"""

import uuid

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.handlers.person_detail_handler import format_person_detail
from src.gramps_mcp.models.api_calls import ApiCalls


class TestPersonDetailResilience:
    """A dangling media reference must not destroy the whole detail."""

    @pytest.mark.asyncio
    async def test_dangling_media_ref_degrades_gracefully(self):
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id
        surname = f"Pytest{uuid.uuid4().hex[:8]}"
        person_handle = None
        media_handle = None

        try:
            media_result = await client.make_api_call(
                api_call=ApiCalls.POST_MEDIA,
                params={"desc": "pytest dangling ref", "path": "pytest-nonexistent"},
                tree_id=tree_id,
            )
            media_handle = media_result[0]["new"]["handle"]

            person_result = await client.make_api_call(
                api_call=ApiCalls.POST_PEOPLE,
                params={
                    "primary_name": {"first_name": "Dangling", "surname_list": [
                        {"surname": surname}
                    ]},
                    "media_list": [{"ref": media_handle}],
                },
                tree_id=tree_id,
            )
            person_handle = person_result[0]["new"]["handle"]

            # Delete the media, leaving the person's ref dangling.
            await client.make_api_call(
                api_call=ApiCalls.DELETE_MEDIA,
                tree_id=tree_id,
                handle=media_handle,
            )
            media_handle = None

            result = await format_person_detail(client, tree_id, person_handle)

            # Reason: the unguarded call used to abort the whole detail.
            assert "error" not in result.lower()
            assert surname in result
        finally:
            if person_handle:
                await client.make_api_call(
                    api_call=ApiCalls.DELETE_PERSON,
                    tree_id=tree_id,
                    handle=person_handle,
                )
            if media_handle:
                await client.make_api_call(
                    api_call=ApiCalls.DELETE_MEDIA,
                    tree_id=tree_id,
                    handle=media_handle,
                )
```

Before running, confirm the enum members used above exist with these exact
names: `grep -nE "POST_MEDIA|DELETE_MEDIA|POST_PEOPLE|DELETE_PERSON" src/gramps_mcp/models/api_calls.py`.
If a name differs, use the real one; do not invent one.

- [ ] **Step 2: Run the test to verify it fails**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_person_detail_resilience.py -v`
Expected: FAIL — the detail comes back as an error string, so either `"error" not in result.lower()` fails or the call raises.

- [ ] **Step 3: Guard both loops**

Replace the media section of `format_person_detail`:

```python
    # Attached media section
    result += "\nAttached media:\n"
    media_list = person_data.get("media_list", [])
    for media_ref in media_list:
        media_handle = media_ref.get("ref", "")
        if media_handle:
            media_data = await client.make_api_call(
                ApiCalls.GET_MEDIA_ITEM, tree_id=tree_id, handle=media_handle
            )
            media_desc = media_data.get("desc", "")
            media_id = media_data.get("gramps_id", "")
            result += f"- {media_desc} ({media_id})\n"
```

with the guarded form, matching `family_detail_handler.py`:

```python
    # Attached media section
    result += "\nAttached media:\n"
    media_list = person_data.get("media_list", [])
    for media_ref in media_list:
        media_handle = media_ref.get("ref", "")
        if media_handle:
            # Reason: a dangling or private handle 404s. Losing one media
            # line is acceptable; losing the whole person detail is not.
            try:
                media_data = await client.make_api_call(
                    ApiCalls.GET_MEDIA_ITEM, tree_id=tree_id, handle=media_handle
                )
                media_desc = media_data.get("desc", "")
                media_id = media_data.get("gramps_id", "")
                result += f"- {media_desc} ({media_id})\n"
            except Exception:
                result += f"- Media ({media_handle})\n"
```

Then replace the notes section:

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

with:

```python
    # Attached notes section
    result += "\nAttached notes:\n"
    note_list = person_data.get("note_list", [])
    for note_handle in note_list:
        try:
            note_data = await client.make_api_call(
                ApiCalls.GET_NOTE, tree_id=tree_id, handle=note_handle
            )
            note_type = note_data.get("type", "")
            note_id = note_data.get("gramps_id", "")
            # Reason: "text" can be present but JSON null, in which case
            # .get("text", {}) returns None and chaining would raise.
            note_full_text = (note_data.get("text") or {}).get("string", "") or ""
            note_text = note_full_text[:50]
            if len(note_full_text) > 50:
                note_text += "..."
            result += f"- {note_type}: {note_text} ({note_id})\n"
        except Exception:
            result += f"- Note ({note_handle})\n"
```

- [ ] **Step 4: Run the test**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_person_detail_resilience.py -v`
Expected: PASS.

- [ ] **Step 5: Confirm the tree is clean**

Run:

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.tools.search_basic import find_anything_tool
print(asyncio.run(find_anything_tool({'query': 'Pytest'}))[0].text[:500])
"
```

Expected: no `Pytest<hex>` person remains. If one does, the cleanup failed — say so and remove it before continuing.

- [ ] **Step 6: Commit**

```bash
rtk git add src/gramps_mcp/handlers/person_detail_handler.py tests/test_person_detail_resilience.py
uv run git commit -m "fix: degrade gracefully on dangling media and note refs in person detail"
```

---

### Task 4: A save that changes nothing must not report failure

`_format_save_response` reads `entity_data.get("handle", "N/A")` at
`data_management.py:159`, before its `try` at 162. `_extract_entity_data`
returns `None` for a falsy response (line 67-68). If a Gramps PUT with
unchanged data returns `[]`, updating an entity with identical data raises
`AttributeError` and reports failure for a save that succeeded.
`sourced_event.py:69` does `source_data["handle"]` on the same `None`.

**This task begins with verifying its own premise.** The spec flags it as
unconfirmed.

**Files:**
- Modify: `src/gramps_mcp/tools/data_management.py:155-161`
- Modify: `src/gramps_mcp/tools/sourced_event.py:68-69`
- Test: `tests/test_save_no_change.py` (new)

**Interfaces:**
- Consumes: `_extract_entity_data`, `_format_save_response` from `src.gramps_mcp.tools.data_management`.
- Produces: no new public names.

- [ ] **Step 1: Verify the premise before writing anything**

Create a throwaway place, then PUT it again with identical data, and print what
the API returns:

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio, uuid
from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
async def m():
    c = GrampsWebAPIClient(); t = get_settings().gramps_tree_id
    name = f'PytestPlace{uuid.uuid4().hex[:8]}'
    created = await c.make_api_call(api_call=ApiCalls.POST_PLACES, params={'name': {'value': name}}, tree_id=t)
    h = created[0]['new']['handle']
    try:
        again = await c.make_api_call(api_call=ApiCalls.PUT_PLACE, params={'name': {'value': name}}, tree_id=t, handle=h)
        print('PUT unchanged returned:', repr(again))
    finally:
        await c.make_api_call(api_call=ApiCalls.DELETE_PLACE, tree_id=t, handle=h)
        print('cleaned up', h)
asyncio.run(m())
"
```

Confirm the enum names first with
`grep -nE "POST_PLACES|PUT_PLACE|DELETE_PLACE" src/gramps_mcp/models/api_calls.py`.

**If the PUT returns `[]` or another falsy value:** the defect is real, continue to Step 2.

**If it returns a populated object:** the defect is theoretical. Stop, report
that the premise did not hold, and skip Tasks 4's remaining steps entirely.
Do not invent a different way to reach the crash. Report BLOCKED with the
observed output so the controller can rule.

- [ ] **Step 2: Write the failing test**

Create `tests/test_save_no_change.py`:

```python
"""
Integration tests for saving unchanged data against the real Gramps API.
"""

import uuid

import pytest

from src.gramps_mcp.tools.data_management import create_place_tool


class TestSaveWithNoChange:
    """Re-saving identical data is a success, not a failure."""

    @pytest.mark.asyncio
    async def test_resaving_identical_place_succeeds(self):
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id
        name = f"PytestPlace{uuid.uuid4().hex[:8]}"
        handle = None

        try:
            first = await create_place_tool({"name": name})
            assert "error" not in first[0].text.lower()

            found = await client.make_api_call(
                api_call=ApiCalls.GET_PLACES, params={"pagesize": 200}, tree_id=tree_id
            )
            for place in found if isinstance(found, list) else []:
                if place.get("name", {}).get("value") == name:
                    handle = place["handle"]
                    break

            # Reason: the second save changes nothing, so Gramps returns an
            # empty payload and the formatter used to dereference None.
            second = await create_place_tool({"name": name})
            assert "error" not in second[0].text.lower()
        finally:
            if handle:
                await client.make_api_call(
                    api_call=ApiCalls.DELETE_PLACE, tree_id=tree_id, handle=handle
                )
```

Add the imports this test needs alongside the others:

```python
from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
```

Check `create_place_tool`'s real parameter names first with
`grep -n "class PlaceSaveParams" -A 20 src/gramps_mcp/models/parameters/place_params.py`,
and use them. If creating a place by name alone is not supported, use whatever
minimal valid payload the model requires. Confirm `GET_PLACES` and
`DELETE_PLACE` exist under those names in the enum; if the place name is not
stored under `name.value`, adjust the lookup to match what the API returns.

- [ ] **Step 3: Run the test to verify it fails**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_save_no_change.py -v`
Expected: FAIL — the second save reports an error mentioning `NoneType`.

- [ ] **Step 4: Fix `_format_save_response`**

Change its signature to accept `None` and handle it before dereferencing:

```python
async def _format_save_response(
    client: GrampsWebAPIClient,
    entity_data: dict | None,
    entity_type: str,
    operation: str,
    tree_id: str,
) -> str:
    """Format successful save operation response using appropriate format handler."""
    # Reason: Gramps returns an empty payload when a PUT changes nothing.
    # The save succeeded; there is simply no entity echoed back.
    if not entity_data:
        return f"Successfully {operation} {entity_type}: no changes were needed.\n"

    handle = entity_data.get("handle", "N/A")
    gramps_id = entity_data.get("gramps_id", "N/A")
```

The rest of the function is unchanged.

- [ ] **Step 5: Fix `sourced_event.py`**

At `src/gramps_mcp/tools/sourced_event.py:68-69`:

```python
            source_data = _extract_entity_data(source_result)
            source_handle = source_data["handle"]
```

becomes:

```python
            source_data = _extract_entity_data(source_result)
            # Reason: a falsy API response would make the subscript raise a
            # TypeError, losing the source that was in fact created.
            if not source_data or not source_data.get("handle"):
                raise GrampsAPIError(
                    "Source creation returned no handle; cannot build the citation."
                )
            source_handle = source_data["handle"]
```

Confirm `GrampsAPIError` is already imported in this file; if not, add
`from ..client import GrampsAPIError` alongside the existing imports.

- [ ] **Step 6: Run the test**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_save_no_change.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add src/gramps_mcp/tools/data_management.py src/gramps_mcp/tools/sourced_event.py tests/test_save_no_change.py
uv run git commit -m "fix: treat a no-change save as the success it is"
```

---

### Task 5: Full verification and pull request

- [ ] **Step 1: Run the whole suite**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest -q`
Expected: the four new test files pass. Pre-existing failures remain — categorise every failure as new-from-this-branch or pre-existing, and check the pre-existing ones against `main` with `git show main:<path>` rather than assuming. A regression reported as pre-existing is the worst possible outcome of this task.

Known pre-existing failures, not yours: `tests/test_server.py` has three (one `serverInfo` versus `server_info` SDK 2.x rename, two comparing the tool count against a stale running container), plus failures in `test_analysis.py`, `test_data_management.py`, `test_parameter_alignment.py` and `test_search_basic.py` concerning `media_path` and live-tree state.

- [ ] **Step 2: Type check**

Run: `uv run mypy src/gramps_mcp --ignore-missing-imports`
Expected: no new errors in the files this branch touched.

- [ ] **Step 3: Lint and format**

Run: `uv run ruff format src/gramps_mcp tests && uv run ruff check src/gramps_mcp tests`
Expected: all checks pass.

- [ ] **Step 4: Confirm the tree is clean**

Run:

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.tools.search_basic import find_anything_tool
print(asyncio.run(find_anything_tool({'query': 'Pytest'}))[0].text[:800])
"
```

Expected: no `Pytest*` person or place remains. If any does, remove it and say so.

- [ ] **Step 5: Commit any formatting changes**

```bash
rtk git add -A
uv run git commit -m "chore: format and lint quality lot 1"
```

Skip this step entirely if ruff changed nothing. Do not create an empty commit.

- [ ] **Step 6: Push and open the pull request**

```bash
rtk git push -u origin fix/quality-lot1-correctness
rtk gh pr create --repo fjacquet/gramps-mcp --title "fix: quality lot 1 - correctness and stability" --body "$(cat <<'BODY'
Fixes four correctness defects found by a full review of `src/gramps_mcp`.

- The `with_client` decorator closed the process-wide HTTP pool on every tool call, tearing it out from under concurrent calls and forcing re-authentication on nested ones.
- A save that produced no change crashed the response formatter and reported failure for a save that succeeded.
- `person_handler` and `family_handler` fetched the whole media collection instead of the referenced item, so the "Attached media" line never appeared.
- A single dangling media or note handle discarded an entire person detail.

Each commit carries one fix and its test. No release tag: lots 2 to 4 follow.

Spec: `docs/superpowers/specs/2026-08-13-quality-lot1-correctness-design.md`

Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01PAZLxVasEXVDbriMRvGmDE
BODY
)"
```

**Do not merge the pull request and do not tag a release.** Both are the repository owner's decision.

---

## Self-Review

**Spec coverage:** All four defects in the spec's scope table have a task — shared pool (Task 1, all six close sites), no-change save (Task 4, both `data_management` and `sourced_event`), media endpoint (Task 2, both handlers), dead handle (Task 3, both loops plus the null-`text` guard). The spec's testing table maps one-to-one onto Tasks 1-4. The spec's premise caveat about the no-change save is Task 4 Step 1, with an explicit instruction to stop rather than work around it.

**Placeholders:** None. Every code step shows the before and after text. Three steps ask the implementer to confirm real enum or field names before use rather than trusting this document — that is verification, not a placeholder, and each says what to do if the name differs.

**Type consistency:** `_format_save_response`'s `entity_data` parameter widens to `dict | None` in Task 4 and no other task calls it. `format_person`, `format_person_detail` and `find_anything_tool` are used with the signatures they already have in the codebase. `ApiCalls` members used in tests are each gated behind a grep check because this plan asserts their names from the enum rather than from the API docs.

**Ordering note:** Task 1 lands first because removing the pool teardown makes the later tests less prone to incidental connection errors. Tasks 2, 3 and 4 are independent of each other and may be reordered without consequence.
