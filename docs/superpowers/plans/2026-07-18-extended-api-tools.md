# Extended API Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register 5 new MCP tools (`get_relationship`, `check_living`, `get_timeline`, `manage_tags`, `get_facts`) that wire up Gramps Web API domains the client already models but never exposes, bringing `TOOL_REGISTRY` from 16 to 21 entries.

**Architecture:** Each tool follows the existing pattern — a small Pydantic "arguments" schema, an async tool function using `@with_client`, a call to `client.make_api_call()` with an already-mapped `ApiCalls` member and parameter model, and a markdown-formatting handler function. A new shared utility (`resolve_person_handle`/`resolve_family_handle` in `utils.py`) replaces the fragile regex-based handle lookup used elsewhere, giving 3 of the 5 tools a clean way to accept a person/family by either `handle` or `gramps_id`.

**Tech Stack:** Python, pydantic, MCP Python SDK, httpx (via the existing `GrampsWebAPIClient`) — no new dependencies.

Spec: `docs/superpowers/specs/2026-07-18-extended-api-tools-design.md`

## Important discovery made while planning (read before starting)

A live Gramps Web server is reachable from this machine at `http://localhost:80`
(a `grampsweb`-style Docker container with port 80 mapped to its internal
port 5000 — confirm with `docker ps`). The project's own `.env` points
`GRAMPS_API_URL` at `http://host.docker.internal:80`, a hostname that only
resolves from *inside* another Docker container, not from a host shell —
that's why direct `uv run pytest` runs on the host see connection errors for
server-dependent tests, even though a real server is right there.

**Do not edit `.env`.** For any test in this plan that needs a live server,
run it with a one-off shell override:

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest ...
```

If `docker ps` shows no such container running, or the override still fails
to connect, treat that test exactly like the project's existing ~31
server-dependent tests: a connection failure is expected and is not a
blocker for this plan (note it in your task report and move on — do not
spend time trying to stand up a server).

While probing the live server to design test fixtures, a **real,
pre-existing bug** was found and confirmed (Task 1 below fixes it): `GET_FACTS`
currently 422s because `FactsParams.living` is an `Enum` field, and
`client.py`'s `model_dump(exclude_none=True)` (default "python" mode) leaves
enum members as objects, which then serialize into the query string as
`living=LivingProxy.INCLUDE_ALL` instead of `living=IncludeAll`. This blocks
`get_facts` (Task 6) entirely, so it must be fixed first.

**Do not reference real people from the live tree in any file this plan
creates or modifies** (this is the user's actual family tree, ~2119 people).
Follow the exact convention the existing test suite already uses: reference
records only by their generic, tree-structural IDs (`I0001`, `F0001` — the
first person/family Gramps assigns in any tree) and assert on *structural*
properties of responses (a field is present, a list is non-empty, no
`Error:` text), never on real names, dates, or places.

## Global Constraints

- Run everything through uv. Commit via `uv run git commit` (pre-commit hooks
  installed: ruff, ruff-format, copyright-notice on `.py` files, file-length
  check ≤500 lines, no-emoji check).
- Never `git add -A` or `git add .` — the working tree may contain the
  user's unrelated WIP (`docker-compose.yml`, `docker/`). Stage only the
  files each task names.
- No emojis. Google-style docstrings on every new function. New `src/`
  files get the 16-line AGPL header (copy verbatim from the top of
  `src/gramps_mcp/client.py`, lines 1-15 plus the blank line 16). Files
  under `tests/` do not get the header.
- `uv run ruff check src/`, `uv run ruff format --check src/ tests/`, and
  `uv run mypy src/gramps_mcp --ignore-missing-imports` must stay clean
  after every task.
- The 4 existing CI-covered offline tests
  (`tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py`)
  must keep passing unchanged; run them after every task as a regression
  check even though this plan's own new tests are server-dependent.
- No new tool in this plan exposes deletion of any entity (decided during
  brainstorming — matches every existing tool in the project).
- All parameter-model-to-API-call mappings needed by this plan already
  exist in `src/gramps_mcp/models/api_mapping.py` — **no task in this plan
  modifies that file.**

---

### Task 1: Fix enum query-parameter serialization in the API client

This is a pre-existing bug, not something introduced by this plan, but
`get_facts` (Task 6) cannot work without it — fixing it now, first, means
every later task builds on a client that actually supports enum-typed
fields correctly.

**Files:**

- Modify: `src/gramps_mcp/client.py` (inside `make_api_call`)
- Test: `tests/test_client.py` (add one test class)

**Interfaces:**

- Consumes: nothing from other tasks.
- Produces: `GrampsWebAPIClient.make_api_call` now serializes any
  Pydantic-enum-typed field to its plain string `.value` before sending it
  as a query parameter or JSON body value. No signature change — purely
  internal behavior fix. Later tasks (Task 6 specifically) rely on this.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_client.py` (the file already has
`from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams`
at the top; add one more import line right after it, then the test class at
the end of the file):

```python
from src.gramps_mcp.models.parameters.facts_params import FactsParams, LivingProxy
```

```python
class TestEnumParamSerialization:
    """Test that enum-typed parameter fields serialize to plain strings."""

    @pytest.mark.asyncio
    async def test_get_facts_with_default_living_proxy_succeeds(self):
        """GET_FACTS must not 422 due to LivingProxy enum leaking into the query string."""
        settings = get_settings()
        client = GrampsWebAPIClient()

        try:
            params = FactsParams(living=LivingProxy.INCLUDE_ALL, rank=1)
            result = await client.make_api_call(
                api_call=ApiCalls.GET_FACTS,
                params=params,
                tree_id=settings.gramps_tree_id,
            )
            assert isinstance(result, list)
        finally:
            await client.close()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_client.py::TestEnumParamSerialization -v
```

Expected: FAIL with `GrampsAPIError: Invalid data provided.` (a 422 from the
live server, because `living` is currently sent as
`LivingProxy.INCLUDE_ALL`). If this test instead fails with a connection
error, follow the "Important discovery" section above — confirm via
`docker ps` whether a live server is reachable at all before concluding
this step didn't work as expected.

- [ ] **Step 3: Fix `client.py`**

In `src/gramps_mcp/client.py`, inside `make_api_call`, find:

```python
        if validated_params is not None:
            params_dict = validated_params.model_dump(exclude_none=True)
```

Replace with:

```python
        if validated_params is not None:
            params_dict = validated_params.model_dump(exclude_none=True, mode="json")
```

(`mode="json"` makes pydantic convert enum members to their plain `.value`
— confirmed to produce byte-identical output to the current "python" mode
for every other field type already in use in this project, since no
parameter model uses `datetime`/`UUID`/other types that mode="json" would
otherwise change.)

- [ ] **Step 4: Run the test to verify it passes**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_client.py::TestEnumParamSerialization -v
```

Expected: PASS.

- [ ] **Step 5: Run the full existing test_client.py file and the offline suite to check for regressions**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_client.py -v
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py -q
uv run ruff check src/
uv run mypy src/gramps_mcp --ignore-missing-imports
```

Expected: all `test_client.py` tests pass (or fail only with a connection
error if the live server isn't reachable in your environment — not this
change's fault); the 4 offline tests still `18 passed`; ruff and mypy clean.

- [ ] **Step 6: Commit**

```bash
git add src/gramps_mcp/client.py tests/test_client.py
uv run git commit -m "fix: serialize enum parameter fields to plain strings in API client"
```

---

### Task 2: Shared handle resolver + `get_relationship` tool

**Files:**

- Modify: `src/gramps_mcp/utils.py` (add `resolve_person_handle`)
- Create: `src/gramps_mcp/tools/relationship_tools.py`
- Create: `src/gramps_mcp/handlers/relationship_handler.py`
- Modify: `src/gramps_mcp/server.py` (imports + `TOOL_REGISTRY`)
- Test: `tests/test_relationship_tools.py`

**Interfaces:**

- Consumes: `RelationParams` (`src/gramps_mcp/models/parameters/relations_params.py`,
  fields `handle1: str`, `handle2: str`, `depth: Optional[int]` — already
  exists, already mapped to both `ApiCalls.GET_RELATIONS` and
  `ApiCalls.GET_RELATIONS_ALL` in `api_mapping.py`); `get_gramps_id_from_handle`
  (`src/gramps_mcp/utils.py`, signature
  `async def get_gramps_id_from_handle(client, obj_class: str, obj_handle: str, tree_id: str) -> str`
  — already exists).
- Produces: `resolve_person_handle(client, tree_id: str, gramps_id: str) -> Optional[str]`
  in `utils.py` — consumed by Task 3 and Task 4. `_resolve_person(client, tree_id, value) -> str`
  (a private helper in `tools/relationship_tools.py` that decides whether
  `value` is a `gramps_id` to resolve or an already-valid handle) — consumed
  by Task 3 and Task 4, which add their own tool functions to this same
  file. `GRAMPS_ID_PATTERN` (a module-level compiled regex in
  `tools/relationship_tools.py`) — consumed the same way.

- [ ] **Step 1: Add `resolve_person_handle` to `utils.py`**

`src/gramps_mcp/utils.py` currently starts:

```python
"""
Utility functions for gramps_mcp.
"""

from markdownify import markdownify as md

from .models.api_calls import ApiCalls
```

Change the import block to add `Optional`:

```python
"""
Utility functions for gramps_mcp.
"""

from typing import Optional

from markdownify import markdownify as md

from .models.api_calls import ApiCalls
```

Append this function at the end of the file:

```python
async def resolve_person_handle(client, tree_id: str, gramps_id: str) -> Optional[str]:
    """
    Look up a person's handle by gramps_id via a direct GQL search.

    Args:
        client: GrampsWebAPIClient instance
        tree_id: Family tree identifier
        gramps_id: The person's gramps_id (e.g. "I0044")

    Returns:
        The person's handle if a matching person is found, otherwise None
    """
    result = await client.make_api_call(
        api_call=ApiCalls.GET_PEOPLE,
        params={"gql": f'gramps_id="{gramps_id}"', "pagesize": 1},
        tree_id=tree_id,
    )
    if result and isinstance(result, list) and len(result) > 0:
        return result[0].get("handle")
    return None
```

- [ ] **Step 2: Create the relationship handler**

Create `src/gramps_mcp/handlers/relationship_handler.py`. Start with the
16-line AGPL header (copy from `client.py` lines 1-15 plus the blank line),
then:

```python
"""
Relationship data handler for Gramps MCP operations.

Formats direct and all-possible relationship results between two people.
"""

from typing import Dict, List

from ..utils import get_gramps_id_from_handle


def format_relationship(data: Dict) -> str:
    """
    Format a single most-direct relationship result.

    Args:
        data: Relationship dict with relationship_string,
            distance_common_origin, distance_common_other

    Returns:
        Formatted relationship string
    """
    if not data:
        return "No relationship found between these two people."

    relationship_string = data.get("relationship_string", "Unknown relationship")
    result = f"**Relationship:** {relationship_string}\n"

    distance_origin = data.get("distance_common_origin")
    distance_other = data.get("distance_common_other")

    if distance_origin is not None and distance_origin != -1:
        result += f"Generations to common ancestor: {distance_origin}\n"
    if distance_other is not None and distance_other != -1:
        result += (
            f"Generations from common ancestor to other person: {distance_other}\n"
        )

    return result


async def format_relationships(data: List[Dict], client, tree_id: str) -> str:
    """
    Format all-possible-relationships results.

    Args:
        data: List of relationship dicts with relationship_string,
            common_ancestors
        client: Gramps API client instance
        tree_id: Family tree identifier

    Returns:
        Formatted relationships string
    """
    if not data:
        return "No relationships found between these two people."

    result = f"Found {len(data)} possible relationship(s):\n\n"

    for item in data:
        relationship_string = item.get("relationship_string", "Unknown relationship")
        result += f"• **{relationship_string}**\n"

        common_ancestors = item.get("common_ancestors", [])
        if common_ancestors:
            ancestor_ids = []
            for handle in common_ancestors:
                gramps_id = await get_gramps_id_from_handle(
                    client, "person", handle, tree_id
                )
                ancestor_ids.append(gramps_id)
            result += f"  Common ancestors: {', '.join(ancestor_ids)}\n"

        result += "\n"

    return result
```

- [ ] **Step 3: Create `tools/relationship_tools.py` with `get_relationship_tool`**

Create `src/gramps_mcp/tools/relationship_tools.py`, starting with the AGPL
header, then:

```python
"""
Relationship analysis MCP tools for genealogy operations.

This module contains tools for calculating relationships between people,
checking living status, and building timelines.
"""

import logging
import re
from typing import Dict, List

from mcp.types import TextContent

from ..client import GrampsAPIError
from ..config import get_settings
from ..handlers.relationship_handler import format_relationship, format_relationships
from ..models.api_calls import ApiCalls
from ..models.parameters.relations_params import RelationParams
from ..utils import resolve_person_handle
from .search_basic import with_client

logger = logging.getLogger(__name__)

GRAMPS_ID_PATTERN = re.compile(r"^[A-Z]+[0-9]+$")


def _format_error_response(error: Exception, operation: str) -> List[TextContent]:
    """Format error into user-friendly MCP response."""
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"

    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


async def _resolve_person(client, tree_id: str, value: str) -> str:
    """
    Resolve a person reference that may be a handle or a gramps_id.

    Values matching GRAMPS_ID_PATTERN (one or more uppercase letters
    followed by one or more digits, e.g. "I0044") are treated as a
    gramps_id and resolved; anything else is treated as an already-valid
    handle.

    Args:
        client: Gramps API client instance
        tree_id: Family tree identifier
        value: Handle or gramps_id string

    Returns:
        A resolved handle

    Raises:
        ValueError: If value looks like a gramps_id but no matching person
            is found
    """
    if GRAMPS_ID_PATTERN.match(value):
        handle = await resolve_person_handle(client, tree_id, value)
        if not handle:
            raise ValueError(f"No person found with gramps_id '{value}'")
        return handle
    return value


@with_client
async def get_relationship_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Calculate the relationship between two people.
    """
    try:
        person1 = arguments.get("person1")
        person2 = arguments.get("person2")
        all_relationships = arguments.get("all_relationships", False)
        depth = arguments.get("depth")

        if not person1 or not person2:
            raise ValueError("person1 and person2 are required")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        handle1 = await _resolve_person(client, tree_id, person1)
        handle2 = await _resolve_person(client, tree_id, person2)

        params = RelationParams(handle1=handle1, handle2=handle2, depth=depth)

        api_call = (
            ApiCalls.GET_RELATIONS_ALL if all_relationships else ApiCalls.GET_RELATIONS
        )

        result = await client.make_api_call(
            api_call=api_call, params=params, tree_id=tree_id
        )

        if all_relationships:
            formatted = await format_relationships(result, client, tree_id)
        else:
            formatted = format_relationship(result)

        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, "relationship calculation")
```

- [ ] **Step 4: Register `get_relationship` in `server.py`**

In `src/gramps_mcp/server.py`, find:

```python
from .tools.search_basic import find_type_tool
from .tools.search_details import get_type_tool
```

Replace with:

```python
from .tools.relationship_tools import get_relationship_tool
from .tools.search_basic import find_type_tool
from .tools.search_details import get_type_tool
```

Find the `AncestorsParams` class (ends right before `# Setup logging`):

```python
class AncestorsParams(BaseModel):
    gramps_id: str = Field(..., description="Person ID")
    max_generations: Optional[int] = Field(
        5,
        description=(
            "Max generations to retrieve (default: 5, use higher values "
            "carefully as they can overflow context)"
        ),
    )


# Setup logging
```

Replace with (adding `RelationshipQueryParams` right after `AncestorsParams`):

```python
class AncestorsParams(BaseModel):
    gramps_id: str = Field(..., description="Person ID")
    max_generations: Optional[int] = Field(
        5,
        description=(
            "Max generations to retrieve (default: 5, use higher values "
            "carefully as they can overflow context)"
        ),
    )


class RelationshipQueryParams(BaseModel):
    person1: str = Field(
        ..., description="Handle or gramps_id of the first person"
    )
    person2: str = Field(
        ..., description="Handle or gramps_id of the second person"
    )
    all_relationships: bool = Field(
        False,
        description=(
            "If true, return all possible relationships; if false, only "
            "the most direct one"
        ),
    )
    depth: Optional[int] = Field(
        None, ge=1, description="Search depth in generations (API default: 15)"
    )


# Setup logging
```

Find the `"recent_changes"` entry (currently the last one in
`TOOL_REGISTRY`, immediately before the closing `}`):

```python
    "recent_changes": {
        "description": "Get recent changes/modifications to the family tree",
        "schema": TransactionHistoryParams,
        "handler": get_recent_changes_tool,
    },
}
```

Replace with:

```python
    "recent_changes": {
        "description": "Get recent changes/modifications to the family tree",
        "schema": TransactionHistoryParams,
        "handler": get_recent_changes_tool,
    },
    "get_relationship": {
        "description": (
            "Calculate the relationship between two people (accepts handle "
            "or gramps_id for each)"
        ),
        "schema": RelationshipQueryParams,
        "handler": get_relationship_tool,
    },
}
```

- [ ] **Step 5: Verify the server module still loads**

```bash
uv run python -c "from src.gramps_mcp.server import TOOL_REGISTRY; print(len(TOOL_REGISTRY))"
```

Expected: `17`.

- [ ] **Step 6: Write the integration test**

Create `tests/test_relationship_tools.py` (no AGPL header — tests are
excluded):

```python
"""
Integration tests for relationship analysis tools using the real Gramps API.

Uses only generic tree-structural IDs (I0001, I0002) - no real person
details are referenced or asserted on.
"""

import pytest

from src.gramps_mcp.tools.relationship_tools import get_relationship_tool


class TestGetRelationshipTool:
    """Test the get_relationship_tool against a live Gramps Web server."""

    @pytest.mark.asyncio
    async def test_get_relationship_by_gramps_id(self):
        result = await get_relationship_tool(
            {"person1": "I0001", "person2": "I0002"}
        )
        text = result[0].text
        assert "error" not in text.lower()
        assert "**Relationship:**" in text

    @pytest.mark.asyncio
    async def test_get_all_relationships_by_gramps_id(self):
        result = await get_relationship_tool(
            {"person1": "I0001", "person2": "I0002", "all_relationships": True}
        )
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_missing_person_argument_returns_error(self):
        result = await get_relationship_tool({"person1": "I0001"})
        text = result[0].text
        assert "error" in text.lower()
```

- [ ] **Step 7: Run the test**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_relationship_tools.py -v
```

Expected: all 3 tests pass. If connection errors occur instead, follow the
"Important discovery" section at the top of this plan — this is expected
and acceptable if no live server is reachable in your environment; note it
in your report rather than treating it as a task failure.

- [ ] **Step 8: Run the offline regression suite and lint**

```bash
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py -q
uv run ruff check src/
uv run ruff format --check src/ tests/
uv run mypy src/gramps_mcp --ignore-missing-imports
```

Expected: `18 passed`; ruff/format/mypy clean.

- [ ] **Step 9: Commit**

```bash
git add src/gramps_mcp/utils.py src/gramps_mcp/tools/relationship_tools.py src/gramps_mcp/handlers/relationship_handler.py src/gramps_mcp/server.py tests/test_relationship_tools.py
uv run git commit -m "feat: add get_relationship tool for relationship calculation"
```

---

### Task 3: `check_living` tool

**Files:**

- Modify: `src/gramps_mcp/tools/relationship_tools.py` (add `check_living_tool`)
- Create: `src/gramps_mcp/handlers/living_handler.py`
- Modify: `src/gramps_mcp/server.py` (imports + `TOOL_REGISTRY`)
- Modify: `tests/test_relationship_tools.py` (add a test class)

**Interfaces:**

- Consumes: `_resolve_person`, `_format_error_response`, `GRAMPS_ID_PATTERN`
  (all from `tools/relationship_tools.py`, added in Task 2); `LivingParams`
  (`src/gramps_mcp/models/parameters/living_params.py`, fields
  `handle: str`, `average_generation_gap: Optional[int]`,
  `max_age_probably_alive: Optional[int]`, `max_sibling_age_difference: Optional[int]`
  — already exists, already mapped to both `ApiCalls.GET_LIVING` and
  `ApiCalls.GET_LIVING_DATES`).
- Produces: `check_living_tool` — consumed only by `server.py`'s
  `TOOL_REGISTRY`, nothing else in this plan depends on it.

- [ ] **Step 1: Create the living-status handler**

Create `src/gramps_mcp/handlers/living_handler.py` with the AGPL header,
then:

```python
"""
Living status data handler for Gramps MCP operations.

Formats living-status and estimated-dates results for a person.
"""

from typing import Dict, Optional


def format_living_status(living: Dict, dates: Optional[Dict]) -> str:
    """
    Format living-status data, optionally including estimated dates.

    Args:
        living: Dict with a "living" boolean field
        dates: Optional dict with "birth", "death", "explain", "other" fields

    Returns:
        Formatted living-status string
    """
    is_living = living.get("living")
    result = f"**Living:** {'Yes' if is_living else 'No'}\n"

    if dates:
        birth = dates.get("birth")
        death = dates.get("death")
        explain = dates.get("explain")

        if birth:
            result += f"Estimated birth: {birth}\n"
        if death:
            result += f"Estimated death: {death}\n"
        if explain:
            result += f"Explanation: {explain}\n"

    return result
```

- [ ] **Step 2: Add `check_living_tool` to `tools/relationship_tools.py`**

At the top of `src/gramps_mcp/tools/relationship_tools.py`, find:

```python
from ..handlers.relationship_handler import format_relationship, format_relationships
from ..models.api_calls import ApiCalls
from ..models.parameters.relations_params import RelationParams
from ..utils import resolve_person_handle
```

Replace with:

```python
from ..handlers.living_handler import format_living_status
from ..handlers.relationship_handler import format_relationship, format_relationships
from ..models.api_calls import ApiCalls
from ..models.parameters.living_params import LivingParams
from ..models.parameters.relations_params import RelationParams
from ..utils import resolve_person_handle
```

At the end of the file, after `get_relationship_tool`, append:

```python
@with_client
async def check_living_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Check whether a person is living and get estimated birth/death dates.
    """
    try:
        person = arguments.get("person")
        include_dates = arguments.get("include_dates", True)

        if not person:
            raise ValueError("person is required")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        handle = await _resolve_person(client, tree_id, person)

        params = LivingParams(
            handle=handle,
            average_generation_gap=arguments.get("average_generation_gap"),
            max_age_probably_alive=arguments.get("max_age_probably_alive"),
            max_sibling_age_difference=arguments.get("max_sibling_age_difference"),
        )

        living_result = await client.make_api_call(
            api_call=ApiCalls.GET_LIVING, params=params, tree_id=tree_id
        )

        dates_result = None
        if include_dates:
            dates_result = await client.make_api_call(
                api_call=ApiCalls.GET_LIVING_DATES, params=params, tree_id=tree_id
            )

        formatted = format_living_status(living_result, dates_result)
        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, "living status check")
```

- [ ] **Step 3: Register `check_living` in `server.py`**

Find:

```python
from .tools.relationship_tools import get_relationship_tool
```

Replace with:

```python
from .tools.relationship_tools import check_living_tool, get_relationship_tool
```

Find the `RelationshipQueryParams` class (added in Task 2), ending right
before `# Setup logging`:

```python
class RelationshipQueryParams(BaseModel):
    person1: str = Field(
        ..., description="Handle or gramps_id of the first person"
    )
    person2: str = Field(
        ..., description="Handle or gramps_id of the second person"
    )
    all_relationships: bool = Field(
        False,
        description=(
            "If true, return all possible relationships; if false, only "
            "the most direct one"
        ),
    )
    depth: Optional[int] = Field(
        None, ge=1, description="Search depth in generations (API default: 15)"
    )


# Setup logging
```

Replace with (adding `LivingStatusParams` right after):

```python
class RelationshipQueryParams(BaseModel):
    person1: str = Field(
        ..., description="Handle or gramps_id of the first person"
    )
    person2: str = Field(
        ..., description="Handle or gramps_id of the second person"
    )
    all_relationships: bool = Field(
        False,
        description=(
            "If true, return all possible relationships; if false, only "
            "the most direct one"
        ),
    )
    depth: Optional[int] = Field(
        None, ge=1, description="Search depth in generations (API default: 15)"
    )


class LivingStatusParams(BaseModel):
    person: str = Field(
        ..., description="Handle or gramps_id of the person to evaluate"
    )
    average_generation_gap: Optional[int] = Field(None, ge=1)
    max_age_probably_alive: Optional[int] = Field(None, ge=1)
    max_sibling_age_difference: Optional[int] = Field(None, ge=0)
    include_dates: bool = Field(
        True, description="Also fetch estimated birth/death dates"
    )


# Setup logging
```

Find the `"get_relationship"` entry (currently last, immediately before the
closing `}`):

```python
    "get_relationship": {
        "description": (
            "Calculate the relationship between two people (accepts handle "
            "or gramps_id for each)"
        ),
        "schema": RelationshipQueryParams,
        "handler": get_relationship_tool,
    },
}
```

Replace with:

```python
    "get_relationship": {
        "description": (
            "Calculate the relationship between two people (accepts handle "
            "or gramps_id for each)"
        ),
        "schema": RelationshipQueryParams,
        "handler": get_relationship_tool,
    },
    "check_living": {
        "description": (
            "Check whether a person is living and get estimated birth/death "
            "dates (accepts handle or gramps_id)"
        ),
        "schema": LivingStatusParams,
        "handler": check_living_tool,
    },
}
```

- [ ] **Step 4: Verify the server module still loads**

```bash
uv run python -c "from src.gramps_mcp.server import TOOL_REGISTRY; print(len(TOOL_REGISTRY))"
```

Expected: `18`.

- [ ] **Step 5: Add the integration test**

Append to `tests/test_relationship_tools.py`:

```python
from src.gramps_mcp.tools.relationship_tools import check_living_tool


class TestCheckLivingTool:
    """Test the check_living_tool against a live Gramps Web server."""

    @pytest.mark.asyncio
    async def test_check_living_by_gramps_id(self):
        result = await check_living_tool({"person": "I0001"})
        text = result[0].text
        assert "error" not in text.lower()
        assert "**Living:**" in text

    @pytest.mark.asyncio
    async def test_check_living_without_dates(self):
        result = await check_living_tool({"person": "I0001", "include_dates": False})
        text = result[0].text
        assert "error" not in text.lower()
        assert "**Living:**" in text

    @pytest.mark.asyncio
    async def test_missing_person_argument_returns_error(self):
        result = await check_living_tool({})
        text = result[0].text
        assert "error" in text.lower()
```

- [ ] **Step 6: Run the test**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_relationship_tools.py -v
```

Expected: all 6 tests (3 from Task 2 + 3 new) pass, or connection errors if
no live server is reachable (see the note in Step 7 of Task 2).

- [ ] **Step 7: Run the offline regression suite and lint**

```bash
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py -q
uv run ruff check src/
uv run ruff format --check src/ tests/
uv run mypy src/gramps_mcp --ignore-missing-imports
```

Expected: `18 passed`; ruff/format/mypy clean.

- [ ] **Step 8: Commit**

```bash
git add src/gramps_mcp/tools/relationship_tools.py src/gramps_mcp/handlers/living_handler.py src/gramps_mcp/server.py tests/test_relationship_tools.py
uv run git commit -m "feat: add check_living tool for living-status checks"
```

---

### Task 4: Family handle resolver + `get_timeline` tool

**Files:**

- Modify: `src/gramps_mcp/utils.py` (add `resolve_family_handle`)
- Modify: `src/gramps_mcp/tools/relationship_tools.py` (add `get_timeline_tool`)
- Create: `src/gramps_mcp/handlers/timeline_handler.py`
- Modify: `src/gramps_mcp/server.py` (imports + `TOOL_REGISTRY`)
- Modify: `tests/test_relationship_tools.py` (add a test class)

**Interfaces:**

- Consumes: `_resolve_person`, `_format_error_response` (from Task 2);
  `PersonTimelineParams` (`src/gramps_mcp/models/parameters/people_params.py`,
  fields `dates`, `first`, `last`, `ancestors`, `offspring`, `events`,
  `event_classes`, `relatives` — all `Optional`, no `handle` field, since
  the handle is a pure URL path parameter for this endpoint);
  `FamilyTimelineParams` (`src/gramps_mcp/models/parameters/family_params.py`,
  fields `handle: str` (required — also a URL path param; this endpoint's
  existing model design means the handle appears in *both* the URL and the
  query string when this call is made — that is pre-existing model design,
  not something this task changes), `dates`, `events`, `event_classes`,
  `ratings`, `discard_empty`, `page`, `pagesize`); `PeopleTimelineParams` and
  `FamiliesTimelineParams` (`src/gramps_mcp/models/parameters/timeline_params.py`,
  fields already listed in the spec) — all four already mapped in
  `api_mapping.py` to `ApiCalls.GET_PERSON_TIMELINE`, `GET_FAMILY_TIMELINE`,
  `GET_TIMELINES_PEOPLE`, `GET_TIMELINES_FAMILIES` respectively.
- Produces: `resolve_family_handle(client, tree_id, gramps_id) -> Optional[str]`
  in `utils.py` — not consumed elsewhere in this plan (only `get_timeline`'s
  family scope needs it). `_resolve_family(client, tree_id, value) -> str`
  helper in `tools/relationship_tools.py`, mirroring `_resolve_person`.

- [ ] **Step 1: Add `resolve_family_handle` to `utils.py`**

Append to `src/gramps_mcp/utils.py` (after `resolve_person_handle`):

```python
async def resolve_family_handle(client, tree_id: str, gramps_id: str) -> Optional[str]:
    """
    Look up a family's handle by gramps_id via a direct GQL search.

    Args:
        client: GrampsWebAPIClient instance
        tree_id: Family tree identifier
        gramps_id: The family's gramps_id (e.g. "F0012")

    Returns:
        The family's handle if a matching family is found, otherwise None
    """
    result = await client.make_api_call(
        api_call=ApiCalls.GET_FAMILIES,
        params={"gql": f'gramps_id="{gramps_id}"', "pagesize": 1},
        tree_id=tree_id,
    )
    if result and isinstance(result, list) and len(result) > 0:
        return result[0].get("handle")
    return None
```

- [ ] **Step 2: Create the timeline handler**

Create `src/gramps_mcp/handlers/timeline_handler.py` with the AGPL header,
then:

```python
"""
Timeline data handler for Gramps MCP operations.

Formats chronological event lists from person, family, and group timeline
endpoints.
"""

from typing import Dict, List, Union


def format_timeline(data: Union[Dict, List[Dict]]) -> str:
    """
    Format timeline event data into a chronological markdown list.

    The Gramps Web API spec for the single-person/single-family timeline
    endpoints does not clearly show list-wrapping in its schema, so this
    accepts either a single event dict or a list of them defensively.

    Args:
        data: A single timeline event dict, or a list of them

    Returns:
        Formatted timeline string
    """
    if not data:
        events = []
    elif isinstance(data, list):
        events = data
    else:
        events = [data]

    if not events:
        return "No timeline events found."

    result = f"Found {len(events)} timeline event(s):\n\n"

    for event in events:
        date = event.get("date", "Unknown date")
        label = event.get("label") or event.get("description", "Event")
        age = event.get("age")

        result += f"• **{date}** - {label}"
        if age:
            result += f" (age {age})"
        result += "\n"

        citations = event.get("citations")
        confidence = event.get("confidence")
        if citations is not None or confidence is not None:
            result += f"  Citations: {citations or 0}, Confidence: {confidence or 0}\n"

        result += "\n"

    return result
```

- [ ] **Step 3: Add `get_timeline_tool` to `tools/relationship_tools.py`**

At the top of `src/gramps_mcp/tools/relationship_tools.py`, find:

```python
from ..handlers.living_handler import format_living_status
from ..handlers.relationship_handler import format_relationship, format_relationships
from ..models.api_calls import ApiCalls
from ..models.parameters.living_params import LivingParams
from ..models.parameters.relations_params import RelationParams
from ..utils import resolve_person_handle
```

Replace with:

```python
from ..handlers.living_handler import format_living_status
from ..handlers.relationship_handler import format_relationship, format_relationships
from ..handlers.timeline_handler import format_timeline
from ..models.api_calls import ApiCalls
from ..models.parameters.family_params import FamilyTimelineParams
from ..models.parameters.living_params import LivingParams
from ..models.parameters.people_params import PersonTimelineParams
from ..models.parameters.relations_params import RelationParams
from ..models.parameters.timeline_params import (
    FamiliesTimelineParams,
    PeopleTimelineParams,
)
from ..utils import resolve_family_handle, resolve_person_handle
```

Add this helper right after `_resolve_person` (which was added in Task 2):

```python
async def _resolve_family(client, tree_id: str, value: str) -> str:
    """
    Resolve a family reference that may be a handle or a gramps_id.

    Values matching GRAMPS_ID_PATTERN are treated as a gramps_id and
    resolved; anything else is treated as an already-valid handle.

    Args:
        client: Gramps API client instance
        tree_id: Family tree identifier
        value: Handle or gramps_id string

    Returns:
        A resolved handle

    Raises:
        ValueError: If value looks like a gramps_id but no matching family
            is found
    """
    if GRAMPS_ID_PATTERN.match(value):
        handle = await resolve_family_handle(client, tree_id, value)
        if not handle:
            raise ValueError(f"No family found with gramps_id '{value}'")
        return handle
    return value
```

At the end of the file, after `check_living_tool`, append:

```python
@with_client
async def get_timeline_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Build a chronological timeline for a person, family, or group.
    """
    try:
        scope = arguments.get("scope")
        target = arguments.get("target")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        if scope == "person":
            if not target:
                raise ValueError("target is required when scope is 'person'")
            handle = await _resolve_person(client, tree_id, target)
            params = PersonTimelineParams(
                dates=arguments.get("dates"),
                first=arguments.get("first"),
                last=arguments.get("last"),
                events=arguments.get("events"),
                event_classes=arguments.get("event_classes"),
            )
            result = await client.make_api_call(
                api_call=ApiCalls.GET_PERSON_TIMELINE,
                params=params,
                tree_id=tree_id,
                handle=handle,
            )

        elif scope == "family":
            if not target:
                raise ValueError("target is required when scope is 'family'")
            handle = await _resolve_family(client, tree_id, target)
            params = FamilyTimelineParams(
                handle=handle,
                dates=arguments.get("dates"),
                events=arguments.get("events"),
                event_classes=arguments.get("event_classes"),
                ratings=arguments.get("ratings"),
                discard_empty=arguments.get("discard_empty"),
                page=arguments.get("page"),
                pagesize=arguments.get("pagesize"),
            )
            result = await client.make_api_call(
                api_call=ApiCalls.GET_FAMILY_TIMELINE,
                params=params,
                tree_id=tree_id,
                handle=handle,
            )

        elif scope == "people":
            anchor = None
            if target:
                anchor = await _resolve_person(client, tree_id, target)
            params = PeopleTimelineParams(
                anchor=anchor,
                dates=arguments.get("dates"),
                first=arguments.get("first", True),
                last=arguments.get("last", True),
                handles=arguments.get("handles"),
                events=arguments.get("events"),
                event_classes=arguments.get("event_classes"),
                ratings=arguments.get("ratings", False),
                precision=arguments.get("precision", 1),
                discard_empty=arguments.get("discard_empty", True),
                page=arguments.get("page", 0),
                pagesize=arguments.get("pagesize", 20),
            )
            result = await client.make_api_call(
                api_call=ApiCalls.GET_TIMELINES_PEOPLE, params=params, tree_id=tree_id
            )

        elif scope == "families":
            params = FamiliesTimelineParams(
                handles=arguments.get("handles"),
                dates=arguments.get("dates"),
                events=arguments.get("events"),
                event_classes=arguments.get("event_classes"),
                ratings=arguments.get("ratings", False),
                discard_empty=arguments.get("discard_empty", True),
                page=arguments.get("page", 0),
                pagesize=arguments.get("pagesize", 20),
            )
            result = await client.make_api_call(
                api_call=ApiCalls.GET_TIMELINES_FAMILIES, params=params, tree_id=tree_id
            )

        else:
            raise ValueError(f"Invalid scope: {scope}")

        formatted = format_timeline(result)
        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, "timeline retrieval")
```

- [ ] **Step 4: Register `get_timeline` in `server.py`**

Find:

```python
from .tools.relationship_tools import check_living_tool, get_relationship_tool
```

Replace with:

```python
from .tools.relationship_tools import (
    check_living_tool,
    get_relationship_tool,
    get_timeline_tool,
)
```

Find the `LivingStatusParams` class (added in Task 3), ending right before
`# Setup logging`:

```python
class LivingStatusParams(BaseModel):
    person: str = Field(
        ..., description="Handle or gramps_id of the person to evaluate"
    )
    average_generation_gap: Optional[int] = Field(None, ge=1)
    max_age_probably_alive: Optional[int] = Field(None, ge=1)
    max_sibling_age_difference: Optional[int] = Field(None, ge=0)
    include_dates: bool = Field(
        True, description="Also fetch estimated birth/death dates"
    )


# Setup logging
```

Replace with (adding `TimelineQueryParams`):

```python
class LivingStatusParams(BaseModel):
    person: str = Field(
        ..., description="Handle or gramps_id of the person to evaluate"
    )
    average_generation_gap: Optional[int] = Field(None, ge=1)
    max_age_probably_alive: Optional[int] = Field(None, ge=1)
    max_sibling_age_difference: Optional[int] = Field(None, ge=0)
    include_dates: bool = Field(
        True, description="Also fetch estimated birth/death dates"
    )


class TimelineQueryParams(BaseModel):
    scope: str = Field(
        ...,
        description=(
            "One of: 'person', 'family', 'people', 'families' - whose "
            "timeline to build"
        ),
    )
    target: Optional[str] = Field(
        None,
        description=(
            "Handle or gramps_id of the person/family (required when scope "
            "is 'person' or 'family'; optional anchor for scope 'people')"
        ),
    )
    dates: Optional[str] = Field(
        None, description="Date range filter, e.g. '1900/1/1-1950/1/1'"
    )
    handles: Optional[str] = Field(
        None, description="Comma-delimited handles (scope 'people'/'families' only)"
    )
    events: Optional[str] = Field(
        None, description="Comma-delimited event types to include"
    )
    event_classes: Optional[str] = Field(
        None, description="Comma-delimited event classes to include"
    )
    ratings: Optional[bool] = Field(
        None,
        description="Include citation count and confidence score (not used for scope 'person')",
    )
    precision: Optional[int] = Field(
        None, ge=1, le=3, description="Date precision, 1-3 (scope 'people' only)"
    )
    discard_empty: Optional[bool] = Field(
        None, description="Discard undated events (not used for scope 'person')"
    )
    first: Optional[bool] = Field(
        None,
        description="Include events before the anchor's first event (scope 'person'/'people' only)",
    )
    last: Optional[bool] = Field(
        None,
        description="Include events after the anchor's last event (scope 'person'/'people' only)",
    )
    page: Optional[int] = Field(
        None, ge=0, description="Page number (not used for scope 'person')"
    )
    pagesize: Optional[int] = Field(
        None, gt=0, description="Items per page (not used for scope 'person')"
    )


# Setup logging
```

(`scope` is typed as plain `str` here, not `Literal`, to keep this class
consistent with the rest of `server.py`'s existing wrapper classes, none of
which use `Literal`; the tool function itself validates the value and
raises a clear `ValueError` for anything else.)

Find the `"check_living"` entry (currently last, immediately before the
closing `}`):

```python
    "check_living": {
        "description": (
            "Check whether a person is living and get estimated birth/death "
            "dates (accepts handle or gramps_id)"
        ),
        "schema": LivingStatusParams,
        "handler": check_living_tool,
    },
}
```

Replace with:

```python
    "check_living": {
        "description": (
            "Check whether a person is living and get estimated birth/death "
            "dates (accepts handle or gramps_id)"
        ),
        "schema": LivingStatusParams,
        "handler": check_living_tool,
    },
    "get_timeline": {
        "description": (
            "Build a chronological timeline for a person, family, or group "
            "(scope: person/family/people/families)"
        ),
        "schema": TimelineQueryParams,
        "handler": get_timeline_tool,
    },
}
```

- [ ] **Step 5: Verify the server module still loads**

```bash
uv run python -c "from src.gramps_mcp.server import TOOL_REGISTRY; print(len(TOOL_REGISTRY))"
```

Expected: `19`.

- [ ] **Step 6: Add the integration test**

Append to `tests/test_relationship_tools.py`:

```python
from src.gramps_mcp.tools.relationship_tools import get_timeline_tool


class TestGetTimelineTool:
    """Test the get_timeline_tool against a live Gramps Web server."""

    @pytest.mark.asyncio
    async def test_person_scope(self):
        result = await get_timeline_tool({"scope": "person", "target": "I0001"})
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_family_scope(self):
        result = await get_timeline_tool({"scope": "family", "target": "F0001"})
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_people_scope_without_anchor(self):
        result = await get_timeline_tool({"scope": "people", "pagesize": 5})
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_families_scope(self):
        result = await get_timeline_tool({"scope": "families", "pagesize": 5})
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_invalid_scope_returns_error(self):
        result = await get_timeline_tool({"scope": "nonsense"})
        text = result[0].text
        assert "error" in text.lower()

    @pytest.mark.asyncio
    async def test_person_scope_without_target_returns_error(self):
        result = await get_timeline_tool({"scope": "person"})
        text = result[0].text
        assert "error" in text.lower()
```

- [ ] **Step 7: Run the test**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_relationship_tools.py -v
```

Expected: all 12 tests (6 from Tasks 2-3 + 6 new) pass, or connection
errors if no live server is reachable.

- [ ] **Step 8: Run the offline regression suite and lint**

```bash
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py -q
uv run ruff check src/
uv run ruff format --check src/ tests/
uv run mypy src/gramps_mcp --ignore-missing-imports
```

Expected: `18 passed`; ruff/format/mypy clean.

- [ ] **Step 9: Commit**

```bash
git add src/gramps_mcp/utils.py src/gramps_mcp/tools/relationship_tools.py src/gramps_mcp/handlers/timeline_handler.py src/gramps_mcp/server.py tests/test_relationship_tools.py
uv run git commit -m "feat: add get_timeline tool for person/family/group timelines"
```

---

### Task 5: `manage_tags` tool

**Files:**

- Modify: `src/gramps_mcp/models/parameters/tag_params.py` (add `ManageTagsParams`)
- Create: `src/gramps_mcp/tools/records_tools.py`
- Create: `src/gramps_mcp/handlers/tag_handler.py`
- Modify: `src/gramps_mcp/server.py` (imports + `TOOL_REGISTRY`)
- Test: `tests/test_records_tools.py`

**Interfaces:**

- Consumes: `TagSearchParams`, `TagSaveParams` (both already exist in
  `tag_params.py`, already mapped to `ApiCalls.GET_TAGS`/`POST_TAGS`/`PUT_TAG`;
  `ApiCalls.GET_TAG` needs no params model, already mapped to `None`).
- Produces: `manage_tags_tool` — consumed only by `server.py`'s
  `TOOL_REGISTRY`. `ManageTagsParams` — consumed only by `server.py` (as the
  tool's schema).

- [ ] **Step 1: Add `ManageTagsParams` to `tag_params.py`**

`src/gramps_mcp/models/parameters/tag_params.py` currently starts:

```python
"""
Pydantic models for tag-related operations.

API calls supported in this category:
- GET_TAGS: Get information about multiple tags
- POST_TAGS: Add a new tag to the database
- GET_TAG: Get information about a specific tag
- PUT_TAG: Update the tag
- DELETE_TAG: Delete the tag
"""

from typing import List, Optional

from pydantic import BaseModel, Field
```

Change the import line:

```python
from typing import List, Literal, Optional
```

Append at the end of the file (after `TagSaveParams`):

```python
class ManageTagsParams(BaseModel):
    """Parameters for the consolidated manage_tags tool (list/get/create-or-update)."""

    action: Literal["list", "get", "create"] = Field(
        ..., description="Which operation to perform"
    )
    handle: Optional[str] = Field(
        None,
        description=(
            "Tag handle (required for 'get'; provide for update, omit for "
            "a new tag on 'create')"
        ),
    )
    name: Optional[str] = Field(None, description="Tag name (required for 'create')")
    color: Optional[str] = Field(None, description="Tag color")
    priority: Optional[int] = Field(None, description="Tag priority")
    page: Optional[int] = Field(None, ge=0, description="Page number (for 'list')")
    pagesize: Optional[int] = Field(
        None, ge=1, le=100, description="Results per page (for 'list')"
    )
    sort: Optional[List[str]] = Field(None, description="Sort order (for 'list')")
```

- [ ] **Step 2: Create the tag handler**

Create `src/gramps_mcp/handlers/tag_handler.py` with the AGPL header, then:

```python
"""
Tag data handler for Gramps MCP operations.

Formats single-tag and tag-list results.
"""

from typing import Dict, List


def format_tag(data: Dict) -> str:
    """
    Format a single tag record.

    Args:
        data: Tag dict with handle, name, color, priority

    Returns:
        Formatted tag string
    """
    if not data:
        return "Tag not found."

    name = data.get("name", "Unnamed tag")
    handle = data.get("handle", "")
    color = data.get("color")
    priority = data.get("priority")

    result = f"**{name}** - [{handle}]\n"
    if color:
        result += f"Color: {color}\n"
    if priority is not None:
        result += f"Priority: {priority}\n"

    return result


def format_tags(data: List[Dict]) -> str:
    """
    Format a list of tag records.

    Args:
        data: List of tag dicts

    Returns:
        Formatted tags string
    """
    if not data:
        return "No tags found."

    result = f"Found {len(data)} tag(s):\n\n"
    for tag in data:
        name = tag.get("name", "Unnamed tag")
        handle = tag.get("handle", "")
        result += f"• {name} - [{handle}]\n"

    return result
```

- [ ] **Step 3: Create `tools/records_tools.py` with `manage_tags_tool`**

Create `src/gramps_mcp/tools/records_tools.py` with the AGPL header, then:

```python
"""
Record management MCP tools for genealogy operations.

This module contains tools for managing tags and retrieving tree facts.
"""

import logging
from typing import Dict, List

from mcp.types import TextContent

from ..client import GrampsAPIError
from ..config import get_settings
from ..handlers.tag_handler import format_tag, format_tags
from ..models.api_calls import ApiCalls
from ..models.parameters.tag_params import TagSaveParams, TagSearchParams
from .search_basic import with_client

logger = logging.getLogger(__name__)


def _format_error_response(error: Exception, operation: str) -> List[TextContent]:
    """Format error into user-friendly MCP response."""
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"

    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


@with_client
async def manage_tags_tool(client, arguments: Dict) -> List[TextContent]:
    """
    List, get, or create/update tags.
    """
    try:
        action = arguments.get("action")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        if action == "list":
            params = TagSearchParams(
                page=arguments.get("page"),
                pagesize=arguments.get("pagesize"),
                sort=arguments.get("sort"),
            )
            result = await client.make_api_call(
                api_call=ApiCalls.GET_TAGS, params=params, tree_id=tree_id
            )
            formatted = format_tags(result)

        elif action == "get":
            handle = arguments.get("handle")
            if not handle:
                raise ValueError("handle is required for action 'get'")
            result = await client.make_api_call(
                api_call=ApiCalls.GET_TAG, params=None, tree_id=tree_id, handle=handle
            )
            formatted = format_tag(result)

        elif action == "create":
            handle = arguments.get("handle")
            name = arguments.get("name")
            if not handle and not name:
                raise ValueError("name is required to create a new tag")

            params = TagSaveParams(
                handle=handle,
                name=name,
                color=arguments.get("color"),
                priority=arguments.get("priority"),
            )

            if handle:
                await client.make_api_call(
                    api_call=ApiCalls.PUT_TAG,
                    params=params,
                    tree_id=tree_id,
                    handle=handle,
                )
                formatted = f"Tag '{name}' updated."
            else:
                await client.make_api_call(
                    api_call=ApiCalls.POST_TAGS, params=params, tree_id=tree_id
                )
                formatted = f"Tag '{name}' created."

        else:
            raise ValueError(f"Invalid action: {action}")

        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, "tag management")
```

(`TagSaveParams.name` is a required field with no default, so passing
`name=None` when only `handle` is given — an update where the caller wants
to change only `color`/`priority` — would fail validation. This is a known
limitation of the underlying model, not something to work around here: if
`name` is omitted on an update, `TagSaveParams(...)` raises a
`ValidationError`, which the surrounding `try/except` turns into a normal
error response rather than a crash. This matches the project's existing
error-handling convention.)

- [ ] **Step 4: Register `manage_tags` in `server.py`**

Find:

```python
from .tools.relationship_tools import (
    check_living_tool,
    get_relationship_tool,
    get_timeline_tool,
)
```

Replace with:

```python
from .tools.records_tools import manage_tags_tool
from .tools.relationship_tools import (
    check_living_tool,
    get_relationship_tool,
    get_timeline_tool,
)
```

Also add the import for `ManageTagsParams` — find:

```python
from .models.parameters.simple_params import (
    SimpleFindParams,
    SimpleGetParams,
    SimpleSearchParams,
)
from .models.parameters.source_params import SourceSaveParams
from .models.parameters.transactions_params import TransactionHistoryParams
```

Replace with:

```python
from .models.parameters.simple_params import (
    SimpleFindParams,
    SimpleGetParams,
    SimpleSearchParams,
)
from .models.parameters.source_params import SourceSaveParams
from .models.parameters.tag_params import ManageTagsParams
from .models.parameters.transactions_params import TransactionHistoryParams
```

Find the `"get_timeline"` entry (currently last, immediately before the
closing `}`):

```python
    "get_timeline": {
        "description": (
            "Build a chronological timeline for a person, family, or group "
            "(scope: person/family/people/families)"
        ),
        "schema": TimelineQueryParams,
        "handler": get_timeline_tool,
    },
}
```

Replace with:

```python
    "get_timeline": {
        "description": (
            "Build a chronological timeline for a person, family, or group "
            "(scope: person/family/people/families)"
        ),
        "schema": TimelineQueryParams,
        "handler": get_timeline_tool,
    },
    "manage_tags": {
        "description": (
            "List, get, or create/update tags (action: list/get/create - "
            "no delete)"
        ),
        "schema": ManageTagsParams,
        "handler": manage_tags_tool,
    },
}
```

- [ ] **Step 5: Verify the server module still loads**

```bash
uv run python -c "from src.gramps_mcp.server import TOOL_REGISTRY; print(len(TOOL_REGISTRY))"
```

Expected: `20`.

- [ ] **Step 6: Write the integration test**

Create `tests/test_records_tools.py` (no AGPL header):

```python
"""
Integration tests for record management tools using the real Gramps API.
"""

import uuid

import pytest

from src.gramps_mcp.tools.records_tools import manage_tags_tool


class TestManageTagsTool:
    """Test the manage_tags_tool against a live Gramps Web server."""

    @pytest.mark.asyncio
    async def test_list_tags(self):
        result = await manage_tags_tool({"action": "list", "pagesize": 5})
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_create_and_get_tag(self):
        unique_name = f"test-tag-{uuid.uuid4().hex[:8]}"

        create_result = await manage_tags_tool(
            {"action": "create", "name": unique_name, "color": "#ff0000"}
        )
        create_text = create_result[0].text
        assert "error" not in create_text.lower()
        assert unique_name in create_text

        list_result = await manage_tags_tool({"action": "list", "pagesize": 100})
        list_text = list_result[0].text
        assert unique_name in list_text

    @pytest.mark.asyncio
    async def test_get_without_handle_returns_error(self):
        result = await manage_tags_tool({"action": "get"})
        text = result[0].text
        assert "error" in text.lower()

    @pytest.mark.asyncio
    async def test_create_without_name_returns_error(self):
        result = await manage_tags_tool({"action": "create"})
        text = result[0].text
        assert "error" in text.lower()

    @pytest.mark.asyncio
    async def test_invalid_action_returns_error(self):
        result = await manage_tags_tool({"action": "delete"})
        text = result[0].text
        assert "error" in text.lower()
```

(`test_create_and_get_tag` creates a real, uniquely-named tag in the live
tree each run — this is a genealogically-neutral, generic label, not a
reference to any real person, and is safe to leave in the tree; the test
does not attempt to clean it up afterward, matching this project's "no
delete tools" convention.)

- [ ] **Step 7: Run the test**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_records_tools.py -v
```

Expected: all 5 tests pass, or connection errors if no live server is
reachable.

- [ ] **Step 8: Run the offline regression suite and lint**

```bash
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py -q
uv run ruff check src/
uv run ruff format --check src/ tests/
uv run mypy src/gramps_mcp --ignore-missing-imports
```

Expected: `18 passed`; ruff/format/mypy clean.

- [ ] **Step 9: Commit**

```bash
git add src/gramps_mcp/models/parameters/tag_params.py src/gramps_mcp/tools/records_tools.py src/gramps_mcp/handlers/tag_handler.py src/gramps_mcp/server.py tests/test_records_tools.py
uv run git commit -m "feat: add manage_tags tool for tag list/get/create-or-update"
```

---

### Task 6: `get_facts` tool

**Files:**

- Modify: `src/gramps_mcp/tools/records_tools.py` (add `get_facts_tool`)
- Create: `src/gramps_mcp/handlers/facts_handler.py`
- Modify: `src/gramps_mcp/server.py` (imports + `TOOL_REGISTRY`)
- Modify: `tests/test_records_tools.py` (add a test class)

**Interfaces:**

- Consumes: the Task 1 enum-serialization fix (this tool is the reason that
  fix exists); `FactsParams` (`src/gramps_mcp/models/parameters/facts_params.py`,
  fields `gramps_id`, `handle`, `living: LivingProxy`, `person`, `private`,
  `rank` — already exists, already mapped to `ApiCalls.GET_FACTS`);
  `get_gramps_id_from_handle` (`src/gramps_mcp/utils.py`).
- Produces: `get_facts_tool` — consumed only by `server.py`'s
  `TOOL_REGISTRY`.

- [ ] **Step 1: Create the facts handler**

Create `src/gramps_mcp/handlers/facts_handler.py` with the AGPL header,
then:

```python
"""
Facts data handler for Gramps MCP operations.

Formats "interesting facts" statistics about the tree.
"""

from typing import Dict, List

from ..utils import get_gramps_id_from_handle


async def format_facts(data: List[Dict], client, tree_id: str) -> str:
    """
    Format a list of RecordFact entries.

    Args:
        data: List of fact dicts with description, key, objects
        client: Gramps API client instance
        tree_id: Family tree identifier

    Returns:
        Formatted facts string
    """
    if not data:
        return "No facts found."

    result = f"Found {len(data)} fact(s):\n\n"

    for fact in data:
        description = fact.get("description", "Unknown fact")
        result += f"• **{description}**\n"

        objects = fact.get("objects", [])
        for obj in objects:
            handle = obj.get("handle") if isinstance(obj, dict) else None
            obj_class = obj.get("class") if isinstance(obj, dict) else None
            if handle and obj_class:
                gramps_id = await get_gramps_id_from_handle(
                    client, obj_class, handle, tree_id
                )
                result += f"  - {obj_class}: {gramps_id}\n"

        result += "\n"

    return result
```

(`RecordFactObject`'s exact field names for `class`/`handle` were not fully
confirmed against the live schema during planning — this handler is
defensive: `isinstance(obj, dict)` and `.get(...)` calls mean an unexpected
shape degrades to omitting that object's line rather than raising. If the
live API's actual field names differ, the implementer should inspect one
real response during Step 3 below and adjust the `.get(...)` keys to
match — note any such adjustment in the task report.)

- [ ] **Step 2: Add `get_facts_tool` to `tools/records_tools.py`**

At the top of `src/gramps_mcp/tools/records_tools.py`, find:

```python
from ..handlers.tag_handler import format_tag, format_tags
from ..models.api_calls import ApiCalls
from ..models.parameters.tag_params import TagSaveParams, TagSearchParams
from .search_basic import with_client
```

Replace with:

```python
from ..handlers.facts_handler import format_facts
from ..handlers.tag_handler import format_tag, format_tags
from ..models.api_calls import ApiCalls
from ..models.parameters.facts_params import FactsParams
from ..models.parameters.tag_params import TagSaveParams, TagSearchParams
from .search_basic import with_client
```

At the end of the file, after `manage_tags_tool`, append:

```python
@with_client
async def get_facts_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Get interesting facts and statistics about the tree.
    """
    try:
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        params = FactsParams(**arguments)

        result = await client.make_api_call(
            api_call=ApiCalls.GET_FACTS, params=params, tree_id=tree_id
        )

        formatted = await format_facts(result, client, tree_id)
        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, "facts retrieval")
```

- [ ] **Step 3: Run a one-off check of a real response shape (not committed)**

Before trusting the handler's `.get("class")`/`.get("handle")` assumptions,
inspect one real response:

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.parameters.facts_params import FactsParams

async def main():
    settings = get_settings()
    client = GrampsWebAPIClient()
    try:
        result = await client.make_api_call(api_call=ApiCalls.GET_FACTS, params=FactsParams(rank=1), tree_id=settings.gramps_tree_id)
        for fact in result[:2]:
            print(fact.get('description'), '->', fact.get('objects'))
    finally:
        await client.close()

asyncio.run(main())
"
```

If the printed `objects` entries use different keys than `class`/`handle`
(e.g. `object_class`/`object_handle`), update
`handlers/facts_handler.py`'s `.get(...)` calls in Step 1 to match before
proceeding, and note the correction in your task report.

- [ ] **Step 4: Register `get_facts` in `server.py`**

Find:

```python
from .tools.records_tools import manage_tags_tool
```

Replace with:

```python
from .tools.records_tools import get_facts_tool, manage_tags_tool
```

Also add the import for `FactsParams` — find:

```python
from .models.parameters.event_params import EventSaveParams
from .models.parameters.family_params import FamilySaveParams
```

Replace with:

```python
from .models.parameters.event_params import EventSaveParams
from .models.parameters.facts_params import FactsParams
from .models.parameters.family_params import FamilySaveParams
```

Find the `"manage_tags"` entry (currently last, immediately before the
closing `}`):

```python
    "manage_tags": {
        "description": (
            "List, get, or create/update tags (action: list/get/create - "
            "no delete)"
        ),
        "schema": ManageTagsParams,
        "handler": manage_tags_tool,
    },
}
```

Replace with:

```python
    "manage_tags": {
        "description": (
            "List, get, or create/update tags (action: list/get/create - "
            "no delete)"
        ),
        "schema": ManageTagsParams,
        "handler": manage_tags_tool,
    },
    "get_facts": {
        "description": "Get interesting facts and statistics about the tree",
        "schema": FactsParams,
        "handler": get_facts_tool,
    },
}
```

- [ ] **Step 5: Verify the server module still loads**

```bash
uv run python -c "from src.gramps_mcp.server import TOOL_REGISTRY; print(len(TOOL_REGISTRY))"
```

Expected: `21`.

- [ ] **Step 6: Write the integration test**

Append to `tests/test_records_tools.py`:

```python
from src.gramps_mcp.tools.records_tools import get_facts_tool


class TestGetFactsTool:
    """Test the get_facts_tool against a live Gramps Web server."""

    @pytest.mark.asyncio
    async def test_get_facts_default(self):
        result = await get_facts_tool({})
        text = result[0].text
        assert "error" not in text.lower()

    @pytest.mark.asyncio
    async def test_get_facts_with_rank(self):
        result = await get_facts_tool({"rank": 2})
        text = result[0].text
        assert "error" not in text.lower()
```

- [ ] **Step 7: Run the test**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_records_tools.py -v
```

Expected: all 7 tests (5 from Task 5 + 2 new) pass, or connection errors if
no live server is reachable.

- [ ] **Step 8: Run the offline regression suite and lint**

```bash
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py -q
uv run ruff check src/
uv run ruff format --check src/ tests/
uv run mypy src/gramps_mcp --ignore-missing-imports
```

Expected: `18 passed`; ruff/format/mypy clean.

- [ ] **Step 9: Commit**

```bash
git add src/gramps_mcp/tools/records_tools.py src/gramps_mcp/handlers/facts_handler.py src/gramps_mcp/server.py tests/test_records_tools.py
uv run git commit -m "feat: add get_facts tool for tree statistics"
```

---

### Task 7: README updates and final verification

**Files:**

- Modify: `README.md` (Features section + Architecture tree)

**Interfaces:**

- Consumes: the final `TOOL_REGISTRY` state (21 tools) from Tasks 1-6.
- Produces: nothing — final task in the plan.

- [ ] **Step 1: Add a Features subsection**

Find this exact block in `README.md`:

```
#### Analysis Tools (4 tools)
- **tree_stats** - Get tree statistics and information
- **get_descendants** - Find all descendants of a person
- **get_ancestors** - Find all ancestors of a person
- **recent_changes** - Track recent modifications to your data
```

Replace with:

```
#### Analysis Tools (4 tools)
- **tree_stats** - Get tree statistics and information
- **get_descendants** - Find all descendants of a person
- **get_ancestors** - Find all ancestors of a person
- **recent_changes** - Track recent modifications to your data

#### Extended Analysis Tools (5 tools)
- **get_relationship** - Calculate how two people are related
- **check_living** - Check living status and estimated birth/death dates
- **get_timeline** - Build a chronological timeline for a person, family, or group
- **manage_tags** - List, get, or create/update tags
- **get_facts** - Get interesting facts and statistics about the tree
```

- [ ] **Step 2: Update the Architecture tree**

Find this exact block in `README.md`:

```
|-- tools/              # MCP tool implementations
|   |-- search_basic.py
|   |-- search_details.py
|   |-- data_management.py
|   `-- analysis.py
|-- handlers/           # Data formatting handlers
`-- resources/          # MCP resources (GQL docs, usage guide)
```

Replace with:

```
|-- tools/              # MCP tool implementations
|   |-- search_basic.py
|   |-- search_details.py
|   |-- data_management.py
|   |-- analysis.py
|   |-- relationship_tools.py
|   `-- records_tools.py
|-- handlers/           # Data formatting handlers
`-- resources/          # MCP resources (GQL docs, usage guide)
```

- [ ] **Step 3: Full final verification**

```bash
uv run ruff check src/
uv run ruff format --check src/ tests/
uv run mypy src/gramps_mcp --ignore-missing-imports
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py -q
uv run python -c "from src.gramps_mcp.server import TOOL_REGISTRY; print(len(TOOL_REGISTRY))"
uv run python -c "import src.gramps_mcp.server; print('server loads')"
```

Expected: ruff/format/mypy clean; `18 passed`; `21`; `server loads`.

If a live server is reachable, also run the full new-tool suite one more
time end to end:

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_relationship_tools.py tests/test_records_tools.py tests/test_client.py -v
```

- [ ] **Step 4: Commit**

```bash
git add README.md
uv run git commit -m "docs: document the 5 new extended analysis tools"
```

---

## Final verification (whole plan)

```bash
uv run ruff check src/
uv run ruff format --check src/ tests/
uv run mypy src/gramps_mcp --ignore-missing-imports
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py -q
uv run python -c "from src.gramps_mcp.server import TOOL_REGISTRY; print(len(TOOL_REGISTRY))"
git status --short
```

All clean/passing; `21`. `git status --short` should show only the user's
pre-existing, untouched `docker-compose.yml`/`docker/` WIP.
