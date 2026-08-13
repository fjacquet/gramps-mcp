# Quality Lot 2 — Data Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix seven defects that let the Gramps MCP server store or display the wrong thing without ever raising an error.

**Architecture:** Four of the seven are fixed in pure functions — `merge.py` and `handlers/date_handler.py` — which makes them testable without a server and gives this lot its strongest tests. The other two tighten Pydantic parameter models so malformed input is refused before any network call. One new model, `DateValue`, is introduced and applied to the five date fields that currently accept `dict[str, Any]`.

**Tech Stack:** Python 3.13, pydantic v2, httpx, MCP Python SDK 2.0, pytest + pytest-asyncio, uv, ruff.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-08-13-quality-lot2-data-fidelity-design.md`.
- Every command runs through uv: `uv run pytest`, `uv run git commit`.
- No mocks, no fixtures, no test clients. Tests that need a server hit the live one.
- Live tests need a URL override from the macOS host, because `.env` targets `host.docker.internal`, which only resolves inside the container: `GRAMPS_API_URL=http://localhost:80 uv run pytest ...`. Never edit `.env`, never commit the override.
- Never create a file longer than 500 lines. A pre-commit hook enforces this.
- No emojis anywhere. A pre-commit hook enforces this, including in markdown.
- Google-style docstrings on every function.
- **One atomic commit per defect**, each carrying its fix and its test together.
- Branch `fix/quality-lot2-data-fidelity`, which already exists and holds the spec commit.
- No release tag. Lot 2 merges into `main` and waits for lots 3 and 4.
- Tests that write to the tree must clean up in a `finally` block. The target is a real genealogy tree.
- Do NOT merge the pull request, create a tag, publish a release, or bump a version. Those are the repository owner's decisions.

---

### Task 1: `merge_put_data` learns to replace a list

`merge_put_data` merges every `_list` key by union, so a caller can add to a
list but never replace one. This task adds the capability to the pure function
only; Task 2 wires it to the API layer.

**Files:**
- Modify: `src/gramps_mcp/merge.py:28-50`
- Test: `tests/test_merge.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `merge_put_data(existing: dict, changes: dict, replace_lists: list[str] | None = None) -> dict`. Task 2 calls it with the third argument.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_merge.py`:

```python
class TestReplaceLists:
    """A named list is replaced outright instead of merged."""

    def test_named_list_is_replaced(self):
        existing = {"placeref_list": [{"ref": "AAA"}]}
        changes = {"placeref_list": [{"ref": "BBB"}]}

        merged = merge_put_data(existing, changes, replace_lists=["placeref_list"])

        assert merged["placeref_list"] == [{"ref": "BBB"}]

    def test_unnamed_list_still_merges(self):
        existing = {"media_list": [{"ref": "AAA"}]}
        changes = {"media_list": [{"ref": "BBB"}]}

        merged = merge_put_data(existing, changes, replace_lists=["placeref_list"])

        assert merged["media_list"] == [{"ref": "AAA"}, {"ref": "BBB"}]

    def test_default_is_still_union(self):
        existing = {"placeref_list": [{"ref": "AAA"}]}
        changes = {"placeref_list": [{"ref": "BBB"}]}

        merged = merge_put_data(existing, changes)

        assert merged["placeref_list"] == [{"ref": "AAA"}, {"ref": "BBB"}]

    def test_replacing_with_an_empty_list_clears_it(self):
        existing = {"placeref_list": [{"ref": "AAA"}]}
        changes = {"placeref_list": []}

        merged = merge_put_data(existing, changes, replace_lists=["placeref_list"])

        assert merged["placeref_list"] == []

    def test_inputs_are_not_mutated(self):
        existing = {"placeref_list": [{"ref": "AAA"}]}
        changes = {"placeref_list": [{"ref": "BBB"}]}

        merge_put_data(existing, changes, replace_lists=["placeref_list"])

        assert existing == {"placeref_list": [{"ref": "AAA"}]}
        assert changes == {"placeref_list": [{"ref": "BBB"}]}
```

Check the existing import line at the top of `tests/test_merge.py` and reuse it rather than adding a duplicate.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_merge.py::TestReplaceLists -v`
Expected: FAIL — `merge_put_data() got an unexpected keyword argument 'replace_lists'`.

- [ ] **Step 3: Implement**

In `src/gramps_mcp/merge.py`, the function currently reads:

```python
def merge_put_data(existing: dict, changes: dict) -> dict:
```

with a body ending:

```python
    merged = existing.copy()
    for key, value in changes.items():
        if key.endswith("_list") and isinstance(value, list) and key in existing:
            merged[key] = _merge_list(existing.get(key, []), value)
        else:
            merged[key] = value
    return merged
```

Change the signature to:

```python
def merge_put_data(
    existing: dict, changes: dict, replace_lists: list[str] | None = None
) -> dict:
```

and the body to:

```python
    replace = set(replace_lists or ())
    merged = existing.copy()
    for key, value in changes.items():
        # Reason: union is the default because a partial update must not wipe
        # lists the caller did not mention, and attaching media relies on it.
        # Replacement is opt-in per key so the intent is visible at the call
        # site rather than inferred from the key's name.
        if (
            key.endswith("_list")
            and isinstance(value, list)
            and key in existing
            and key not in replace
        ):
            merged[key] = _merge_list(existing.get(key, []), value)
        else:
            merged[key] = value
    return merged
```

Extend the docstring's Args section with:

```
        replace_lists (List | None): Keys whose lists should be replaced
            outright rather than merged. Everything else keeps the default
            union behaviour.
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_merge.py -v`
Expected: PASS, including the pre-existing tests in that file.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/merge.py tests/test_merge.py
uv run git commit -m "feat: let merge_put_data replace a named list instead of merging it"
```

---

### Task 2: Wire replacement through to the place tool

Task 1's capability is unreachable until the API layer and a tool expose it.
Moving a place to a new parent is the case that motivated it.

**Files:**
- Modify: `src/gramps_mcp/client.py:243-252`
- Modify: `src/gramps_mcp/models/parameters/place_params.py`
- Modify: `src/gramps_mcp/tools/data_management.py` (the place branch of the CRUD handler)
- Test: `tests/test_place_move.py` (new)

**Interfaces:**
- Consumes: `merge_put_data(existing, changes, replace_lists=None)` from Task 1.
- Produces: `make_api_call(..., replace_lists: list[str] | None = None)`; `PlaceSaveParams.replace_lists: list[str] | None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_place_move.py`:

```python
"""
Integration tests for replacing a place's parent against the real Gramps API.
"""

import uuid

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls


class TestPlaceMove:
    """Replacing placeref_list must move a place, not add a second parent."""

    @pytest.mark.asyncio
    async def test_replacing_placeref_list_moves_the_place(self):
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id
        suffix = uuid.uuid4().hex[:8]
        handles = []

        try:
            for label in ("ParentA", "ParentB", "Child"):
                created = await client.make_api_call(
                    api_call=ApiCalls.POST_PLACES,
                    params={
                        "name": {"value": f"Pytest{label}{suffix}"},
                        "place_type": "City",
                    },
                    tree_id=tree_id,
                )
                handles.append(created[0]["new"]["handle"])
            parent_a, parent_b, child = handles

            await client.make_api_call(
                api_call=ApiCalls.PUT_PLACE,
                params={"placeref_list": [{"ref": parent_a}]},
                tree_id=tree_id,
                handle=child,
            )

            await client.make_api_call(
                api_call=ApiCalls.PUT_PLACE,
                params={"placeref_list": [{"ref": parent_b}]},
                tree_id=tree_id,
                handle=child,
                replace_lists=["placeref_list"],
            )

            moved = await client.make_api_call(
                api_call=ApiCalls.GET_PLACE, tree_id=tree_id, handle=child
            )
            refs = [entry.get("ref") for entry in moved.get("placeref_list", [])]

            # Reason: without replacement this reads [parent_a, parent_b] and
            # Gramps keeps the first, so the move silently does nothing.
            assert refs == [parent_b]
        finally:
            for handle in reversed(handles):
                await client.make_api_call(
                    api_call=ApiCalls.DELETE_PLACE, tree_id=tree_id, handle=handle
                )
```

Confirm the enum names first: `grep -nE "POST_PLACES|PUT_PLACE|GET_PLACE|DELETE_PLACE" src/gramps_mcp/models/api_calls.py`. If any differs, use the real one; do not invent one. If `POST_PLACES` needs fields beyond `name` and `place_type`, read `PlaceSaveParams` and supply the minimum it requires.

- [ ] **Step 2: Run the test to verify it fails**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_place_move.py -v`
Expected: FAIL — `make_api_call() got an unexpected keyword argument 'replace_lists'`.

- [ ] **Step 3: Thread the parameter through `make_api_call`**

In `src/gramps_mcp/client.py`, the signature currently reads:

```python
    async def make_api_call(
        self,
        api_call: ApiCalls,
        params: dict | BaseModel | None = None,
        tree_id: str = "default",
        with_headers: bool = False,
        **url_params,
    ):
```

Add the parameter before `**url_params`:

```python
    async def make_api_call(
        self,
        api_call: ApiCalls,
        params: dict | BaseModel | None = None,
        tree_id: str = "default",
        with_headers: bool = False,
        replace_lists: list[str] | None = None,
        **url_params,
    ):
```

Document it in the docstring's Args section:

```
            replace_lists: Keys whose lists should be replaced outright rather
                than merged into the existing record. PUT operations only.
```

Then at the PUT merge site, which currently reads:

```python
                if existing:
                    json_data = merge_put_data(existing, json_data)
```

change it to:

```python
                if existing:
                    json_data = merge_put_data(existing, json_data, replace_lists)
```

- [ ] **Step 4: Expose it on the place model and tool**

In `src/gramps_mcp/models/parameters/place_params.py`, add to `PlaceSaveParams`
next to the other optional fields:

```python
    replace_lists: list[str] | None = Field(
        None,
        description=(
            "List field names to overwrite rather than add to, for example "
            "['placeref_list'] to move a place to a different parent instead "
            "of giving it a second one. Omit to add to existing lists."
        ),
    )
```

Then find the place branch of the CRUD handler in
`src/gramps_mcp/tools/data_management.py` and make it pass the value through to
`make_api_call` while keeping it out of the request body. Read the surrounding
code first: the handler builds a params model and calls `make_api_call`. Pull
`replace_lists` off the arguments before the model is constructed, or exclude it
from the serialised body, whichever matches how that function already handles
fields that are instructions rather than data. If nothing in the file
establishes such a pattern, pop it from the incoming `arguments` dict before
building the model and pass it as the `replace_lists` keyword.

- [ ] **Step 5: Run the test**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_place_move.py -v`
Expected: PASS.

- [ ] **Step 6: Verify the tree is clean**

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.tools.search_basic import find_anything_tool
print(asyncio.run(find_anything_tool({'query': 'Pytest'}))[0].text[:400])
"
```

Expected: no `Pytest*` place remains. If one does, say so rather than quietly deleting it.

- [ ] **Step 7: Commit**

```bash
rtk git add src/gramps_mcp/client.py src/gramps_mcp/models/parameters/place_params.py src/gramps_mcp/tools/data_management.py tests/test_place_move.py
uv run git commit -m "feat: expose list replacement so a place can be moved"
```

---

### Task 3: Stop `attribute_list` accumulating duplicates

`_merge_list` deduplicates dicts carrying a `ref` and lists of strings.
`attribute_list` entries are `{"type": ..., "value": ...}` dicts with no `ref`,
so they match neither branch and fall through to plain concatenation. Sending
the same attribute twice stores it twice.

**Files:**
- Modify: `src/gramps_mcp/merge.py:86-95`
- Test: `tests/test_merge.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: no new names.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_merge.py`:

```python
class TestAttributeDeduplication:
    """Dicts without a ref deduplicate on their whole content."""

    def test_identical_attribute_is_not_duplicated(self):
        attribute = {"type": "Occupation", "value": "Cordonnier"}
        existing = {"attribute_list": [attribute]}
        changes = {"attribute_list": [dict(attribute)]}

        merged = merge_put_data(existing, changes)

        assert merged["attribute_list"] == [attribute]

    def test_different_attribute_is_appended(self):
        existing = {"attribute_list": [{"type": "Occupation", "value": "Cordonnier"}]}
        changes = {"attribute_list": [{"type": "Occupation", "value": "Meunier"}]}

        merged = merge_put_data(existing, changes)

        assert merged["attribute_list"] == [
            {"type": "Occupation", "value": "Cordonnier"},
            {"type": "Occupation", "value": "Meunier"},
        ]

    def test_ref_dicts_still_deduplicate_on_ref_alone(self):
        # Reason: two refs to the same object differ in their other keys but
        # must still count as one; ref identity must keep winning over
        # whole-content identity.
        existing = {"media_list": [{"ref": "AAA", "private": False}]}
        changes = {"media_list": [{"ref": "AAA", "private": True}]}

        merged = merge_put_data(existing, changes)

        assert merged["media_list"] == [{"ref": "AAA", "private": False}]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_merge.py::TestAttributeDeduplication -v`
Expected: `test_identical_attribute_is_not_duplicated` FAILS with the attribute appearing twice. The other two pass already.

- [ ] **Step 3: Implement**

In `src/gramps_mcp/merge.py`, `_merge_list` currently ends:

```python
    if isinstance(sample_existing, str) and isinstance(sample_new, str):
        existing_set = set(existing_items)
        return existing_items + [item for item in new_items if item not in existing_set]

    # Reason: mixed/unknown item types - concatenation is the safe fallback
    return existing_items + new_items
```

Insert a dict branch before the fallback, so the function reads:

```python
    if isinstance(sample_existing, str) and isinstance(sample_new, str):
        existing_set = set(existing_items)
        return existing_items + [item for item in new_items if item not in existing_set]

    if isinstance(sample_existing, dict) and isinstance(sample_new, dict):
        # Reason: attribute_list entries are {type, value} dicts with no ref,
        # so they miss the ref branch above. Without this they concatenate,
        # and N identical updates leave N copies.
        existing_serialised = [
            sorted(item.items()) for item in existing_items if isinstance(item, dict)
        ]
        additions = [
            item
            for item in new_items
            if isinstance(item, dict) and sorted(item.items()) not in existing_serialised
        ]
        return existing_items + additions

    # Reason: mixed/unknown item types - concatenation is the safe fallback
    return existing_items + new_items
```

If `sorted(item.items())` raises a `TypeError` for an attribute whose value is
itself a dict or list, fall back to comparing `item` against `existing_items`
directly with `in`, which uses dict equality and needs no sorting. Prefer the
simpler `in` comparison if it passes all three tests — it is easier to read.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_merge.py -v`
Expected: PASS, all classes.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/merge.py tests/test_merge.py
uv run git commit -m "fix: deduplicate ref-less dicts so attributes do not accumulate"
```

---

### Task 4: Render range, span and free-text dates

`format_date` reads only `dateval[0:3]`. Range and span dates carry an
eight-element `dateval` — `(d1, m1, y1, s1, d2, m2, y2, s2)` — so the second
date is dropped and a 12-to-26 March 1885 range renders as
`between 12 March 1885`. Free-text dates keep their content in
`date_obj["text"]`, which nothing reads, and their `dateval` of `[0,0,0,False]`
trips the `year <= 0` guard, so they always display as `date unknown`.

**Files:**
- Modify: `src/gramps_mcp/handlers/date_handler.py:38-97`
- Test: `tests/test_date_handler.py` (new)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `format_date(date_obj: dict) -> str` keeps its signature.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_date_handler.py`:

```python
"""
Unit tests for Gramps date rendering. These are pure functions - no server.
"""

from src.gramps_mcp.handlers.date_handler import format_date


class TestRangeAndSpan:
    """Modifiers carrying two dates must render both."""

    def test_range_renders_both_endpoints(self):
        date_obj = {
            "dateval": [12, 3, 1885, False, 26, 3, 1885, False],
            "modifier": 4,
            "quality": 0,
        }

        result = format_date(date_obj)

        assert "12 March 1885" in result
        assert "26 March 1885" in result

    def test_span_renders_both_endpoints(self):
        date_obj = {
            "dateval": [1, 1, 1900, False, 31, 12, 1910, False],
            "modifier": 5,
            "quality": 0,
        }

        result = format_date(date_obj)

        assert "1900" in result
        assert "1910" in result

    def test_single_date_is_unchanged(self):
        date_obj = {"dateval": [12, 3, 1885, False], "modifier": 0, "quality": 0}

        assert format_date(date_obj) == "12 March 1885"


class TestFreeText:
    """Modifier 6 keeps its content in the text field."""

    def test_free_text_date_is_returned(self):
        date_obj = {
            "dateval": [0, 0, 0, False],
            "modifier": 6,
            "quality": 0,
            "text": "vers la Saint-Jean 1885",
        }

        assert format_date(date_obj) == "vers la Saint-Jean 1885"

    def test_free_text_without_content_is_unknown(self):
        date_obj = {"dateval": [0, 0, 0, False], "modifier": 6, "quality": 0, "text": ""}

        assert format_date(date_obj) == "date unknown"


class TestExistingBehaviour:
    """The preformatted string and the empty cases keep winning."""

    def test_preformatted_string_wins(self):
        date_obj = {"string": "1885-03-12", "dateval": [12, 3, 1885, False]}

        assert format_date(date_obj) == "1885-03-12"

    def test_empty_object_is_unknown(self):
        assert format_date({}) == "date unknown"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_date_handler.py -v`
Expected: `test_range_renders_both_endpoints`, `test_span_renders_both_endpoints` and `test_free_text_date_is_returned` FAIL. The others pass.

- [ ] **Step 3: Implement**

In `src/gramps_mcp/handlers/date_handler.py`, `format_date` currently returns
early on a missing `dateval`, then extracts `day, month, year` from the first
three entries, then builds `base_date` and applies a prefix and suffix.

Make three changes.

First, handle free text before the `dateval` guard rejects it. Immediately
after the block that returns the preformatted `string`, insert:

```python
    # Reason: a text-only date (modifier 6) carries its content in "text" and
    # a dateval of [0, 0, 0, False], which the year guard below would reject.
    if date_obj.get("modifier") == 6:
        text = date_obj.get("text") or ""
        return text if text else "date unknown"
```

Second, extract the date-formatting logic into a helper so both endpoints can
use it. Add above `format_date`:

```python
def _format_single_date(day: int, month: int, year: int) -> str:
    """
    Format one date triple as human-readable text.

    Args:
        day (int): Day of month, 0 when unknown.
        month (int): Month number, 0 when unknown.
        year (int): Year, must be positive.

    Returns:
        str: The formatted date, falling back to the year alone.
    """
    try:
        if day > 0 and month > 0:
            return datetime(year, month, day).strftime("%d %B %Y")
        if month > 0:
            return datetime(year, month, 1).strftime("%B %Y")
        return str(year)
    except (ValueError, TypeError):
        return str(year) if year > 0 else "date unknown"
```

Replace the inline `try`/`except` that builds `base_date` with a call to it:

```python
    base_date = _format_single_date(day, month, year)
```

Third, render the second endpoint. After `base_date` is computed and before the
prefix and suffix are applied, insert:

```python
    # Reason: modifiers 4, 5, 7 and 8 carry two dates in an eight-element
    # dateval. Rendering only the first turns "between X and Y" into
    # "between X", which reads as a different claim rather than a partial one.
    if modifier in (4, 5, 7, 8) and len(dateval) >= 8:
        end_day, end_month, end_year = dateval[4], dateval[5], dateval[6]
        if end_year > 0:
            joiner = " and " if modifier == 4 else " to "
            base_date = (
                f"{base_date}{joiner}{_format_single_date(end_day, end_month, end_year)}"
            )
```

Leave the `modifier_prefixes` and `quality_suffixes` tables as they are.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_date_handler.py -v`
Expected: PASS, 7 tests.

- [ ] **Step 5: Check nothing downstream depended on the old output**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_search_details.py tests/test_relationship_tools.py -q`
Expected: no NEW failures. Some tests in these files fail for pre-existing reasons; confirm any failure you see is not caused by the changed date output before continuing.

- [ ] **Step 6: Commit**

```bash
rtk git add src/gramps_mcp/handlers/date_handler.py tests/test_date_handler.py
uv run git commit -m "fix: render both endpoints of range and span dates, and free text"
```

---

### Task 5: Validate the date structure with a model

The five date fields are `dict[str, Any]`, so nothing checks that a modifier
promising two dates carries two. `CLAUDE.md` records the consequence: a
modifier 4 or 5 with a four-element `dateval` saves without error and later
crashes the XML export with `IndexError: tuple index out of range`.

**Files:**
- Create: `src/gramps_mcp/models/parameters/date_params.py`
- Modify: `src/gramps_mcp/models/parameters/event_params.py:51`
- Modify: `src/gramps_mcp/models/parameters/citation_params.py:46`
- Modify: `src/gramps_mcp/models/parameters/media_params.py:77`
- Modify: `src/gramps_mcp/models/parameters/sourced_event_params.py:41,55`
- Test: `tests/test_date_params.py` (new)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `class DateValue(BaseModel)` with fields `dateval: list[int | bool]`, `modifier: int = 0`, `quality: int = 0`, `text: str = ""`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_date_params.py`:

```python
"""
Unit tests for date parameter validation. No server involved.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.date_params import DateValue


class TestDateValue:
    """A modifier promising two dates must carry two."""

    def test_range_without_second_date_is_rejected(self):
        with pytest.raises(ValidationError):
            DateValue(dateval=[12, 3, 1885, False], modifier=4)

    def test_span_without_second_date_is_rejected(self):
        with pytest.raises(ValidationError):
            DateValue(dateval=[1, 1, 1900, False], modifier=5)

    def test_range_with_second_date_is_accepted(self):
        value = DateValue(dateval=[12, 3, 1885, False, 26, 3, 1885, False], modifier=4)

        assert len(value.dateval) == 8

    def test_plain_date_is_accepted(self):
        value = DateValue(dateval=[12, 3, 1885, False])

        assert value.modifier == 0
        assert value.quality == 0

    def test_estimated_quality_is_accepted(self):
        # Reason: CLAUDE.md recommends quality 1 with modifier 0 for an
        # approximate date, precisely to avoid the malformed range case.
        value = DateValue(dateval=[0, 0, 1885, False], quality=1, modifier=0)

        assert value.quality == 1

    def test_text_only_date_is_accepted(self):
        value = DateValue(dateval=[0, 0, 0, False], modifier=6, text="vers 1885")

        assert value.text == "vers 1885"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_date_params.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.gramps_mcp.models.parameters.date_params'`.

- [ ] **Step 3: Create the model**

Create `src/gramps_mcp/models/parameters/date_params.py`, starting with the
15-line AGPL header copied verbatim from
`src/gramps_mcp/models/parameters/event_params.py`, then:

```python
"""
Date parameter model shared by every tool that accepts a Gramps date.
"""

from pydantic import BaseModel, Field, model_validator

# Modifiers whose dateval carries a second date: range, span, from, to.
TWO_DATE_MODIFIERS = (4, 5, 7, 8)


class DateValue(BaseModel):
    """A Gramps date object."""

    dateval: list[int | bool] = Field(
        ...,
        description=(
            "Date values: [day, month, year, False] for a single date, or "
            "[day1, month1, year1, False, day2, month2, year2, False] for a "
            "range or span. Use 0 for an unknown day or month."
        ),
    )
    modifier: int = Field(
        0,
        description=(
            "0=regular, 1=before, 2=after, 3=about, 4=range, 5=span, "
            "6=textonly, 7=from, 8=to"
        ),
    )
    quality: int = Field(
        0, description="0=regular, 1=estimated, 2=calculated"
    )
    text: str = Field(
        "", description="Free-text date, used when modifier is 6"
    )

    @model_validator(mode="after")
    def check_two_date_modifiers(self) -> "DateValue":
        """
        Reject a range or span that carries only one date.

        Returns:
            DateValue: The validated model.

        Raises:
            ValueError: If a two-date modifier has fewer than eight dateval
                entries.
        """
        # Reason: Gramps accepts the malformed object and only fails later,
        # during the XML export, with IndexError in exportxml.py. Refusing it
        # here turns a corrupted backup into an immediate validation error.
        if self.modifier in TWO_DATE_MODIFIERS and len(self.dateval) < 8:
            raise ValueError(
                f"modifier {self.modifier} needs a second date: dateval must "
                "have 8 entries, [day1, month1, year1, False, day2, month2, "
                "year2, False]. For an approximate single date use quality=1 "
                "with modifier=0 instead."
            )
        return self
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_date_params.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 5: Apply the model to the five date fields**

Replace the `dict[str, Any]` declaration at each of these sites with
`DateValue`, keeping the field optional and keeping its existing description
where one adds information the model does not already carry:

- `src/gramps_mcp/models/parameters/event_params.py:51` — `date`
- `src/gramps_mcp/models/parameters/citation_params.py:46` — `date`
- `src/gramps_mcp/models/parameters/media_params.py:77` — `date`
- `src/gramps_mcp/models/parameters/sourced_event_params.py:41` — `citation_date`
- `src/gramps_mcp/models/parameters/sourced_event_params.py:55` — `event_date`

Each becomes, adapting the field name:

```python
    date: DateValue | None = Field(None, description="Event date")
```

Add `from .date_params import DateValue` to each file's imports. Remove any
`Any` import that becomes unused — ruff will flag it.

- [ ] **Step 6: Check the tools still serialise dates correctly**

The API expects a plain dict. Confirm the model reaches the request body as one:
`make_api_call` calls `validated_params.model_dump(exclude_none=True, mode="json")`
on the whole params model, which recurses into nested models, so `DateValue`
becomes a dict automatically. Verify this rather than trusting it:

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
from src.gramps_mcp.models.parameters.event_params import EventSaveParams
p = EventSaveParams(type='Birth', citation_list=[], date={'dateval': [12, 3, 1885, False]})
print(p.model_dump(exclude_none=True, mode='json'))
"
```

Expected: the `date` key holds a plain dict, not a `DateValue` repr. If it does not, stop and report — the serialisation assumption is wrong and the plan needs revising.

- [ ] **Step 7: Run the affected suites**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_date_params.py tests/test_parameter_alignment.py -q`
Expected: `test_date_params.py` passes. `tests/test_parameter_alignment.py` has three pre-existing failures about `media_path`; confirm you have not added a fourth.

- [ ] **Step 8: Commit**

```bash
rtk git add src/gramps_mcp/models/parameters/ tests/test_date_params.py
uv run git commit -m "feat: validate date structures that would break the XML export"
```

---

### Task 6: Refuse a place name where a handle is required

`event_params.py:61` declares `place: str | None` with no shape validation, and
`merge_put_data` replaces non-`_list` keys outright, so passing a place name
overwrites the event's valid place handle with text that resolves to nothing.
`CLAUDE.md` documents this trap.

**Files:**
- Modify: `src/gramps_mcp/models/parameters/event_params.py:61`
- Test: `tests/test_place_param_validation.py` (new)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `HANDLE_PATTERN` in `event_params.py`, importable by later work.

- [ ] **Step 1: Confirm what a real handle looks like**

Do not trust this plan's pattern without checking. Run:

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
async def m():
    c = GrampsWebAPIClient(); t = get_settings().gramps_tree_id
    places = await c.make_api_call(api_call=ApiCalls.GET_PLACES, params={'pagesize': 5}, tree_id=t)
    for p in places[:5]:
        h = p.get('handle', '')
        print(repr(h), len(h))
asyncio.run(m())
"
```

Record the observed lengths and character set in your report. The pattern below
assumes at least 16 alphanumeric characters. If real handles are shorter, or
contain other characters, adjust the pattern to match what you observed and say
so — a pattern that rejects real handles is worse than the bug it fixes.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_place_param_validation.py`:

```python
"""
Unit tests for the event place parameter. No server involved.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.event_params import EventSaveParams


class TestPlaceValidation:
    """place takes a handle, never a name."""

    def test_place_name_is_rejected(self):
        with pytest.raises(ValidationError):
            EventSaveParams(type="Birth", citation_list=[], place="Lyon")

    def test_place_name_with_spaces_is_rejected(self):
        with pytest.raises(ValidationError):
            EventSaveParams(type="Birth", citation_list=[], place="Saint-Germain")

    def test_handle_is_accepted(self):
        params = EventSaveParams(
            type="Birth", citation_list=[], place="103c4094f2414e2400974f979824"
        )

        assert params.place == "103c4094f2414e2400974f979824"

    def test_place_may_be_omitted(self):
        params = EventSaveParams(type="Birth", citation_list=[])

        assert params.place is None
```

If Step 1 showed handles in a different shape, replace the literal handle in
`test_handle_is_accepted` with a real one you observed.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_place_param_validation.py -v`
Expected: the two rejection tests FAIL — the name is currently accepted.

- [ ] **Step 4: Implement**

In `src/gramps_mcp/models/parameters/event_params.py`, add near the top, after
the imports:

```python
# Reason: a Gramps handle is a long alphanumeric string. Place names contain
# spaces, hyphens or accents, or are simply short, so this pattern separates
# them. Passing a name here used to overwrite a valid handle with text that
# resolves to nothing - the trap documented in CLAUDE.md.
HANDLE_PATTERN = r"^[0-9a-zA-Z]{16,}$"
```

Then change the field, which currently reads:

```python
    place: str | None = Field(None, description="Place handle where event occurred")
```

to:

```python
    place: str | None = Field(
        None,
        pattern=HANDLE_PATTERN,
        description=(
            "Place handle where the event occurred. This is a handle, not a "
            "name: use find_type(type='place', ...) to obtain one. Passing a "
            "name overwrites the event's existing place."
        ),
    )
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_place_param_validation.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 6: Check no existing test passed a name**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_data_management.py tests/test_complete_workflow.py -q`
Expected: no NEW failures. If a test now fails because it passed a place name, that test was relying on the broken behaviour — report it rather than loosening the pattern.

- [ ] **Step 7: Commit**

```bash
rtk git add src/gramps_mcp/models/parameters/event_params.py tests/test_place_param_validation.py
uv run git commit -m "fix: refuse a place name where a handle is required"
```

---

### Task 7: Align the place model with the API

This task has two halves, both in `place_params.py`, and produces **two**
commits — one per defect, as the lot's convention requires.

**Half B was added during execution**, after Task 2 showed that the list
replacement it had just delivered was awkward to use: moving a place through
`create_place_tool` also required resupplying `place_type`, because
`PUT_PLACE` and `POST_PLACES` share `PlaceSaveParams` and the field is
declared required. The repository owner approved folding it into this lot
rather than deferring it, on the grounds that it is the same class of defect
as half A — a Pydantic model that does not match what the API accepts.

#### Half B: `place_type` must not be required for a partial update

- [ ] **Step B1: Write the failing test**

Append to `tests/test_place_media.py`:

```python
class TestPartialPlaceUpdate:
    """A partial update must not demand fields it is not changing."""

    def test_place_type_is_optional(self):
        params = PlaceSaveParams(
            handle="103c4094f2414e2400974f979824",
            placeref_list=[{"ref": "103c732d2adc19424a3fad17954c"}],
        )

        assert params.place_type is None

    def test_creation_still_carries_a_type(self):
        params = PlaceSaveParams(name={"value": "Somewhere"}, place_type="City")

        assert params.place_type == "City"
```

- [ ] **Step B2: Run it to verify it fails**

Run: `uv run pytest tests/test_place_media.py::TestPartialPlaceUpdate -v`
Expected: `test_place_type_is_optional` FAILS — `place_type` is currently required.

- [ ] **Step B3: Implement**

In `src/gramps_mcp/models/parameters/place_params.py`, change:

```python
    place_type: str = Field(..., description="Place type")
```

to:

```python
    place_type: str | None = Field(
        None,
        description=(
            "Place type, for example City or Parish. Required when creating a "
            "place; omit it when updating one, so a partial update does not "
            "have to resupply it."
        ),
    )
```

- [ ] **Step B4: Check nothing relied on the field being required**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_place_media.py tests/test_place_move.py tests/test_data_management.py -q`
Expected: no NEW failures. `tests/test_place_move.py` currently passes `place_type` on its PUT calls to work around this very requirement; it should still pass, and the redundant argument may now be removed from its two PUT calls. Remove it and confirm the test still passes — that removal is the proof this half worked.

- [ ] **Step B5: Commit**

```bash
rtk git add src/gramps_mcp/models/parameters/place_params.py tests/test_place_media.py tests/test_place_move.py
uv run git commit -m "fix: stop requiring place_type on a partial place update"
```

#### Half A: the list types

`place_params.py:63` declares `media_list: list[str]` while the API expects
MediaRef objects, which is what `base_params.py:157` (`list[dict[str, Any]]`)
and `family_params.py:55` (`list[dict]`) already use. Attaching a photo to a
place is impossible in both directions: the correct dict shape is rejected by
Pydantic, the advertised string shape by Gramps. `alt_names: list[str]` at line
59 has the same mismatch, the API expecting PlaceName objects.

**Files:**
- Modify: `src/gramps_mcp/models/parameters/place_params.py:59,63`
- Test: `tests/test_place_media.py` (new)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: no new names.

- [ ] **Step 1: Write the failing test**

Create `tests/test_place_media.py`:

```python
"""
Integration test for attaching media to a place, against the real Gramps API.
"""

import uuid

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.parameters.place_params import PlaceSaveParams


class TestPlaceMedia:
    """A place must accept a media reference in the shape the API expects."""

    def test_model_accepts_media_ref_objects(self):
        params = PlaceSaveParams(
            name={"value": "Somewhere"},
            place_type="City",
            media_list=[{"ref": "103c4094f2414e2400974f979824"}],
        )

        assert params.media_list == [{"ref": "103c4094f2414e2400974f979824"}]

    @pytest.mark.asyncio
    async def test_media_can_be_attached_to_a_place(self):
        client = GrampsWebAPIClient()
        tree_id = get_settings().gramps_tree_id
        suffix = uuid.uuid4().hex[:8]
        place_handle = None
        media_handle = None

        try:
            # Reason: POST_MEDIA takes no JSON body (file upload only, see
            # api_mapping.py), so media objects are created via the
            # multipart upload endpoint, not make_api_call(POST_MEDIA, ...).
            upload_result = await client.upload_media_file(
                file_content=f"pytest media {suffix}".encode(),
                mime_type="text/plain",
                tree_id=tree_id,
            )
            media_handle = upload_result[0]["new"]["handle"]

            created = await client.make_api_call(
                api_call=ApiCalls.POST_PLACES,
                params={
                    "name": {"value": f"PytestPlace{suffix}"},
                    "place_type": "City",
                    "media_list": [{"ref": media_handle}],
                },
                tree_id=tree_id,
            )
            place_handle = created[0]["new"]["handle"]

            fetched = await client.make_api_call(
                api_call=ApiCalls.GET_PLACE, tree_id=tree_id, handle=place_handle
            )
            refs = [entry.get("ref") for entry in fetched.get("media_list", [])]

            assert media_handle in refs
        finally:
            if place_handle:
                await client.make_api_call(
                    api_call=ApiCalls.DELETE_PLACE, tree_id=tree_id, handle=place_handle
                )
            if media_handle:
                await client.make_api_call(
                    api_call=ApiCalls.DELETE_MEDIA_ITEM,
                    tree_id=tree_id,
                    handle=media_handle,
                )
```

Media objects are created via `client.upload_media_file` (multipart upload),
not `make_api_call(ApiCalls.POST_MEDIA, ...)` — `POST_MEDIA` takes no JSON
body, it is upload-only. Clean up with `ApiCalls.DELETE_MEDIA_ITEM` (not
`DELETE_MEDIA` — that enum member does not exist). Confirm the enum names
first with `grep -nE "DELETE_MEDIA_ITEM|POST_PLACES|GET_PLACE|DELETE_PLACE" src/gramps_mcp/models/api_calls.py`,
and use the real ones.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_place_media.py -v`
Expected: `test_model_accepts_media_ref_objects` FAILS with a Pydantic error, because `media_list` currently demands strings.

- [ ] **Step 3: Implement**

In `src/gramps_mcp/models/parameters/place_params.py`, change:

```python
    alt_names: list[str] | None = Field(None, description="Alternative names")
```

to:

```python
    alt_names: list[dict[str, Any]] | None = Field(
        None,
        description="Alternative names as PlaceName objects, for example [{'value': 'Lugdunum'}]",
    )
```

and:

```python
    media_list: list[str] | None = Field(None, description="List of media handles")
```

to:

```python
    media_list: list[dict[str, Any]] | None = Field(
        None,
        description="Media references as objects, for example [{'ref': '<handle>'}]",
    )
```

Add `from typing import Any` to the imports if it is not already there.

- [ ] **Step 4: Run the tests**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_place_media.py -v`
Expected: PASS, 2 tests.

- [ ] **Step 5: Verify the tree is clean**

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.tools.search_basic import find_anything_tool
print(asyncio.run(find_anything_tool({'query': 'Pytest'}))[0].text[:400])
"
```

Expected: no `Pytest*` object remains.

- [ ] **Step 6: Commit**

```bash
rtk git add src/gramps_mcp/models/parameters/place_params.py tests/test_place_media.py
uv run git commit -m "fix: align place media_list and alt_names with the API"
```

---

### Task 8: Verification and pull request

- [ ] **Step 1: Run the whole suite**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest -q`
Expected: the new test files pass. Categorise every failure as new-from-this-branch or pre-existing, and check rather than assume — `git show main:<path>` reads a file as it is on main without switching branches. Do not check out main and do not stash. A regression reported as pre-existing is the worst possible outcome of this task.

Known pre-existing failures, not yours: three in `tests/test_server.py` (one asserting `result.serverInfo`, renamed to `server_info` in MCP SDK 2.x; two comparing the tool count against a stale running container), plus failures in `test_analysis.py`, `test_data_management.py`, `test_parameter_alignment.py` and `test_search_basic.py` concerning `media_path`, live-tree state, and an account permission gap on `tree_stats`.

Pay particular attention to failures caused by this lot's deliberate tightening: a test that passed a place name, or a malformed range date, now fails by design. Report any such test rather than loosening the validation.

- [ ] **Step 2: Type check**

Run: `uv run mypy src/gramps_mcp --ignore-missing-imports`
Expected: no new errors in the files this branch touched.

- [ ] **Step 3: Lint and format**

Run: `uv run ruff format src/gramps_mcp tests && uv run ruff check src/gramps_mcp tests`
Expected: all checks pass.

- [ ] **Step 4: Confirm the tree is clean**

```bash
GRAMPS_API_URL=http://localhost:80 uv run python -c "
import asyncio
from src.gramps_mcp.tools.search_basic import find_anything_tool
print(asyncio.run(find_anything_tool({'query': 'Pytest'}))[0].text[:800])
"
```

Expected: no `Pytest*` object remains. If any does, remove it and say so.

- [ ] **Step 5: Commit any formatting changes**

```bash
rtk git add -A
uv run git commit -m "chore: format and lint quality lot 2"
```

Skip this step if ruff changed nothing. Do not create an empty commit.

- [ ] **Step 6: Push and open the pull request**

```bash
rtk git push -u origin fix/quality-lot2-data-fidelity
rtk gh pr create --repo fjacquet/gramps-mcp --title "fix: quality lot 2 - data fidelity" --body "$(cat <<'BODY'
Fixes seven defects that let the server store or display the wrong thing without raising an error.

- `merge_put_data` can now replace a named list instead of only adding to it, so a place can be moved to a new parent rather than gaining a second one. Union stays the default.
- Dicts without a `ref` deduplicate on their content, so `attribute_list` no longer accumulates a copy per update.
- Range, span and free-text dates render their real content instead of dropping the second endpoint or showing "date unknown".
- A new `DateValue` model refuses a range or span that carries only one date - the structure that saves cleanly and later crashes the XML export.
- The event `place` parameter refuses a place name, which used to overwrite a valid handle silently.
- `place_params` declares media and alternative names in the shape the API actually accepts.
- `place_type` is no longer required for a partial update, so moving a place via `placeref_list` no longer forces the caller to resupply it.

Behaviour change: calls that relied on the permissive validation now fail loudly. That is the point, but it is a break.

Spec: `docs/superpowers/specs/2026-08-13-quality-lot2-data-fidelity-design.md`

Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01PAZLxVasEXVDbriMRvGmDE
BODY
)"
```

**Do not merge the pull request and do not tag a release.** Both are the repository owner's decision.

---

## Self-Review

**Spec coverage:** All seven defects in the spec's scope table have a task — list replacement (Tasks 1 and 2, split because the pure function and its plumbing are separately reviewable), attribute duplication (Task 3), date rendering (Task 4), date validation (Task 5), place validation (Task 6), place list types and the optional `place_type` (Task 7, halves A and B). The spec's testing table maps onto Tasks 1 to 7; its accepted-risk section about deliberately breaking permissive calls is surfaced in Task 8 Step 1.

**Placeholders:** None. Every code step shows the before and after text. Four steps ask the implementer to verify a real value — the handle shape, the enum names, the serialisation behaviour, the attribute comparison method — before trusting this document, and each says what to do if the observation differs.

**Type consistency:** `merge_put_data(existing, changes, replace_lists=None)` is defined in Task 1 and called with that third argument in Task 2. `make_api_call`'s new `replace_lists` keyword is added in Task 2 and used by Task 2's test only. `DateValue` is defined in Task 5 and applied within the same task. `HANDLE_PATTERN` is introduced in Task 6 and used only there. `_format_single_date(day, month, year)` is introduced and consumed inside Task 4.

**Ordering note:** Tasks 1 and 2 must run in that order. Tasks 3 to 7 are independent of each other and of 1 and 2, and may be reordered.
