# PUT Merge Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `merge_put_data` preserve everything a partial update did not mention, at every depth, so a PUT can no longer silently destroy or discard genealogy data.

**Architecture:** `merge_put_data` currently reasons only about top-level keys and dispatches on the key's *name* (`endswith("_list")`). Three changes fix six confirmed defects: dispatch on the value's *type* so `urls` and `alt_names` merge like any other list; recurse into dict-valued keys so a partial `primary_name` keeps the sub-keys it did not mention; and deduplicate ref-carrying dicts on whole content rather than on `ref` alone, so a role change is applied instead of discarded. All of it is pure logic in one 155-line module - no server, no transport, no async.

**Nested lists replace, they do not union.** This is a deliberate decision, not an oversight. Top-level reference lists (`media_list`, `citation_list`, `event_ref_list`) are *associative* - the caller is adding a link, so union is right. A list nested inside a descriptive object (`primary_name.surname_list`) is *stated* - the caller is declaring what the name is. Unioning it would make correcting a surname impossible: fixing "Smith" to "Smith-Jones" would yield both. `tests/test_client_merge.py:138` already encodes that intent and must keep passing. The cost is that a caller who omits a second surname loses it; Task 5 documents that a `surname_list` resend states the whole list.

**Tech Stack:** Python 3.13, pytest, `uv` for all execution. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-26-mcp-audit-design.md` (finding A)

## Global Constraints

- Run everything through `uv`: `uv run pytest`, `uv run git commit`.
- TDD is mandatory: write the test, watch it fail, then implement. Never write implementation first.
- Tests live in `tests/test_client_merge.py` (288 lines today) and must stay under 500 lines. If the file would exceed it, create `tests/test_merge_nested.py` and put the new classes there.
- `src/gramps_mcp/merge.py` is 155 lines; the limit is 500.
- Google-style docstrings on every function. `# Reason:` comments explain *why*, not *what*. No emojis anywhere.
- `uv run ruff format src tests` and `uv run ruff check src tests` must pass before each commit; pre-commit runs them anyway.
- Never run a test that writes to the live Gramps server. The full offline suite is `uv run pytest -m "not integration" -q` and is green at 289 passed.
- Do not change `_merge_list`'s existing string-dedup or attribute-dict-dedup behaviour; those are correct and covered by existing tests.

---

### Task 1: Merge lists by value type, not key name

Writable list fields whose name does not end in `_list` - `urls` on
`PersonData`, `FamilySaveParams`, `PlaceSaveParams`, `RepositoryData`, and
`alt_names` on `PlaceSaveParams` - currently take the replace branch and
destroy existing entries.

**Files:**
- Modify: `src/gramps_mcp/merge.py:55-63`
- Test: `tests/test_client_merge.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `merge_put_data(existing: dict, changes: dict, replace_lists: list[str] | None = None) -> dict` - unchanged signature; only the list-detection rule changes.

- [ ] **Step 1: Write the failing tests**

First add the import at the top of `tests/test_client_merge.py`, beside the
existing `from src.gramps_mcp.client import GrampsWebAPIClient`:

```python
from src.gramps_mcp.merge import merge_put_data
```

The existing tests in this file drive the merge through the client with a
mocked transport. The new tests call the pure function directly - it takes no
client and does no I/O, so the extra machinery would only obscure them.

Then add, inside `class TestClientMergeLogic`:

```python
    def test_urls_merge_instead_of_replacing(self):
        # Reason: urls is a declared writable list on person, family, place
        # and repository, but its name does not end in _list. Dispatching on
        # the name rather than the value replaced it, destroying every URL
        # the caller did not resend.
        existing = {"urls": [{"path": "https://a.example", "desc": "A"}]}
        changes = {"urls": [{"path": "https://b.example", "desc": "B"}]}
        result = merge_put_data(existing, changes)
        assert result["urls"] == [
            {"path": "https://a.example", "desc": "A"},
            {"path": "https://b.example", "desc": "B"},
        ]

    def test_alt_names_merge_instead_of_replacing(self):
        existing = {"alt_names": [{"value": "Lugdunum"}, {"value": "Lyon"}]}
        changes = {"alt_names": [{"value": "Lyons"}]}
        result = merge_put_data(existing, changes)
        assert result["alt_names"] == [
            {"value": "Lugdunum"},
            {"value": "Lyon"},
            {"value": "Lyons"},
        ]

    def test_replace_lists_still_wins_for_a_non_list_suffixed_key(self):
        existing = {"urls": [{"path": "https://a.example"}]}
        changes = {"urls": [{"path": "https://b.example"}]}
        result = merge_put_data(existing, changes, replace_lists=["urls"])
        assert result["urls"] == [{"path": "https://b.example"}]

    def test_a_non_list_value_still_replaces(self):
        # Reason: widening the rule must not turn scalar replacement into
        # anything else - a changed surname must overwrite the old one.
        existing = {"gender": 1, "gramps_id": "I0001"}
        changes = {"gender": 0}
        result = merge_put_data(existing, changes)
        assert result["gender"] == 0
        assert result["gramps_id"] == "I0001"

    def test_a_list_absent_from_existing_is_taken_as_is(self):
        existing = {"gramps_id": "I0001"}
        changes = {"urls": [{"path": "https://a.example"}]}
        result = merge_put_data(existing, changes)
        assert result["urls"] == [{"path": "https://a.example"}]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_client_merge.py -q -k "urls or alt_names or non_list"`

Expected: `test_urls_merge_instead_of_replacing` and
`test_alt_names_merge_instead_of_replacing` FAIL with the new list replacing
the old one. The other three PASS already - they are guards proving the change
does not break replacement, not new behaviour. That is expected and correct;
do not "fix" them.

- [ ] **Step 3: Change the dispatch rule**

In `src/gramps_mcp/merge.py`, replace the condition at lines 55-63:

```python
        # Reason: dispatch on the value being a list, not on the key's name.
        # urls and alt_names are writable lists whose names do not end in
        # _list; keying off the suffix sent them down the replace branch and
        # destroyed entries the caller never mentioned.
        if (
            isinstance(value, list)
            and isinstance(existing.get(key), list)
            and key not in replace
        ):
            merged[key] = _merge_list(existing.get(key, []), value)
        else:
            merged[key] = value
```

Update the docstring at lines 32-35 to match:

```python
    Keys whose value is a list and whose existing value is also a list are
    merged with deduplication; every other key in changes replaces the
    existing value. Neither input is mutated.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_client_merge.py -q`

Expected: all pass, including the pre-existing tests.

- [ ] **Step 5: Run the full offline suite**

Run: `uv run pytest -m "not integration" -q`

Expected: 294 passed (289 before, 5 added).

- [ ] **Step 6: Commit**

```bash
uv run git add src/gramps_mcp/merge.py tests/test_client_merge.py
uv run git commit -m "fix: merge lists by value type, not key name

urls and alt_names are declared writable lists whose names do not end in
_list, so the suffix-based dispatch sent them down the replace branch. A
place with three alternate names lost all three when a fourth was added,
and the call reported success. Dispatch now tests the value."
```

---

### Task 2: Recurse into nested dicts

A partial `primary_name` currently replaces the whole name object. Because
`PersonData.primary_name` is required, it is resent on every person update -
including updates that have nothing to do with the name.

**Files:**
- Modify: `src/gramps_mcp/merge.py` (the `else` branch from Task 1)
- Test: `tests/test_client_merge.py`

**Interfaces:**
- Consumes: `merge_put_data` as modified by Task 1.
- Produces: `_merge_dict(existing_value: dict, new_value: dict) -> dict` - a new private helper in `merge.py`, recursive, mutating neither argument.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_client_merge.py`:

```python
    def test_partial_primary_name_keeps_the_sub_keys_it_omits(self):
        # Reason: primary_name is required on PersonData, so every person
        # update resends it. Replacing it wholesale destroyed 13 of the 15
        # sub-keys every person in the live tree carries.
        existing = {
            "primary_name": {
                "first_name": "Jean-Pierre",
                "surname_list": [{"surname": "Jacquet"}],
                "suffix": "Jr",
                "call": "JP",
                "type": "Birth Name",
            }
        }
        changes = {"primary_name": {"first_name": "Jean"}}
        result = merge_put_data(existing, changes)
        assert result["primary_name"] == {
            "first_name": "Jean",
            "surname_list": [{"surname": "Jacquet"}],
            "suffix": "Jr",
            "call": "JP",
            "type": "Birth Name",
        }

    def test_a_stated_nested_list_replaces_so_a_surname_can_be_corrected(self):
        # Reason: a list nested inside a descriptive object is stated, not
        # appended to. Unioning it would make correcting a surname
        # impossible - fixing Smith to Smith-Jones would yield both.
        existing = {"primary_name": {"surname_list": [{"surname": "Smith"}]}}
        changes = {"primary_name": {"surname_list": [{"surname": "Smith-Jones"}]}}
        result = merge_put_data(existing, changes)
        assert result["primary_name"]["surname_list"] == [{"surname": "Smith-Jones"}]

    def test_an_unmentioned_nested_list_is_kept(self):
        # Reason: replacement applies only to a list the caller stated. A
        # nested list they never mentioned must survive like any sub-key.
        existing = {
            "primary_name": {
                "first_name": "Jean",
                "surname_list": [{"surname": "Jacquet"}],
                "citation_list": ["c1"],
            }
        }
        changes = {"primary_name": {"first_name": "Pierre"}}
        result = merge_put_data(existing, changes)
        assert result["primary_name"]["surname_list"] == [{"surname": "Jacquet"}]
        assert result["primary_name"]["citation_list"] == ["c1"]

    def test_a_partial_place_name_keeps_lang_and_date(self):
        existing = {"name": {"value": "Lyon", "lang": "fr", "date": {"year": 1800}}}
        changes = {"name": {"value": "Lugdunum"}}
        result = merge_put_data(existing, changes)
        assert result["name"] == {
            "value": "Lugdunum",
            "lang": "fr",
            "date": {"year": 1800},
        }

    def test_a_dict_absent_from_existing_is_taken_as_is(self):
        existing = {"gramps_id": "I0001"}
        changes = {"primary_name": {"first_name": "Jean"}}
        result = merge_put_data(existing, changes)
        assert result["primary_name"] == {"first_name": "Jean"}

    def test_a_dict_replacing_a_scalar_is_taken_as_is(self):
        # Reason: type mismatch between existing and new means the record
        # shape changed; merging two incompatible types would invent data.
        existing = {"name": "Lyon"}
        changes = {"name": {"value": "Lyon", "lang": "fr"}}
        result = merge_put_data(existing, changes)
        assert result["name"] == {"value": "Lyon", "lang": "fr"}

    def test_neither_input_is_mutated_by_a_nested_merge(self):
        existing = {"primary_name": {"first_name": "Jean", "suffix": "Jr"}}
        changes = {"primary_name": {"first_name": "Pierre"}}
        merge_put_data(existing, changes)
        assert existing == {"primary_name": {"first_name": "Jean", "suffix": "Jr"}}
        assert changes == {"primary_name": {"first_name": "Pierre"}}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_client_merge.py -q -k "primary_name or place_name or nested or dict_absent or dict_replacing or mutated or corrected"`

Expected: `test_partial_primary_name_keeps_the_sub_keys_it_omits`,
`test_an_unmentioned_nested_list_is_kept` and
`test_a_partial_place_name_keeps_lang_and_date` FAIL - the nested dict is
replaced wholesale. The rest PASS as guards, including
`test_a_stated_nested_list_replaces_so_a_surname_can_be_corrected`, which
must still pass after the change.

- [ ] **Step 3: Add the recursive helper**

Add to `src/gramps_mcp/merge.py`, after `merge_put_data`:

```python
def _merge_dict(existing_value: dict, new_value: dict) -> dict:
    """
    Merge a nested object, preserving sub-keys the caller did not mention.

    Applies the same rules as merge_put_data one level down, recursively:
    a list merges with the existing list, a dict merges with the existing
    dict, and anything else replaces. Neither input is mutated.

    Args:
        existing_value (dict): The nested object currently stored in Gramps.
        new_value (dict): The sub-keys the caller wants to change.

    Returns:
        dict: A new dict containing the merged object.
    """
    merged = existing_value.copy()
    for key, value in new_value.items():
        current = existing_value.get(key)
        # Reason: a nested dict merges, but a nested LIST replaces. A list
        # inside a descriptive object is stated, not appended to - unioning
        # surname_list would make correcting a surname impossible, yielding
        # both the old and the new. Only unmentioned sub-keys are preserved.
        if isinstance(value, dict) and isinstance(current, dict):
            merged[key] = _merge_dict(current, value)
        else:
            merged[key] = value
    return merged
```

Note the docstring above must match: replace "a list merges with the existing
list, a dict merges with the existing dict, and anything else replaces" with:

```python
    Applies one rule one level down, recursively: a nested dict merges with
    the existing dict, and everything else - including a nested list -
    replaces. Sub-keys the caller does not mention are always preserved.
```

- [ ] **Step 4: Route dict values through it**

In `merge_put_data`, extend the branch from Task 1:

```python
        if (
            isinstance(value, list)
            and isinstance(existing.get(key), list)
            and key not in replace
        ):
            merged[key] = _merge_list(existing.get(key, []), value)
        # Reason: primary_name is required on PersonData, so it is resent on
        # every person update - including ones that have nothing to do with
        # the name. Replacing it wholesale destroyed surname_list, suffix,
        # type and the name's own citations. replace_lists is honoured here
        # too, so an explicit replacement is still available per key.
        elif (
            isinstance(value, dict)
            and isinstance(existing.get(key), dict)
            and key not in replace
        ):
            merged[key] = _merge_dict(existing[key], value)
        else:
            merged[key] = value
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_client_merge.py -q`

Expected: all pass.

- [ ] **Step 6: Run the full offline suite**

Run: `uv run pytest -m "not integration" -q`

Expected: 301 passed.

- [ ] **Step 7: Commit**

```bash
uv run git add src/gramps_mcp/merge.py tests/test_client_merge.py
uv run git commit -m "fix: merge nested objects instead of replacing them

primary_name is required on PersonData, so every person update resends
it. Replacing it wholesale destroyed 13 of the 15 sub-keys every person
in the live tree carries - surname_list, suffix, type, and the name's own
citation and note lists - while reporting success. The same shape applied
to a place's name object."
```

---

### Task 3: Stop discarding a changed role

`_merge_list` deduplicates ref-carrying dicts on `ref` alone, so an entry
whose `ref` matches an existing one but whose `role`, `rel` or `rect` differs
is dropped. The tool reports success and nothing changed.

**Files:**
- Modify: `src/gramps_mcp/merge.py` (the ref branch of `_merge_list`)
- Test: `tests/test_client_merge.py`

**Interfaces:**
- Consumes: `_merge_list` as it exists today.
- Produces: no new public names; `_merge_list`'s ref branch changes behaviour only for entries whose non-`ref` content differs.

- [ ] **Step 1: Write the failing tests**

```python
    def test_a_changed_role_on_the_same_event_is_applied(self):
        # Reason: deduplicating on ref alone silently discarded the change
        # and reported success. Recording someone as a witness on an event
        # where they already appear in another role is routine.
        existing = {"event_ref_list": [{"ref": "ev1", "role": "Primary"}]}
        changes = {"event_ref_list": [{"ref": "ev1", "role": "Witness"}]}
        result = merge_put_data(existing, changes)
        assert result["event_ref_list"] == [
            {"ref": "ev1", "role": "Primary"},
            {"ref": "ev1", "role": "Witness"},
        ]

    def test_an_identical_ref_entry_is_still_deduplicated(self):
        existing = {"event_ref_list": [{"ref": "ev1", "role": "Primary"}]}
        changes = {"event_ref_list": [{"ref": "ev1", "role": "Primary"}]}
        result = merge_put_data(existing, changes)
        assert result["event_ref_list"] == [{"ref": "ev1", "role": "Primary"}]

    def test_the_same_photo_in_two_regions_is_kept_twice(self):
        existing = {"media_list": [{"ref": "m1", "rect": [0, 0, 10, 10]}]}
        changes = {"media_list": [{"ref": "m1", "rect": [50, 50, 60, 60]}]}
        result = merge_put_data(existing, changes)
        assert result["media_list"] == [
            {"ref": "m1", "rect": [0, 0, 10, 10]},
            {"ref": "m1", "rect": [50, 50, 60, 60]},
        ]

    def test_a_bare_ref_addition_still_deduplicates(self):
        existing = {"citation_list": [{"ref": "c1"}]}
        changes = {"citation_list": [{"ref": "c1"}, {"ref": "c2"}]}
        result = merge_put_data(existing, changes)
        assert result["citation_list"] == [{"ref": "c1"}, {"ref": "c2"}]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_client_merge.py -q -k "role or photo or bare_ref or identical_ref"`

Expected: `test_a_changed_role_on_the_same_event_is_applied` and
`test_the_same_photo_in_two_regions_is_kept_twice` FAIL - the new entry is
dropped. The other two PASS as guards.

- [ ] **Step 3: Deduplicate on whole content**

In `src/gramps_mcp/merge.py`, replace the ref branch of `_merge_list`:

```python
    if (
        isinstance(sample_existing, dict)
        and "ref" in sample_existing
        and isinstance(sample_new, dict)
        and "ref" in sample_new
    ):
        # Reason: deduplicating on ref alone discarded a genuine change and
        # reported success - the same person on the same event in a second
        # role, or the same photo cropped to a second face. Two entries are
        # the same entry only when everything about them matches.
        existing_keys = {_entry_key(item) for item in existing_items}
        additions = [
            item for item in new_items if _entry_key(item) not in existing_keys
        ]
        return existing_items + additions
```

Add the helper below `_merge_list`:

```python
def _entry_key(item) -> str:
    """
    Build a stable identity for a reference-list entry.

    Args:
        item: One element of a reference list, normally a dict.

    Returns:
        str: A key equal for two entries exactly when their whole content
        matches, so a differing role, rel or rect counts as a new entry.
    """
    # Reason: sort_keys makes the key independent of dict ordering, and
    # default=str keeps a non-serialisable value from raising here - an
    # unmergeable entry should fall through as distinct, not crash a write.
    return json.dumps(item, sort_keys=True, default=str)
```

Add `import json` at the top of the module, below the module docstring.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_client_merge.py -q`

Expected: all pass.

- [ ] **Step 5: Run the full offline suite**

Run: `uv run pytest -m "not integration" -q`

Expected: 305 passed.

- [ ] **Step 6: Commit**

```bash
uv run git add src/gramps_mcp/merge.py tests/test_client_merge.py
uv run git commit -m "fix: treat a changed role as a new reference entry

_merge_list deduplicated ref-carrying dicts on ref alone, so adding
someone as a witness to an event where they already appear as primary was
dropped as a duplicate while the tool reported success. The same applied
to one photo attached twice with two different crop regions."
```

---

### Task 4: Verify the fix against the live tree, read-only

The three tasks above are pure logic proven offline. This task confirms the
merged result matches what the live server actually stores, without writing
to it.

**Files:**
- Create: `tests/test_merge_live_shapes.py`

**Interfaces:**
- Consumes: `merge_put_data` as modified by Tasks 1-3.
- Produces: nothing later tasks rely on.

- [ ] **Step 1: Write the test**

```python
"""
Check merge_put_data against the shapes the live Gramps server returns.

The offline merge tests use hand-written records. This module fetches a
real person and a real place and asserts that a partial update of the
shape the usage guide tells the assistant to send preserves everything
the server actually stores. Read-only: it issues GETs and never writes.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.merge import merge_put_data
from src.gramps_mcp.models.api_calls import ApiCalls

pytestmark = pytest.mark.integration


class TestMergeAgainstLiveShapes:
    async def test_a_partial_name_update_preserves_every_stored_sub_key(self):
        client = GrampsWebAPIClient()
        people = await client.make_api_call(
            api_call=ApiCalls.GET_PEOPLE, params={"pagesize": 1, "page": 1}
        )
        stored = people[0]
        assert stored.get("primary_name"), "fixture person has no primary_name"

        merged = merge_put_data(
            stored, {"primary_name": {"first_name": "TestFirstName"}}
        )

        assert merged["primary_name"]["first_name"] == "TestFirstName"
        for key, value in stored["primary_name"].items():
            if key == "first_name":
                continue
            assert merged["primary_name"][key] == value, (
                f"sub-key {key} was lost by a partial update"
            )

    async def test_a_partial_place_name_update_preserves_lang_and_date(self):
        client = GrampsWebAPIClient()
        places = await client.make_api_call(
            api_call=ApiCalls.GET_PLACES, params={"pagesize": 1, "page": 1}
        )
        stored = places[0]
        if not isinstance(stored.get("name"), dict):
            pytest.skip("fixture place has no structured name object")

        merged = merge_put_data(stored, {"name": {"value": "TestPlaceName"}})

        assert merged["name"]["value"] == "TestPlaceName"
        for key, value in stored["name"].items():
            if key == "value":
                continue
            assert merged["name"][key] == value, f"sub-key {key} was lost"
```

- [ ] **Step 2: Run it and watch it pass**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_merge_live_shapes.py -q`

Expected: 2 passed. If it fails, the live record carries a shape the offline
tests did not model - read the assertion message, add the missing case to
`tests/test_client_merge.py` as a failing offline test, and fix `merge.py`
before continuing.

Note: the `GRAMPS_API_URL` override is required from the macOS host because
`.env` points at `host.docker.internal`, which only resolves inside the
container. Do not edit `.env` and do not commit the override.

- [ ] **Step 3: Confirm the module is excluded from the offline selection**

Run: `uv run pytest -m "not integration" -q --collect-only | tail -3`

Expected: `tests/test_merge_live_shapes.py` does not appear. The
`pytestmark = pytest.mark.integration` at module level handles this.

- [ ] **Step 4: Commit**

```bash
uv run git add tests/test_merge_live_shapes.py
uv run git commit -m "test: check merge against the shapes the live server stores

The offline merge tests use hand-written records. This asserts that a
partial update of the shape the usage guide tells the assistant to send
preserves every sub-key a real person and a real place actually carry.
Read-only - GETs only, marked integration."
```

---

### Task 5: Document the merge contract where callers read it

The behaviour changed. `resources/gramps-usage-guide.md` is served to MCP
clients, so it is what the assistant reads before composing an update.

**Files:**
- Modify: `src/gramps_mcp/resources/gramps-usage-guide.md`
- Modify: `docs/user-guide/gotchas.md`

**Interfaces:**
- Consumes: the behaviour established by Tasks 1-3.
- Produces: nothing later tasks rely on.

- [ ] **Step 1: Check whether an alignment test constrains the guide**

Run: `uv run pytest tests/test_alignment_*.py -q`

Expected: passes before your edit. These modules hold hardcoded field
inventories that must track the guide; if your edit adds a *field name*, they
will fail and must be updated in the same commit. Adding prose does not
trigger them.

- [ ] **Step 2: Add the merge contract to the usage guide**

In `src/gramps_mcp/resources/gramps-usage-guide.md`, immediately after the
"If entity exists but **missing some of the new info**" bullet near the top:

```markdown
**What an update preserves.** A `create_X` call carrying a handle is an
update, and it merges rather than overwrites: any field you do not mention is
kept, lists you supply are added to the existing ones, and a nested object
such as `primary_name` merges sub-key by sub-key. So sending
`primary_name={"first_name": "Jean"}` changes the first name and leaves the
surname, suffix and name type alone.

Two consequences worth knowing:

- **Adding an entry to a list never removes one.** To remove one, use
  `detach_reference`. Supplying an empty list does nothing.
- **A reference repeated with different details is a new entry, not a
  duplicate.** The same person on one event as both Primary and Witness, or
  one photo cropped to two different faces, are two entries and both are
  kept.
```

- [ ] **Step 3: Record the change in the gotchas page**

In `docs/user-guide/gotchas.md`, add:

```markdown
## Partial updates merge, including inside nested objects

Before 2026-08-26, `merge_put_data` reasoned only about top-level keys whose
name ended in `_list`. A partial `primary_name` replaced the whole name
object, `urls` and `alt_names` were replaced outright, and a reference whose
`ref` already existed was dropped even when its role differed. All three are
fixed: dispatch is by value type, nested dicts merge recursively, and
reference entries are compared on their whole content.

If you need the old replace-outright behaviour for a specific key, pass it in
`replace_lists` - which now covers nested objects as well as lists.
```

- [ ] **Step 4: Verify the docs build**

Run: `uv run --with mkdocs-material mkdocs build --strict`

Expected: builds with no warnings. Strict mode fails on broken internal
links, which is the usual way a docs change breaks the published site.

- [ ] **Step 5: Run the alignment tests and the full offline suite**

Run: `uv run pytest -m "not integration" -q`

Expected: 305 passed.

- [ ] **Step 6: Commit**

```bash
uv run git add src/gramps_mcp/resources/gramps-usage-guide.md docs/user-guide/gotchas.md
uv run git commit -m "docs: state what a partial update preserves

The usage guide is served to MCP clients, so it is what the assistant
reads before composing an update. It never said whether an update merges
or overwrites - which is why partial primary_name resends were being
composed at all."
```

---

## Self-Review

**Spec coverage.** Finding A lists seven reproduced defects. Task 1 closes
`urls` and `alt_names`. Task 2 closes partial `primary_name` and the
partial place `name`. Task 3 closes the discarded role
change. The nested `surname_list` case from the spec is deliberately **not** closed
by union: see the Architecture note - unioning it would make correcting a
surname impossible, and the decision is to have a stated nested list replace,
with Task 5 documenting that a resend states the whole list.

The seventh - `tag_list` cannot be emptied - is deliberately **not**
scheduled: the spec records it as a design question rather than a bug, its
answer depends on `replace_lists`' fate (finding D, workstream 2), and
changing empty-list semantics without that decision would make the same
mistake twice. Task 5 documents the boundary so the gap is visible to callers.

**Placeholders.** None. Every code step carries the actual code; every run
step carries the actual command and its expected output.

**Type consistency.** `merge_put_data` keeps its signature throughout.
`_merge_dict(existing_value: dict, new_value: dict) -> dict` is defined in
Task 2 and used only there. `_entry_key(item) -> str` is defined in Task 3 and
used only in `_merge_list`. `_merge_list` keeps its signature; Task 2 calls it
from `_merge_dict`, which is why Task 2 must land after Task 1's rule change
and not before.

**One risk worth naming.** Tasks 1 and 2 make updates preserve *more* than
before. Any caller that relied on replacement to clear a field will now find
the field kept. Nothing in `tools/` does this today - `detach_reference` is
the removal path and operates through `replace_lists` - but it is the change's
one behavioural sharp edge, which is why Task 5 states it in the guide rather
than leaving it to be discovered.
