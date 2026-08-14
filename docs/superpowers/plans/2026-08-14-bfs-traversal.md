# BFS Traversal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the HTML-report round trip behind `get_ancestors` and `get_descendants` with a direct breadth-first walk of the family graph.

**Architecture:** A new pure module `traversal.py` walks the graph one generation at a time, fetching each generation's people concurrently (one request per person, `profile=self` plus `extend=parent_family_list`/`family_list` returns both the person profile and the full family objects). It returns a `TraversalResult` dataclass. A new `handlers/traversal_handler.py` renders that dataclass to markdown with no I/O. The two tools in `tools/analysis.py` shrink to argument validation plus a call to each.

**Tech Stack:** Python 3.13, asyncio, pydantic v2, httpx (via the existing `GrampsWebAPIClient`), pytest.

**Spec:** `docs/superpowers/specs/2026-08-14-bfs-traversal-design.md`

## Global Constraints

- Use `uv` for everything: `uv run pytest`, `uv run git commit` (the pre-commit hooks fail with "Executable `python` not found" under a bare `git commit`).
- No file may exceed 500 lines, tests included — the `check-file-length` pre-commit hook covers the whole tree.
- No emojis anywhere in source (`check-no-emojis` hook).
- Google-style docstrings on every function. Type hints throughout.
- TDD: the failing test is written and *run* before the implementation exists.
- Offline tests carry no `integration` marker and must pass with no Gramps server reachable. Server-dependent tests are marked `pytestmark = pytest.mark.integration`.
- Live tests run from the macOS host need `GRAMPS_API_URL=http://localhost:80` as an env override on the command line. Never edit `.env`, never commit the override.
- Visit cap: `500` people. Default `max_generations`: `5`. Upper bound on `max_generations`: `20`.
- Concurrency within one generation: `asyncio.Semaphore(8)`.
- Work happens on branch `feat/bfs-traversal`, cut from `main`.

---

### Task 0: Branch

- [ ] **Step 1: Cut the branch**

```bash
cd /Users/fjacquet/Projects/gramps-mcp
git checkout main
git checkout -b feat/bfs-traversal
```

---

### Task 1: `TraversalResult` and the markdown renderer

The renderer is written first because it is pure, needs no server, and pins
down the shape the walk must produce.

**Files:**
- Create: `src/gramps_mcp/traversal.py` (dataclass only in this task)
- Create: `src/gramps_mcp/handlers/traversal_handler.py`
- Test: `tests/test_traversal_handler.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `TraversalResult` dataclass in `src/gramps_mcp/traversal.py` with fields
    `root: str`, `nodes: dict[str, dict]`, `edges: dict[str, list[str]]`,
    `truncated_by_cap: bool`, `unexplored: int`, `revisited: set[str]`,
    `failed: dict[str, str]`
  - `format_traversal(result: TraversalResult, direction: str) -> str` in
    `src/gramps_mcp/handlers/traversal_handler.py`, where `direction` is
    `"ancestors"` or `"descendants"`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_traversal_handler.py`:

```python
"""
Unit tests for the traversal markdown renderer. Pure formatting, no server.
"""

from src.gramps_mcp.handlers.traversal_handler import format_traversal
from src.gramps_mcp.traversal import TraversalResult


def _profile(handle: str, gramps_id: str, name: str, **extra) -> dict:
    """
    Build a person profile shaped like the Gramps Web profile=self payload.

    Args:
        handle (str): Person handle.
        gramps_id (str): Gramps ID.
        name (str): Display name.
        **extra: Additional profile keys, for example birth= or death=.

    Returns:
        dict: A person profile.
    """
    return {"handle": handle, "gramps_id": gramps_id, "name_display": name, **extra}


def _result(**overrides) -> TraversalResult:
    """
    Build a two-generation TraversalResult with defaults callers can override.

    Args:
        **overrides: Fields to replace on the result.

    Returns:
        TraversalResult: The assembled result.
    """
    base = {
        "root": "h1",
        "nodes": {
            "h1": _profile(
                "h1",
                "I0001",
                "JACQUET, Frederic",
                birth={"date": "10 Aug 1976", "place_name": "Bourges"},
            ),
            "h2": _profile(
                "h2",
                "I0042",
                "JACQUET, Yvan",
                birth={"date": "1948", "place_name": "Lyon"},
                death={"date": "2011"},
            ),
            "h3": _profile("h3", "I0129", "MARIAUD, Odile"),
        },
        "edges": {"h1": ["h2", "h3"]},
        "truncated_by_cap": False,
        "unexplored": 0,
        "revisited": set(),
        "failed": {},
    }
    base.update(overrides)
    return TraversalResult(**base)


class TestFormatTraversal:
    def test_header_names_direction_generations_and_count(self):
        text = format_traversal(_result(), "ancestors")
        assert text.splitlines()[0] == (
            "# Ancestors of JACQUET, Frederic (I0001) - 2 generations, 3 people"
        )

    def test_descendants_direction_changes_only_the_header_word(self):
        text = format_traversal(_result(), "descendants")
        assert text.splitlines()[0].startswith("# Descendants of JACQUET, Frederic")

    def test_root_line_carries_id_birth_date_and_place(self):
        text = format_traversal(_result(), "ancestors")
        assert "- JACQUET, Frederic (I0001), b. 10 Aug 1976 Bourges" in text

    def test_child_lines_are_indented_two_spaces_per_generation(self):
        text = format_traversal(_result(), "ancestors")
        assert "  - JACQUET, Yvan (I0042), b. 1948 Lyon, d. 2011" in text

    def test_absent_dates_are_omitted_entirely(self):
        text = format_traversal(_result(), "ancestors")
        assert "  - MARIAUD, Odile (I0129)" in text

    def test_revisited_node_is_marked_and_not_expanded_twice(self):
        result = _result(
            edges={"h1": ["h2", "h3"], "h2": ["h3"]},
            revisited={"h3"},
        )
        text = format_traversal(result, "ancestors")
        assert text.count("MARIAUD, Odile (I0129)") == 2
        assert "[already listed above]" in text
        # Reason: the marker must sit on the deeper repeat, not the first
        # occurrence, or the reader loses the branch that was expanded.
        first, second = [
            line for line in text.splitlines() if "MARIAUD" in line
        ]
        assert "[already listed above]" not in first
        assert "[already listed above]" in second

    def test_failed_node_renders_with_its_handle_and_reason(self):
        result = _result(
            edges={"h1": ["h2", "h9"]},
            failed={"h9": "HTTP 500"},
        )
        text = format_traversal(result, "ancestors")
        assert "  - (handle h9) [unavailable: HTTP 500]" in text

    def test_cap_truncation_is_announced_in_a_footer(self):
        result = _result(truncated_by_cap=True, unexplored=42)
        text = format_traversal(result, "ancestors")
        assert text.rstrip().endswith(
            "**Truncated**: visit cap of 500 reached, 42 branches unexplored. "
            "Lower max_generations or start from a nearer ancestor."
        )

    def test_no_footer_when_the_walk_completed(self):
        text = format_traversal(_result(), "ancestors")
        assert "Truncated" not in text

    def test_lone_person_with_no_relatives_reads_as_one_generation(self):
        result = _result(nodes={"h1": _profile("h1", "I0001", "JACQUET, Frederic")}, edges={})
        text = format_traversal(result, "ancestors")
        assert "1 generations, 1 people" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_traversal_handler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.gramps_mcp.traversal'`

- [ ] **Step 3: Create the dataclass**

Create `src/gramps_mcp/traversal.py` (the AGPL copyright header is added
automatically by the pre-commit hook, so write the module body only):

```python
"""
Breadth-first traversal of the Gramps family graph.

Pure graph logic: this module fetches people and follows family links. It
formats nothing - rendering lives in handlers/traversal_handler.py.
"""

from dataclasses import dataclass, field

VISIT_CAP = 500


@dataclass
class TraversalResult:
    """Outcome of one breadth-first walk of the family graph."""

    root: str
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: dict[str, list[str]] = field(default_factory=dict)
    truncated_by_cap: bool = False
    unexplored: int = 0
    revisited: set[str] = field(default_factory=set)
    failed: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: Write the renderer**

Create `src/gramps_mcp/handlers/traversal_handler.py`:

```python
"""
Markdown rendering for breadth-first traversal results.

No I/O: everything here operates on an in-memory TraversalResult.
"""

from ..traversal import VISIT_CAP, TraversalResult

INDENT = "  "


def _format_event(event: dict | None, prefix: str) -> str:
    """
    Render one birth or death as a compact suffix.

    Args:
        event (dict | None): The profile's birth or death object.
        prefix (str): "b." or "d.".

    Returns:
        str: For example "b. 1948 Lyon", or "" when there is no date.
    """
    if not event or not event.get("date"):
        return ""
    place = event.get("place_name") or ""
    # Reason: place_name only, never the full hierarchy the API also
    # returns - token economy is the point of this whole change.
    return f"{prefix} {event['date']} {place}".rstrip()


def _format_person(profile: dict) -> str:
    """
    Render one person as a single line without indentation or bullet.

    Args:
        profile (dict): A profile=self payload for one person.

    Returns:
        str: For example "JACQUET, Yvan (I0042), b. 1948 Lyon, d. 2011".
    """
    line = f"{profile.get('name_display', '?')} ({profile.get('gramps_id', '?')})"
    for part in (
        _format_event(profile.get("birth"), "b."),
        _format_event(profile.get("death"), "d."),
    ):
        if part:
            line += f", {part}"
    return line


def _walk_lines(
    result: TraversalResult, handle: str, depth: int, seen: set[str], lines: list[str]
) -> int:
    """
    Append the markdown lines for one subtree, depth-first for readability.

    Args:
        result (TraversalResult): The walk to render.
        handle (str): Handle of the person to render at this position.
        depth (int): Current generation, zero for the root.
        seen (set[str]): Handles already rendered somewhere above.
        lines (list[str]): Accumulator, mutated in place.

    Returns:
        int: The deepest generation reached under this handle, one-based.
    """
    pad = INDENT * depth
    if handle in result.failed:
        lines.append(f"{pad}- (handle {handle}) [unavailable: {result.failed[handle]}]")
        return depth + 1
    profile = result.nodes.get(handle)
    if profile is None:
        lines.append(f"{pad}- (handle {handle}) [unavailable: not fetched]")
        return depth + 1
    if handle in seen:
        lines.append(f"{pad}- {_format_person(profile)} [already listed above]")
        return depth + 1
    seen.add(handle)
    lines.append(f"{pad}- {_format_person(profile)}")
    deepest = depth + 1
    for child in result.edges.get(handle, []):
        deepest = max(deepest, _walk_lines(result, child, depth + 1, seen, lines))
    return deepest


def format_traversal(result: TraversalResult, direction: str) -> str:
    """
    Render a traversal result as an indented markdown tree.

    Args:
        result (TraversalResult): The walk to render.
        direction (str): "ancestors" or "descendants", used in the heading.

    Returns:
        str: Markdown ready to hand back as tool output.
    """
    lines: list[str] = []
    generations = _walk_lines(result, result.root, 0, set(), lines)
    root_profile = result.nodes.get(result.root, {})
    header = (
        f"# {direction.capitalize()} of "
        f"{root_profile.get('name_display', '?')} "
        f"({root_profile.get('gramps_id', '?')}) - "
        f"{generations} generations, {len(result.nodes)} people"
    )
    text = header + "\n\n" + "\n".join(lines) + "\n"
    if result.truncated_by_cap:
        text += (
            f"\n**Truncated**: visit cap of {VISIT_CAP} reached, "
            f"{result.unexplored} branches unexplored. Lower max_generations "
            "or start from a nearer ancestor.\n"
        )
    return text
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_traversal_handler.py -v`
Expected: PASS, 10 tests.

- [ ] **Step 6: Run the whole offline suite**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS, no regression against the 233 tests that passed before.

- [ ] **Step 7: Commit**

```bash
uv run git add src/gramps_mcp/traversal.py src/gramps_mcp/handlers/traversal_handler.py tests/test_traversal_handler.py
uv run git commit -m "feat: render traversal results as an indented markdown tree

Adds the TraversalResult dataclass and its markdown renderer, the pure
half of replacing the HTML report path in get_ancestors/get_descendants
(upstream issue #6). One line per person carrying the gramps_id so the
assistant can chain a get_type call, dates only when present, and place
reduced to place_name.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: The breadth-first walk

**Files:**
- Modify: `src/gramps_mcp/traversal.py`
- Test: `tests/test_traversal.py`

**Interfaces:**
- Consumes: `TraversalResult`, `VISIT_CAP` from Task 1.
- Produces, all in `src/gramps_mcp/traversal.py`:
  - `async def resolve_person_handle(client, tree_id: str, gramps_id: str) -> str | None`
  - `async def walk_ancestors(client, tree_id: str, start_handle: str, max_generations: int, visit_cap: int = VISIT_CAP) -> TraversalResult`
  - `async def walk_descendants(client, tree_id: str, start_handle: str, max_generations: int, visit_cap: int = VISIT_CAP) -> TraversalResult`

Facts already verified against the live server, do not re-derive them:

- `GET /people/{handle}` with `params={"profile": "self", "extend": "parent_family_list"}` returns `profile` (with `name_display`, `gramps_id`, `birth`, `death`) and `extended.parent_families`, a list of full family objects carrying `father_handle` and `mother_handle`.
- The same call with `extend=family_list` returns `extended.families`, whose `child_ref_list` entries carry `ref`.
- `GET /people/` with `params={"gql": 'gramps_id = I0001', "profile": "self", "pagesize": 1}` returns a list; empty means no such person.
- GQL has no `in` or `or` operator, so a generation cannot be fetched in one query.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_traversal.py`:

```python
"""
Unit tests for the breadth-first family-graph walk.

These patch the transport seam (GrampsWebAPIClient._make_request) over a
synthetic tree and need no server. Assertions read the returned
TraversalResult, never the patch's call arguments.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.traversal import (
    TraversalResult,
    resolve_person_handle,
    walk_ancestors,
    walk_descendants,
)

# A synthetic four-generation tree.
#   h1 - child of family f1 (father h2, mother h3)
#   h2 - child of family f2 (father h4, mother h5)
#   h3 - no parents
PEOPLE = {
    "h1": {"gramps_id": "I0001", "name": "JACQUET, Frederic", "parents": ("h2", "h3")},
    "h2": {"gramps_id": "I0042", "name": "JACQUET, Yvan", "parents": ("h4", "h5")},
    "h3": {"gramps_id": "I0129", "name": "MARIAUD, Odile", "parents": None},
    "h4": {"gramps_id": "I0107", "name": "JACQUET, Joseph", "parents": None},
    "h5": {"gramps_id": "I0108", "name": "RIPPERT, Marie", "parents": None},
}


def _person_payload(handle: str, people: dict) -> dict:
    """
    Build the response GET /people/{handle} gives for an ancestor walk.

    Args:
        handle (str): Person handle being fetched.
        people (dict): The synthetic tree to read from.

    Returns:
        dict: A person payload with profile and extended.parent_families.
    """
    person = people[handle]
    parents = person["parents"]
    families = []
    if parents:
        families.append({"father_handle": parents[0], "mother_handle": parents[1]})
    return {
        "handle": handle,
        "gramps_id": person["gramps_id"],
        "profile": {
            "handle": handle,
            "gramps_id": person["gramps_id"],
            "name_display": person["name"],
        },
        "extended": {"parent_families": families},
    }


def _ancestor_transport(people: dict = PEOPLE, failures: dict | None = None):
    """
    Build a _make_request replacement serving the synthetic tree.

    Args:
        people (dict): The synthetic tree.
        failures (dict | None): handle -> exception to raise for that person.

    Returns:
        Callable: An async callable matching _make_request's signature.
    """
    failures = failures or {}

    # Reason: patch.object installs this on the class, so it is looked up
    # through the instance and receives self as its first argument. Omitting
    # self here makes the client's url= land in method= and every test
    # misbehaves in a way that looks like a traversal bug.
    async def _request(self, method=None, url=None, **kwargs):
        handle = url.rstrip("/").rsplit("/", 1)[-1]
        if handle in failures:
            raise failures[handle]
        return _person_payload(handle, people)

    return _request


class TestResolvePersonHandle:
    async def test_returns_the_handle_for_a_known_gramps_id(self):
        async def _request(self, method=None, url=None, **kwargs):
            return [{"handle": "h1", "gramps_id": "I0001"}]

        with patch.object(GrampsWebAPIClient, "_make_request", new=_request):
            handle = await resolve_person_handle(
                GrampsWebAPIClient(), "default", "I0001"
            )
        assert handle == "h1"

    async def test_returns_none_when_no_person_matches(self):
        async def _request(self, method=None, url=None, **kwargs):
            return []

        with patch.object(GrampsWebAPIClient, "_make_request", new=_request):
            handle = await resolve_person_handle(
                GrampsWebAPIClient(), "default", "I9999"
            )
        assert handle is None


class TestWalkAncestors:
    async def test_reaches_every_ancestor_within_the_generation_limit(self):
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport()
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 3)
        assert set(result.nodes) == {"h1", "h2", "h3", "h4", "h5"}
        assert result.edges["h1"] == ["h2", "h3"]
        assert result.edges["h2"] == ["h4", "h5"]
        assert result.truncated_by_cap is False

    async def test_generation_limit_stops_the_walk(self):
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport()
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 2)
        assert set(result.nodes) == {"h1", "h2", "h3"}
        assert "h4" not in result.edges.get("h2", [])

    async def test_a_person_reached_twice_is_recorded_once_and_marked(self):
        # h1's father and mother share the same parents - a cousin marriage,
        # which this tree really contains.
        people = {
            "h1": {"gramps_id": "I0001", "name": "A", "parents": ("h2", "h3")},
            "h2": {"gramps_id": "I0002", "name": "B", "parents": ("h4", "h5")},
            "h3": {"gramps_id": "I0003", "name": "C", "parents": ("h4", "h5")},
            "h4": {"gramps_id": "I0004", "name": "D", "parents": None},
            "h5": {"gramps_id": "I0005", "name": "E", "parents": None},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(people)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 5)
        assert set(result.nodes) == {"h1", "h2", "h3", "h4", "h5"}
        assert result.revisited == {"h4", "h5"}

    async def test_a_cycle_does_not_hang_the_walk(self):
        # A person who is their own grandparent cannot happen in real data,
        # but a corrupted tree can express it and must not spin forever.
        people = {
            "h1": {"gramps_id": "I0001", "name": "A", "parents": ("h2", "h2")},
            "h2": {"gramps_id": "I0002", "name": "B", "parents": ("h1", "h1")},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(people)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 10)
        assert set(result.nodes) == {"h1", "h2"}

    async def test_visit_cap_stops_the_walk_and_reports_what_is_left(self):
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport()
        ):
            result = await walk_ancestors(
                GrampsWebAPIClient(), "default", "h1", 5, visit_cap=3
            )
        assert len(result.nodes) <= 3
        assert result.truncated_by_cap is True
        assert result.unexplored > 0

    async def test_one_failing_person_does_not_lose_the_rest_of_the_level(self):
        transport = _ancestor_transport(failures={"h3": RuntimeError("HTTP 500")})
        with patch.object(GrampsWebAPIClient, "_make_request", new=transport):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 3)
        assert "HTTP 500" in result.failed["h3"]
        assert set(result.nodes) >= {"h1", "h2", "h4", "h5"}
        assert result.truncated_by_cap is False

    async def test_a_failing_root_yields_an_empty_walk_not_an_exception(self):
        transport = _ancestor_transport(failures={"h1": RuntimeError("HTTP 500")})
        with patch.object(GrampsWebAPIClient, "_make_request", new=transport):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 3)
        assert result.nodes == {}
        assert "h1" in result.failed


class TestWalkDescendants:
    async def test_follows_child_ref_list_down_the_generations(self):
        children = {"h1": ["h2", "h3"], "h2": ["h4"], "h3": [], "h4": []}
        names = {"h1": "A", "h2": "B", "h3": "C", "h4": "D"}

        async def _request(self, method=None, url=None, **kwargs):
            handle = url.rstrip("/").rsplit("/", 1)[-1]
            return {
                "handle": handle,
                "profile": {
                    "handle": handle,
                    "gramps_id": f"I{handle}",
                    "name_display": names[handle],
                },
                "extended": {
                    "families": [
                        {
                            "child_ref_list": [
                                {"ref": c} for c in children[handle]
                            ]
                        }
                    ]
                },
            }

        with patch.object(GrampsWebAPIClient, "_make_request", new=_request):
            result = await walk_descendants(GrampsWebAPIClient(), "default", "h1", 3)
        assert set(result.nodes) == {"h1", "h2", "h3", "h4"}
        assert result.edges["h1"] == ["h2", "h3"]
        assert result.edges["h2"] == ["h4"]

    async def test_returns_a_traversal_result(self):
        async def _request(self, method=None, url=None, **kwargs):
            return {
                "handle": "h1",
                "profile": {"handle": "h1", "gramps_id": "I0001", "name_display": "A"},
                "extended": {"families": []},
            }

        with patch.object(GrampsWebAPIClient, "_make_request", new=_request):
            result = await walk_descendants(GrampsWebAPIClient(), "default", "h1", 3)
        assert isinstance(result, TraversalResult)
        assert result.root == "h1"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_traversal.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_person_handle'`

- [ ] **Step 3: Implement the walk**

Append to `src/gramps_mcp/traversal.py` (add the imports at the top of the
module alongside the existing dataclass import):

```python
import asyncio
import logging

from .models.api_calls import ApiCalls

logger = logging.getLogger(__name__)

MAX_CONCURRENT_FETCHES = 8


async def resolve_person_handle(client, tree_id: str, gramps_id: str) -> str | None:
    """
    Look up a person's handle from their Gramps ID.

    Args:
        client: A GrampsWebAPIClient.
        tree_id (str): Family tree identifier.
        gramps_id (str): The Gramps ID to resolve, for example "I0001".

    Returns:
        str | None: The handle, or None when no person matches.
    """
    people = await client.make_api_call(
        api_call=ApiCalls.GET_PEOPLE,
        params={"gql": f'gramps_id = "{gramps_id}"', "pagesize": 1, "page": 1},
        tree_id=tree_id,
    )
    if not people:
        return None
    return people[0].get("handle")


async def _fetch_person(client, tree_id: str, handle: str, extend: str) -> dict:
    """
    Fetch one person with their profile and their extended families.

    Args:
        client: A GrampsWebAPIClient.
        tree_id (str): Family tree identifier.
        handle (str): Person handle.
        extend (str): "parent_family_list" or "family_list".

    Returns:
        dict: The raw person payload.
    """
    return await client.make_api_call(
        api_call=ApiCalls.GET_PERSON,
        params={"profile": "self", "extend": extend},
        tree_id=tree_id,
        handle=handle,
    )


async def _fetch_level(
    client, tree_id: str, handles: list[str], extend: str
) -> dict[str, dict | Exception]:
    """
    Fetch one generation concurrently.

    Args:
        client: A GrampsWebAPIClient.
        tree_id (str): Family tree identifier.
        handles (list[str]): Handles making up this generation.
        extend (str): "parent_family_list" or "family_list".

    Returns:
        dict[str, dict | Exception]: Payload or the exception, per handle.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def _bounded(handle: str):
        async with semaphore:
            return await _fetch_person(client, tree_id, handle, extend)

    # Reason: return_exceptions keeps one server error from discarding the
    # hundreds of fetches that succeeded alongside it.
    payloads = await asyncio.gather(
        *(_bounded(handle) for handle in handles), return_exceptions=True
    )
    return dict(zip(handles, payloads, strict=True))


def _parents_of(payload: dict) -> list[str]:
    """
    Read a person's parent handles from an extended parent_family_list.

    Args:
        payload (dict): A person payload fetched with extend=parent_family_list.

    Returns:
        list[str]: Father then mother, per family, skipping empty slots.
    """
    handles: list[str] = []
    for family in payload.get("extended", {}).get("parent_families", []) or []:
        for key in ("father_handle", "mother_handle"):
            handle = family.get(key)
            if handle:
                handles.append(handle)
    return handles


def _children_of(payload: dict) -> list[str]:
    """
    Read a person's child handles from an extended family_list.

    Args:
        payload (dict): A person payload fetched with extend=family_list.

    Returns:
        list[str]: Child handles across all families, in family order.
    """
    handles: list[str] = []
    for family in payload.get("extended", {}).get("families", []) or []:
        for child_ref in family.get("child_ref_list", []) or []:
            handle = child_ref.get("ref")
            if handle:
                handles.append(handle)
    return handles


async def _walk(
    client,
    tree_id: str,
    start_handle: str,
    max_generations: int,
    visit_cap: int,
    extend: str,
    successors,
) -> TraversalResult:
    """
    Walk the family graph breadth-first from one person.

    Args:
        client: A GrampsWebAPIClient.
        tree_id (str): Family tree identifier.
        start_handle (str): Handle of the subject.
        max_generations (int): Generations to fetch, the subject counting as one.
        visit_cap (int): Hard ceiling on people fetched.
        extend (str): "parent_family_list" or "family_list".
        successors (Callable[[dict], list[str]]): Reads the next generation's
            handles out of a person payload.

    Returns:
        TraversalResult: Nodes, edges, and what the walk could not reach.
    """
    result = TraversalResult(root=start_handle)
    seen: set[str] = {start_handle}
    level = [start_handle]

    for _ in range(max_generations):
        if not level:
            break
        if len(result.nodes) + len(level) > visit_cap:
            # Reason: the tail is counted once, below. Clearing level here
            # keeps the cap break from double-counting the generation it
            # just refused to fetch.
            result.truncated_by_cap = True
            result.unexplored += len(level)
            level = []
            break

        payloads = await _fetch_level(client, tree_id, level, extend)
        next_level: list[str] = []
        for handle, payload in payloads.items():
            if isinstance(payload, Exception):
                logger.warning(f"Traversal could not fetch {handle}: {payload}")
                result.failed[handle] = str(payload)
                continue
            result.nodes[handle] = payload.get("profile") or {
                "handle": handle,
                "gramps_id": payload.get("gramps_id", "?"),
                "name_display": "?",
            }
            children = successors(payload)
            if children:
                result.edges[handle] = children
            for child in children:
                if child in seen:
                    result.revisited.add(child)
                    continue
                seen.add(child)
                next_level.append(child)
        level = next_level

    result.unexplored += len(level)
    return result


async def walk_ancestors(
    client,
    tree_id: str,
    start_handle: str,
    max_generations: int,
    visit_cap: int = VISIT_CAP,
) -> TraversalResult:
    """
    Walk up the family graph from one person.

    Args:
        client: A GrampsWebAPIClient.
        tree_id (str): Family tree identifier.
        start_handle (str): Handle of the subject.
        max_generations (int): Generations to fetch, the subject counting as one.
        visit_cap (int): Hard ceiling on people fetched.

    Returns:
        TraversalResult: The ancestry reached.
    """
    return await _walk(
        client,
        tree_id,
        start_handle,
        max_generations,
        visit_cap,
        "parent_family_list",
        _parents_of,
    )


async def walk_descendants(
    client,
    tree_id: str,
    start_handle: str,
    max_generations: int,
    visit_cap: int = VISIT_CAP,
) -> TraversalResult:
    """
    Walk down the family graph from one person.

    Args:
        client: A GrampsWebAPIClient.
        tree_id (str): Family tree identifier.
        start_handle (str): Handle of the subject.
        max_generations (int): Generations to fetch, the subject counting as one.
        visit_cap (int): Hard ceiling on people fetched.

    Returns:
        TraversalResult: The descendancy reached.
    """
    return await _walk(
        client,
        tree_id,
        start_handle,
        max_generations,
        visit_cap,
        "family_list",
        _children_of,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_traversal.py -v`
Expected: PASS, 11 tests.

If `test_visit_cap_stops_the_walk_and_reports_what_is_left` fails on
`result.unexplored > 0`, the cap check ran before any level was queued —
check that `unexplored` accumulates both the abandoned level and the
never-fetched tail.

- [ ] **Step 5: Check the file length**

Run: `wc -l src/gramps_mcp/traversal.py`
Expected: under 500. If over, move `_parents_of` and `_children_of` into
`src/gramps_mcp/traversal_edges.py` and import them.

- [ ] **Step 6: Run the whole offline suite**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
uv run git add src/gramps_mcp/traversal.py tests/test_traversal.py
uv run git commit -m "feat: walk the family graph breadth-first

Adds walk_ancestors, walk_descendants and resolve_person_handle. One
request per person: profile=self plus extend=parent_family_list (or
family_list) returns the profile and the full family objects together,
so no separate family fetch is needed. A generation's fetches run
concurrently behind a semaphore of 8.

A visited set cuts cycles and cousin marriages, a 500-person cap bounds
the walk, and return_exceptions keeps one failed person from discarding
the rest of its generation.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Performance gate

The spec makes speed the justification for this change. Measure it before
deleting anything, so a failed premise is caught while the old path still
exists.

**Files:**
- Create: `/private/tmp/claude-501/-Users-fjacquet-Projects-gramps-mcp/2d7e0ae7-6ee5-4edd-9930-9929a7320fd9/scratchpad/bench_traversal.py` (throwaway, never committed)

**Interfaces:**
- Consumes: `walk_ancestors` from Task 2, `get_ancestors_tool` as it exists today.
- Produces: a timing figure quoted in Task 4's commit message.

- [ ] **Step 1: Write the benchmark**

Create the scratchpad file:

```python
"""Throwaway benchmark: HTML report path versus BFS walk. Not committed."""

import asyncio
import time

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.tools.analysis import get_ancestors_tool
from src.gramps_mcp.traversal import resolve_person_handle, walk_ancestors

GRAMPS_ID = "I0001"
GENERATIONS = 5


async def main():
    settings = get_settings()
    tree_id = settings.gramps_tree_id
    client = GrampsWebAPIClient()

    start = time.perf_counter()
    old = await get_ancestors_tool(
        {"gramps_id": GRAMPS_ID, "max_generations": GENERATIONS}
    )
    old_seconds = time.perf_counter() - start

    handle = await resolve_person_handle(client, tree_id, GRAMPS_ID)
    start = time.perf_counter()
    new = await walk_ancestors(client, tree_id, handle, GENERATIONS)
    new_seconds = time.perf_counter() - start

    print(f"report path: {old_seconds:.2f}s, {len(old[0].text)} chars")
    print(f"bfs path:    {new_seconds:.2f}s, {len(new.nodes)} people")


asyncio.run(main())
```

- [ ] **Step 2: Run it against the live tree**

Run:
```bash
GRAMPS_API_URL=http://localhost:80 uv run python /private/tmp/claude-501/-Users-fjacquet-Projects-gramps-mcp/2d7e0ae7-6ee5-4edd-9930-9929a7320fd9/scratchpad/bench_traversal.py
```
Expected: two timings printed.

- [ ] **Step 3: Decide**

If the BFS path is faster, record both numbers and continue to Task 4.

If it is **not** faster, STOP and report to the user before touching
`analysis.py`. The spec's premise failed and deleting the report path is no
longer the agreed change. Do not silently keep going.

---

### Task 4: Wire the tools and delete the report path

**Files:**
- Modify: `src/gramps_mcp/tools/analysis.py` (replace `get_descendants_tool` at lines 181-266 and `get_ancestors_tool` at lines 269-357; delete `_wait_for_task_completion` at lines 109-174)
- Modify: `src/gramps_mcp/models/parameters/analysis_params.py:29-49`
- Modify: `src/gramps_mcp/resources/gramps-usage-guide.md:425-428`
- Test: `tests/test_analysis.py`

**Interfaces:**
- Consumes: `resolve_person_handle`, `walk_ancestors`, `walk_descendants` from Task 2; `format_traversal` from Task 1.
- Produces: no new interface. `get_ancestors_tool(arguments: dict) -> list[TextContent]` and `get_descendants_tool(arguments: dict) -> list[TextContent]` keep their signatures.

- [ ] **Step 1: Write the failing live tests**

Append to `tests/test_analysis.py` (the module already carries
`pytestmark = pytest.mark.integration`; if it does not, add it):

```python
class TestBfsAncestorOutput:
    """Live checks on the BFS output shape. Needs a populated tree."""

    async def test_ancestors_of_i0001_name_the_known_parents(self):
        result = await get_ancestors_tool(
            {"gramps_id": "I0001", "max_generations": 3}
        )
        text = result[0].text
        assert text.startswith("# Ancestors of")
        # Reason: I0001 is the tree owner and has both parents recorded.
        # If this ever fails, check the tree before the code.
        assert text.count("\n  - ") >= 2

    async def test_fewer_generations_return_strictly_fewer_lines(self):
        shallow = await get_ancestors_tool(
            {"gramps_id": "I0001", "max_generations": 1}
        )
        deep = await get_ancestors_tool(
            {"gramps_id": "I0001", "max_generations": 3}
        )
        assert len(shallow[0].text.splitlines()) < len(deep[0].text.splitlines())

    async def test_every_person_line_carries_a_gramps_id(self):
        result = await get_ancestors_tool(
            {"gramps_id": "I0001", "max_generations": 2}
        )
        person_lines = [
            line for line in result[0].text.splitlines() if line.lstrip().startswith("- ")
        ]
        assert person_lines
        for line in person_lines:
            assert "(I" in line or "[unavailable" in line

    async def test_unknown_gramps_id_reports_an_error(self):
        result = await get_ancestors_tool({"gramps_id": "I999999"})
        assert "Error:" in result[0].text
```

- [ ] **Step 2: Run them to verify they fail**

Run:
```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_analysis.py::TestBfsAncestorOutput -v
```
Expected: FAIL — the current HTML-derived output does not start with
`# Ancestors of`.

- [ ] **Step 3: Rewrite the two tools**

In `src/gramps_mcp/tools/analysis.py`, delete `_wait_for_task_completion`
entirely and replace both tool bodies with:

```python
async def _traverse_and_format(
    client, arguments: dict, direction: str, walk
) -> list[TextContent]:
    """
    Resolve the subject, walk the graph, and render the result.

    Args:
        client: A GrampsWebAPIClient, injected by with_client.
        arguments (dict): Tool arguments carrying gramps_id and max_generations.
        direction (str): "ancestors" or "descendants", used in the heading.
        walk (Callable): walk_ancestors or walk_descendants.

    Returns:
        list[TextContent]: The rendered tree, or an error message.
    """
    try:
        gramps_id = arguments.get("gramps_id")
        if not gramps_id:
            raise ValueError("gramps_id is required")
        max_generations = arguments.get("max_generations") or 5

        tree_id = get_settings().gramps_tree_id
        start_handle = await resolve_person_handle(client, tree_id, gramps_id)
        if start_handle is None:
            raise ValueError(f"no person found with gramps_id {gramps_id}")

        result = await walk(client, tree_id, start_handle, max_generations)
        return [TextContent(type="text", text=format_traversal(result, direction))]
    except Exception as e:
        return _format_error_response(e, f"{direction} search")


@with_client
async def get_descendants_tool(client, arguments: dict) -> list[TextContent]:
    """
    Find all descendants of a person.

    Args:
        client: A GrampsWebAPIClient, injected by with_client.
        arguments (dict): Tool arguments carrying gramps_id and max_generations.

    Returns:
        list[TextContent]: An indented markdown tree of descendants.
    """
    return await _traverse_and_format(
        client, arguments, "descendants", walk_descendants
    )


@with_client
async def get_ancestors_tool(client, arguments: dict) -> list[TextContent]:
    """
    Find all ancestors of a person.

    Args:
        client: A GrampsWebAPIClient, injected by with_client.
        arguments (dict): Tool arguments carrying gramps_id and max_generations.

    Returns:
        list[TextContent]: An indented markdown tree of ancestors.
    """
    return await _traverse_and_format(client, arguments, "ancestors", walk_ancestors)
```

Fix the imports at the top of the module: drop
`from ..models.parameters.reports_params import ReportFileParams`, drop
`html_to_markdown` from the `..utils` import (keep
`get_gramps_id_from_handle`), drop `import json` and `import asyncio` if
nothing else in the module still uses them (check with
`grep -n "json\.\|asyncio\." src/gramps_mcp/tools/analysis.py`), and add:

```python
from ..handlers.traversal_handler import format_traversal
from ..traversal import resolve_person_handle, walk_ancestors, walk_descendants
```

- [ ] **Step 4: Bound max_generations**

In `src/gramps_mcp/models/parameters/analysis_params.py`, add `ge=1, le=20`
to the `max_generations` field of both `DescendantsParams` and
`AncestorsParams`, and update the description:

```python
    max_generations: int | None = Field(
        5,
        ge=1,
        le=20,
        description=(
            "Max generations to retrieve (default: 5, max: 20). The walk "
            "also stops after 500 people and says so in its output."
        ),
    )
```

- [ ] **Step 5: Run the live tests to verify they pass**

Run:
```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_analysis.py -v
```
Expected: PASS, including the pre-existing descendant and ancestor tests.
Those assert on substrings like `"descendant"` and on `"Error:"` for an
invalid ID; if one now fails because it asserted on HTML-report wording,
update that assertion to the new format and say so in the commit message.

- [ ] **Step 6: Run the offline suite**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS.

- [ ] **Step 7: Update the usage guide**

In `src/gramps_mcp/resources/gramps-usage-guide.md`, rewrite the
`### get_ancestors / get_descendants - token-heavy, start small` section so
it describes the new output: an indented markdown tree, one line per person
carrying the gramps_id, `max_generations` capped at 20, and a 500-person
visit cap that announces itself in the output. Keep the heading text
unchanged so the section stays findable.

- [ ] **Step 8: Check the alignment tests still pass**

Run: `uv run pytest tests/test_alignment_records.py tests/test_alignment_sourcing.py -v -m "not integration"`
Expected: PASS. These hold hardcoded field inventories tracking the usage
guide; a changed field list there fails them. Fix the guide first, then the
inventory — never the inventory alone.

- [ ] **Step 9: Build the docs**

Run: `uv run --with mkdocs-material mkdocs build --strict`
Expected: builds clean.

- [ ] **Step 10: Commit**

```bash
uv run git add src/gramps_mcp/tools/analysis.py src/gramps_mcp/models/parameters/analysis_params.py src/gramps_mcp/resources/gramps-usage-guide.md tests/test_analysis.py
uv run git commit -m "feat: serve ancestors and descendants from the BFS walk

get_ancestors and get_descendants no longer render an HTML report, poll a
Celery task and convert the download to markdown. They resolve the
subject, walk the graph, and format the result (upstream issue #6).

Measured on the live tree, five generations from I0001: <OLD>s via the
report path, <NEW>s via the walk.

Deletes _wait_for_task_completion and the report calls from analysis.py.
ReportFileParams, the ApiCalls report entries and html_to_markdown stay -
they describe real endpoints and cost nothing to keep. max_generations
gains a ceiling of 20, which it never had.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Replace `<OLD>` and `<NEW>` with the figures from Task 3.

---

### Task 5: Pull request

**Files:** none.

- [ ] **Step 1: Push**

```bash
uv run git push -u origin feat/bfs-traversal
```

- [ ] **Step 2: Open the PR against the fork, not the parent**

```bash
gh pr create --repo fjacquet/gramps-mcp \
  --title "feat: BFS traversal for get_ancestors and get_descendants" \
  --body "Implements the design in docs/superpowers/specs/2026-08-14-bfs-traversal-design.md, addressing upstream issue cabout-me/gramps-mcp#6.

Both tools now walk the family graph directly instead of rendering an HTML report, polling a Celery task and converting the download. One request per person; a generation's requests run concurrently.

Output is an indented markdown tree, one line per person carrying the gramps_id so a get_type call can be chained on any line. Cycles are cut, a 500-person cap bounds the walk and announces itself, and one failed fetch no longer discards its whole generation.

Timings on the live tree are in the implementation commit.

Generated with [Claude Code](https://claude.com/claude-code)"
```

The standard PR-body trailer carries a robot emoji. Leave it out here: the
`check-no-emojis` pre-commit hook covers the whole tree and rejects this
file if the emoji is written into it.

Without `--repo fjacquet/gramps-mcp` the command targets the upstream parent
and fails with a misleading token error.

- [ ] **Step 3: Merge when green**

Merge with `--merge`, never `--squash` — the per-defect commits must survive.

---

## Notes for the implementer

- `walk_ancestors(..., max_generations=1)` returns the subject alone. The
  subject counts as generation one, matching how the old report counted.
- `resolve_person_handle` quotes the Gramps ID in the GQL string
  (`gramps_id = "I0001"`). GQL needs the quotes when a value could parse as
  a number, and quoting always is simpler than deciding when.
- `tree_stats` fails with "Permission denied for this operation" even for
  the owner account in `.env`. If a test in `tests/test_analysis.py` fails
  that way, it is an environment fact, not something this change broke.
- The MCP tools exposed as `mcp__gramps__*` run the server's startup code,
  not the working tree. Do not verify this work through them; run the tests.
