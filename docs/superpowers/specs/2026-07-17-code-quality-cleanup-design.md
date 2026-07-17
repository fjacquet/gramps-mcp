# Code Quality Cleanup — Design

Date: 2026-07-17
Status: Approved

## Context

A code-quality review of the gramps-mcp server found a well-structured codebase
(clean tool registry, modular tools/handlers/models split, ruff-clean) with a
handful of concrete debts: dead code, documentation drift, an untested 70-line
data-merge block in the API client, duplicated URL construction, and broken
tooling. This cleanup fixes those without changing any runtime behavior.

Out of scope (deliberately): the offline-failing integration test suite
(requires a live Gramps Web instance), host/port configurability, mypy strict
mode, and new MCP tools. These are separate efforts.

## Changes

### 1. Remove dead module `src/gramps_mcp/tools.py`

The `tools/` package shadows the `tools.py` module: Python always resolves
`from .tools import ...` to the package, so the module has been unreachable
since the initial commit. Delete the file. No import in `src/` or `tests/`
can observe the difference. (Explicit user approval given for this deletion.)

### 2. Fix documentation/version drift

- `server.py` root endpoint: replace hardcoded `"version": "1.0.0"` with the
  package version read via `importlib.metadata.version("gramps-mcp")`.
- `server.py` root and `/health` endpoints: replace hardcoded `16` tool counts
  with `len(TOOL_REGISTRY)`.
- Fix docstrings that claim "23 genealogy tools" (server.py module docstring;
  any other occurrence found by grep).
- README "Architecture" section: reflect the real layout — `models/` is a
  package with a `parameters/` subpackage (not `models.py`); there is no
  `client/` directory and no `tools/tree_management.py`.

### 3. Extract PUT merge logic into a pure module

Create `src/gramps_mcp/merge.py` with a single pure function:

```python
def merge_put_data(existing: dict, changes: dict) -> dict
```

It reproduces, unchanged, the current inline logic in
`client.py` (`make_api_call`, PUT branch):

- Keys ending in `_list` whose value is a list and which exist in `existing`
  are merged with deduplication:
  - lists of dicts carrying a `ref` field: deduplicate by `ref`,
    keeping existing items first, appending only new refs;
  - lists of strings: deduplicate by value, existing first;
  - mixed/unknown item types: plain concatenation;
  - if either list is empty: plain concatenation.
- All other keys: the new value replaces the existing one.
- The input dicts are not mutated; the function returns the merged dict.

`GrampsWebAPIClient.make_api_call` calls `merge_put_data(existing, json_data)`
in place of the inline block. The surrounding flow (GET-before-PUT, the
`handle` lookup) stays in the client.

Tests in `tests/test_merge.py` (pure data transformation — no API involved,
so this complies with the project's no-mocks policy; there is nothing to
mock):

- dedup of ref-object lists (`event_ref_list`-style) by `ref`;
- dedup of plain string-handle lists;
- mixed-type lists fall back to concatenation;
- empty existing list / empty new list;
- non-`_list` fields are replaced, not merged;
- keys absent from `existing` are taken from `changes` as-is;
- inputs are not mutated.

Written TDD-style: tests capture the current behavior first, then the
extraction makes them pass against the new module.

### 4. Deduplicate base-URL construction

The `rstrip("/") + "/api"` construction exists in both `auth.py`
(`AuthManager.client` property) and `client.py` (`__init__`). Add a helper in
`config.py`:

```python
def get_api_base_url(settings) -> str
```

and use it in both places.

### 5. Tooling fixes

- `models/api_mapping.py` `validate_api_call_params`: annotate the return type
  as `Optional[BaseModel]` (it legitimately returns `None` when the call takes
  no parameters; the only caller, `client.py`, already guards for `None`).
  Update the docstring accordingly.
- `tools/data_management.py` `_extract_entity_data`: `entity_type: str = None`
  becomes `entity_type: Optional[str] = None`.
- black is broken in the venv (blib2to3 ImportError under Python 3.13):
  upgrade black to a current release and `uv sync` so `black --check` runs
  again (pre-commit relies on it).

## Verification

- `uv run ruff check src/` — clean (already clean today; must stay clean).
- `uv run black --check src/ tests/` — runs and passes.
- `uv run mypy src/gramps_mcp --ignore-missing-imports` — zero errors.
- `uv run pytest tests/test_merge.py tests/test_utils.py` — green.
- Full test suite: integration tests requiring the live server remain
  environment-dependent and are not gated on by this work.

## Risks

- The merge extraction touches the code path that mutates real genealogy data.
  Mitigation: the extraction is mechanical, behavior is pinned by unit tests
  written against the current logic before the move.
- Version lookup via `importlib.metadata` requires the package to be installed
  (it is, via `uv sync` / the Docker image). Fallback: catch
  `PackageNotFoundError` and return `"unknown"`.
