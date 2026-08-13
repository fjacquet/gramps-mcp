# Quality Lot 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the order dependence and the 500-line breaches from the test suite, and give the media upload the shared request path's error handling.

**Architecture:** A `tests/conftest.py` creates real Gramps records as module-scoped pytest fixtures and deletes them on teardown, replacing a chain of module-level globals. Once no test depends on another's leftovers, three oversized test modules split cleanly, and the file-length hook can stop exempting `tests/`. Separately, `_make_request` gains an optional `content` parameter so `upload_media_file` can route through it instead of duplicating a subset of its error handling.

**Tech Stack:** Python 3.12+, pytest with `pytest-asyncio` (mode=auto), httpx, pydantic, uv, pre-commit.

## Global Constraints

- Never create a file longer than 500 lines.
- Test against the real Gramps API. No fixtures, test clients or stubbed responses standing in for the server. Replacing the transport seam alone is permitted in offline unit tests; assertions must read the output of the code under test, never the stub's call arguments.
- No emojis anywhere. A pre-commit hook enforces this.
- Google-style docstrings on every function.
- Add an inline `# Reason:` comment when logic is non-obvious.
- Use `uv run` for every command. Commit with `uv run git commit` so pre-commit hooks fire.
- **Never use `git stash`.** Compare against `main` with `git show main:<path>`.
- Live tests need `GRAMPS_API_URL=http://localhost:80` as an env override from the macOS host. Do not edit `.env`, do not commit the override.
- `tree_stats` returns a permission error regardless of role. That is an environment fact, not a regression.
- Every fix passes a revert-check before its commit: remove the fix, run the test, confirm it fails, restore, confirm it passes. Revert each independent half separately. Record both observations in the report.

## Two branches

Tasks 1 to 7 land on `fix/quality-lot5a-test-structure`. Task 8 lands on `fix/quality-lot5b-upload-request-path`, cut from `main` after 5a merges. One pull request each, merged with a merge commit, never squashed.

## Ordering correction to the spec

The spec says to remove the hook's `tests/` exclusion first, so the hook forces the splits. That does not work: the hook checks staged `.py` files, so with the exclusion removed, **every commit that touches `test_data_management.py` fails until the file is already under 500 lines** - including the commits that do the splitting. The hook change therefore lands last, in Task 6.

The spec also says the chain of globals lives entirely in the sourcing classes. It does not. The real graph is:

```
Note -> Repository -> Source -> Citation -> Event -> Person -> Family
Media -----------------------------^        ^
Place --------------------------------------|
```

Eight of the ten classes participate. Splitting by domain cuts the chain across files, so **the chain must die before the split**, not after. Task 2 precedes Task 3 for that reason.

## File structure

| File | Responsibility |
|---|---|
| `tests/conftest.py` (new) | Module-scoped fixtures creating real records, with teardown |
| `tests/test_create_sourcing.py` (new) | Repository, source, citation, sourced-event creation |
| `tests/test_create_people.py` (new) | Person and family creation |
| `tests/test_create_records.py` (new) | Note, media, place, event creation |
| `tests/test_data_management.py` (deleted) | Split into the three above |
| `tests/test_alignment_sourcing.py` (new) | Repository, source, citation, media alignment |
| `tests/test_alignment_records.py` (new) | Event, person, family, place, note alignment |
| `tests/test_alignment_simple_params.py` (new) | Simple-params and reference-validation checks |
| `tests/test_parameter_alignment.py` (deleted) | Split into the three above |
| `tests/test_workflow_marriage.py` (new) | The marriage-record and place-hierarchy workflows |
| `tests/test_workflow_attributes.py` (new) | One test per entity, from the 665-line comprehensive test |
| `tests/test_complete_workflow.py` (deleted) | Split into the two above |
| `.pre-commit-config.yaml` | Hook stops exempting `tests/` |
| `src/gramps_mcp/client.py` | `_make_request` gains `content`; `upload_media_file` routes through it |

---

## Task 1: Real-record fixtures in conftest.py

**Files:**
- Create: `tests/conftest.py`
- Test: `tests/test_conftest_fixtures.py`

**Interfaces:**
- Produces: fixtures `gramps_client`, `tree_id`, `note_handle`, `media_handle`, `repository_handle`, `source_handle`, `citation_handle`, `place_handle`, `event_handle`, `person_handles`, `family_handle`. Every handle fixture yields a `str` except `person_handles`, which yields `list[str]` of length 2. All are module-scoped.
- Produces: `create_entity(client, tree_id, api_call, params_model, entity_type) -> str`, an async helper returning the created handle.

- [ ] **Step 1: Write the failing test**

Create `tests/test_conftest_fixtures.py`:

```python
"""
Verify the shared fixtures create real records and hand back real handles.

These run against the live Gramps Web API, like the tests that consume them.
"""

import pytest

pytestmark = pytest.mark.integration

HANDLE_LENGTH = 16


class TestSharedFixtures:
    """The fixtures in conftest.py must yield usable handles."""

    @pytest.mark.asyncio
    async def test_root_fixtures_yield_handles(
        self, note_handle, media_handle, place_handle
    ):
        """Fixtures with no prerequisites each create a record."""
        for handle in (note_handle, media_handle, place_handle):
            assert isinstance(handle, str)
            assert len(handle) >= HANDLE_LENGTH

    @pytest.mark.asyncio
    async def test_chained_fixtures_yield_handles(
        self, repository_handle, source_handle, citation_handle, event_handle
    ):
        """Fixtures that depend on earlier records resolve their chain."""
        for handle in (
            repository_handle,
            source_handle,
            citation_handle,
            event_handle,
        ):
            assert isinstance(handle, str)
            assert len(handle) >= HANDLE_LENGTH

    @pytest.mark.asyncio
    async def test_person_fixture_yields_two_handles(self, person_handles):
        """The family tests need two people, so the fixture creates two."""
        assert len(person_handles) == 2
        assert len(set(person_handles)) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_conftest_fixtures.py -v`
Expected: FAIL with `fixture 'note_handle' not found`

- [ ] **Step 3: Write conftest.py**

Create `tests/conftest.py`. Read `src/gramps_mcp/models/parameters/` for each model's required fields and confirm every field name below exists before relying on it. `_extract_entity_data` is in `src/gramps_mcp/tools/data_management.py` and returns the created entity as a dict, so the handle is read structurally rather than scraped from formatted output.

```python
"""
Shared fixtures creating real records in the Gramps Web tree.

Nothing here fakes the API. Each fixture performs a real create against the
configured server, yields the handle, and deletes the record afterwards. They
exist so that no test depends on another test having run first.

Scope is "module": one set of records per test module, reused by its tests.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.parameters.citation_params import CitationData
from src.gramps_mcp.models.parameters.event_params import EventSaveParams
from src.gramps_mcp.models.parameters.media_params import MediaSaveParams
from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
from src.gramps_mcp.models.parameters.people_params import PersonData
from src.gramps_mcp.models.parameters.place_params import PlaceSaveParams
from src.gramps_mcp.models.parameters.repository_params import RepositoryData
from src.gramps_mcp.models.parameters.source_params import SourceSaveParams
from src.gramps_mcp.tools.data_management import _extract_entity_data

# Reason: every record these fixtures create is named with this prefix so a
# run killed mid-test leaves objects that are obvious in the tree and easy to
# find and remove by hand.
PREFIX = "Pytest Lot5"


async def create_entity(client, tree_id, api_call, params_model, entity_type) -> str:
    """
    Create one entity and return its handle.

    Args:
        client (GrampsWebAPIClient): Client to issue the call with.
        tree_id (str): Family tree identifier.
        api_call (ApiCalls): The POST call for this entity type.
        params_model (BaseModel): Validated parameters for the new entity.
        entity_type (str): Entity name as _extract_entity_data expects it.

    Returns:
        str: The handle of the created entity.
    """
    result = await client.make_api_call(
        api_call=api_call, params=params_model, tree_id=tree_id
    )
    return _extract_entity_data(result, entity_type)["handle"]


async def delete_entity(client, tree_id, api_call, handle) -> None:
    """
    Delete one entity, ignoring a failure so teardown never masks a test result.

    Args:
        client (GrampsWebAPIClient): Client to issue the call with.
        tree_id (str): Family tree identifier.
        api_call (ApiCalls): The DELETE call for this entity type.
        handle (str): Handle of the record to remove.

    Returns:
        None
    """
    try:
        await client.make_api_call(api_call=api_call, tree_id=tree_id, handle=handle)
    except Exception:
        # Reason: a teardown failure must not turn a passing test red. The
        # PREFIX above is what makes the leftover findable if this happens.
        pass


@pytest_asyncio.fixture(scope="module")
async def gramps_client() -> AsyncIterator[GrampsWebAPIClient]:
    """Yield a client for the configured tree."""
    yield GrampsWebAPIClient()


@pytest.fixture(scope="module")
def tree_id() -> str:
    """Return the configured family tree identifier."""
    return get_settings().gramps_tree_id


@pytest_asyncio.fixture(scope="module")
async def note_handle(gramps_client, tree_id) -> AsyncIterator[str]:
    """Create a note with no prerequisites."""
    handle = await create_entity(
        gramps_client,
        tree_id,
        ApiCalls.POST_NOTES,
        NoteSaveParams(text=f"{PREFIX} note", type="Transcript"),
        "note",
    )
    yield handle
    await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_NOTE, handle)
```

Write the remaining fixtures the same way, in dependency order. Each one requests the fixtures it needs as arguments, so pytest resolves the chain:

- `media_handle` - `MediaSaveParams(desc=f"{PREFIX} media")`, `ApiCalls.POST_MEDIA_OBJECTS`, entity type `"media"`, deleted with `ApiCalls.DELETE_MEDIA_ITEM`.
- `repository_handle(gramps_client, tree_id, note_handle)` - `RepositoryData(name=f"{PREFIX} repository", type="Archive", note_list=[note_handle])`, deleted with `ApiCalls.DELETE_REPOSITORY`.
- `source_handle(gramps_client, tree_id, repository_handle)` - `SourceSaveParams(title=f"{PREFIX} source", reporef_list=[{"ref": repository_handle}])`, deleted with `ApiCalls.DELETE_SOURCE`.
- `citation_handle(gramps_client, tree_id, source_handle)` - `CitationData(source_handle=source_handle, page=f"{PREFIX} page 1")`, deleted with `ApiCalls.DELETE_CITATION`.
- `place_handle` - `PlaceSaveParams(name=f"{PREFIX} place", place_type="City")`, deleted with `ApiCalls.DELETE_PLACE`.
- `event_handle(gramps_client, tree_id, citation_handle, place_handle)` - `EventSaveParams` with type `"Marriage"`, `place=place_handle`, `citation_list=[citation_handle]`, deleted with `ApiCalls.DELETE_EVENT`.
- `person_handles(gramps_client, tree_id)` - creates two people, `f"{PREFIX} Father"` and `f"{PREFIX} Mother"`, yields `[father, mother]`, deletes both with `ApiCalls.DELETE_PERSON`.
- `family_handle(gramps_client, tree_id, person_handles)` - father and mother handles from the list, deleted with `ApiCalls.DELETE_FAMILY`.

Verify each `ApiCalls` member name against `src/gramps_mcp/models/api_calls.py` before use. The POST member names are not all of the form `POST_<TYPE>`.

- [ ] **Step 4: Run test to verify it passes**

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_conftest_fixtures.py -v`
Expected: PASS, 3 tests

Then confirm the records were removed: search the tree for `Pytest Lot5` and expect nothing.

Run: `GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_conftest_fixtures.py -v` a second time. Expected: PASS again. A second green run proves teardown worked; if the first run leaked, the second would collide on duplicate names or leave two sets behind.

- [ ] **Step 5: Commit**

```bash
uv run git add tests/conftest.py tests/test_conftest_fixtures.py
uv run git commit -m "test: add real-record fixtures to replace the handle chain"
```

---

## Task 2: Convert test_data_management.py to the fixtures

**Files:**
- Modify: `tests/test_data_management.py` (remove lines 29-37 and every `global` statement)

**Interfaces:**
- Consumes: every fixture from Task 1.

- [ ] **Step 1: Record the baseline collection count**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_data_management.py --collect-only -q | tail -3
```

Write the number down. It must not change in this task or in Task 3.

- [ ] **Step 2: Replace the globals, one class at a time**

Delete the module-level globals at lines 29-37 and the `_handle_on_line` helper if nothing still uses it. For each test that read a global, take the fixture as a parameter instead. For each test that wrote a global, delete the `global` statement and the regex extraction block; the record it created is now the test's own and needs no export.

Example, `TestCreateRepositoryTool.test_create_repository_success`:

```python
    @pytest.mark.asyncio
    async def test_create_repository_success(self, note_handle):
        """Test successful repository creation with a note attached."""
        result = await create_repository_tool(
            {
                "name": "National Archives - Boston Branch",
                "type": "Archive",
                "urls": [
                    {
                        "type": "Web Home",
                        "path": "https://www.archives.gov/boston",
                        "desc": "Official website",
                    }
                ],
                "note_list": [note_handle],
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()
        assert "National Archives - Boston Branch" in text
        assert "Archive" in text
        assert "https://www.archives.gov/boston" in text
        assert "Official website" in text
        assert "Attached notes: N" in text
```

The `pytest.fail("No ... handle available from previous test")` guards all disappear: a missing fixture is now an error pytest raises itself, naming the fixture.

Keep every assertion. Keep the `print` blocks if they are there; they are diagnostic output, not scope for this task.

- [ ] **Step 3: Verify no globals remain**

```bash
grep -n "global \|run tests in order" tests/test_data_management.py
```

Expected: no output.

- [ ] **Step 4: Run the module and compare the count**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_data_management.py --collect-only -q | tail -3
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_data_management.py -q
```

Expected: the same collection count as Step 1, and no failure reading "No ... handle available from previous test".

- [ ] **Step 5: Prove a single test now runs alone**

This is the point of the task, so test it directly:

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest "tests/test_data_management.py::TestCreateSourceTool" -q
```

Expected: PASS. Before this task it failed with "No repository handle available from previous test". Record both observations in the report.

- [ ] **Step 6: Commit**

```bash
uv run git add tests/test_data_management.py
uv run git commit -m "test: replace the global handle chain with fixtures"
```

---

## Task 3: Split test_data_management.py

**Files:**
- Create: `tests/test_create_sourcing.py`, `tests/test_create_people.py`, `tests/test_create_records.py`
- Delete: `tests/test_data_management.py`

- [ ] **Step 1: Record the baseline counts**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest --collect-only -q -m "not integration" | tail -3
GRAMPS_API_URL=http://localhost:80 uv run pytest --collect-only -q -m integration | tail -3
```

- [ ] **Step 2: Move the classes**

| Destination | Classes |
|---|---|
| `tests/test_create_sourcing.py` | `TestCreateRepositoryTool`, `TestCreateSourceTool`, `TestCreateCitationTool`, `TestCreateSourcedEventTool` |
| `tests/test_create_people.py` | `TestCreatePersonTool`, `TestCreateFamilyTool` |
| `tests/test_create_records.py` | `TestCreateNoteTool`, `TestCreateMediaTool`, `TestCreatePlaceTool`, `TestCreateEventTool` |

Each new file carries `pytestmark = pytest.mark.integration` at module level, as the original had, and imports only the tools its classes call. Give each a module docstring naming what it covers.

Do not reword any test. This is a move.

- [ ] **Step 3: Verify the counts and the line lengths**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest --collect-only -q -m "not integration" | tail -3
GRAMPS_API_URL=http://localhost:80 uv run pytest --collect-only -q -m integration | tail -3
wc -l tests/test_create_sourcing.py tests/test_create_people.py tests/test_create_records.py
```

Expected: both counts identical to Step 1; every new file under 500 lines.

- [ ] **Step 4: Run the three modules**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_create_sourcing.py tests/test_create_people.py tests/test_create_records.py -q
```

- [ ] **Step 5: Commit**

```bash
uv run git add tests/test_create_sourcing.py tests/test_create_people.py tests/test_create_records.py
uv run git rm tests/test_data_management.py
uv run git commit -m "test: split data-management tests by domain"
```

---

## Task 4: Split test_parameter_alignment.py

**Files:**
- Create: `tests/test_alignment_sourcing.py`, `tests/test_alignment_records.py`, `tests/test_alignment_simple_params.py`
- Delete: `tests/test_parameter_alignment.py`

- [ ] **Step 1: Record the baseline counts**

```bash
uv run pytest --collect-only -q -m "not integration" | tail -3
```

- [ ] **Step 2: Move the tests**

The file holds one class, `TestParameterAlignment`, with eleven independent methods and no shared state. Each destination keeps a class of the same shape with a name matching its file.

| Destination | Methods |
|---|---|
| `tests/test_alignment_sourcing.py` | `test_repository_parameters_alignment`, `test_source_parameters_alignment`, `test_citation_parameters_alignment`, `test_media_parameters_alignment` |
| `tests/test_alignment_records.py` | `test_event_parameters_alignment`, `test_person_parameters_alignment`, `test_family_parameters_alignment`, `test_place_parameters_alignment`, `test_note_parameters_alignment` |
| `tests/test_alignment_simple_params.py` | `test_simple_params_exist_and_structured_correctly`, `test_person_event_reference_validation` |

Import in each file only the models its tests use. These tests need no server; do not mark them `integration`.

- [ ] **Step 3: Verify**

```bash
uv run pytest --collect-only -q -m "not integration" | tail -3
uv run pytest tests/test_alignment_sourcing.py tests/test_alignment_records.py tests/test_alignment_simple_params.py -q
wc -l tests/test_alignment_*.py
```

Expected: count unchanged, all pass, every file under 500 lines.

- [ ] **Step 4: Commit**

```bash
uv run git add tests/test_alignment_sourcing.py tests/test_alignment_records.py tests/test_alignment_simple_params.py
uv run git rm tests/test_parameter_alignment.py
uv run git commit -m "test: split parameter alignment tests by entity group"
```

---

## Task 5: Break up the comprehensive workflow test

**Files:**
- Create: `tests/test_workflow_marriage.py`, `tests/test_workflow_attributes.py`
- Delete: `tests/test_complete_workflow.py`

This is the only task in lot 5a that is not a move. `test_all_entity_attributes_comprehensive` is 665 lines in one test, so splitting the file by method leaves it over the limit on its own.

- [ ] **Step 1: Record the baseline count**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_complete_workflow.py --collect-only -q | tail -3
```

Expected: 3 tests. The count **will** rise in this task - that is the point - so record what the three were, not just the number.

- [ ] **Step 2: Move the two small tests**

`tests/test_workflow_marriage.py` takes `test_complete_marriage_record_workflow` and `test_place_hierarchy_creation` unchanged, with the module's `pytestmark = pytest.mark.integration` and whatever helper methods those two call.

- [ ] **Step 3: Split the comprehensive test by entity**

Read `test_all_entity_attributes_comprehensive` in full first. It runs as sequential blocks, each introduced by a comment of the form `# Test <Entity> creation` and each exercising one entity type.

Turn each block into its own test method in `tests/test_workflow_attributes.py`, named `test_<entity>_attributes`. Where a block needs a record an earlier block created, take the matching Task 1 fixture as a parameter rather than recreating it or preserving the sequence.

Keep every assertion the original made. Do not add assertions; do not drop any. If a block's assertions depend on a value computed by an earlier block that no fixture provides, compute it inside the new test from the fixture handles - and say so in the report, naming the block.

- [ ] **Step 4: Verify nothing was lost**

Diff the assertions rather than trusting a reading:

```bash
git show HEAD:tests/test_complete_workflow.py | grep -c "assert "
grep -c "assert " tests/test_workflow_marriage.py tests/test_workflow_attributes.py
```

Expected: the two new files' assertions sum to at least the original's. Report both numbers.

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_workflow_marriage.py tests/test_workflow_attributes.py -q
wc -l tests/test_workflow_marriage.py tests/test_workflow_attributes.py
```

Expected: all pass, both files under 500 lines.

- [ ] **Step 5: Commit**

```bash
uv run git add tests/test_workflow_marriage.py tests/test_workflow_attributes.py
uv run git rm tests/test_complete_workflow.py
uv run git commit -m "test: split the comprehensive workflow test into one test per entity"
```

---

## Task 6: Enforce the file-length rule in tests, and clarify the fixtures rule

**Files:**
- Modify: `.pre-commit-config.yaml:26`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Confirm no test file exceeds the limit**

```bash
find tests -name '*.py' -exec wc -l {} + | sort -rn | head -5
```

Expected: the largest is under 500. If not, the earlier splits are incomplete - stop and fix them before continuing.

- [ ] **Step 2: Remove the exemption**

In `.pre-commit-config.yaml`, delete the `exclude: ^tests/` line from the `check-file-length` hook only. Leave the `exclude: ^(tests/|examples/)` on the copyright hook alone, and leave `pyproject.toml`'s `"tests/*" = ["E501"]` alone - line length is a separate rule with its own written reason.

- [ ] **Step 3: Verify the hook now covers tests**

```bash
uv run pre-commit run check-file-length --all-files
```

Expected: PASS. Then prove it is actually looking at `tests/`:

```bash
python3 -c "open('tests/_toolong.py','w').write('# x\n'*501)"
uv run pre-commit run check-file-length --files tests/_toolong.py
rm tests/_toolong.py
```

Expected: the middle command FAILS naming `tests/_toolong.py`. Record that observation - it is the revert-check for this task.

- [ ] **Step 4: Clarify the fixtures rule in CLAUDE.md**

The rule currently forbids fixtures without qualification, which would forbid `tests/conftest.py` from Task 1. Amend the testing bullet to read:

```markdown
- **Test against the real Gramps API - do not fake its behaviour.** No test
  clients and no stubbed responses standing in for the server. Setup that
  creates real records against the real server is not faking - that is what
  `tests/conftest.py` does, and tests take those records as fixture arguments
  rather than depending on another test having run. Replacing the transport
  seam alone is permitted in offline unit tests, and is what
  `tests/test_client_merge.py` and `tests/test_http_error_detail.py` do.
  Assertions must read the output of the code under test, never the stub's
  call arguments - a test that asserts on its own mock proves nothing.
```

Also update the bullet describing the order dependence in `tests/test_data_management.py`: that file no longer exists and the dependence is gone. Delete it.

- [ ] **Step 5: Commit**

```bash
uv run git add .pre-commit-config.yaml CLAUDE.md
uv run git commit -m "chore: enforce the 500-line rule in tests and clarify the fixtures rule"
```

---

## Task 7: Verify lot 5a and open the pull request

- [ ] **Step 1: Run the offline suite**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest -m "not integration" -q
```

Expected: green. It was green at `9f7cca9`; any failure here is a regression this branch introduced.

- [ ] **Step 2: Run the full suite**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest -q
```

Compare against the baseline at `main`: 7 failed, 254 passed, 1 skipped. Three of those seven were the order-dependent `test_create_*_with_media_path` failures, which this branch should fix. Categorise every remaining failure as pre-existing or new, and name the ones that changed.

- [ ] **Step 3: Check types, lint and file lengths**

```bash
uv run mypy src/gramps_mcp --ignore-missing-imports
uv run ruff check src tests
uv run ruff format --check src tests
find src tests -name '*.py' -exec wc -l {} + | sort -rn | head -5
```

Expected: mypy clean on 63 files, ruff clean, no file over 500 lines.

- [ ] **Step 4: Confirm no leftover records**

Search the tree for `Pytest Lot5` and for `Pytest`. Report anything found and remove it.

- [ ] **Step 5: Push and open the pull request**

```bash
uv run git push -u origin fix/quality-lot5a-test-structure
gh pr create --repo fjacquet/gramps-mcp --title "Quality lot 5a: test structure"
```

Write the pull request body yourself from what you observed: the before and after of running a single sourcing test alone, the collection counts either side of each split, the assertion counts either side of the workflow split, and the full-suite comparison against the 7-failure baseline.

The `--repo` flag is required: this is a fork, and without it the error names a token problem, which is misleading.

---

## Task 8: Route the media upload through the shared request path

**Branch:** `fix/quality-lot5b-upload-request-path`, cut from `main` after lot 5a merges.

**Files:**
- Modify: `src/gramps_mcp/client.py:75-131` (`_make_request`), `src/gramps_mcp/client.py:343-377` (`upload_media_file`)
- Test: `tests/test_upload_request_path.py`

**Interfaces:**
- Produces: `_make_request(..., content: bytes | None = None, extra_headers: dict | None = None)`. When `content` is not None it is passed to httpx as the request body in place of `json_data`. `extra_headers` is merged over the headers `_get_headers` builds, so a caller can set `Content-Type` without duplicating header construction. Both default to `None`, so existing callers are unaffected.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_upload_request_path.py`. These need no server: they replace the transport seam only, and every assertion reads what the client returns or raises, never the stub's call arguments. Follow the pattern already in `tests/test_http_error_detail.py`.

```python
"""
The media upload must inherit the shared request path's error handling.

No server is needed: only httpx's transport is replaced. The responses are
real httpx.Response objects and every assertion reads what the client returns
or raises.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.gramps_mcp.client import GrampsAPIError, GrampsWebAPIClient


class TestUploadSharedRequestPath:
    """upload_media_file must behave like every other call."""

    @pytest.mark.asyncio
    async def test_connect_error_becomes_gramps_api_error(self):
        """An unreachable server must not leak httpx.ConnectError."""
        client = GrampsWebAPIClient()
        with (
            patch.object(client.auth_manager, "get_token", AsyncMock(return_value="t")),
            patch.object(
                client.auth_manager, "get_headers", AsyncMock(return_value={})
            ),
            patch.object(
                client.auth_manager.client,
                "request",
                AsyncMock(side_effect=httpx.ConnectError("no route")),
            ),
        ):
            with pytest.raises(GrampsAPIError) as excinfo:
                await client.upload_media_file(b"bytes", "image/jpeg")

        assert "Cannot connect to Gramps API" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_401_refreshes_the_token_and_retries(self):
        """A stale token must be refreshed once, not surfaced to the caller."""
        request = httpx.Request("POST", "http://example.invalid/api/media/")
        unauthorised = httpx.Response(401, request=request)
        created = httpx.Response(
            200, json=[{"new": {"handle": "abc123"}}], request=request
        )
        client = GrampsWebAPIClient()
        with (
            patch.object(client.auth_manager, "get_token", AsyncMock(return_value="t")),
            patch.object(
                client.auth_manager, "get_headers", AsyncMock(return_value={})
            ),
            patch.object(
                client.auth_manager, "authenticate", AsyncMock()
            ) as authenticate,
            patch.object(
                client.auth_manager.client,
                "request",
                AsyncMock(side_effect=[unauthorised, created]),
            ),
        ):
            result = await client.upload_media_file(b"bytes", "image/jpeg")

        assert authenticate.await_count == 1
        assert result == [{"new": {"handle": "abc123"}}]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_upload_request_path.py -v`
Expected: both FAIL. The first raises `httpx.ConnectError` rather than `GrampsAPIError`; the second raises `GrampsAPIError` about authentication instead of retrying.

- [ ] **Step 3: Add the content parameter to _make_request**

In `src/gramps_mcp/client.py`, add `content: bytes | None = None` to `_make_request`'s signature, pass it through on the retry call alongside the other arguments, and use it in the httpx call:

```python
        # Reason: a media upload sends raw bytes with its own Content-Type,
        # so it cannot use the json= path. Everything after the send - the 401
        # retry, the status formatting, the connect and timeout wrapping, the
        # empty-body case - is identical, which is why the upload routes
        # through here rather than repeating a subset of it.
        response = await self.auth_manager.client.request(
            method=method,
            url=url,
            params=params,
            json=json_data if content is None else None,
            content=content,
            headers=headers,
        )
```

Read the existing call at `client.py:92` first and keep every argument it already passes.

- [ ] **Step 4: Route upload_media_file through it**

Replace the body of `upload_media_file` after the URL and header construction:

```python
        url = self._build_url(tree_id, "media/")
        return await self._make_request(
            "POST", url, content=file_content, extra_headers={"Content-Type": mime_type}
        )
```

This needs `_make_request` to accept `extra_headers: dict | None = None` and merge it over what `_get_headers` builds, so the upload can set its `Content-Type` without duplicating header construction. Add it in the same step as `content`, and pass both through on the 401 retry call. Read `_get_headers` first and keep its behaviour intact.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_upload_request_path.py -v`
Expected: both PASS.

- [ ] **Step 6: Revert-check each half separately**

Two independent behaviours were fixed, so revert them one at a time. Reverting both together would credit two detectors where there may be one.

1. Restore the direct `auth_manager.client.request` call in `upload_media_file`. Run both tests. Expected: both fail. Restore the fix.
2. Keep the routing but remove the `content` parameter's use in `_make_request` so the body is dropped. Run the whole client test suite. Expected: a failure showing the upload sends no body. Restore.

Record all four observations in the report.

- [ ] **Step 7: Run the full suite**

```bash
uv run pytest -m "not integration" -q
GRAMPS_API_URL=http://localhost:80 uv run pytest -q
uv run mypy src/gramps_mcp --ignore-missing-imports
```

`_make_request` is the path every tool uses, so the **full integration suite must run before merge**, not only the offline subset. Compare failures against the lot 5a baseline and categorise each.

- [ ] **Step 8: Commit and open the pull request**

```bash
uv run git add src/gramps_mcp/client.py tests/test_upload_request_path.py
uv run git commit -m "fix: route the media upload through the shared request path"
uv run git push -u origin fix/quality-lot5b-upload-request-path
gh pr create --repo fjacquet/gramps-mcp --title "Quality lot 5b: media upload request path"
```

Write the pull request body from what you observed: the four revert-check results, and the full integration suite compared against the lot 5a baseline.

---

## After both merges

Bump `pyproject.toml` and `src/gramps_mcp/__init__.py`, run `uv lock` **in the same commit**, tag, and publish the release. `uv.lock` pins the project's own version and CI runs `uv sync --locked`; a bump without it turns `main` red while the Docker publish stays green, so the breakage is invisible from the release page.
