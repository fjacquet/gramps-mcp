# Destructive Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the MCP server parity with the Gramps Web UI for destructive
operations: delete a record, merge two records, remove one element from a list,
and undo a transaction.

**Architecture:** Four tools registered in `TOOL_REGISTRY`, dispatching on a
`type` parameter the way `find_type` and `get_type` already do. All decision
logic lives in one pure module (`src/gramps_mcp/destructive.py`) so it is
unit-testable with no server, following the precedent of `merge.py`. Deletion
refuses while backlinks exist unless `force=true`; the refusal message carries
the information a dry run would have.

**Tech Stack:** Python 3.12+, pydantic, httpx, MCP Python SDK 2.x, pytest +
pytest-asyncio, uv for everything.

**Spec:** `docs/superpowers/specs/2026-08-14-delete-merge-detach-design.md`

**Branch:** `feat/destructive-operations` (already exists, spec committed there)

## Global Constraints

- Run everything through `uv`: `uv run pytest`, `uv run mypy`, `uv run git commit`.
- Files are capped at **500 lines**, enforced by a pre-commit hook over the
  whole tree, tests included.
- **No emojis** anywhere, enforced by a pre-commit hook.
- Every new Python file needs the AGPL copyright header. Copy the 15-line block
  verbatim from the top of `src/gramps_mcp/merge.py`.
- Google-style docstrings on every function.
- Write-path parameter models extend `StrictModel` (from
  `models/parameters/base_params.py`), never bare `BaseModel`. `StrictModel`
  refuses unknown keys; `BaseModel` silently drops them, which is the bug
  behind issues #16 and #17.
- Tests run against a **live production genealogy tree**. Live tests need
  `GRAMPS_API_URL=http://localhost:80` as an env override on the macOS host
  (`.env` points at `host.docker.internal`, which only resolves inside the
  container). Do not edit `.env`.
- Server-dependent test modules carry `pytestmark = pytest.mark.integration`.
  The offline selection `uv run pytest -m "not integration"` must stay green.
- No mocks of the Gramps API (ADR 0002). Only the transport seam may be
  replaced, as `tests/test_client_merge.py` does. Assertions read the output of
  the code under test, never a stub's call arguments.

---

### Task 1: Pure decision logic

**Files:**
- Create: `src/gramps_mcp/destructive.py`
- Test: `tests/test_destructive_logic.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `TYPE_ENDPOINTS: dict[str, TypeEndpoints]` where `TypeEndpoints` is a
    `NamedTuple` with fields `get: ApiCalls`, `delete: ApiCalls`,
    `merge: ApiCalls | None`.
  - `should_refuse_delete(backlinks: dict[str, list[str]]) -> str | None`
  - `remove_from_list(obj: dict, list_name: str, ref_handle: str) -> dict`

This module is pure: no I/O, no client, no async. That is what makes it
testable offline, and it is why the `ApiCalls` members (plain enum data) may be
referenced here.

- [ ] **Step 1: Write the failing test**

Create `tests/test_destructive_logic.py`. No `pytestmark` — this file must run
in the offline selection.

```python
"""Unit tests for the pure destructive-operation logic."""

import pytest

from src.gramps_mcp.destructive import (
    TYPE_ENDPOINTS,
    remove_from_list,
    should_refuse_delete,
)


class TestShouldRefuseDelete:
    def test_no_backlinks_allows_delete(self):
        assert should_refuse_delete({}) is None

    def test_empty_backlink_lists_allow_delete(self):
        assert should_refuse_delete({"person": [], "family": []}) is None

    def test_backlinks_produce_a_refusal_naming_types_and_counts(self):
        refusal = should_refuse_delete({"person": ["h1", "h2"], "family": ["h3"]})
        assert refusal is not None
        assert "2 person" in refusal
        assert "1 family" in refusal
        assert "force=true" in refusal

    def test_refusal_lists_the_referencing_handles(self):
        refusal = should_refuse_delete({"citation": ["abc123"]})
        assert "abc123" in refusal


class TestRemoveFromList:
    def test_removes_a_plain_string_handle(self):
        obj = {"note_list": ["a", "b", "c"]}
        assert remove_from_list(obj, "note_list", "b") == {"note_list": ["a", "c"]}

    def test_removes_a_ref_dict_by_ref_key(self):
        obj = {"event_ref_list": [{"ref": "a", "role": "Primary"}, {"ref": "b"}]}
        result = remove_from_list(obj, "event_ref_list", "a")
        assert result["event_ref_list"] == [{"ref": "b"}]

    def test_does_not_mutate_the_input(self):
        obj = {"note_list": ["a", "b"]}
        remove_from_list(obj, "note_list", "a")
        assert obj == {"note_list": ["a", "b"]}

    def test_leaves_other_keys_untouched(self):
        obj = {"note_list": ["a"], "gramps_id": "I0001", "media_list": [{"ref": "m"}]}
        result = remove_from_list(obj, "note_list", "a")
        assert result["gramps_id"] == "I0001"
        assert result["media_list"] == [{"ref": "m"}]

    def test_absent_handle_raises(self):
        with pytest.raises(ValueError, match="not present"):
            remove_from_list({"note_list": ["a"]}, "note_list", "zzz")

    def test_absent_list_raises(self):
        with pytest.raises(ValueError, match="no list"):
            remove_from_list({"note_list": ["a"]}, "nope_list", "a")


class TestTypeEndpoints:
    def test_covers_the_nine_record_types_plus_tag(self):
        assert set(TYPE_ENDPOINTS) == {
            "person", "family", "event", "place", "source",
            "citation", "repository", "media", "note", "tag",
        }

    def test_tag_is_deletable_but_not_mergeable(self):
        assert TYPE_ENDPOINTS["tag"].delete is not None
        assert TYPE_ENDPOINTS["tag"].merge is None

    def test_every_non_tag_type_is_mergeable(self):
        for name, endpoints in TYPE_ENDPOINTS.items():
            if name != "tag":
                assert endpoints.merge is not None, name

    def test_every_type_has_get_put_and_delete(self):
        for name, endpoints in TYPE_ENDPOINTS.items():
            assert endpoints.get is not None, name
            assert endpoints.put is not None, name
            assert endpoints.delete is not None, name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_destructive_logic.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'src.gramps_mcp.destructive'`

- [ ] **Step 3: Write minimal implementation**

Create `src/gramps_mcp/destructive.py`. Start with the 15-line AGPL header
copied from `merge.py`, then:

```python
"""
Pure decision logic for destructive operations.

Deleting a record, and removing one element from a list, both need a decision
made before any request is sent: may this deletion proceed, and what does the
list look like afterwards. That logic lives here as pure, side-effect-free
functions so it can be unit-tested without a live server, exactly as
merge.py does for PUT merging.
"""

from typing import NamedTuple

from .models.api_calls import ApiCalls


class TypeEndpoints(NamedTuple):
    """The API calls that serve one record type."""

    get: ApiCalls
    put: ApiCalls
    delete: ApiCalls
    merge: ApiCalls | None


TYPE_ENDPOINTS: dict[str, TypeEndpoints] = {
    "person": TypeEndpoints(
        ApiCalls.GET_PERSON,
        ApiCalls.PUT_PERSON,
        ApiCalls.DELETE_PERSON,
        ApiCalls.MERGE_PERSON,
    ),
    "family": TypeEndpoints(
        ApiCalls.GET_FAMILY,
        ApiCalls.PUT_FAMILY,
        ApiCalls.DELETE_FAMILY,
        ApiCalls.MERGE_FAMILY,
    ),
    "event": TypeEndpoints(
        ApiCalls.GET_EVENT,
        ApiCalls.PUT_EVENT,
        ApiCalls.DELETE_EVENT,
        ApiCalls.MERGE_EVENT,
    ),
    "place": TypeEndpoints(
        ApiCalls.GET_PLACE,
        ApiCalls.PUT_PLACE,
        ApiCalls.DELETE_PLACE,
        ApiCalls.MERGE_PLACE,
    ),
    "source": TypeEndpoints(
        ApiCalls.GET_SOURCE,
        ApiCalls.PUT_SOURCE,
        ApiCalls.DELETE_SOURCE,
        ApiCalls.MERGE_SOURCE,
    ),
    "citation": TypeEndpoints(
        ApiCalls.GET_CITATION,
        ApiCalls.PUT_CITATION,
        ApiCalls.DELETE_CITATION,
        ApiCalls.MERGE_CITATION,
    ),
    "repository": TypeEndpoints(
        ApiCalls.GET_REPOSITORY,
        ApiCalls.PUT_REPOSITORY,
        ApiCalls.DELETE_REPOSITORY,
        ApiCalls.MERGE_REPOSITORY,
    ),
    "media": TypeEndpoints(
        ApiCalls.GET_MEDIA_ITEM,
        ApiCalls.PUT_MEDIA_ITEM,
        ApiCalls.DELETE_MEDIA_ITEM,
        ApiCalls.MERGE_MEDIA,
    ),
    "note": TypeEndpoints(
        ApiCalls.GET_NOTE,
        ApiCalls.PUT_NOTE,
        ApiCalls.DELETE_NOTE,
        ApiCalls.MERGE_NOTE,
    ),
    # Reason: tags are deletable but Gramps Web offers no tag merge endpoint.
    "tag": TypeEndpoints(
        ApiCalls.GET_TAG, ApiCalls.PUT_TAG, ApiCalls.DELETE_TAG, None
    ),
}

MAX_LISTED_BACKLINKS = 20


def should_refuse_delete(backlinks: dict[str, list[str]]) -> str | None:
    """
    Decide whether a deletion must be refused because references remain.

    Args:
        backlinks (dict): Mapping of object type to referencing handles, as
            returned by GET {type}/{handle}?backlinks=1.

    Returns:
        str | None: A refusal message naming what still references the record,
            or None when nothing does and the deletion may proceed.
    """
    present = {kind: handles for kind, handles in backlinks.items() if handles}
    if not present:
        return None

    lines = []
    for kind in sorted(present):
        handles = present[kind]
        shown = handles[:MAX_LISTED_BACKLINKS]
        suffix = "" if len(handles) <= MAX_LISTED_BACKLINKS else ", ..."
        lines.append(f"  {len(handles)} {kind}: {', '.join(shown)}{suffix}")

    total = sum(len(h) for h in present.values())
    return (
        f"Refused: {total} object(s) still reference this record.\n"
        + "\n".join(lines)
        + "\nDeleting it would sever those references. Detach them first with "
        "detach_reference, or pass force=true to delete anyway."
    )


def remove_from_list(obj: dict, list_name: str, ref_handle: str) -> dict:
    """
    Return a copy of obj with ref_handle removed from the named list.

    Handles both shapes Gramps uses: a list of plain handle strings (note_list,
    tag_list) and a list of reference dicts carrying a "ref" key
    (event_ref_list, media_list, child_ref_list).

    Args:
        obj (dict): The record as returned by the API.
        list_name (str): Name of the list field to edit.
        ref_handle (str): The handle to remove.

    Returns:
        dict: A new record with the element removed. The input is not mutated.

    Raises:
        ValueError: If the record has no such list, or the handle is absent
            from it. Both are refused rather than silently succeeding.
    """
    if list_name not in obj or not isinstance(obj[list_name], list):
        raise ValueError(f"Record has no list named '{list_name}'")

    current = obj[list_name]

    def matches(item: object) -> bool:
        if isinstance(item, dict):
            return item.get("ref") == ref_handle
        return item == ref_handle

    remaining = [item for item in current if not matches(item)]
    if len(remaining) == len(current):
        raise ValueError(f"Handle '{ref_handle}' is not present in '{list_name}'")

    return {**obj, list_name: remaining}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_destructive_logic.py -v`
Expected: FAIL still, on `AttributeError: MERGE_PERSON` — the enum members do
not exist yet. That is expected and Task 2 adds them. To confirm the rest is
sound, temporarily run only the two classes that do not touch the enum:

Run: `uv run pytest tests/test_destructive_logic.py::TestShouldRefuseDelete tests/test_destructive_logic.py::TestRemoveFromList -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
uv run git add src/gramps_mcp/destructive.py tests/test_destructive_logic.py
uv run git commit -m "feat: pure decision logic for destructive operations"
```

---

### Task 2: Merge and undo API endpoints

**Files:**
- Modify: `src/gramps_mcp/models/api_calls.py`
- Modify: `src/gramps_mcp/models/api_mapping.py`
- Test: `tests/test_destructive_logic.py` (the `TestTypeEndpoints` class from
  Task 1 starts passing here)

**Interfaces:**
- Consumes: `TYPE_ENDPOINTS` from Task 1, which already names these members.
- Produces: `ApiCalls.MERGE_PERSON`, `MERGE_FAMILY`, `MERGE_EVENT`,
  `MERGE_PLACE`, `MERGE_SOURCE`, `MERGE_CITATION`, `MERGE_REPOSITORY`,
  `MERGE_MEDIA`, `MERGE_NOTE`, `POST_TRANSACTION_UNDO`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_destructive_logic.py`:

```python
class TestMergeAndUndoEndpoints:
    def test_merge_person_endpoint_shape(self):
        from src.gramps_mcp.models.api_calls import ApiCalls

        assert ApiCalls.MERGE_PERSON.method == "POST"
        assert (
            ApiCalls.MERGE_PERSON.endpoint
            == "people/{phoenix_handle}/merge/{titanic_handle}"
        )

    def test_every_merge_call_is_a_post_with_both_handles(self):
        from src.gramps_mcp.models.api_calls import ApiCalls

        merges = [c for c in ApiCalls if c.name.startswith("MERGE_")]
        assert len(merges) == 9
        for call in merges:
            assert call.method == "POST", call.name
            assert "{phoenix_handle}" in call.endpoint, call.name
            assert "{titanic_handle}" in call.endpoint, call.name

    def test_undo_endpoint_shape(self):
        from src.gramps_mcp.models.api_calls import ApiCalls

        assert ApiCalls.POST_TRANSACTION_UNDO.method == "POST"
        assert (
            ApiCalls.POST_TRANSACTION_UNDO.endpoint
            == "transactions/history/{transaction_id}/undo"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_destructive_logic.py -v`
Expected: FAIL with `AttributeError: MERGE_PERSON`

- [ ] **Step 3: Write minimal implementation**

In `src/gramps_mcp/models/api_calls.py`, add one merge member next to each
type's existing block (beside `DELETE_PERSON` at line 32, `DELETE_FAMILY` at
41, and so on):

```python
    MERGE_PERSON = ("POST", "people/{phoenix_handle}/merge/{titanic_handle}")
    MERGE_FAMILY = ("POST", "families/{phoenix_handle}/merge/{titanic_handle}")
    MERGE_EVENT = ("POST", "events/{phoenix_handle}/merge/{titanic_handle}")
    MERGE_PLACE = ("POST", "places/{phoenix_handle}/merge/{titanic_handle}")
    MERGE_SOURCE = ("POST", "sources/{phoenix_handle}/merge/{titanic_handle}")
    MERGE_CITATION = ("POST", "citations/{phoenix_handle}/merge/{titanic_handle}")
    MERGE_REPOSITORY = (
        "POST",
        "repositories/{phoenix_handle}/merge/{titanic_handle}",
    )
    MERGE_MEDIA = ("POST", "media/{phoenix_handle}/merge/{titanic_handle}")
    MERGE_NOTE = ("POST", "notes/{phoenix_handle}/merge/{titanic_handle}")
```

And in the transactions block, next to `GET_TRANSACTIONS_HISTORY` (line 122):

```python
    # Reason: the server reads this endpoint's only optional argument
    # (message) from the query string, while make_api_call sends a JSON body
    # for POST. No parameter model is mapped, so params stays None and the
    # server applies its default message of "Undo".
    POST_TRANSACTION_UNDO = ("POST", "transactions/history/{transaction_id}/undo")
```

In `src/gramps_mcp/models/api_mapping.py`, beside the existing `DELETE_*`
entries around lines 71-131, add:

```python
    ApiCalls.MERGE_PERSON: None,  # Handles travel in the URL
    ApiCalls.MERGE_FAMILY: None,  # Handles travel in the URL
    ApiCalls.MERGE_EVENT: None,  # Handles travel in the URL
    ApiCalls.MERGE_PLACE: None,  # Handles travel in the URL
    ApiCalls.MERGE_SOURCE: None,  # Handles travel in the URL
    ApiCalls.MERGE_CITATION: None,  # Handles travel in the URL
    ApiCalls.MERGE_REPOSITORY: None,  # Handles travel in the URL
    ApiCalls.MERGE_MEDIA: None,  # Handles travel in the URL
    ApiCalls.MERGE_NOTE: None,  # Handles travel in the URL
    ApiCalls.POST_TRANSACTION_UNDO: None,  # transaction_id travels in the URL
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_destructive_logic.py -v`
Expected: PASS, all classes including `TestTypeEndpoints`

Run: `uv run mypy src/gramps_mcp --ignore-missing-imports`
Expected: no new errors

- [ ] **Step 5: Commit**

```bash
uv run git add src/gramps_mcp/models/api_calls.py src/gramps_mcp/models/api_mapping.py tests/test_destructive_logic.py
uv run git commit -m "feat: declare merge and transaction-undo endpoints"
```

---

### Task 3: `delete_type` tool

**Files:**
- Create: `src/gramps_mcp/models/parameters/destructive_params.py`
- Create: `src/gramps_mcp/tools/destructive.py`
- Modify: `src/gramps_mcp/server.py` (imports, and `TOOL_REGISTRY` before its
  closing brace at line 270)
- Test: `tests/test_destructive_delete.py`

**Interfaces:**
- Consumes: `TYPE_ENDPOINTS`, `should_refuse_delete` (Task 1); the `ApiCalls`
  members (Task 2).
- Produces:
  - `DeleteTypeParams` with fields `type: RecordType`, `handle: str | None`,
    `gramps_id: str | None`, `force: bool = False`
  - `RecordType = Literal["person", "family", "event", "place", "source",
    "citation", "repository", "media", "note", "tag"]`
  - `delete_type_tool(arguments: dict) -> list[TextContent]`
  - `resolve_target_handle(client, tree_id, obj_type, handle, gramps_id) -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_destructive_delete.py`. This file mixes an offline class and
a live class, so mark only the live one.

```python
"""Tests for the delete_type tool."""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.tools.destructive import delete_type_tool


class TestDeleteRefusal:
    """Offline: the refusal path, exercised through the transport seam."""

    async def test_refuses_when_backlinks_exist_and_force_is_unset(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.return_value = {
                "handle": "h1",
                "gramps_id": "N0001",
                "backlinks": {"person": ["p1", "p2"]},
            }
            result = await delete_type_tool(
                {"type": "note", "handle": "h1", "force": False}
            )

        text = result[0].text
        assert "Refused" in text
        assert "2 person" in text
        assert "force=true" in text

    async def test_deletes_when_no_backlinks(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.return_value = {"handle": "h1", "gramps_id": "N0001", "backlinks": {}}
            result = await delete_type_tool({"type": "note", "handle": "h1"})

        assert "Deleted" in result[0].text
        assert "N0001" in result[0].text

    async def test_rejects_an_unknown_type(self):
        result = await delete_type_tool({"type": "banana", "handle": "h1"})
        assert "Error" in result[0].text

    async def test_requires_handle_or_gramps_id(self):
        result = await delete_type_tool({"type": "note"})
        assert "Error" in result[0].text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_destructive_delete.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'src.gramps_mcp.tools.destructive'`

- [ ] **Step 3: Write minimal implementation**

Create `src/gramps_mcp/models/parameters/destructive_params.py` (AGPL header
first):

```python
"""Parameter models for the destructive operation tools."""

from typing import Literal

from pydantic import Field

from .base_params import StrictModel

RecordType = Literal[
    "person", "family", "event", "place", "source",
    "citation", "repository", "media", "note", "tag",
]

MergeableType = Literal[
    "person", "family", "event", "place", "source",
    "citation", "repository", "media", "note",
]


class DeleteTypeParams(StrictModel):
    """Parameters for deleting a single record."""

    type: RecordType = Field(description="Record type to delete")
    handle: str | None = Field(None, description="Object handle")
    gramps_id: str | None = Field(
        None, description="Gramps ID, for example I0001 (alternative to handle)"
    )
    force: bool = Field(
        False,
        description=(
            "Delete even though other records still reference this one, "
            "severing those references. Without it the call is refused and "
            "the referencing records are listed."
        ),
    )
```

Create `src/gramps_mcp/tools/destructive.py` (AGPL header first):

```python
"""
Destructive MCP tools: delete, merge, detach and undo.

Every tool here can remove data. The guard rails live in destructive.py as
pure functions; this module does the I/O and the formatting.
"""

import logging

from mcp.types import TextContent

from ..client import GrampsAPIError
from ..config import get_settings
from ..destructive import TYPE_ENDPOINTS, should_refuse_delete
from ..models.parameters.destructive_params import DeleteTypeParams
from .search_basic import with_client

logger = logging.getLogger(__name__)


def _format_error_response(error: Exception, operation: str) -> list[TextContent]:
    """Format an error into a user-facing MCP response."""
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"
    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


async def resolve_target_handle(
    client, tree_id: str, obj_type: str, handle: str | None, gramps_id: str | None
) -> str:
    """
    Return the handle for a target named by handle or by gramps_id.

    Args:
        client (GrampsWebAPIClient): Client to issue the lookup with.
        tree_id (str): Family tree identifier.
        obj_type (str): One of the keys of TYPE_ENDPOINTS.
        handle (str | None): Handle, used directly when given.
        gramps_id (str | None): Gramps ID, resolved by a GQL search.

    Returns:
        str: The resolved handle.

    Raises:
        ValueError: If neither identifier is given, or the gramps_id matches
            no record.
    """
    if handle:
        return handle
    if not gramps_id:
        raise ValueError("Either handle or gramps_id is required")

    from ..models.api_calls import ApiCalls

    plural = {
        "person": ApiCalls.GET_PEOPLE,
        "family": ApiCalls.GET_FAMILIES,
        "event": ApiCalls.GET_EVENTS,
        "place": ApiCalls.GET_PLACES,
        "source": ApiCalls.GET_SOURCES,
        "citation": ApiCalls.GET_CITATIONS,
        "repository": ApiCalls.GET_REPOSITORIES,
        "media": ApiCalls.GET_MEDIA,
        "note": ApiCalls.GET_NOTES,
        "tag": ApiCalls.GET_TAGS,
    }[obj_type]

    results = await client.make_api_call(
        api_call=plural,
        params={"gql": f'gramps_id="{gramps_id}"', "pagesize": 1},
        tree_id=tree_id,
    )
    if not results:
        raise ValueError(f"No {obj_type} found with gramps_id {gramps_id}")
    return results[0]["handle"]


@with_client
async def delete_type_tool(client, arguments: dict) -> list[TextContent]:
    """Delete one record, refusing while other records still reference it."""
    try:
        params = DeleteTypeParams(**arguments)
        tree_id = get_settings().gramps_tree_id
        endpoints = TYPE_ENDPOINTS[params.type]

        handle = await resolve_target_handle(
            client, tree_id, params.type, params.handle, params.gramps_id
        )

        record = await client.make_api_call(
            api_call=endpoints.get,
            params={"backlinks": True},
            tree_id=tree_id,
            handle=handle,
        )
        gramps_id = record.get("gramps_id", handle)
        backlinks = record.get("backlinks") or {}

        refusal = should_refuse_delete(backlinks)
        if refusal and not params.force:
            return [
                TextContent(
                    type="text",
                    text=f"{params.type} {gramps_id}\n{refusal}",
                )
            ]

        await client.make_api_call(
            api_call=endpoints.delete, tree_id=tree_id, handle=handle
        )

        severed = ""
        if refusal:
            total = sum(len(v) for v in backlinks.values() if v)
            severed = f" {total} reference(s) were severed (force=true)."
        return [
            TextContent(
                type="text",
                text=f"Deleted {params.type} {gramps_id}.{severed}",
            )
        ]

    except KeyError as e:
        return _format_error_response(
            ValueError(f"Unsupported record type: {e}"), "deletion"
        )
    except Exception as e:
        return _format_error_response(e, "deletion")
```

In `src/gramps_mcp/server.py`, add the import next to the other parameter
imports (around line 44) and the tool import next to the other tool imports:

```python
from .models.parameters.destructive_params import DeleteTypeParams
from .tools.destructive import delete_type_tool
```

Then add this entry to `TOOL_REGISTRY`, before its closing `}` at line 270:

```python
    "delete_type": {
        "description": (
            "Delete one record (person, family, event, place, source, "
            "citation, repository, media, note, tag). Refuses while other "
            "records still reference it, listing them; pass force=true to "
            "delete anyway and sever those references. Deletions can be "
            "reversed with undo_change"
        ),
        "schema": DeleteTypeParams,
        "handler": delete_type_tool,
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_destructive_delete.py -v`
Expected: PASS (4 tests)

Run: `uv run pytest -m "not integration"`
Expected: PASS, no regressions

- [ ] **Step 5: Add the live test**

Append to `tests/test_destructive_delete.py`:

```python
@pytest.mark.integration
class TestDeleteLive:
    """
    Live tests against the configured tree.

    Two hard rules, because the reference tree is production data:
    a test never passes a handle it did not create in that same test, and
    force=true is never used on anything but a record the test created.
    """

    async def test_deletes_a_note_it_created(self, gramps_client, tree_id):
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
        from tests.conftest import create_entity
        from tests.constants import PREFIX

        handle = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_NOTES,
            NoteSaveParams(text=f"{PREFIX} delete me", type="Transcript"),
            "note",
        )

        result = await delete_type_tool({"type": "note", "handle": handle})
        assert "Deleted" in result[0].text

        second = await delete_type_tool({"type": "note", "handle": handle})
        assert "Error" in second[0].text
```

- [ ] **Step 6: Run the live test**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_destructive_delete.py -v -m integration`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
uv run git add src/gramps_mcp/models/parameters/destructive_params.py src/gramps_mcp/tools/destructive.py src/gramps_mcp/server.py tests/test_destructive_delete.py
uv run git commit -m "feat: add delete_type tool with a backlink guard"
```

---

### Task 4: `detach_reference` tool

**Files:**
- Modify: `src/gramps_mcp/models/parameters/destructive_params.py`
- Modify: `src/gramps_mcp/tools/destructive.py`
- Modify: `src/gramps_mcp/server.py`
- Test: `tests/test_destructive_detach.py`

**Interfaces:**
- Consumes: `remove_from_list`, `TYPE_ENDPOINTS`, `resolve_target_handle`.
- Produces: `DetachReferenceParams`, `detach_reference_tool(arguments: dict)`.

The tool reads the record, removes the handle from the named list, and writes
it back asking for replacement of **that one list**. Every other list stays in
union mode, so nothing unrelated can be lost. This is the explicit removal path
ADR 0007 describes.

- [ ] **Step 1: Write the failing test**

Create `tests/test_destructive_detach.py`:

```python
"""Tests for the detach_reference tool."""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.tools.destructive import detach_reference_tool


class TestDetachOffline:
    async def test_refuses_when_the_handle_is_absent_from_the_list(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.return_value = {
                "handle": "p1",
                "gramps_id": "I0001",
                "note_list": ["other"],
            }
            result = await detach_reference_tool(
                {
                    "type": "person",
                    "handle": "p1",
                    "list_name": "note_list",
                    "ref_handle": "missing",
                }
            )

        assert "Error" in result[0].text
        assert "not present" in result[0].text

    async def test_reports_success_naming_what_was_detached(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.return_value = {
                "handle": "p1",
                "gramps_id": "I0001",
                "note_list": ["n1", "n2"],
            }
            result = await detach_reference_tool(
                {
                    "type": "person",
                    "handle": "p1",
                    "list_name": "note_list",
                    "ref_handle": "n1",
                }
            )

        text = result[0].text
        assert "Detached" in text
        assert "note_list" in text
        assert "I0001" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_destructive_detach.py -v`
Expected: FAIL, `ImportError: cannot import name 'detach_reference_tool'`

- [ ] **Step 3: Write minimal implementation**

Append to `destructive_params.py`:

```python
class DetachReferenceParams(StrictModel):
    """Parameters for removing one element from a record's list."""

    type: RecordType = Field(description="Type of the record holding the list")
    handle: str | None = Field(None, description="Object handle")
    gramps_id: str | None = Field(
        None, description="Gramps ID (alternative to handle)"
    )
    list_name: str = Field(
        description=(
            "Name of the list to edit, for example event_ref_list, "
            "child_ref_list, media_list, note_list, citation_list, tag_list"
        )
    )
    ref_handle: str = Field(description="Handle of the element to remove")
```

Append to `tools/destructive.py` (extend the existing imports with
`remove_from_list` and `DetachReferenceParams`):

```python
@with_client
async def detach_reference_tool(client, arguments: dict) -> list[TextContent]:
    """Remove one element from a record's list, leaving every other list alone."""
    try:
        params = DetachReferenceParams(**arguments)
        tree_id = get_settings().gramps_tree_id
        endpoints = TYPE_ENDPOINTS[params.type]

        handle = await resolve_target_handle(
            client, tree_id, params.type, params.handle, params.gramps_id
        )

        record = await client.make_api_call(
            api_call=endpoints.get, tree_id=tree_id, handle=handle
        )
        gramps_id = record.get("gramps_id", handle)

        updated = remove_from_list(record, params.list_name, params.ref_handle)

        # Reason: only the edited list is replaced. Every other list keeps the
        # union semantics of ADR 0003, so this call cannot drop unrelated data.
        await client.make_api_call(
            api_call=endpoints.put,
            params={params.list_name: updated[params.list_name]},
            tree_id=tree_id,
            handle=handle,
            replace_lists=[params.list_name],
        )

        return [
            TextContent(
                type="text",
                text=(
                    f"Detached {params.ref_handle} from {params.list_name} "
                    f"of {params.type} {gramps_id}."
                ),
            )
        ]

    except Exception as e:
        return _format_error_response(e, "detach")
```

`endpoints.put` and the `replace_lists` argument are what make this the one
narrow door for removal: `make_api_call` hands `replace_lists` to
`merge_put_data`, which replaces exactly the listed keys and unions every
other list as before.

Register in `server.py`:

```python
    "detach_reference": {
        "description": (
            "Remove one element from a record's list (event_ref_list, "
            "child_ref_list, media_list, note_list, citation_list, tag_list). "
            "Only the named list is rewritten; every other list keeps its "
            "merge-on-update behaviour. Refuses if the element is not in the list"
        ),
        "schema": DetachReferenceParams,
        "handler": detach_reference_tool,
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_destructive_detach.py tests/test_destructive_logic.py -v`
Expected: PASS

- [ ] **Step 5: Add the live test**

Append to `tests/test_destructive_detach.py`:

```python
@pytest.mark.integration
class TestDetachLive:
    async def test_detaches_a_note_from_a_person_it_created(
        self, gramps_client, tree_id
    ):
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
        from src.gramps_mcp.models.parameters.people_params import PersonData
        from src.gramps_mcp.tools.destructive import delete_type_tool
        from tests.conftest import create_entity, delete_entity
        from tests.constants import PREFIX

        note = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_NOTES,
            NoteSaveParams(text=f"{PREFIX} detach me", type="Transcript"),
            "note",
        )
        person = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_PEOPLE,
            PersonData(
                primary_name={
                    "first_name": PREFIX,
                    "surname_list": [{"surname": "Detach"}],
                },
                gender=2,
                note_list=[note],
            ),
            "person",
        )
        try:
            result = await detach_reference_tool(
                {
                    "type": "person",
                    "handle": person,
                    "list_name": "note_list",
                    "ref_handle": note,
                }
            )
            assert "Detached" in result[0].text

            after = await gramps_client.make_api_call(
                api_call=ApiCalls.GET_PERSON, tree_id=tree_id, handle=person
            )
            assert note not in after["note_list"]
        finally:
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_PERSON, person)
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_NOTE, note)
```

- [ ] **Step 6: Run the live test**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_destructive_detach.py -v -m integration`
Expected: PASS. The assertion that matters is `note not in after["note_list"]` —
it reads the tree, not the tool's own words.

- [ ] **Step 7: Commit**

```bash
uv run git add src/gramps_mcp/models/parameters/destructive_params.py src/gramps_mcp/tools/destructive.py src/gramps_mcp/server.py tests/test_destructive_detach.py
uv run git commit -m "feat: add detach_reference tool for targeted list removal"
```

---

### Task 5: `merge_type` tool

**Files:**
- Modify: `src/gramps_mcp/models/parameters/destructive_params.py`
- Modify: `src/gramps_mcp/tools/destructive.py`
- Create: `src/gramps_mcp/handlers/destructive_handler.py`
- Modify: `src/gramps_mcp/server.py`
- Test: `tests/test_destructive_merge.py`

**Interfaces:**
- Consumes: `TYPE_ENDPOINTS`, `resolve_target_handle`.
- Produces: `MergeTypeParams`, `merge_type_tool(arguments: dict)`,
  `format_merge_preview(phoenix: dict, titanic: dict, obj_type: str) -> str`.

Merge is the one tool that keeps a confirmation step. The backlink guard cannot
help here: both records are legitimately referenced, so there is nothing to
refuse, and a phoenix/titanic inversion silently keeps the wrong record.

- [ ] **Step 1: Write the failing test**

Create `tests/test_destructive_merge.py`:

```python
"""Tests for the merge_type tool."""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.handlers.destructive_handler import format_merge_preview
from src.gramps_mcp.tools.destructive import merge_type_tool


class TestMergePreviewFormatting:
    def test_preview_names_which_record_survives(self):
        text = format_merge_preview(
            {"handle": "a", "gramps_id": "S0001", "title": "Keep me"},
            {"handle": "b", "gramps_id": "S0002", "title": "Absorb me"},
            "source",
        )
        assert "S0001" in text
        assert "S0002" in text
        assert "survives" in text.lower()
        assert "confirm=true" in text


class TestMergeOffline:
    async def test_without_confirm_it_previews_and_does_not_merge(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = [
                {"handle": "a", "gramps_id": "S0001", "title": "Keep"},
                {"handle": "b", "gramps_id": "S0002", "title": "Absorb"},
            ]
            result = await merge_type_tool(
                {
                    "type": "source",
                    "phoenix_handle": "a",
                    "titanic_handle": "b",
                }
            )

        assert "confirm=true" in result[0].text
        assert call.await_count == 2

    async def test_rejects_merging_a_record_with_itself(self):
        result = await merge_type_tool(
            {"type": "source", "phoenix_handle": "a", "titanic_handle": "a"}
        )
        assert "Error" in result[0].text

    async def test_rejects_tag_which_has_no_merge_endpoint(self):
        result = await merge_type_tool(
            {"type": "tag", "phoenix_handle": "a", "titanic_handle": "b"}
        )
        assert "Error" in result[0].text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_destructive_merge.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'src.gramps_mcp.handlers.destructive_handler'`

- [ ] **Step 3: Write minimal implementation**

Create `src/gramps_mcp/handlers/destructive_handler.py` (AGPL header first):

```python
"""Formatting for destructive-operation results and previews."""


def _label(obj: dict) -> str:
    """Return the most human-readable label a record offers."""
    for key in ("title", "desc", "text", "page", "gramps_id", "handle"):
        value = obj.get(key)
        if isinstance(value, dict):
            value = value.get("string") or value.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()[:80]
    return "(no label)"


def format_merge_preview(phoenix: dict, titanic: dict, obj_type: str) -> str:
    """
    Describe a merge without performing it.

    Args:
        phoenix (dict): The record that survives.
        titanic (dict): The record that is absorbed and disappears.
        obj_type (str): The record type being merged.

    Returns:
        str: A preview naming both records and what happens to each.
    """
    return (
        f"Merge preview for {obj_type}:\n"
        f"  SURVIVES (phoenix): {phoenix.get('gramps_id', '?')} - "
        f"{_label(phoenix)}\n"
        f"  ABSORBED (titanic): {titanic.get('gramps_id', '?')} - "
        f"{_label(titanic)}\n"
        "The absorbed record disappears and every reference to it is "
        "repointed at the surviving one.\n"
        "Check the direction: if these are the wrong way round, swap "
        "phoenix_handle and titanic_handle.\n"
        "Call again with confirm=true to perform the merge."
    )
```

Append to `destructive_params.py`:

```python
class MergeTypeParams(StrictModel):
    """Parameters for merging two records of the same type."""

    type: MergeableType = Field(
        description="Record type to merge (tags cannot be merged)"
    )
    phoenix_handle: str = Field(description="Handle of the record that survives")
    titanic_handle: str = Field(
        description="Handle of the record that is absorbed and disappears"
    )
    confirm: bool = Field(
        False,
        description=(
            "Perform the merge. Without it the call returns a preview of both "
            "records and changes nothing."
        ),
    )
    phoenix_father_handle: str | None = Field(
        None, description="Family merges only: which father the result keeps"
    )
    phoenix_mother_handle: str | None = Field(
        None, description="Family merges only: which mother the result keeps"
    )
```

Append to `tools/destructive.py`:

```python
@with_client
async def merge_type_tool(client, arguments: dict) -> list[TextContent]:
    """Merge two records of the same type, previewing unless confirm is set."""
    try:
        params = MergeTypeParams(**arguments)
        tree_id = get_settings().gramps_tree_id

        if params.phoenix_handle == params.titanic_handle:
            raise ValueError("phoenix_handle and titanic_handle must differ")

        endpoints = TYPE_ENDPOINTS[params.type]
        if endpoints.merge is None:
            raise ValueError(f"{params.type} records cannot be merged")

        phoenix = await client.make_api_call(
            api_call=endpoints.get, tree_id=tree_id, handle=params.phoenix_handle
        )
        titanic = await client.make_api_call(
            api_call=endpoints.get, tree_id=tree_id, handle=params.titanic_handle
        )

        if not params.confirm:
            return [
                TextContent(
                    type="text",
                    text=format_merge_preview(phoenix, titanic, params.type),
                )
            ]

        extra = {}
        if params.phoenix_father_handle:
            extra["phoenix_father_handle"] = params.phoenix_father_handle
        if params.phoenix_mother_handle:
            extra["phoenix_mother_handle"] = params.phoenix_mother_handle

        await client.make_api_call(
            api_call=endpoints.merge,
            params=extra or None,
            tree_id=tree_id,
            phoenix_handle=params.phoenix_handle,
            titanic_handle=params.titanic_handle,
        )

        return [
            TextContent(
                type="text",
                text=(
                    f"Merged {params.type} {titanic.get('gramps_id', '?')} into "
                    f"{phoenix.get('gramps_id', '?')}. The absorbed record is gone; "
                    "use undo_change to reverse this."
                ),
            )
        ]

    except Exception as e:
        return _format_error_response(e, "merge")
```

Add the imports (`MergeTypeParams`, `format_merge_preview`) at the top of
`tools/destructive.py`, and register in `server.py`:

```python
    "merge_type": {
        "description": (
            "Merge two records of the same type. The phoenix survives, the "
            "titanic is absorbed and every reference to it is repointed. "
            "Returns a preview and changes nothing unless confirm=true. "
            "Tags cannot be merged"
        ),
        "schema": MergeTypeParams,
        "handler": merge_type_tool,
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_destructive_merge.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Add the live test**

Append to `tests/test_destructive_merge.py`:

```python
@pytest.mark.integration
class TestMergeLive:
    async def test_merges_two_sources_it_created(self, gramps_client, tree_id):
        from src.gramps_mcp.client import GrampsAPIError
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.source_params import SourceSaveParams
        from tests.conftest import create_entity, delete_entity
        from tests.constants import PREFIX

        keep = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_SOURCES,
            SourceSaveParams(title=f"{PREFIX} phoenix source"),
            "source",
        )
        absorb = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_SOURCES,
            SourceSaveParams(title=f"{PREFIX} titanic source"),
            "source",
        )
        try:
            preview = await merge_type_tool(
                {"type": "source", "phoenix_handle": keep, "titanic_handle": absorb}
            )
            assert "confirm=true" in preview[0].text

            done = await merge_type_tool(
                {
                    "type": "source",
                    "phoenix_handle": keep,
                    "titanic_handle": absorb,
                    "confirm": True,
                }
            )
            assert "Merged" in done[0].text

            with pytest.raises(GrampsAPIError):
                await gramps_client.make_api_call(
                    api_call=ApiCalls.GET_SOURCE, tree_id=tree_id, handle=absorb
                )
        finally:
            await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_SOURCE, keep)
```

- [ ] **Step 6: Run the live test**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_destructive_merge.py -v -m integration`
Expected: PASS. The teardown deletes only the phoenix; the titanic is gone by
the merge, which is what the `pytest.raises` proves.

- [ ] **Step 7: Commit**

```bash
uv run git add src/gramps_mcp/handlers/destructive_handler.py src/gramps_mcp/models/parameters/destructive_params.py src/gramps_mcp/tools/destructive.py src/gramps_mcp/server.py tests/test_destructive_merge.py
uv run git commit -m "feat: add merge_type tool with a confirmation preview"
```

---

### Task 6: `undo_change` tool

**Files:**
- Modify: `src/gramps_mcp/models/parameters/destructive_params.py`
- Modify: `src/gramps_mcp/tools/destructive.py`
- Modify: `src/gramps_mcp/server.py`
- Test: `tests/test_destructive_undo.py`

**Interfaces:**
- Consumes: `ApiCalls.POST_TRANSACTION_UNDO` (Task 2).
- Produces: `UndoChangeParams`, `undo_change_tool(arguments: dict)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_destructive_undo.py`:

```python
"""Tests for the undo_change tool."""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.tools.destructive import undo_change_tool


class TestUndoOffline:
    async def test_reports_the_transaction_it_undid(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.return_value = {}
            result = await undo_change_tool({"transaction_id": 42})

        assert "42" in result[0].text
        assert "ndone" in result[0].text

    async def test_rejects_a_non_numeric_transaction_id(self):
        result = await undo_change_tool({"transaction_id": "not-a-number"})
        assert "Error" in result[0].text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_destructive_undo.py -v`
Expected: FAIL, `ImportError: cannot import name 'undo_change_tool'`

- [ ] **Step 3: Write minimal implementation**

Append to `destructive_params.py`:

```python
class UndoChangeParams(StrictModel):
    """Parameters for undoing a recorded transaction."""

    transaction_id: int = Field(
        description=(
            "Transaction id to undo, as listed by recent_changes. Undoing "
            "reverses every object change that transaction made."
        )
    )
```

Append to `tools/destructive.py`:

```python
@with_client
async def undo_change_tool(client, arguments: dict) -> list[TextContent]:
    """Undo one recorded transaction."""
    try:
        params = UndoChangeParams(**arguments)
        tree_id = get_settings().gramps_tree_id

        # Reason: params stays None. The endpoint reads its only optional
        # argument from the query string, while make_api_call sends a JSON
        # body for POST, so the server would ignore it anyway and apply its
        # own default message.
        await client.make_api_call(
            api_call=ApiCalls.POST_TRANSACTION_UNDO,
            tree_id=tree_id,
            transaction_id=params.transaction_id,
        )

        return [
            TextContent(
                type="text",
                text=(
                    f"Transaction {params.transaction_id} undone. "
                    "Run recent_changes to confirm the tree is as expected."
                ),
            )
        ]

    except Exception as e:
        return _format_error_response(e, "undo")
```

Add `from ..models.api_calls import ApiCalls` to the module imports (it is
currently imported inside `resolve_target_handle`; move it to the top and drop
the local import). Register in `server.py`:

```python
    "undo_change": {
        "description": (
            "Undo one recorded transaction by id, reversing every object "
            "change it made. Use recent_changes to find the id. This is the "
            "recovery path for a delete or merge that went the wrong way"
        ),
        "schema": UndoChangeParams,
        "handler": undo_change_tool,
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_destructive_undo.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Add the live round-trip test**

This is the test that proves the whole safety story. Append to
`tests/test_destructive_undo.py`:

```python
@pytest.mark.integration
class TestUndoLive:
    async def test_undoes_a_deletion_it_performed(self, gramps_client, tree_id):
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
        from src.gramps_mcp.tools.destructive import delete_type_tool
        from tests.conftest import create_entity, delete_entity
        from tests.constants import PREFIX

        handle = await create_entity(
            gramps_client,
            tree_id,
            ApiCalls.POST_NOTES,
            NoteSaveParams(text=f"{PREFIX} undo me", type="Transcript"),
            "note",
        )

        result = await delete_type_tool({"type": "note", "handle": handle})
        assert "Deleted" in result[0].text

        history = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_TRANSACTIONS_HISTORY,
            params={"page": 1, "pagesize": 1, "sort": "-id"},
            tree_id=tree_id,
        )
        transaction_id = history[0]["id"]

        undone = await undo_change_tool({"transaction_id": transaction_id})
        assert "undone" in undone[0].text

        restored = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_NOTE, tree_id=tree_id, handle=handle
        )
        assert restored["handle"] == handle

        await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_NOTE, handle)
```

- [ ] **Step 6: Run the live test**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_destructive_undo.py -v -m integration`
Expected: PASS

If the undo endpoint turns out to run in the background and return before the
change lands, the `restored` fetch may need a short poll. Do not paper over a
failure with a bare sleep: poll `GET_NOTE` for up to five seconds and assert on
the outcome, so a genuinely broken undo still fails the test.

- [ ] **Step 7: Commit**

```bash
uv run git add src/gramps_mcp/models/parameters/destructive_params.py src/gramps_mcp/tools/destructive.py src/gramps_mcp/server.py tests/test_destructive_undo.py
uv run git commit -m "feat: add undo_change tool"
```

---

### Task 7: Documentation, ADR and release

**Files:**
- Create: `docs/adr/0007-expose-destructive-operations.md`
- Modify: `docs/adr/0003-merge-semantics-for-put-updates.md` (Status section)
- Modify: `docs/prd.md`
- Modify: `src/gramps_mcp/resources/gramps-usage-guide.md`
- Modify: `tests/test_alignment_*.py` (field inventories)
- Modify: `README.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `pyproject.toml`, `src/gramps_mcp/__init__.py`, `uv.lock`

**Interfaces:**
- Consumes: the four tools from Tasks 3-6.
- Produces: no code.

- [ ] **Step 1: Write ADR 0007**

Create `docs/adr/0007-expose-destructive-operations.md`, following the shape of
the existing ADRs (title, Date, Status, Context, Decision, Consequences):

- Context: the server could not delete, merge or detach; the eleven `DELETE_*`
  endpoints were already declared and exercised by `conftest.py`; Gramps Web
  exposes a merge endpoint the PRD never mentioned; a cleanup backlog had
  accumulated that no tool could execute.
- Decision: expose four tools with generic type dispatch. Deletion refuses
  while backlinks exist unless `force=true`. Merge previews unless
  `confirm=true`. Removal from a list happens only through `detach_reference`,
  which replaces exactly one named list.
- Consequences: this ADR supersedes ADR 0003 in scope only. Union stays the
  default for every write; what changes is that removal is no longer
  impossible, it is explicit and separately named.

- [ ] **Step 2: Mark ADR 0003 superseded**

In `docs/adr/0003-merge-semantics-for-put-updates.md`, change the Status
section to `Superseded by ADR 0007` and add one sentence: the union behaviour
it describes is unchanged, only its claim that removal is impossible is.

- [ ] **Step 3: Correct the PRD**

In `docs/prd.md`:
- Replace the paragraph at line 85, "It does not delete records. No tool maps
  to a DELETE endpoint, for any object type, including tags." Describe
  `delete_type` and its backlink guard instead.
- Rewrite the paragraph at lines 75-83 that begins "It cannot remove anything
  from a list": the union behaviour stands, and `detach_reference` is now the
  removal path.
- Add merge to the capability list and to the "API surface depended on"
  paragraph at line 119.
- Update the issue #12 line at line 168: duplicate sources can now be merged.

- [ ] **Step 4: Update the usage guide, then the alignment inventories**

Add the four tools and every parameter to
`src/gramps_mcp/resources/gramps-usage-guide.md`. This resource is served to
MCP clients, so an undocumented parameter is one the assistant can pass but was
never told about.

Then run the alignment tests and update the hardcoded field inventories they
hold:

Run: `uv run pytest tests/test_alignment_*.py -v`
Expected: FAIL until the inventories list the new fields. Fix the guide first,
the inventory second — never the inventory alone.

- [ ] **Step 5: Update README and CI**

Add the four tools to the tool table in `README.md`.

In `.github/workflows/ci.yml` line 42, add the offline test files to the
explicit list so CI covers them:

```
tests/test_destructive_logic.py tests/test_destructive_delete.py tests/test_destructive_detach.py tests/test_destructive_merge.py tests/test_destructive_undo.py
```

- [ ] **Step 6: Verify the whole suite**

Run: `uv run pytest -m "not integration"`
Expected: PASS

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest -m integration`
Expected: PASS

Run: `uv run mypy src/gramps_mcp --ignore-missing-imports`
Expected: clean

Run: `uv run --with mkdocs-material mkdocs build --strict`
Expected: clean, no broken internal links

- [ ] **Step 7: Count the tree before and after**

The regression guard the spec calls for. Before and after a full suite run,
count every record category and compare:

```bash
curl -s -H "Authorization: Bearer $TOK" "http://localhost:80/api/people/?keys=gramps_id" | python3 -c "import sys,json;print('people',len(json.load(sys.stdin)))"
```

Repeat for families, events, places, sources, citations, media, notes.
Expected: identical counts before and after. A delete tool that over-reaches
shows up here, not in a green test.

- [ ] **Step 8: Bump the version and commit**

Bump `pyproject.toml` and `src/gramps_mcp/__init__.py` to the next minor
version, then regenerate the lock **in the same commit** — `uv.lock` pins the
project's own version and CI runs `uv sync --locked`, so a bump without it
turns main red while the Docker publish stays green.

```bash
uv lock
uv run git add docs/ README.md src/gramps_mcp/resources/gramps-usage-guide.md tests/ .github/workflows/ci.yml pyproject.toml src/gramps_mcp/__init__.py uv.lock
uv run git commit -m "docs: record destructive operations in ADR 0007, PRD and usage guide"
```

- [ ] **Step 9: Open the pull request**

This is a fork, so the repo must be named explicitly or the error will
misleadingly blame the token. Merge with `--merge`, never `--squash`.

```bash
uv run git push -u origin feat/destructive-operations
gh pr create --repo fjacquet/gramps-mcp --title "feat: destructive operations (delete, merge, detach, undo)" --body "Implements docs/superpowers/specs/2026-08-14-delete-merge-detach-design.md"
```
