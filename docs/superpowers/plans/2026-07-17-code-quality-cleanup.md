# Code Quality Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove dead code, fix version/documentation drift, extract the untested PUT merge logic into a pure tested module, deduplicate base-URL construction, fix mypy errors, and standardize formatting on ruff format — with zero runtime behavior change.

**Architecture:** Pure-function extraction (`merge.py`, `get_api_base_url`) so the risky data-merge logic becomes unit-testable without a live Gramps Web server. Everything else is mechanical cleanup pinned by the existing offline test suite.

**Tech Stack:** Python >=3.10, uv, pytest (+pytest-asyncio, `asyncio_mode = auto`), ruff (lint + format), mypy, pydantic v2, httpx.

Spec: `docs/superpowers/specs/2026-07-17-code-quality-cleanup-design.md`

## Global Constraints

- Run everything through uv: `uv run pytest`, `uv run ruff`, etc. Commits via `uv run git commit` (ensures pre-commit hooks run with the right interpreter).
- Every **new** file under `src/` must start with the 16-line AGPL header (copied verbatim in the task below). Files under `tests/` do NOT get the header (pre-commit excludes `^(tests/|examples/)`).
- No emojis anywhere in code or docs (pre-commit hook rejects them).
- Max 500 lines per file under `src/` (pre-commit hook enforces).
- Google-style docstrings on every new function.
- The integration test suite needs a live Gramps Web server and fails offline. **Never gate on the full suite.** The offline verification command used throughout this plan is:
  `uv run pytest tests/test_client_merge.py tests/test_utils.py -q`
  (Task 2 adds `tests/test_merge.py` and Task 3 adds `tests/test_config.py` to that list.)
- `uv run ruff check src/` is clean today and must stay clean after every task.
- Do NOT touch `docker-compose.yml` or the `docker/` directory — they hold the user's unrelated work-in-progress. Stage files explicitly by name; never `git add -A` or `git add .`.

**AGPL header for new `src/` files (copy verbatim):**

```python
# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
```

---

### Task 1: Delete dead module `src/gramps_mcp/tools.py`

The `tools/` **package** shadows the `tools.py` **module**: Python resolves `from .tools import ...` to the package, so the module has been unreachable since the initial commit. The user gave explicit approval for this deletion.

**Files:**

- Delete: `src/gramps_mcp/tools.py`

**Interfaces:**

- Consumes: nothing.
- Produces: nothing — later tasks rely only on the `tools/` package, which is untouched.

- [ ] **Step 1: Prove the module is shadowed (evidence before deletion)**

Run:

```bash
uv run python -c "import src.gramps_mcp.tools as t; print(t.__file__)"
```

Expected output ends with `src/gramps_mcp/tools/__init__.py` (the package), NOT `tools.py`. If it prints `tools.py`, STOP — the premise is wrong; do not delete.

- [ ] **Step 2: Delete the file**

```bash
git rm src/gramps_mcp/tools.py
```

- [ ] **Step 3: Verify imports and server module still load**

```bash
uv run python -c "from src.gramps_mcp.tools import create_person_tool, find_anything_tool; import src.gramps_mcp.server; print('ok')"
```

Expected: `ok` (an `INFO` log line about tool registration may appear first).

- [ ] **Step 4: Run offline tests**

```bash
uv run pytest tests/test_client_merge.py tests/test_utils.py -q
```

Expected: all pass (5 passed as of writing).

- [ ] **Step 5: Commit**

```bash
uv run git commit -m "refactor: remove dead tools.py module shadowed by tools package"
```

---

### Task 2: Extract PUT merge logic into pure `merge.py` (TDD)

`GrampsWebAPIClient.make_api_call` contains ~70 inline lines that merge user changes into the existing record before a PUT (Gramps Web PUT replaces the whole object). This is the code path that mutates real genealogy data and it has no isolated unit tests. Extract it verbatim into a pure function. The existing `tests/test_client_merge.py` (runs offline) pins the end-to-end behavior through `make_api_call` — it must pass unchanged before AND after.

**Files:**

- Create: `tests/test_merge.py`
- Create: `src/gramps_mcp/merge.py`
- Modify: `src/gramps_mcp/client.py` (imports block near line 32; PUT-merge block currently at lines 247–319)

**Interfaces:**

- Consumes: nothing from other tasks.
- Produces: `merge_put_data(existing: Dict, changes: Dict) -> Dict` in `src/gramps_mcp/merge.py`. No other task consumes it, but Task 5's README tree mentions `merge.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_merge.py` (no AGPL header — tests are excluded) with exactly:

```python
"""
Unit tests for the pure PUT merge logic in src/gramps_mcp/merge.py.

These are pure data-transformation tests - no API, no mocks needed.
"""

from src.gramps_mcp.merge import merge_put_data


class TestMergePutData:
    """Behavior pinned from the original inline logic in client.py."""

    def test_ref_object_lists_deduplicate_by_ref(self):
        existing = {"event_ref_list": [{"ref": "birth", "role": "Primary"}]}
        changes = {
            "event_ref_list": [
                {"ref": "birth", "role": "Primary"},
                {"ref": "death", "role": "Primary"},
            ]
        }
        merged = merge_put_data(existing, changes)
        refs = [item["ref"] for item in merged["event_ref_list"]]
        assert refs == ["birth", "death"]

    def test_string_handle_lists_deduplicate_by_value(self):
        existing = {"note_list": ["note1"]}
        changes = {"note_list": ["note1", "note2"]}
        merged = merge_put_data(existing, changes)
        assert merged["note_list"] == ["note1", "note2"]

    def test_existing_items_come_first(self):
        existing = {"note_list": ["a", "b"]}
        changes = {"note_list": ["c"]}
        assert merge_put_data(existing, changes)["note_list"] == ["a", "b", "c"]

    def test_dict_items_without_ref_concatenate_without_dedup(self):
        existing = {"tag_list": [{"name": "x"}]}
        changes = {"tag_list": [{"name": "x"}]}
        merged = merge_put_data(existing, changes)
        assert merged["tag_list"] == [{"name": "x"}, {"name": "x"}]

    def test_empty_existing_list_concatenates(self):
        existing = {"note_list": []}
        changes = {"note_list": ["n1"]}
        assert merge_put_data(existing, changes)["note_list"] == ["n1"]

    def test_empty_new_list_keeps_existing(self):
        existing = {"note_list": ["n1"]}
        changes = {"note_list": []}
        assert merge_put_data(existing, changes)["note_list"] == ["n1"]

    def test_non_list_fields_are_replaced(self):
        existing = {"private": False, "gender": 1}
        changes = {"private": True}
        merged = merge_put_data(existing, changes)
        assert merged["private"] is True
        assert merged["gender"] == 1

    def test_fields_absent_from_changes_are_preserved(self):
        existing = {"handle": "h1", "gramps_id": "I0001", "change": 1234567890}
        changes = {"handle": "h1"}
        merged = merge_put_data(existing, changes)
        assert merged["gramps_id"] == "I0001"
        assert merged["change"] == 1234567890

    def test_list_key_absent_from_existing_is_replaced_not_merged(self):
        existing = {"handle": "h1"}
        changes = {"note_list": ["n1"]}
        assert merge_put_data(existing, changes)["note_list"] == ["n1"]

    def test_inputs_are_not_mutated(self):
        existing = {"note_list": ["n1"], "private": False}
        changes = {"note_list": ["n2"], "private": True}
        merge_put_data(existing, changes)
        assert existing == {"note_list": ["n1"], "private": False}
        assert changes == {"note_list": ["n2"], "private": True}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_merge.py -q
```

Expected: collection error — `ModuleNotFoundError: No module named 'src.gramps_mcp.merge'`.

- [ ] **Step 3: Create `src/gramps_mcp/merge.py`**

Start the file with the AGPL header from Global Constraints, then exactly:

```python
"""
Pure merge logic for PUT (update) operations.

Gramps Web API PUT requests replace the whole object. To preserve data the
caller did not mention, the client fetches the existing record and merges the
requested changes into it before sending. This module holds that merge logic
as a pure, side-effect-free function so it can be unit-tested without a live
server.
"""

from typing import Dict, List


def merge_put_data(existing: Dict, changes: Dict) -> Dict:
    """
    Merge requested changes into an existing record for a PUT update.

    Keys ending in "_list" whose value is a list and which are present in
    the existing record are merged with deduplication; every other key in
    changes replaces the existing value. Neither input is mutated.

    Args:
        existing (Dict): The record currently stored in Gramps.
        changes (Dict): The fields the caller wants to change.

    Returns:
        Dict: A new dict containing the merged record.
    """
    merged = existing.copy()
    for key, value in changes.items():
        if key.endswith("_list") and isinstance(value, list) and key in existing:
            merged[key] = _merge_list(existing.get(key, []), value)
        else:
            merged[key] = value
    return merged


def _merge_list(existing_items: List, new_items: List) -> List:
    """
    Merge two lists, deduplicating when the item type supports it.

    Lists of dicts carrying a "ref" field (event_ref_list, media_list, ...)
    are deduplicated by ref; lists of strings by value. Existing items always
    come first. Mixed or unknown item types are concatenated as-is.

    Args:
        existing_items (List): Items already stored in Gramps.
        new_items (List): Items requested in the update.

    Returns:
        List: The merged list.
    """
    # Reason: if either side is empty there is nothing to deduplicate
    if not existing_items or not new_items:
        return existing_items + new_items

    sample_existing = existing_items[0]
    sample_new = new_items[0]

    if (
        isinstance(sample_existing, dict)
        and "ref" in sample_existing
        and isinstance(sample_new, dict)
        and "ref" in sample_new
    ):
        existing_refs = {
            item.get("ref") for item in existing_items if isinstance(item, dict)
        }
        additions = [
            item
            for item in new_items
            if isinstance(item, dict) and item.get("ref") not in existing_refs
        ]
        return existing_items + additions

    if isinstance(sample_existing, str) and isinstance(sample_new, str):
        existing_set = set(existing_items)
        return existing_items + [
            item for item in new_items if item not in existing_set
        ]

    # Reason: mixed/unknown item types - concatenation is the safe fallback
    return existing_items + new_items
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_merge.py -q
```

Expected: 10 passed.

- [ ] **Step 5: Switch `client.py` to the pure function**

In `src/gramps_mcp/client.py`, add the import after the existing `from .config import get_settings` line:

```python
from .merge import merge_put_data
```

Then replace the entire inline merge block. The current code (lines 247–319) is:

```python
        # For PUT operations, preserve existing data by merging with changes
        if api_call.method == "PUT" and json_data:
            handle = url_params.get("handle") or json_data.get("handle")
            if handle:
                # Use same endpoint for GET (remove method-specific parts if any)
                get_endpoint = endpoint
                get_url = self._build_url_with_substitution(
                    tree_id, get_endpoint, {"handle": handle}
                )
                existing = await self._make_request("GET", get_url)
                if existing:
                    # Merge existing data with changes
                    merged_data = existing.copy()
```

...continuing through the nested deduplication logic down to:

```python
                        else:
                            merged_data[key] = value
                    json_data = merged_data
```

Replace that whole block (from `# For PUT operations...` through `json_data = merged_data` inclusive) with:

```python
        # For PUT operations, preserve existing data by merging with changes
        if api_call.method == "PUT" and json_data:
            handle = url_params.get("handle") or json_data.get("handle")
            if handle:
                get_url = self._build_url_with_substitution(
                    tree_id, endpoint, {"handle": handle}
                )
                existing = await self._make_request("GET", get_url)
                if existing:
                    json_data = merge_put_data(existing, json_data)
```

Everything after (`# Make the API request` and the final `_make_request` call) stays unchanged.

- [ ] **Step 6: Verify end-to-end behavior is unchanged**

```bash
uv run pytest tests/test_merge.py tests/test_client_merge.py tests/test_utils.py -q
uv run ruff check src/
```

Expected: all tests pass (`test_client_merge.py` passing unchanged proves the extraction is behavior-identical); ruff clean.

- [ ] **Step 7: Commit**

```bash
git add tests/test_merge.py src/gramps_mcp/merge.py src/gramps_mcp/client.py
uv run git commit -m "refactor: extract PUT merge logic into pure merge module with tests"
```

---

### Task 3: Deduplicate base-URL construction (TDD)

The `rstrip("/") + "/api"` construction exists in both `auth.py` (in the `AuthManager.client` property) and `client.py` (`__init__`). Extract one helper into `config.py`.

**Files:**

- Create: `tests/test_config.py`
- Modify: `src/gramps_mcp/config.py` (append helper at end of file)
- Modify: `src/gramps_mcp/client.py:49-59` (`__init__`) and its `from .config import get_settings` import
- Modify: `src/gramps_mcp/auth.py:110-119` (`client` property) and its `from .config import get_settings` import

**Interfaces:**

- Consumes: nothing from other tasks.
- Produces: `get_api_base_url(settings: Settings) -> str` in `src/gramps_mcp/config.py`, returning the API base URL ending in `/api` with no trailing slash.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config.py` with exactly:

```python
"""Unit tests for configuration helpers - pure functions, no API needed."""

from pydantic import HttpUrl

from src.gramps_mcp.config import Settings, get_api_base_url


def make_settings(url: str) -> Settings:
    return Settings(
        gramps_api_url=HttpUrl(url),
        gramps_username="user",
        gramps_password="password",
        gramps_tree_id="tree1",
    )


def test_appends_api_suffix():
    settings = make_settings("https://gramps.example.com")
    assert get_api_base_url(settings) == "https://gramps.example.com/api"


def test_strips_trailing_slash():
    settings = make_settings("https://gramps.example.com/")
    assert get_api_base_url(settings) == "https://gramps.example.com/api"


def test_keeps_existing_api_suffix():
    settings = make_settings("https://gramps.example.com/api")
    assert get_api_base_url(settings) == "https://gramps.example.com/api"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_config.py -q
```

Expected: `ImportError: cannot import name 'get_api_base_url'`.

- [ ] **Step 3: Implement the helper**

Append to `src/gramps_mcp/config.py`:

```python
def get_api_base_url(settings: Settings) -> str:
    """
    Build the Gramps Web API base URL from settings.

    Args:
        settings (Settings): Application settings.

    Returns:
        str: Base URL ending in "/api", without a trailing slash.
    """
    base_url = str(settings.gramps_api_url).rstrip("/")
    if not base_url.endswith("/api"):
        base_url += "/api"
    return base_url
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_config.py -q
```

Expected: 3 passed.

- [ ] **Step 5: Use the helper in `client.py` and `auth.py`**

In `src/gramps_mcp/client.py`, change the import:

```python
from .config import get_api_base_url, get_settings
```

and replace in `__init__`:

```python
        # Construct base API URL
        base_url = str(self.settings.gramps_api_url).rstrip("/")
        if not base_url.endswith("/api"):
            base_url += "/api"
        self.base_url = base_url
```

with:

```python
        self.base_url = get_api_base_url(self.settings)
```

In `src/gramps_mcp/auth.py`, change the import:

```python
from .config import get_api_base_url, get_settings
```

and replace in the `client` property:

```python
            # Create new client with current event loop
            base_url = str(self.settings.gramps_api_url).rstrip("/")
            if not base_url.endswith("/api"):
                base_url += "/api"

            self._client = httpx.AsyncClient(
                base_url=base_url, timeout=httpx.Timeout(timeout=30.0, connect=10.0)
            )
```

with:

```python
            # Create new client with current event loop
            self._client = httpx.AsyncClient(
                base_url=get_api_base_url(self.settings),
                timeout=httpx.Timeout(timeout=30.0, connect=10.0),
            )
```

- [ ] **Step 6: Run offline tests and lint**

```bash
uv run pytest tests/test_config.py tests/test_merge.py tests/test_client_merge.py tests/test_utils.py -q
uv run ruff check src/
```

Expected: all pass; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add tests/test_config.py src/gramps_mcp/config.py src/gramps_mcp/client.py src/gramps_mcp/auth.py
uv run git commit -m "refactor: deduplicate API base URL construction into config helper"
```

---

### Task 4: Fix the two mypy errors

**Files:**

- Modify: `src/gramps_mcp/models/api_mapping.py:185` (`validate_api_call_params` signature and docstring)
- Modify: `src/gramps_mcp/tools/data_management.py:65` (`_extract_entity_data` signature) and its `from typing import Dict, List` import

**Interfaces:**

- Consumes: nothing from other tasks.
- Produces: no signature changes visible to other tasks (annotation-only).

- [ ] **Step 1: Reproduce the errors**

```bash
uv run mypy src/gramps_mcp --ignore-missing-imports
```

Expected: exactly 2 errors — `api_mapping.py` L208 `[return-value]` (returns `None`, declared `BaseModel`) and `data_management.py` L65 `[assignment]` (implicit Optional).

- [ ] **Step 2: Fix `validate_api_call_params`**

In `src/gramps_mcp/models/api_mapping.py` (`Optional` is already imported), change:

```python
def validate_api_call_params(api_call: ApiCalls, params: dict) -> BaseModel:
```

to:

```python
def validate_api_call_params(api_call: ApiCalls, params: dict) -> Optional[BaseModel]:
```

and in its docstring change the `Returns:` line to:

```python
    Returns:
        Validated parameter model instance, or None if the API call takes
        no parameters and none were provided
```

(The only caller, `client.py:make_api_call`, already guards `if validated_params is not None`.)

- [ ] **Step 3: Fix `_extract_entity_data`**

In `src/gramps_mcp/tools/data_management.py`, change the typing import:

```python
from typing import Dict, List, Optional
```

and the signature:

```python
def _extract_entity_data(result, entity_type: Optional[str] = None):
```

- [ ] **Step 4: Verify mypy is clean and tests pass**

```bash
uv run mypy src/gramps_mcp --ignore-missing-imports
uv run pytest tests/test_config.py tests/test_merge.py tests/test_client_merge.py tests/test_utils.py -q
uv run ruff check src/
```

Expected: `Success: no issues found`; all tests pass; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/gramps_mcp/models/api_mapping.py src/gramps_mcp/tools/data_management.py
uv run git commit -m "fix: correct type annotations flagged by mypy"
```

---

### Task 5: Fix version and documentation drift

Three conflicting versions exist (pyproject 1.1.0, server.py "1.0.0", `__init__.py` "0.1.0"). The package is not installed as a distribution (no build-system), so `importlib.metadata` cannot work — `__init__.py.__version__` becomes the single runtime source. Tool counts and docstrings also drifted.

**Files:**

- Modify: `src/gramps_mcp/__init__.py` (version bump)
- Modify: `src/gramps_mcp/server.py` (module docstring line 21, root endpoint ~line 286-299, health endpoint ~line 302-309)
- Modify: `src/gramps_mcp/tools/data_management.py` (module docstring, lines 17-23)
- Modify: `README.md` (Architecture section, lines 213-233)

**Interfaces:**

- Consumes: `merge.py` must exist (Task 2) for the README tree to be accurate.
- Produces: `src.gramps_mcp.__version__ == "1.1.0"`.

- [ ] **Step 1: Single-source the version**

In `src/gramps_mcp/__init__.py`, change:

```python
__version__ = "0.1.0"
```

to:

```python
__version__ = "1.1.0"
```

- [ ] **Step 2: Fix `server.py`**

Module docstring (line 21): change `all 23 genealogy tools` to `all genealogy tools` (count-free, cannot drift again).

Add to the imports (after the `from pydantic import BaseModel, Field` line):

```python
from . import __version__
```

In the `root` endpoint, replace:

```python
    return JSONResponse(
        {
            "service": "Gramps MCP Server",
            "version": "1.0.0",
            "description": "MCP server for Gramps Web API genealogy operations",
            "mcp_endpoint": "/mcp",
            "tools_count": 16,
        }
    )
```

with:

```python
    return JSONResponse(
        {
            "service": "Gramps MCP Server",
            "version": __version__,
            "description": "MCP server for Gramps Web API genealogy operations",
            "mcp_endpoint": "/mcp",
            "tools_count": len(TOOL_REGISTRY),
        }
    )
```

In the `health_check` endpoint, replace:

```python
    return JSONResponse(
        {"status": "healthy", "service": "Gramps MCP Server", "tools": 16}
    )
```

with:

```python
    return JSONResponse(
        {"status": "healthy", "service": "Gramps MCP Server", "tools": len(TOOL_REGISTRY)}
    )
```

- [ ] **Step 3: Fix the `data_management.py` docstring**

It claims "8 CRUD tools" and omits repositories; there are 9. Replace:

```python
This module contains 8 CRUD tools for creating and updating people, families,
events, places, sources, citations, notes, and media records.
```

with:

```python
This module contains 9 CRUD tools for creating and updating people, families,
events, places, sources, citations, notes, media, and repository records.
```

- [ ] **Step 4: Fix the README Architecture section**

In `README.md`, replace the tree inside the "Core Components" code block (which currently lists a nonexistent `models.py`, `tools/tree_management.py`, and `client/` directory) with:

```
src/gramps_mcp/
|-- server.py           # MCP server, tool registry, HTTP/stdio transports
|-- client.py           # Unified Gramps Web API client
|-- merge.py            # Pure merge logic for PUT updates
|-- auth.py             # JWT authentication (singleton)
|-- config.py           # Configuration management
|-- utils.py            # Shared helpers
|-- models/             # Pydantic models
|   |-- api_calls.py    # API endpoint definitions
|   |-- api_mapping.py  # API call to parameter model mapping
|   `-- parameters/     # Parameter models per domain
|-- tools/              # MCP tool implementations
|   |-- search_basic.py
|   |-- search_details.py
|   |-- data_management.py
|   `-- analysis.py
|-- handlers/           # Data formatting handlers
`-- resources/          # MCP resources (GQL docs, usage guide)
```

- [ ] **Step 5: Verify**

```bash
uv run python -c "from src.gramps_mcp.server import TOOL_REGISTRY; from src.gramps_mcp import __version__; print(__version__, len(TOOL_REGISTRY))"
grep -rn "23 genealogy\|tools_count.*16\|\"tools\": 16\|1\.0\.0" src/gramps_mcp --include="*.py"
uv run pytest tests/test_config.py tests/test_merge.py tests/test_client_merge.py tests/test_utils.py -q
uv run ruff check src/
```

Expected: first command prints `1.1.0 16`; grep finds nothing; tests pass; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/gramps_mcp/__init__.py src/gramps_mcp/server.py src/gramps_mcp/tools/data_management.py README.md
uv run git commit -m "docs: fix version and tool-count drift in server, README, docstrings"
```

---

### Task 6: Standardize formatting on ruff format, drop black

Decision made with the user: pre-commit already enforces ruff-format; black disagrees with it and neither has been applied tree-wide (ruff format flags ~15 files). Standardize on ruff format, remove black, update CLAUDE.md. This task is LAST so the big mechanical diff never mixes with logic changes.

**Files:**

- Modify: `pyproject.toml` + `uv.lock` (via `uv remove`)
- Modify: `CLAUDE.md` (line 34, "Style & Conventions")
- Modify: ~15 files under `src/` and `tests/` (formatting only, done by ruff)

**Interfaces:**

- Consumes: all previous tasks committed (formats their final state).
- Produces: nothing consumed later.

- [ ] **Step 1: Remove black from dev dependencies**

```bash
uv remove --dev black
```

Expected: pyproject `[dependency-groups] dev` no longer lists black; lock updated; sync succeeds.

- [ ] **Step 2: Update CLAUDE.md**

Line 34, change:

```markdown
- **Follow PEP8**, use type hints, format with `black`, and lint with `ruff`.
```

to:

```markdown
- **Follow PEP8**, use type hints, format with `ruff format`, and lint with `ruff`.
```

- [ ] **Step 3: Format the tree**

```bash
uv run ruff format src/ tests/
```

Expected: reports ~15 files reformatted (count may differ slightly after earlier tasks).

- [ ] **Step 4: Verify everything still passes**

```bash
uv run ruff format --check src/ tests/
uv run ruff check src/
uv run mypy src/gramps_mcp --ignore-missing-imports
uv run pytest tests/test_config.py tests/test_merge.py tests/test_client_merge.py tests/test_utils.py -q
```

Expected: format check clean, ruff clean, mypy `Success: no issues found`, all tests pass.

- [ ] **Step 5: Commit**

Stage the formatted files explicitly (never `git add -A` — the user's `docker-compose.yml` / `docker/` changes must stay out):

```bash
git add pyproject.toml uv.lock CLAUDE.md src/ tests/
git status --short
```

Check `git status` output: `docker-compose.yml` and `docker/` must still show as unstaged/untracked. Then:

```bash
uv run git commit -m "chore: standardize formatting on ruff format, drop black"
```

---

## Final verification (whole plan)

```bash
uv run ruff check src/
uv run ruff format --check src/ tests/
uv run mypy src/gramps_mcp --ignore-missing-imports
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py -q
uv run python -c "import src.gramps_mcp.server; print('server loads')"
```

All clean/passing. The integration tests (`test_search_basic.py`, `test_data_management.py`, ...) still require a live Gramps Web server and are expected to fail offline — unchanged from before this work.
