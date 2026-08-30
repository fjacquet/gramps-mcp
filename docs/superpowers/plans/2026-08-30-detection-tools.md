# Detection Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three read-only MCP tools - `find_duplicates`, `audit_quality`, `geocode_place` - so the assistant can find defects in the tree instead of only acting on defects a human already found.

**Architecture:** A new `src/gramps_mcp/genealogy/` package holds pure logic copied from `crewai-custom-tools`, plus one new networked module `collect.py` that feeds it records from the existing `GrampsWebAPIClient`. Tools are thin wrappers; rendering lives in `handlers/`, matching the existing `traversal.py` / `handlers/traversal_handler.py` split.

**Tech Stack:** Python 3.12, pydantic v2, httpx, pytest, uv, ruff.

**Spec:** `docs/superpowers/specs/2026-08-30-detection-tools-design.md`

## Global Constraints

- **Branch:** `feat/detection-tools`. Already exists, already carries the spec.
- **Run everything from the repo root.** A `cd` elsewhere in the same compound command selects another project and breaks the venv (`ModuleNotFoundError: httpx`).
- **Source repo for every copy:** `/Users/fjacquet/Projects/crewai_custom_tools`, at `v0.31.1` (sha `19d78f7`), subtree `src/crewai_custom_tools/tools/genealogy/`. Referred to below as `$SRC`.
- **No new runtime dependency.** `pyproject.toml` is not modified. `requests` is never imported; the one module that used it is ported to `httpx`.
- **Provenance header.** Every copied file's module docstring ends with these three lines, filled in per file:

```python
"""<the original docstring's first line, kept verbatim>

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/<original/path.py>.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.
"""
```

- **Import rewrite, applied to every copied file:** `from crewai_custom_tools.tools.genealogy.<subpkg>.<mod> import` becomes a package-relative import inside `src/gramps_mcp/genealogy/`. Source files use relative imports (`from .domain import ...`, `from ..client import ...`), matching the rest of `src/gramps_mcp/`. Test files use absolute imports (`from src.gramps_mcp.genealogy.duplicates import ...`), matching the rest of `tests/`.
- **File length:** 500 lines maximum, enforced by pre-commit on `*.py` only. The largest file in this plan is 243 lines.
- **No emoji in code**, enforced by pre-commit.
- **Commit with `uv run git commit`** so the hooks run. Prefix shell commands with `rtk` where a filter exists.
- **The AGPL copyright header is added automatically** by the `add_copyright_notice` pre-commit hook on first commit of each new `.py` file. Do not write it by hand.
- **Tests are ported with their code, in the same task and the same commit.** A copied module without its tests is unverified code in a TDD repo.
- **Ported tests must run offline.** They replace the HTTP seam (`_http_get`, `sparql_rows`) with `monkeypatch`, which is the one mocking pattern `CLAUDE.md` permits. They must pass under `uv run pytest -m "not integration"`.
- **Live tests carry `pytestmark = pytest.mark.integration`.**
- **Never write with a raw `PUT`.** Nothing in this plan writes to the tree at all; if a task seems to need a write, stop and report it.

### Test volume, corrected

The spec cites 1 934 lines of ported tests. The real figure is **2 290** across 21 files: the spec's count omitted `test_genealogy_places_parse.py` (177), `test_genealogy_places_score.py` (73), `test_genealogy_wikidata_sparql.py` (59) and `test_genealogy_place_dates.py` (47). Task 21 corrects the figure in the spec.

---

## File Structure

**Created under `src/gramps_mcp/genealogy/`:**

| File | Responsibility |
|---|---|
| `__init__.py` | Empty package marker |
| `domain.py` | Pydantic fact and result models, trimmed to those in scope |
| `phonetics.py` | Name normalisation and phonetic keys |
| `duplicates.py` | Blocking, candidate pairing, proof rules |
| `merge_plan.py` | Pair to cluster, phoenix choice, gender patch |
| `rules.py` | Consistency rules R1-R9 |
| `facts.py` | Raw Gramps JSON to `PersonFacts` / `FamilyFacts` |
| `collect.py` | **New.** Paginates the tree through `GrampsWebAPIClient` |
| `rate_limit.py` | Token-bucket limiter, four providers |
| `geo/__init__.py` | Empty package marker |
| `geo/places_parse.py` | Free text to `ParsedPlace` |
| `geo/score.py` | Similarity, ambiguity detection |
| `geo/transitions.py` | Historical commune transitions |
| `geo/france.py` | `geo.api.gouv.fr` resolver |
| `geo/suisse.py` | Swisstopo resolver |
| `geo/sparql.py` | `sparql_rows`, ported to httpx |
| `geo/france_ex_communes.py` | Merged and renamed communes |
| `geo/nominatim.py` | Worldwide fallback |
| `geo/registry.py` | Country routing, action decision |
| `geo/data/transitions.csv` | 3.5 KB data file |

**Created under `src/gramps_mcp/`:**

| File | Responsibility |
|---|---|
| `tools/detection.py` | The three tool entry points |
| `handlers/duplicates_handler.py` | Renders duplicate clusters |
| `handlers/audit_handler.py` | Renders anomalies |
| `handlers/geocode_handler.py` | Renders a place resolution |
| `models/parameters/detection_params.py` | The three parameter models |

**Modified:**

| File | Change |
|---|---|
| `tool_registry.py` | Three entries, three imports |
| `resources/gramps-usage-guide.md` | One section per tool |
| `tests/test_server.py:87,155,187` | Tool count 23 to 26 |
| `CLAUDE.md` | Copy decision, provenance, egress |
| `README.md` | Tool list, egress in setup |

---

## Phase A - Pure detection core

### Task 1: Package skeleton and domain models

**Files:**
- Create: `src/gramps_mcp/genealogy/__init__.py`
- Create: `src/gramps_mcp/genealogy/domain.py`
- Test: `tests/test_genealogy_domain.py`

**Interfaces:**
- Consumes: nothing
- Produces: `EventFact`, `PersonFacts`, `FamilyFacts`, `Anomaly`, `DuplicateCandidate`, `ParsedPlace`, `PlaceLevel`, `DatedName`, `DatedChain`, `ResolvedPlace`, `MergePair`, `MergeCluster` - every later task imports from here.

- [ ] **Step 1: Create the package marker**

```bash
mkdir -p src/gramps_mcp/genealogy
printf '"""Genealogy analysis logic copied from crewai-custom-tools."""\n' > src/gramps_mcp/genealogy/__init__.py
```

- [ ] **Step 2: Copy domain.py and keep only the models in scope**

The source is 378 lines and 22 classes. Keep these line ranges from `$SRC/models/domain.py`, in this order: `1-75` (module docstring, imports, `EventFact`, `PersonFacts`, `FamilyFacts`, `Anomaly`, `DuplicateCandidate`), `91-140` (`ParsedPlace`, `PlaceLevel`, `DatedName`, `DatedChain`, `ResolvedPlace`), `307-313` (the `MergeTier` alias `MergePair.tier` is annotated with - it is a type alias, not a model, which is why it appears in neither list below), `316-343` (`MergePair`, `MergeCluster`).

`FacteurConcordance` (line 250), the only other alias in the file, is not copied: it belongs to `PropositionAudit`, which is dropped.

Dropped: `Proposition`, `PlaceProposition`, `PlaceFacts`, `PlaceMergeProposition`, `PropositionAudit`, `PropositionsLot`, `Piste`, `Subdivision`, `CollisionIso`, `EntiteEcartee`.

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
{ sed -n '1,75p' $SRC/models/domain.py; sed -n '91,140p' $SRC/models/domain.py; sed -n '307,313p' $SRC/models/domain.py; sed -n '316,343p' $SRC/models/domain.py; } > src/gramps_mcp/genealogy/domain.py
```

- [ ] **Step 3: Add the provenance header**

Edit the module docstring at the top of `src/gramps_mcp/genealogy/domain.py` to the form given in Global Constraints, with `models/domain.py` as the original path.

- [ ] **Step 4: Verify the file is self-contained**

```bash
uv run python -c "
from src.gramps_mcp.genealogy.domain import EventFact, PersonFacts, FamilyFacts, Anomaly, DuplicateCandidate, ParsedPlace, PlaceLevel, DatedName, DatedChain, ResolvedPlace, MergePair, MergeCluster
MergePair(gramps_id_a='I1', gramps_id_b='I2', handle_a='a', handle_b='b', tier='arbitrage', regle=None, blocs=[])
MergeCluster(phoenix_handle='a', phoenix_gramps_id='I1', titanic_handles=['b'], titanic_gramps_ids=['I2'], gender_patch=None)
print('ok')
"
```

Expected: `ok`. The probe **instantiates** rather than only importing: the file carries `from __future__ import annotations`, which makes pydantic defer model building, so a bare import succeeds even on a model whose annotations reference a name that was never copied. If this raises `PydanticUserError`, `NameError` or `ImportError`, a kept class references something the trim dropped - report which, and do not re-add a dropped model without saying so.

- [ ] **Step 5: Port the domain tests**

```bash
cp /Users/fjacquet/Projects/crewai_custom_tools/tests/test_genealogy_domain.py tests/test_genealogy_domain.py
sed -i '' 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' tests/test_genealogy_domain.py
```

- [ ] **Step 6: Run the tests, delete the cases covering dropped models**

```bash
uv run pytest tests/test_genealogy_domain.py -v
```

Any test that fails with `ImportError` on a dropped model (`Piste`, `PlaceFacts`, `Subdivision`, `PropositionsLot`, `Proposition`, `PlaceProposition`, `PlaceMergeProposition`, `PropositionAudit`, `CollisionIso`, `EntiteEcartee`) is deleted - those models are deliberately out of scope. Any other failure is a real problem: stop and report it.

- [ ] **Step 7: Verify the remaining tests pass**

```bash
uv run pytest tests/test_genealogy_domain.py -v
```

Expected: all PASS, and at least the cases covering `PersonFacts`, `FamilyFacts` and `MergePair` still present.

- [ ] **Step 8: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/ tests/test_genealogy_domain.py
uv run git commit -m "feat: add genealogy domain models copied from crewai-custom-tools"
```

---

### Task 2: Phonetic keys

**Files:**
- Create: `src/gramps_mcp/genealogy/phonetics.py`
- Test: `tests/test_genealogy_phonetics.py`

**Interfaces:**
- Consumes: nothing (stdlib `unicodedata` only)
- Produces: `normalize_name(s: str) -> str`, `cle_phonetique(nom: str) -> str`

- [ ] **Step 1: Port the tests first**

```bash
cp /Users/fjacquet/Projects/crewai_custom_tools/tests/test_genealogy_phonetics.py tests/test_genealogy_phonetics.py
sed -i '' 's|from crewai_custom_tools.tools.genealogy.analysis.phonetics|from src.gramps_mcp.genealogy.phonetics|g' tests/test_genealogy_phonetics.py
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_genealogy_phonetics.py -v
```

Expected: FAIL, `ModuleNotFoundError: No module named 'src.gramps_mcp.genealogy.phonetics'`

- [ ] **Step 3: Copy the module**

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
cp $SRC/analysis/phonetics.py src/gramps_mcp/genealogy/phonetics.py
```

It imports only `unicodedata`, so no import rewrite is needed. Add the provenance header with `analysis/phonetics.py` as the original path.

- [ ] **Step 4: Run to verify they pass**

```bash
uv run pytest tests/test_genealogy_phonetics.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/phonetics.py tests/test_genealogy_phonetics.py
uv run git commit -m "feat: add phonetic name keys"
```

---

### Task 3: Duplicate detection

**Files:**
- Create: `src/gramps_mcp/genealogy/duplicates.py`
- Test: `tests/test_genealogy_duplicates.py`, `tests/test_genealogy_blocking.py`, `tests/test_genealogy_merge_tiers.py`

**Interfaces:**
- Consumes: `domain.PersonFacts`, `domain.FamilyFacts`, `domain.EventFact`, `domain.DuplicateCandidate`, `domain.MergePair`; `phonetics.normalize_name`, `phonetics.cle_phonetique`
- Produces: `etager(people: list[PersonFacts], familles: dict[str, FamilyFacts]) -> tuple[list[MergePair], list]` - the entry point the `find_duplicates` tool calls; also `find_duplicates(people, threshold=0.85) -> list[DuplicateCandidate]` (the quadratic scan, used by `audit_quality`), `blocking_keys`, `candidate_pairs`, `date_complete`, and the constants `MAX_BLOC = 60` and `BIRTH_YEAR_WINDOW`.

**Note for the implementer:** two different things share the name `find_duplicates` - the MCP tool built in Task 8 wraps `etager`, not the function of that name. Do not rename either; Task 8's docstring records which is which.

- [ ] **Step 1: Port the three test files**

```bash
CCT=/Users/fjacquet/Projects/crewai_custom_tools
for t in duplicates blocking merge_tiers; do
  cp $CCT/tests/test_genealogy_$t.py tests/test_genealogy_$t.py
  sed -i '' -e 's|from crewai_custom_tools.tools.genealogy.analysis.duplicates|from src.gramps_mcp.genealogy.duplicates|g' \
            -e 's|from crewai_custom_tools.tools.genealogy.analysis.phonetics|from src.gramps_mcp.genealogy.phonetics|g' \
            -e 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' \
            tests/test_genealogy_$t.py
done
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_genealogy_duplicates.py tests/test_genealogy_blocking.py tests/test_genealogy_merge_tiers.py -v
```

Expected: FAIL, `ModuleNotFoundError` on `src.gramps_mcp.genealogy.duplicates`.

- [ ] **Step 3: Copy the module and rewrite its imports**

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
cp $SRC/analysis/duplicates.py src/gramps_mcp/genealogy/duplicates.py
sed -i '' -e 's|from crewai_custom_tools.tools.genealogy.analysis.phonetics import|from .phonetics import|' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain import|from .domain import|' \
          src/gramps_mcp/genealogy/duplicates.py
```

Add the provenance header with `analysis/duplicates.py` as the original path.

- [ ] **Step 4: Run to verify they pass**

```bash
uv run pytest tests/test_genealogy_duplicates.py tests/test_genealogy_blocking.py tests/test_genealogy_merge_tiers.py -v
```

Expected: all PASS.

- [ ] **Step 5: Confirm the MAX_BLOC guard survived the copy**

```bash
rtk grep "MAX_BLOC" src/gramps_mcp/genealogy/duplicates.py
```

Expected: `MAX_BLOC = 60`. Without it a surname like `Pagan` (151 people) alone yields 11 325 pairs.

- [ ] **Step 6: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/duplicates.py tests/test_genealogy_duplicates.py tests/test_genealogy_blocking.py tests/test_genealogy_merge_tiers.py
uv run git commit -m "feat: add duplicate detection with blocking"
```

---

### Task 4: Merge planning

**Files:**
- Create: `src/gramps_mcp/genealogy/merge_plan.py`
- Test: `tests/test_genealogy_merge_plan.py`, `tests/test_genealogy_merge_models.py`

**Interfaces:**
- Consumes: `domain.PersonFacts`, `domain.MergePair`, `domain.MergeCluster`
- Produces: `plan_fusions(paires: list[MergePair], par_handle: dict[str, PersonFacts]) -> list[MergeCluster]`, `choisir_phoenix(membres: list[PersonFacts]) -> PersonFacts`, `score_completude(p: PersonFacts) -> int`

- [ ] **Step 1: Port the tests**

```bash
CCT=/Users/fjacquet/Projects/crewai_custom_tools
for t in merge_plan merge_models; do
  cp $CCT/tests/test_genealogy_$t.py tests/test_genealogy_$t.py
  sed -i '' -e 's|from crewai_custom_tools.tools.genealogy.analysis.merge_plan|from src.gramps_mcp.genealogy.merge_plan|g' \
            -e 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' \
            tests/test_genealogy_$t.py
done
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_genealogy_merge_plan.py tests/test_genealogy_merge_models.py -v
```

Expected: FAIL, `ModuleNotFoundError` on `src.gramps_mcp.genealogy.merge_plan`.

- [ ] **Step 3: Copy and rewrite**

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
cp $SRC/analysis/merge_plan.py src/gramps_mcp/genealogy/merge_plan.py
sed -i '' 's|from crewai_custom_tools.tools.genealogy.models.domain import|from .domain import|' src/gramps_mcp/genealogy/merge_plan.py
```

Add the provenance header with `analysis/merge_plan.py` as the original path.

- [ ] **Step 4: Run to verify they pass**

```bash
uv run pytest tests/test_genealogy_merge_plan.py tests/test_genealogy_merge_models.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/merge_plan.py tests/test_genealogy_merge_plan.py tests/test_genealogy_merge_models.py
uv run git commit -m "feat: add merge planning and phoenix selection"
```

---

### Task 5: Consistency rules R1-R9

**Files:**
- Create: `src/gramps_mcp/genealogy/rules.py`
- Test: `tests/test_genealogy_rules_person.py`, `tests/test_genealogy_rules_family.py`

**Interfaces:**
- Consumes: `domain.PersonFacts`, `domain.FamilyFacts`, `domain.Anomaly`, `domain.EventFact`
- Produces: `check_person(person: PersonFacts) -> list[Anomaly]`, `check_family(family: FamilyFacts, persons: dict[str, PersonFacts]) -> list[Anomaly]`

- [ ] **Step 1: Port the tests**

```bash
CCT=/Users/fjacquet/Projects/crewai_custom_tools
for t in rules_person rules_family; do
  cp $CCT/tests/test_genealogy_$t.py tests/test_genealogy_$t.py
  sed -i '' -e 's|from crewai_custom_tools.tools.genealogy.analysis.rules|from src.gramps_mcp.genealogy.rules|g' \
            -e 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' \
            tests/test_genealogy_$t.py
done
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_genealogy_rules_person.py tests/test_genealogy_rules_family.py -v
```

Expected: FAIL, `ModuleNotFoundError` on `src.gramps_mcp.genealogy.rules`.

- [ ] **Step 3: Copy and rewrite**

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
cp $SRC/analysis/rules.py src/gramps_mcp/genealogy/rules.py
sed -i '' 's|from crewai_custom_tools.tools.genealogy.models.domain import|from .domain import|' src/gramps_mcp/genealogy/rules.py
```

Add the provenance header with `analysis/rules.py` as the original path.

- [ ] **Step 4: Run to verify they pass**

```bash
uv run pytest tests/test_genealogy_rules_person.py tests/test_genealogy_rules_family.py -v
```

Expected: all PASS.

- [ ] **Step 5: Confirm the unknown-date guard survived**

```bash
rtk grep -n "sortval" src/gramps_mcp/genealogy/rules.py
```

Expected: `is_valid` checks `sortval`. A rule is skipped when the dates it needs are unknown, so unknown data never produces a false positive. If this is missing, the copy is wrong.

- [ ] **Step 6: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/rules.py tests/test_genealogy_rules_person.py tests/test_genealogy_rules_family.py
uv run git commit -m "feat: add deterministic consistency rules R1-R9"
```

---

### Task 6: Raw JSON to facts converters

**Files:**
- Create: `src/gramps_mcp/genealogy/facts.py`
- Test: `tests/test_genealogy_facts.py`

**Interfaces:**
- Consumes: `domain.PersonFacts`, `domain.FamilyFacts`, `domain.EventFact`
- Produces: `person_from_json(raw: dict) -> PersonFacts`, `family_from_json(raw: dict) -> FamilyFacts`, and the constant `_LIST_PARAMS` (the query parameters the Gramps list endpoints need: `{"profile": "all", "extend": "event_ref_list", "sort": "gramps_id"}`) - Task 7 uses it.

- [ ] **Step 1: Port the tests**

```bash
CCT=/Users/fjacquet/Projects/crewai_custom_tools
cp $CCT/tests/test_genealogy_facts.py tests/test_genealogy_facts.py
sed -i '' -e 's|from crewai_custom_tools.tools.genealogy.gramps.facts|from src.gramps_mcp.genealogy.facts|g' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' \
          tests/test_genealogy_facts.py
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_genealogy_facts.py -v
```

Expected: FAIL, `ModuleNotFoundError` on `src.gramps_mcp.genealogy.facts`.

- [ ] **Step 3: Copy only the pure part**

The source is 128 lines; `class FactsFetcher` starts at line 88 and is bound to `GrampsClient`, which this repo does not have. Keep lines 1-87 only.

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
sed -n '1,87p' $SRC/gramps/facts.py > src/gramps_mcp/genealogy/facts.py
sed -i '' -e '/from crewai_custom_tools.tools.genealogy.gramps.client import GrampsClient/d' \
          -e '/^import httpx$/d' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain import|from .domain import|' \
          src/gramps_mcp/genealogy/facts.py
```

Add the provenance header with `gramps/facts.py` as the original path, and note in it that `FactsFetcher` was deliberately not copied.

- [ ] **Step 4: Verify no dangling import remains**

```bash
uv run python -c "from src.gramps_mcp.genealogy.facts import person_from_json, family_from_json, _LIST_PARAMS; print(_LIST_PARAMS)"
```

Expected: `{'profile': 'all', 'extend': 'event_ref_list', 'sort': 'gramps_id'}`

- [ ] **Step 5: Run the tests; delete only the FactsFetcher cases**

```bash
uv run pytest tests/test_genealogy_facts.py -v
```

Tests exercising `FactsFetcher` fail on import and are deleted - that class is deliberately out of scope. Tests of `person_from_json` and `family_from_json` must pass. Any other failure: stop and report.

- [ ] **Step 6: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/facts.py tests/test_genealogy_facts.py
uv run git commit -m "feat: add Gramps JSON to facts converters"
```

---

## Phase B - Collection and the two detection tools

### Task 7: Tree collection

**Files:**
- Create: `src/gramps_mcp/genealogy/collect.py`
- Test: `tests/test_genealogy_collect.py`

**Interfaces:**
- Consumes: `facts.person_from_json`, `facts.family_from_json`, `facts._LIST_PARAMS`, `domain.PersonFacts`, `domain.FamilyFacts`, and `ApiCalls` from `..models.api_calls`
- Produces: `async def collect_tree(client, tree_id: str, limit: int | None = None) -> CollectResult`, where `CollectResult` is a dataclass with fields `people: list[PersonFacts]`, `families: dict[str, FamilyFacts]`, `skipped: int`, `partial: bool`, `error: str | None`.

This is the only module written from scratch and the only one that talks to the Gramps API.

- [ ] **Step 1: Find the list endpoints this repo already declares**

```bash
rtk grep -n "GET_PEOPLE\|GET_FAMILIES" src/gramps_mcp/models/api_calls.py
```

Use whatever names come back in the implementation below. If the enum members are named differently, use the real names - do not invent them.

- [ ] **Step 2: Write the failing test**

Create `tests/test_genealogy_collect.py`:

```python
"""Tests for tree collection."""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.genealogy.collect import collect_tree


class TestCollectOffline:
    async def test_converts_people_and_families(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = [
                [{"handle": "p1", "gramps_id": "I0001", "gender": 1,
                  "primary_name": {"first_name": "Jean",
                                   "surname_list": [{"surname": "Jacquet"}]}}],
                [{"handle": "f1", "gramps_id": "F0001",
                  "father_handle": "p1", "mother_handle": None,
                  "child_ref_list": []}],
            ]
            from src.gramps_mcp.client import GrampsWebAPIClient

            result = await collect_tree(GrampsWebAPIClient(), "tree")

        assert [p.gramps_id for p in result.people] == ["I0001"]
        assert "f1" in result.families
        assert result.partial is False
        assert result.skipped == 0

    async def test_a_record_that_cannot_be_converted_is_counted_not_fatal(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = [
                [{"handle": "p1"}, {"handle": "p2", "gramps_id": "I0002",
                                    "gender": 1,
                                    "primary_name": {"first_name": "Anne",
                                                     "surname_list": [{"surname": "Raucaz"}]}}],
                [],
            ]
            from src.gramps_mcp.client import GrampsWebAPIClient

            result = await collect_tree(GrampsWebAPIClient(), "tree")

        assert result.skipped == 1
        assert len(result.people) == 1

    async def test_a_failure_mid_scan_reports_partial(self):
        with patch(
            "src.gramps_mcp.client.GrampsWebAPIClient.make_api_call",
            new_callable=AsyncMock,
        ) as call:
            call.side_effect = RuntimeError("connection reset")
            from src.gramps_mcp.client import GrampsWebAPIClient

            result = await collect_tree(GrampsWebAPIClient(), "tree")

        assert result.partial is True
        assert result.error is not None
        assert "connection reset" in result.error
```

The third test is the one that matters most: "no duplicates found" over half a tree is a worse answer than an error.

- [ ] **Step 3: Run to verify it fails**

```bash
uv run pytest tests/test_genealogy_collect.py -v
```

Expected: FAIL, `ModuleNotFoundError` on `src.gramps_mcp.genealogy.collect`.

- [ ] **Step 4: Implement collect.py**

```python
"""Paginate the tree and convert every record to facts."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..models.api_calls import ApiCalls
from .domain import FamilyFacts, PersonFacts
from .facts import _LIST_PARAMS, family_from_json, person_from_json

logger = logging.getLogger(__name__)


@dataclass
class CollectResult:
    """One pass over the tree, with what it could not read stated explicitly."""

    people: list[PersonFacts] = field(default_factory=list)
    families: dict[str, FamilyFacts] = field(default_factory=dict)
    skipped: int = 0
    partial: bool = False
    error: str | None = None


async def collect_tree(client, tree_id: str, limit: int | None = None) -> CollectResult:
    """
    Fetch every person and family, converted to facts.

    Args:
        client (GrampsWebAPIClient): Client to issue the reads with.
        tree_id (str): Family tree identifier.
        limit (int | None): Stop after this many people, for a cheap probe.

    Returns:
        CollectResult: The facts, plus how many records were unreadable and
            whether the pass completed.
    """
    out = CollectResult()

    # Reason: a partial scan that renders like a complete one is the failure
    # that matters here - "no duplicates found" over half a tree reads as a
    # clean bill of health. Every early exit sets partial=True.
    try:
        raw_people = await client.make_api_call(
            api_call=ApiCalls.GET_PEOPLE, params=dict(_LIST_PARAMS), tree_id=tree_id
        )
        for raw in raw_people[:limit] if limit else raw_people:
            try:
                out.people.append(person_from_json(raw))
            except Exception:
                out.skipped += 1
                logger.debug("unreadable person record: %s", raw.get("handle"))

        raw_families = await client.make_api_call(
            api_call=ApiCalls.GET_FAMILIES, params=dict(_LIST_PARAMS), tree_id=tree_id
        )
        for raw in raw_families:
            try:
                family = family_from_json(raw)
                out.families[raw["handle"]] = family
            except Exception:
                out.skipped += 1
                logger.debug("unreadable family record: %s", raw.get("handle"))
    except Exception as exc:
        out.partial = True
        out.error = str(exc)

    return out
```

Adjust the `ApiCalls` member names to whatever Step 1 found.

- [ ] **Step 5: Run to verify it passes**

```bash
uv run pytest tests/test_genealogy_collect.py -v
```

Expected: all three PASS.

- [ ] **Step 6: Add a live test**

Append to `tests/test_genealogy_collect.py`:

```python
class TestCollectLive:
    pytestmark = pytest.mark.integration

    async def test_reads_the_real_tree(self, gramps_client, tree_id):
        result = await collect_tree(gramps_client, tree_id, limit=25)

        assert result.partial is False
        assert result.error is None
        assert len(result.people) > 0
        assert all(p.gramps_id for p in result.people)
```

- [ ] **Step 7: Run the live test**

```bash
uv run pytest tests/test_genealogy_collect.py::TestCollectLive -v
```

Expected: PASS against the remote Gramps Web server. A connection error here means the server is unreachable, which is an environment fact, not a regression - report it and move on.

- [ ] **Step 8: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/collect.py tests/test_genealogy_collect.py
uv run git commit -m "feat: add tree collection with explicit partial-scan reporting"
```

---

### Task 8: The `find_duplicates` tool

**Files:**
- Create: `src/gramps_mcp/models/parameters/detection_params.py`
- Create: `src/gramps_mcp/handlers/duplicates_handler.py`
- Create: `src/gramps_mcp/tools/detection.py`
- Modify: `src/gramps_mcp/tool_registry.py`
- Modify: `src/gramps_mcp/resources/gramps-usage-guide.md`
- Modify: `tests/test_server.py:87,155,187`
- Test: `tests/test_detection_duplicates.py`

**Interfaces:**
- Consumes: `collect.collect_tree`, `duplicates.etager`, `merge_plan.plan_fusions`
- Produces: `FindDuplicatesParams`, `find_duplicates_tool(client, arguments: dict) -> list[TextContent]`, `format_duplicate_clusters(clusters, arbitration_pairs, people_by_handle, skipped: int, partial: bool, error: str | None) -> str`

**Read this before writing the tool.** `plan_fusions` builds clusters from
`tier == "auto"` pairs **only** - it filters with `[p for p in paires if p.tier
== "auto"]` and the `arbitrage` and `rejet` pairs never reach its output. So a
tool that calls `etager` and then renders only `plan_fusions`' result silently
drops every pair needing human arbitration, which is exactly the split the spec
forbids collapsing. Keep the full pair list from `etager` and pass
`[p for p in pairs if p.tier == "arbitrage"]` to the handler as its own
argument. `rejet` pairs are dropped deliberately - they were matched on name
resemblance alone, which the source's own comment calls "jamais une preuve".

`MergePair` fields, verified: `gramps_id_a`, `gramps_id_b`, `handle_a`,
`handle_b`, `tier`, `regle`, `blocs`. `MergeCluster` fields, verified:
`phoenix_handle`, `phoenix_gramps_id`, `titanic_handles`, `titanic_gramps_ids`,
`gender_patch`.

- [ ] **Step 1: Write the failing handler test**

Create `tests/test_detection_duplicates.py`:

```python
"""Tests for the find_duplicates tool and its rendering."""

from unittest.mock import AsyncMock, patch

from src.gramps_mcp.genealogy.domain import MergeCluster, PersonFacts
from src.gramps_mcp.handlers.duplicates_handler import format_duplicate_clusters


class TestDuplicateRendering:
    def test_it_names_the_surviving_record(self):
        phoenix = PersonFacts(handle="a", gramps_id="I0001", surname="Jacquet",
                              given="Jean", sex="M")
        titanic = PersonFacts(handle="b", gramps_id="I0002", surname="Jacquet",
                              given="Jean", sex="M")
        cluster = MergeCluster(
            phoenix_handle="a", phoenix_gramps_id="I0001",
            titanic_handles=["b"], titanic_gramps_ids=["I0002"],
        )

        text = format_duplicate_clusters(
            [cluster], [], {"a": phoenix, "b": titanic},
            skipped=0, partial=False, error=None,
        )

        assert "I0001" in text
        assert "I0002" in text
        assert "survives" in text.lower()

    def test_an_arbitration_pair_is_not_presented_as_proved(self):
        from src.gramps_mcp.genealogy.domain import MergePair

        pair = MergePair(
            gramps_id_a="I0003", gramps_id_b="I0004",
            handle_a="c", handle_b="d",
            tier="arbitrage", regle=None, blocs=["pho:JCQ"],
        )

        text = format_duplicate_clusters(
            [], [pair], {}, skipped=0, partial=False, error=None
        )

        assert "I0003" in text
        assert "arbitration" in text.lower() or "review" in text.lower()

    def test_a_partial_scan_says_so(self):
        text = format_duplicate_clusters(
            [], [], {}, skipped=0, partial=True, error="connection reset"
        )

        assert "partial" in text.lower()
        assert "connection reset" in text

    def test_skipped_records_are_reported(self):
        text = format_duplicate_clusters(
            [], [], {}, skipped=3, partial=False, error=None
        )

        assert "3" in text
```

Read `src/gramps_mcp/genealogy/domain.py` for any field these constructors still
miss - `PersonFacts` and `MergePair` may require fields beyond those shown. Do
not drop a required field; supply a plausible value for it.

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_detection_duplicates.py -v
```

Expected: FAIL, `ModuleNotFoundError` on `src.gramps_mcp.handlers.duplicates_handler`.

- [ ] **Step 3: Write the parameter model**

Create `src/gramps_mcp/models/parameters/detection_params.py`:

```python
"""
Pydantic models for the read-only detection tools.

Tools supported in this category:
- find_duplicates: candidate duplicate people, clustered
- audit_quality: deterministic consistency anomalies
- geocode_place: a free-text place name resolved against gazetteers
"""

from pydantic import BaseModel, Field


class FindDuplicatesParams(BaseModel):
    """Parameters for finding candidate duplicate people."""

    limit: int | None = Field(
        None,
        description=(
            "Stop after this many people, for a cheap probe. Omit to scan "
            "the whole tree."
        ),
    )
    threshold: float = Field(
        0.85,
        ge=0.0,
        le=1.0,
        description="Minimum similarity for a pair to be reported",
    )
```

- [ ] **Step 4: Write the handler**

Create `src/gramps_mcp/handlers/duplicates_handler.py` with `format_duplicate_clusters(clusters, arbitration_pairs, people_by_handle, skipped, partial, error)`. It must render, in this order: a partial-scan warning when `partial` is true (naming `error`), the count of skipped records when non-zero, then the proved clusters - each naming the phoenix, why it was chosen (completeness score), and each titanic - and finally the arbitration pairs under their own heading. The two groups never render under one heading: collapsing them would let the caller treat a guess as a proof. A cluster whose `gender_patch` is not None renders that too, because the caller must apply it before merging.

- [ ] **Step 5: Run the handler tests**

```bash
uv run pytest tests/test_detection_duplicates.py -v
```

Expected: all PASS.

- [ ] **Step 6: Write the tool**

Create `src/gramps_mcp/tools/detection.py`:

```python
"""Read-only detection tools: duplicates, quality audit, place resolution."""

import logging

from mcp.types import TextContent

from ..client import GrampsAPIError
from ..config import get_settings
from ..genealogy.collect import collect_tree
from ..genealogy.duplicates import etager
from ..genealogy.merge_plan import plan_fusions
from ..handlers.duplicates_handler import format_duplicate_clusters
from ..models.parameters.detection_params import FindDuplicatesParams

logger = logging.getLogger(__name__)


def _format_error_response(error: Exception, operation: str) -> list[TextContent]:
    """Format an error into a user-facing MCP response."""
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"
    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


async def find_duplicates_tool(client, arguments: dict) -> list[TextContent]:
    """
    Find candidate duplicate people in the tree.

    Wraps `duplicates.etager` - the blocking path - not the module-level
    function that happens to share this tool's name, which is a quadratic
    scan meant for an already-small batch.
    """
    try:
        params = FindDuplicatesParams(**arguments)
        tree_id = get_settings().gramps_tree_id

        collected = await collect_tree(client, tree_id, limit=params.limit)
        pairs, _ignored = etager(collected.people, collected.families)
        by_handle = {p.handle: p for p in collected.people}
        clusters = plan_fusions(pairs, by_handle)

        # Reason: plan_fusions keeps only tier == "auto" pairs, so the pairs
        # needing human arbitration never reach its output. They are carried
        # separately rather than dropped - the spec forbids collapsing the
        # proved/unproved split, because a collapsed one reads as proof.
        arbitration = [p for p in pairs if p.tier == "arbitrage"]

        return [
            TextContent(
                type="text",
                text=format_duplicate_clusters(
                    clusters,
                    arbitration,
                    by_handle,
                    skipped=collected.skipped,
                    partial=collected.partial,
                    error=collected.error,
                ),
            )
        ]

    except Exception as e:
        return _format_error_response(e, "duplicate detection")
```

- [ ] **Step 7: Register the tool**

In `src/gramps_mcp/tool_registry.py`, import `FindDuplicatesParams` and `find_duplicates_tool`, then add an entry beside the other read tools, matching the existing shape:

```python
    "find_duplicates": {
        "description": (
            "Find candidate duplicate people, grouped into clusters with the "
            "record that would survive a merge already chosen. Read-only: it "
            "reports pairs the rules proved and, separately, pairs needing "
            "human arbitration. Feed a proved pair to merge_type"
        ),
        "schema": FindDuplicatesParams,
        "handler": find_duplicates_tool,
    },
```

- [ ] **Step 8: Update the tool count**

`tests/test_server.py` asserts the count in three places - lines 87, 155 and 187. Change `23` to `24`.

```bash
rtk grep -n "== 23" tests/test_server.py
```

- [ ] **Step 9: Document the tool**

Add a `### find_duplicates` section to `src/gramps_mcp/resources/gramps-usage-guide.md`, next to the other read tools, listing both parameters. This is not optional: `tests/test_alignment_*.py` hold hardcoded field inventories that fail when a parameter model is undocumented, and the guide is served to MCP clients.

- [ ] **Step 10: Run the whole offline suite**

```bash
uv run pytest -m "not integration" -q
```

Expected: green. If an alignment test fails, the guide is missing a field - fix the guide, then the inventory, never the inventory alone.

- [ ] **Step 11: Commit**

```bash
rtk git add src/gramps_mcp tests/test_detection_duplicates.py tests/test_server.py
uv run git commit -m "feat: add find_duplicates tool"
```

---

### Task 9: The `audit_quality` tool

**Files:**
- Modify: `src/gramps_mcp/models/parameters/detection_params.py`
- Create: `src/gramps_mcp/handlers/audit_handler.py`
- Modify: `src/gramps_mcp/tools/detection.py`
- Modify: `src/gramps_mcp/tool_registry.py`
- Modify: `src/gramps_mcp/resources/gramps-usage-guide.md`
- Modify: `tests/test_server.py`
- Test: `tests/test_detection_audit.py`

**Interfaces:**
- Consumes: `collect.collect_tree`, `rules.check_person`, `rules.check_family`
- Produces: `AuditQualityParams`, `audit_quality_tool(client, arguments: dict) -> list[TextContent]`, `format_anomalies(anomalies, skipped: int, partial: bool, error: str | None) -> str`

- [ ] **Step 1: Write the failing handler test**

Create `tests/test_detection_audit.py`:

```python
"""Tests for the audit_quality tool and its rendering."""

from src.gramps_mcp.genealogy.domain import Anomaly
from src.gramps_mcp.handlers.audit_handler import format_anomalies


class TestAuditRendering:
    def test_it_groups_by_severity_and_names_the_rule(self):
        anomalies = [
            Anomaly(rule="R1", severity="high", gramps_id="I0001",
                    message="Death before birth"),
            Anomaly(rule="R4", severity="low", gramps_id="I0002",
                    message="Marriage before age 14"),
        ]

        text = format_anomalies(anomalies, skipped=0, partial=False, error=None)

        assert "R1" in text
        assert "R4" in text
        assert "I0001" in text
        assert text.index("R1") < text.index("R4")

    def test_a_clean_tree_says_so_rather_than_rendering_nothing(self):
        text = format_anomalies([], skipped=0, partial=False, error=None)

        assert text.strip()
        assert "0" in text or "none" in text.lower()

    def test_a_partial_scan_says_so(self):
        text = format_anomalies([], skipped=0, partial=True, error="timeout")

        assert "partial" in text.lower()
        assert "timeout" in text
```

Adjust `Anomaly`'s field names to those in `src/gramps_mcp/genealogy/domain.py`.

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_detection_audit.py -v
```

Expected: FAIL, `ModuleNotFoundError` on `src.gramps_mcp.handlers.audit_handler`.

- [ ] **Step 3: Add the parameter model**

Append to `src/gramps_mcp/models/parameters/detection_params.py`:

```python
class AuditQualityParams(BaseModel):
    """Parameters for the deterministic quality audit."""

    limit: int | None = Field(
        None,
        description=(
            "Stop after this many people, for a cheap probe. Omit to scan "
            "the whole tree."
        ),
    )
    severity: str | None = Field(
        None,
        description=(
            "Report only anomalies at this severity. Omit to report every "
            "severity."
        ),
    )
```

- [ ] **Step 4: Write the handler**

Create `src/gramps_mcp/handlers/audit_handler.py` with `format_anomalies(anomalies, skipped, partial, error)`. Highest severity first. A clean result renders an explicit "no anomalies" line, never an empty string - an empty answer is indistinguishable from a broken one. A partial scan is stated before any finding.

- [ ] **Step 5: Run the handler tests**

```bash
uv run pytest tests/test_detection_audit.py -v
```

Expected: all PASS.

- [ ] **Step 6: Write the tool**

Append `audit_quality_tool` to `src/gramps_mcp/tools/detection.py`, following the shape of `find_duplicates_tool`: build `AuditQualityParams`, call `collect_tree`, run `check_person` over `collected.people` and `check_family` over `collected.families` (passing a `{handle: PersonFacts}` map as its second argument), filter by `params.severity` when given, then render through `format_anomalies`, passing `collected.skipped`, `collected.partial` and `collected.error` through unchanged.

- [ ] **Step 7: Register and document**

Add the registry entry:

```python
    "audit_quality": {
        "description": (
            "Run the deterministic consistency rules over the tree and report "
            "anomalies by severity. Read-only. Rules needing a date are "
            "skipped when that date is unknown, so unknown data never "
            "produces a false positive"
        ),
        "schema": AuditQualityParams,
        "handler": audit_quality_tool,
    },
```

Add an `### audit_quality` section to `src/gramps_mcp/resources/gramps-usage-guide.md`, listing both parameters.

- [ ] **Step 8: Update the tool count**

Change `24` to `25` at the three sites in `tests/test_server.py`.

- [ ] **Step 9: Run the whole offline suite**

```bash
uv run pytest -m "not integration" -q
```

Expected: green.

- [ ] **Step 10: Commit**

```bash
rtk git add src/gramps_mcp tests/test_detection_audit.py tests/test_server.py
uv run git commit -m "feat: add audit_quality tool"
```

---

## Phase C - Geo resolvers

### Task 10: Rate limiter

**Files:**
- Create: `src/gramps_mcp/genealogy/rate_limit.py`
- Test: `tests/test_genealogy_rate_limit.py`

**Interfaces:**
- Consumes: nothing (stdlib only)
- Produces: `get_rate_limiter()`, `RateLimit`, `RateLimitExceeded`

- [ ] **Step 1: Copy and trim the provider table**

Source: `/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/core/rate_limiter.py`, 140 lines. Keep only four providers: `Nominatim`, `Swisstopo`, `GeoApiGouvFr`, `Wikidata`. Drop every finance and OSINT entry (`AlphaVantage`, `YahooFinance`, `TwelveData`, `ChartImg`, `CoinMarketCap`, `Kraken`, `SECEdgar`, `Perplexity`, `FRED`, `FearGreed`, `TickerValidation`, `CoinGecko`, `DeFiLlama`) and the `_PREMIUM` overrides table.

```bash
cp /Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/core/rate_limiter.py src/gramps_mcp/genealogy/rate_limit.py
```

Then edit out the dropped entries by hand. Add the provenance header with `core/rate_limiter.py` as the original path - note that this one comes from `core/`, not the genealogy subtree.

- [ ] **Step 2: Verify Nominatim's limit survived**

```bash
rtk grep -n "Nominatim" src/gramps_mcp/genealogy/rate_limit.py
```

Expected: `RateLimit(requests_per_minute=60, burst=1)`. This is an ODbL licence obligation - 1 request per second, no burst - not a courtesy. If the trim changed it, restore it.

- [ ] **Step 3: Write the test**

Create `tests/test_genealogy_rate_limit.py`:

```python
"""Tests for the trimmed provider rate limiter."""

import pytest

from src.gramps_mcp.genealogy.rate_limit import get_rate_limiter


class TestRateLimit:
    def test_the_four_providers_in_scope_are_known(self):
        limiter = get_rate_limiter()
        for provider in ("Nominatim", "Swisstopo", "GeoApiGouvFr", "Wikidata"):
            limiter.acquire(provider)

    def test_nominatim_keeps_its_odbl_limit(self):
        from src.gramps_mcp.genealogy import rate_limit

        limit = rate_limit._LIMITS["Nominatim"]
        assert limit.requests_per_minute == 60
        assert limit.burst == 1
```

Adjust `_LIMITS` to the real table name in the copied file.

- [ ] **Step 4: Run the tests**

```bash
uv run pytest tests/test_genealogy_rate_limit.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/rate_limit.py tests/test_genealogy_rate_limit.py
uv run git commit -m "feat: add rate limiter trimmed to the four gazetteer providers"
```

---

### Task 11: Similarity scoring

**Files:**
- Create: `src/gramps_mcp/genealogy/geo/__init__.py`
- Create: `src/gramps_mcp/genealogy/geo/score.py`
- Test: `tests/test_genealogy_places_score.py`

**Interfaces:**
- Consumes: nothing outside stdlib
- Produces: `best_similarity`, `is_ambiguous`, `similarity`, `_norm` - Tasks 13, 14, 16 and 18 all import from here.

**Scope note.** An earlier draft of this task also created `places_parse.py`. It
cannot: `standardize/places.py:14` imports `split_canton_suffix` from
`geo/suisse.py`, which does not exist until Task 14. `places_parse.py` is
therefore created in Task 14, right after the module it depends on. The
dependency is one-way - `suisse.py` does not import `places_parse` - so no
circular import exists and neither copy needs to diverge from its source.

- [ ] **Step 1: Create the geo package and port the score test**

```bash
mkdir -p src/gramps_mcp/genealogy/geo
printf '"""Place resolvers copied from crewai-custom-tools."""\n' > src/gramps_mcp/genealogy/geo/__init__.py
CCT=/Users/fjacquet/Projects/crewai_custom_tools
cp $CCT/tests/test_genealogy_places_score.py tests/test_genealogy_places_score.py
sed -i '' -e 's|from crewai_custom_tools.tools.genealogy.geo.score|from src.gramps_mcp.genealogy.geo.score|g' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' \
          tests/test_genealogy_places_score.py
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_genealogy_places_score.py -v
```

Expected: FAIL, `ModuleNotFoundError` on `src.gramps_mcp.genealogy.geo.score`.

- [ ] **Step 3: Copy the module**

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
cp $SRC/geo/score.py src/gramps_mcp/genealogy/geo/score.py
sed -i '' 's|from crewai_custom_tools.tools.genealogy.models.domain import|from ..domain import|' src/gramps_mcp/genealogy/geo/score.py
```

Add the provenance header with `geo/score.py` as the original path.

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/test_genealogy_places_score.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/geo/ tests/test_genealogy_places_score.py
uv run git commit -m "feat: add place similarity scoring"
```

---

### Task 12: Historical commune transitions

**Files:**
- Create: `src/gramps_mcp/genealogy/geo/transitions.py`
- Create: `src/gramps_mcp/genealogy/geo/data/transitions.csv`
- Test: `tests/test_genealogy_geo_transitions.py`, `tests/test_genealogy_place_dates.py`

**Interfaces:**
- Consumes: `domain.ParsedPlace`, `domain.ResolvedPlace`, `domain.DatedChain`, `domain.DatedName`
- Produces: `apply_transition(resolved, parsed, transitions)`, `load_transitions()`

- [ ] **Step 1: Port both test files**

```bash
CCT=/Users/fjacquet/Projects/crewai_custom_tools
for t in geo_transitions place_dates; do
  cp $CCT/tests/test_genealogy_$t.py tests/test_genealogy_$t.py
  sed -i '' -e 's|from crewai_custom_tools.tools.genealogy.geo.transitions|from src.gramps_mcp.genealogy.geo.transitions|g' \
            -e 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' \
            tests/test_genealogy_$t.py
done
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_genealogy_geo_transitions.py tests/test_genealogy_place_dates.py -v
```

Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Copy the module and its data file**

The source resolves its data path as `Path(__file__).resolve().parent.parent / "data" / "transitions.csv"`. Here the layout differs, so the path expression must change to `Path(__file__).resolve().parent / "data" / "transitions.csv"`.

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
mkdir -p src/gramps_mcp/genealogy/geo/data
cp $SRC/data/transitions.csv src/gramps_mcp/genealogy/geo/data/transitions.csv
cp $SRC/geo/transitions.py src/gramps_mcp/genealogy/geo/transitions.py
sed -i '' -e 's|Path(__file__).resolve().parent.parent / "data"|Path(__file__).resolve().parent / "data"|' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain import|from ..domain import|' \
          src/gramps_mcp/genealogy/geo/transitions.py
```

Add the provenance header with `geo/transitions.py` as the original path.

- [ ] **Step 4: Verify the data file is found**

```bash
uv run python -c "from src.gramps_mcp.genealogy.geo.transitions import load_transitions; print(len(load_transitions()))"
```

Expected: a non-zero count. Zero means the path expression is still wrong - a silently empty table would make every transition a no-op.

- [ ] **Step 5: Run to verify the tests pass**

```bash
uv run pytest tests/test_genealogy_geo_transitions.py tests/test_genealogy_place_dates.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/geo/ tests/test_genealogy_geo_transitions.py tests/test_genealogy_place_dates.py
uv run git commit -m "feat: add historical commune transitions"
```

---

### Task 13: France resolver

**Files:**
- Create: `src/gramps_mcp/genealogy/geo/france.py`
- Test: `tests/test_genealogy_geo_france.py`

**Interfaces:**
- Consumes: `score._norm`, `domain.{DatedChain,DatedName,ParsedPlace,PlaceLevel,ResolvedPlace}`, `rate_limit.get_rate_limiter`
- Produces: `resolve_fr(parsed: ParsedPlace) -> ResolvedPlace | None`, `map_commune(payload: dict, parsed: ParsedPlace) -> ResolvedPlace`, `_http_get(path: str, params: dict) -> dict`

`_http_get` is the seam the tests replace. It already uses `httpx`, so no transport port is needed.

- [ ] **Step 1: Port the test file**

```bash
CCT=/Users/fjacquet/Projects/crewai_custom_tools
cp $CCT/tests/test_genealogy_geo_france.py tests/test_genealogy_geo_france.py
sed -i '' -e 's|from crewai_custom_tools.tools.genealogy.geo.france|from src.gramps_mcp.genealogy.geo.france|g' \
          -e 's|crewai_custom_tools.tools.genealogy.geo.france|src.gramps_mcp.genealogy.geo.france|g' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' \
          tests/test_genealogy_geo_france.py
```

The second pattern catches `monkeypatch.setattr("crewai_custom_tools...france._http_get", ...)` string targets, which the first pattern misses.

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_genealogy_geo_france.py -v
```

Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Copy and rewrite**

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
cp $SRC/geo/france.py src/gramps_mcp/genealogy/geo/france.py
sed -i '' -e 's|from crewai_custom_tools.core.rate_limiter import|from ..rate_limit import|' \
          -e 's|from crewai_custom_tools.tools.genealogy.geo.score import|from .score import|' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain import|from ..domain import|' \
          src/gramps_mcp/genealogy/geo/france.py
```

Add the provenance header with `geo/france.py` as the original path.

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/test_genealogy_geo_france.py -v
```

Expected: all PASS, and no network call made - the tests replace `_http_get`.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/geo/france.py tests/test_genealogy_geo_france.py
uv run git commit -m "feat: add France place resolver"
```

---

### Task 14: Switzerland resolver and place parsing

**Files:**
- Create: `src/gramps_mcp/genealogy/geo/suisse.py`
- Create: `src/gramps_mcp/genealogy/geo/places_parse.py`
- Test: `tests/test_genealogy_geo_suisse.py`, `tests/test_genealogy_places_parse.py`

**Interfaces:**
- Consumes: `rate_limit.get_rate_limiter`, `score` helpers, `domain` models
- Produces: `resolve_ch(parsed: ParsedPlace) -> ResolvedPlace | None`, `split_canton_suffix(label: str) -> tuple[str, str | None]`, `parse_pname(raw: str) -> ParsedPlace`

**Why the two ship together.** `standardize/places.py:14` imports
`split_canton_suffix` from `geo/suisse.py` and calls it at line 116. The
dependency is one-way, so copying `suisse.py` first and `places_parse.py`
second in this same task keeps both faithful to their source. Do not move the
function or invert the import.

- [ ] **Step 1: Port the test file**

```bash
CCT=/Users/fjacquet/Projects/crewai_custom_tools
cp $CCT/tests/test_genealogy_geo_suisse.py tests/test_genealogy_geo_suisse.py
sed -i '' -e 's|crewai_custom_tools.tools.genealogy.geo.suisse|src.gramps_mcp.genealogy.geo.suisse|g' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' \
          tests/test_genealogy_geo_suisse.py
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_genealogy_geo_suisse.py -v
```

Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Copy and rewrite**

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
cp $SRC/geo/suisse.py src/gramps_mcp/genealogy/geo/suisse.py
sed -i '' -e 's|from crewai_custom_tools.core.rate_limiter import|from ..rate_limit import|' \
          -e 's|from crewai_custom_tools.tools.genealogy.geo.score import|from .score import|' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain import|from ..domain import|' \
          src/gramps_mcp/genealogy/geo/suisse.py
```

Add the provenance header with `geo/suisse.py` as the original path. Keep `split_canton_suffix` defined here - `places_parse.py` imports it from this module in Step 6.

- [ ] **Step 4: Run to verify the Switzerland tests pass**

```bash
uv run pytest tests/test_genealogy_geo_suisse.py -v
```

Expected: all PASS.

- [ ] **Step 5: Port the place-parsing test**

```bash
CCT=/Users/fjacquet/Projects/crewai_custom_tools
cp $CCT/tests/test_genealogy_places_parse.py tests/test_genealogy_places_parse.py
sed -i '' -e 's|from crewai_custom_tools.tools.genealogy.standardize.places|from src.gramps_mcp.genealogy.geo.places_parse|g' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' \
          tests/test_genealogy_places_parse.py
uv run pytest tests/test_genealogy_places_parse.py -v
```

Expected: FAIL, `ModuleNotFoundError` on `src.gramps_mcp.genealogy.geo.places_parse`.

- [ ] **Step 6: Copy places_parse.py**

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
cp $SRC/standardize/places.py src/gramps_mcp/genealogy/geo/places_parse.py
sed -i '' -e 's|from crewai_custom_tools.tools.genealogy.geo.suisse import|from .suisse import|' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain import|from ..domain import|' \
          src/gramps_mcp/genealogy/geo/places_parse.py
```

Add the provenance header with `standardize/places.py` as the original path, noting that the module was renamed from `places.py` to `places_parse.py` to avoid colliding with the repo's existing `place_handler` naming.

- [ ] **Step 7: Run both test files**

```bash
uv run pytest tests/test_genealogy_geo_suisse.py tests/test_genealogy_places_parse.py -v
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/geo/suisse.py src/gramps_mcp/genealogy/geo/places_parse.py tests/test_genealogy_geo_suisse.py tests/test_genealogy_places_parse.py
uv run git commit -m "feat: add Switzerland resolver and place parsing"
```

---

### Task 15: SPARQL transport, ported to httpx

**Files:**
- Create: `src/gramps_mcp/genealogy/geo/sparql.py`
- Test: `tests/test_genealogy_wikidata_sparql.py`

**Interfaces:**
- Consumes: `httpx`
- Produces: `sparql_rows(query: str, *, timeout: float = 30.0) -> list[dict[str, str]]`

- [ ] **Step 1: Write the module**

The source, `$CCT/src/crewai_custom_tools/tools/web/wikidata.py:18-34`, uses `requests`. This repo uses `httpx` and must not gain a `requests` dependency. Create `src/gramps_mcp/genealogy/geo/sparql.py`:

```python
"""SPARQL transport for the Wikidata endpoint.

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/web/wikidata.py, and ported from requests to
httpx so this repo gains no new dependency. Divergence from that copy is
expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.
"""

from __future__ import annotations

import httpx

from .. import __version__ as _pkg_version  # adjust the relative depth if needed

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# Reason: Wikimedia's User-Agent policy exists so an operator seeing traffic can
# reach whoever sent it. The upstream module names crewai-custom-tools; sending
# that from here would point Wikidata at the wrong maintainer, so this names
# gramps-mcp and reads the version rather than hardcoding one that drifts.
USER_AGENT = (
    f"gramps-mcp/{_pkg_version} "
    "(https://github.com/fjacquet/gramps-mcp; place resolution)"
)


def sparql_rows(query: str, *, timeout: float = 30.0) -> list[dict[str, str]]:
    """
    Run a SPARQL query and return its bindings flattened as {variable: value}.

    Args:
        query (str): The SPARQL query to run.
        timeout (float): Seconds before the request is abandoned.

    Returns:
        list[dict[str, str]]: One dict per result row.

    Raises:
        httpx.HTTPStatusError: If the endpoint returns an error status.
    """
    response = httpx.get(
        SPARQL_ENDPOINT,
        params={"query": query, "format": "json"},
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    bindings = response.json().get("results", {}).get("bindings", [])
    return [
        {var: cell.get("value") for var, cell in binding.items()}
        for binding in bindings
    ]
```

Copy `SPARQL_ENDPOINT` verbatim from `$CCT/src/crewai_custom_tools/tools/web/wikidata.py:14`. Do **not** copy that file's `USER_AGENT` (line 15): it identifies crewai-custom-tools, and the request now comes from this project. `__version__` lives at `src/gramps_mcp/__init__.py:19`; verify the relative import depth resolves from `genealogy/geo/sparql.py` and fix it if it does not.

The `core/user_agent.py` helper in the source repo is a different mechanism used by other modules - `wikidata.py` does not call it. Ignore it.

- [ ] **Step 2: Port the test and convert it from requests to httpx**

```bash
CCT=/Users/fjacquet/Projects/crewai_custom_tools
cp $CCT/tests/test_genealogy_wikidata_sparql.py tests/test_genealogy_wikidata_sparql.py
```

Then edit it: the file imports `requests` and monkeypatches `wikidata.requests.get`. Change the import to `httpx`, the target to `src.gramps_mcp.genealogy.geo.sparql.httpx.get`, and the module import to `from src.gramps_mcp.genealogy.geo import sparql`. The `_FakeResponse` class needs no change - it already implements `raise_for_status` and `json`.

- [ ] **Step 3: Run the tests**

```bash
uv run pytest tests/test_genealogy_wikidata_sparql.py -v
```

Expected: all PASS, no network call.

- [ ] **Step 4: Confirm requests was not introduced**

```bash
rtk grep -rn "import requests" src/gramps_mcp/
```

Expected: no matches.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/geo/sparql.py tests/test_genealogy_wikidata_sparql.py
uv run git commit -m "feat: add SPARQL transport ported to httpx"
```

---

### Task 16: Merged and renamed communes

**Files:**
- Create: `src/gramps_mcp/genealogy/geo/france_ex_communes.py`
- Test: `tests/test_genealogy_geo_france_ex_communes.py`

**Interfaces:**
- Consumes: `france.map_commune`, `sparql.sparql_rows`, `rate_limit.get_rate_limiter`, `domain` models
- Produces: `resolve_fr_ex_commune(parsed: ParsedPlace) -> ResolvedPlace | None`

At 243 lines this is the largest file in the plan, and its test file (411 lines) is the largest test. In scope because merged and renamed communes are frequent in the 19th-century Cher.

- [ ] **Step 1: Port the test file**

```bash
CCT=/Users/fjacquet/Projects/crewai_custom_tools
cp $CCT/tests/test_genealogy_geo_france_ex_communes.py tests/test_genealogy_geo_france_ex_communes.py
sed -i '' -e 's|crewai_custom_tools.tools.genealogy.geo.france_ex_communes|src.gramps_mcp.genealogy.geo.france_ex_communes|g' \
          -e 's|crewai_custom_tools.tools.genealogy.geo.france|src.gramps_mcp.genealogy.geo.france|g' \
          -e 's|crewai_custom_tools.tools.web.wikidata|src.gramps_mcp.genealogy.geo.sparql|g' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' \
          tests/test_genealogy_geo_france_ex_communes.py
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_genealogy_geo_france_ex_communes.py -v
```

Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Copy and rewrite, including the requests exception**

The source catches `requests.RequestException` at line 132. With `sparql_rows` on httpx that exception can no longer be raised; it becomes `httpx.HTTPError`.

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
cp $SRC/geo/france_ex_communes.py src/gramps_mcp/genealogy/geo/france_ex_communes.py
sed -i '' -e 's|from crewai_custom_tools.core.rate_limiter import|from ..rate_limit import|' \
          -e 's|from crewai_custom_tools.tools.web.wikidata import|from .sparql import|' \
          -e 's|from crewai_custom_tools.tools.genealogy.geo.france import|from .france import|' \
          -e 's|from crewai_custom_tools.tools.genealogy.geo.score import|from .score import|' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain import|from ..domain import|' \
          -e 's|^import requests$|import httpx|' \
          -e 's|except requests.RequestException:|except httpx.HTTPError:|' \
          src/gramps_mcp/genealogy/geo/france_ex_communes.py
```

Add the provenance header with `geo/france_ex_communes.py` as the original path, and note the requests-to-httpx change in it.

- [ ] **Step 4: Verify no requests reference survived**

```bash
rtk grep -n "requests" src/gramps_mcp/genealogy/geo/france_ex_communes.py
```

Expected: no matches.

- [ ] **Step 5: Run to verify the tests pass**

```bash
uv run pytest tests/test_genealogy_geo_france_ex_communes.py -v
```

Expected: all PASS. A test asserting on `requests.RequestException` needs the same substitution as the source - make it, and say so in the handoff.

- [ ] **Step 6: Check the file length**

```bash
uv run python scripts/check_file_length.py src/gramps_mcp/genealogy/geo/france_ex_communes.py
```

Expected: pass, at 243 lines plus the header.

- [ ] **Step 7: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/geo/france_ex_communes.py tests/test_genealogy_geo_france_ex_communes.py
uv run git commit -m "feat: add merged and renamed commune resolver"
```

---

### Task 17: Worldwide fallback

**Files:**
- Create: `src/gramps_mcp/genealogy/geo/nominatim.py`
- Test: `tests/test_genealogy_geo_nominatim.py`

**Interfaces:**
- Consumes: `rate_limit.get_rate_limiter`, `domain` models
- Produces: `resolve_world(parsed: ParsedPlace) -> ResolvedPlace | None`

- [ ] **Step 1: Port the test file**

```bash
CCT=/Users/fjacquet/Projects/crewai_custom_tools
cp $CCT/tests/test_genealogy_geo_nominatim.py tests/test_genealogy_geo_nominatim.py
sed -i '' -e 's|crewai_custom_tools.tools.genealogy.geo.nominatim|src.gramps_mcp.genealogy.geo.nominatim|g' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' \
          tests/test_genealogy_geo_nominatim.py
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_genealogy_geo_nominatim.py -v
```

Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Copy and rewrite**

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
cp $SRC/geo/nominatim.py src/gramps_mcp/genealogy/geo/nominatim.py
sed -i '' -e 's|from crewai_custom_tools.core.rate_limiter import|from ..rate_limit import|' \
          -e 's|from crewai_custom_tools.tools.genealogy.geo.score import|from .score import|' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain import|from ..domain import|' \
          src/gramps_mcp/genealogy/geo/nominatim.py
```

Its full import list, verified: `httpx`, `core.rate_limiter`, `geo.score`, `models.domain`. It sends no User-Agent of its own, so nothing from Task 15 is needed here. Add the provenance header with `geo/nominatim.py` as the original path.

- [ ] **Step 4: Verify the rate limit is acquired before the call**

```bash
rtk grep -n "get_rate_limiter" src/gramps_mcp/genealogy/geo/nominatim.py
```

Expected: an `acquire` call before the HTTP request. Nominatim's ODbL terms make this an obligation, not a courtesy.

- [ ] **Step 5: Run to verify the tests pass**

```bash
uv run pytest tests/test_genealogy_geo_nominatim.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/geo/nominatim.py tests/test_genealogy_geo_nominatim.py
uv run git commit -m "feat: add worldwide place fallback"
```

---

### Task 18: Country routing

**Files:**
- Create: `src/gramps_mcp/genealogy/geo/registry.py`
- Test: `tests/test_genealogy_geo_registry.py`

**Interfaces:**
- Consumes: `france.resolve_fr`, `france_ex_communes.resolve_fr_ex_commune`, `suisse.resolve_ch`, `nominatim.resolve_world`, `transitions.apply_transition`, `transitions.load_transitions`
- Produces: `resolve_place(parsed: ParsedPlace) -> ResolvedPlace | None`, `decide_action(resolved, min_score: float) -> str` returning `"ecrire" | "proposition" | "indecidable"`, `confiance_of(resolved, min_score=0.90) -> str`

- [ ] **Step 1: Port the test file**

```bash
CCT=/Users/fjacquet/Projects/crewai_custom_tools
cp $CCT/tests/test_genealogy_geo_registry.py tests/test_genealogy_geo_registry.py
sed -i '' -e 's|crewai_custom_tools.tools.genealogy.geo.registry|src.gramps_mcp.genealogy.geo.registry|g' \
          -e 's|crewai_custom_tools.tools.genealogy.geo|src.gramps_mcp.genealogy.geo|g' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain|from src.gramps_mcp.genealogy.domain|g' \
          tests/test_genealogy_geo_registry.py
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_genealogy_geo_registry.py -v
```

Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Copy the module, dropping Germany and the United States**

Delete the `resolve_de` and `resolve_us` imports and their two `_BY_COUNTRY` entries. That single edit is what removes `de_communes.csv` (789 KB) and `us_places.csv` (1.56 MB) from this repo's scope. The `France` entry, `lambda p: resolve_fr(p) or resolve_fr_ex_commune(p)`, must be kept exactly as written - the ex-commune fallback runs before Nominatim, which would otherwise lose the hierarchy.

```bash
SRC=/Users/fjacquet/Projects/crewai_custom_tools/src/crewai_custom_tools/tools/genealogy
cp $SRC/geo/registry.py src/gramps_mcp/genealogy/geo/registry.py
sed -i '' -e '/geo.allemagne import resolve_de/d' \
          -e '/geo.usa import resolve_us/d' \
          -e '/"Allemagne": lambda p: resolve_de(p),/d' \
          -e '/"États-Unis": lambda p: resolve_us(p),/d' \
          -e 's|from crewai_custom_tools.tools.genealogy.geo.|from .|' \
          -e 's|from crewai_custom_tools.tools.genealogy.models.domain import|from ..domain import|' \
          src/gramps_mcp/genealogy/geo/registry.py
```

Add the provenance header, naming the two dropped resolvers.

- [ ] **Step 4: Verify the country table**

```bash
uv run python -c "from src.gramps_mcp.genealogy.geo.registry import _BY_COUNTRY; print(sorted(_BY_COUNTRY))"
```

Expected: `['France', 'Suisse']`

- [ ] **Step 5: Run the tests, deleting only the DE and US cases**

```bash
uv run pytest tests/test_genealogy_geo_registry.py -v
```

Tests routing to Germany or the United States are deleted - those resolvers are deliberately out of scope. Every other test must pass; in particular the case proving that ambiguity beats a perfect score in `decide_action` must survive.

- [ ] **Step 6: Commit**

```bash
rtk git add src/gramps_mcp/genealogy/geo/registry.py tests/test_genealogy_geo_registry.py
uv run git commit -m "feat: add country routing for France and Switzerland"
```

---

## Phase D - The geocode tool

### Task 19: The `geocode_place` tool

**Files:**
- Modify: `src/gramps_mcp/models/parameters/detection_params.py`
- Create: `src/gramps_mcp/handlers/geocode_handler.py`
- Modify: `src/gramps_mcp/tools/detection.py`
- Modify: `src/gramps_mcp/tool_registry.py`
- Modify: `src/gramps_mcp/resources/gramps-usage-guide.md`
- Modify: `tests/test_server.py`
- Test: `tests/test_detection_geocode.py`

**Interfaces:**
- Consumes: `geo.places_parse.parse_pname`, `geo.registry.resolve_place`, `geo.registry.decide_action`, `geo.registry.confiance_of`
- Produces: `GeocodePlaceParams`, `geocode_place_tool(client, arguments: dict) -> list[TextContent]`, `format_place_resolution(resolved, action: str, confiance: str, query: str) -> str`

**This tool never writes.** `genecrew`'s `lieu_import` creates the hierarchy when the score allows; here the tool proposes and the caller chains to `create_place`.

- [ ] **Step 1: Write the failing handler test**

Create `tests/test_detection_geocode.py`:

```python
"""Tests for the geocode_place tool and its rendering."""

from src.gramps_mcp.handlers.geocode_handler import format_place_resolution


class TestGeocodeRendering:
    def test_no_match_and_a_provider_error_render_differently(self):
        no_match = format_place_resolution(
            None, action="indecidable", confiance="basse", query="Nowhere"
        )
        failed = format_place_resolution(
            None, action="indecidable", confiance="basse", query="Nowhere",
            error="geo.api.gouv.fr timed out",
        )

        assert no_match != failed
        assert "timed out" in failed
        assert "timed out" not in no_match

    def test_an_ambiguous_result_is_flagged_not_silently_picked(self):
        from src.gramps_mcp.genealogy.domain import ResolvedPlace

        resolved = ResolvedPlace(name="Le Rocher", score=0.93, ambiguous=True)

        text = format_place_resolution(
            resolved, action="proposition", confiance="basse", query="Le Rocher"
        )

        assert "ambigu" in text.lower() or "ambiguous" in text.lower()

    def test_it_never_claims_to_have_written_anything(self):
        from src.gramps_mcp.genealogy.domain import ResolvedPlace

        resolved = ResolvedPlace(name="Bourges", score=1.0, ambiguous=False)

        text = format_place_resolution(
            resolved, action="ecrire", confiance="haute", query="Bourges, Cher"
        )

        assert "created" not in text.lower()
        assert "create_place" in text
```

The last test pins the design decision: even when the score says `ecrire`, this tool renders a proposal and names the tool that would write it. Fill `ResolvedPlace`'s required fields from `src/gramps_mcp/genealogy/domain.py` rather than guessing.

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_detection_geocode.py -v
```

Expected: FAIL, `ModuleNotFoundError` on `src.gramps_mcp.handlers.geocode_handler`.

- [ ] **Step 3: Add the parameter model**

Append to `src/gramps_mcp/models/parameters/detection_params.py`:

```python
class GeocodePlaceParams(BaseModel):
    """Parameters for resolving a free-text place name."""

    query: str = Field(
        description="Free-text place name, for example 'Bourges, Cher, France'"
    )
    min_score: float = Field(
        0.90,
        ge=0.0,
        le=1.0,
        description=(
            "Score at or above which the resolution is considered solid. "
            "Below it, the result is rendered as a proposal to review."
        ),
    )
```

- [ ] **Step 4: Write the handler**

Create `src/gramps_mcp/handlers/geocode_handler.py` with `format_place_resolution(resolved, action, confiance, query, error=None)`. It renders the administrative chain, coordinates, the INSEE or Swiss code, the score, and the confidence. Three rules the tests pin:

1. A provider failure and "no match" render differently; they are different answers.
2. `resolved.ambiguous` is stated prominently. `CLAUDE.md` records what silence costs here: "Le Rocher" (Cher) matched Saint-Antoine-du-Rocher (Indre-et-Loire) on the region alone, and "le rocher" is a genuine alias of that commune.
3. The output names `create_place` as the next step and never implies a write happened.

- [ ] **Step 5: Run the handler tests**

```bash
uv run pytest tests/test_detection_geocode.py -v
```

Expected: all PASS.

- [ ] **Step 6: Write the tool**

Append `geocode_place_tool` to `src/gramps_mcp/tools/detection.py`: build `GeocodePlaceParams`, call `parse_pname(params.query)`, then `resolve_place(parsed)`, then `decide_action(resolved, params.min_score)` and `confiance_of(resolved, params.min_score)`, then render. Catch `httpx.HTTPError` separately from every other exception and pass its message as the handler's `error` argument, so a gazetteer being unreachable is reported as such rather than as "no match".

- [ ] **Step 7: Register and document**

```python
    "geocode_place": {
        "description": (
            "Resolve a free-text place name against authoritative gazetteers "
            "(France, Switzerland, worldwide fallback). Read-only: it returns "
            "the administrative chain, coordinates and a score, and flags an "
            "ambiguous match instead of picking one. Pass the result to "
            "create_place to record it"
        ),
        "schema": GeocodePlaceParams,
        "handler": geocode_place_tool,
    },
```

Add a `### geocode_place` section to `src/gramps_mcp/resources/gramps-usage-guide.md`, listing both parameters, and stating that a verified QID is still checked against the nearest identified ancestor - this tool supplies candidates, it does not replace that check.

- [ ] **Step 8: Update the tool count**

Change `25` to `26` at the three sites in `tests/test_server.py`.

- [ ] **Step 9: Run the whole offline suite**

```bash
uv run pytest -m "not integration" -q
```

Expected: green.

- [ ] **Step 10: Add one live test per gazetteer**

Append to `tests/test_detection_geocode.py`:

```python
class TestGeocodeLive:
    pytestmark = pytest.mark.integration

    async def test_it_resolves_a_french_commune(self):
        from src.gramps_mcp.tools.detection import geocode_place_tool

        result = await geocode_place_tool(None, {"query": "Bourges, Cher, France"})
        text = result[0].text

        assert "Bourges" in text
        assert "18033" in text or "Cher" in text

    async def test_it_resolves_a_swiss_commune(self):
        from src.gramps_mcp.tools.detection import geocode_place_tool

        result = await geocode_place_tool(None, {"query": "Nidau, Berne, Suisse"})
        text = result[0].text

        assert "Nidau" in text
```

These exist so a provider changing its response shape is caught rather than silently degrading every resolution. Add `import pytest` to the file if it is not already imported.

- [ ] **Step 11: Run the live tests**

```bash
uv run pytest tests/test_detection_geocode.py::TestGeocodeLive -v
```

Expected: PASS. A network failure here is an environment fact - report it rather than weakening the assertion.

- [ ] **Step 12: Commit**

```bash
rtk git add src/gramps_mcp tests/test_detection_geocode.py tests/test_server.py
uv run git commit -m "feat: add geocode_place tool"
```

---

## Phase E - Documentation and close-out

### Task 20: Record the copy decision and the new egress

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-08-30-detection-tools-design.md`

- [ ] **Step 1: Add the copy decision to CLAUDE.md**

Under "Code Structure & Modularity", add an entry for the new package:

```markdown
  - `genealogy/` - pure detection logic (duplicate blocking, consistency rules
    R1-R9, merge planning, place resolvers) **copied** from
    fjacquet/crewai-custom-tools v0.31.1 (19d78f7). The duplication is
    deliberate, decided by the repo owner; divergence from that repo is
    expected and is not a defect to repair. Each file's docstring names its
    origin. Do not "fix" this by re-unifying the two copies.
```

- [ ] **Step 2: Add the egress fact to CLAUDE.md**

Under "Testing & Reliability", add:

```markdown
- **The server now calls third-party hosts.** `geocode_place` reaches
  `geo.api.gouv.fr`, `api3.geo.admin.ch`, `query.wikidata.org` and
  `nominatim.openstreetmap.org`; the Docker container needs egress to them.
  The two detection tools do not - they keep working when a gazetteer is
  unreachable. Nominatim's 1 request per second with no burst is an ODbL
  licence obligation encoded in `genealogy/rate_limit.py`, not a courtesy.
```

- [ ] **Step 3: Update README.md**

Add the three tools to the tool list, and note the outbound hosts in the setup section - egress is now a runtime requirement, not an implementation detail.

- [ ] **Step 4: Correct the test figure in the spec**

The spec's "Testing" section cites 1 934 lines of ported tests across 17 files. The real figure is 2 290 across 21: it omitted `test_genealogy_places_parse.py` (177), `test_genealogy_places_score.py` (73), `test_genealogy_wikidata_sparql.py` (59) and `test_genealogy_place_dates.py` (47). Correct both numbers and add the four filenames.

- [ ] **Step 5: Build the docs**

```bash
uv run --with mkdocs-material mkdocs build --strict
```

Expected: builds clean. Strict mode fails on broken internal links, which is the usual way a docs change breaks the published site.

- [ ] **Step 6: Commit**

```bash
rtk git add CLAUDE.md README.md docs/
uv run git commit -m "docs: record the copy decision, provenance and new egress"
```

---

### Task 21: Full verification

**Files:** none modified unless a failure demands it.

- [ ] **Step 1: Run the offline suite**

```bash
uv run pytest -m "not integration" -q
```

Expected: green. This selection is green on `main` today, so any failure here is caused by this branch.

- [ ] **Step 2: Run the integration suite**

```bash
uv run pytest -m integration -q
```

Expected: green against the remote Gramps Web server. Two known environment facts are not regressions: `tree_stats` returns a permission error even for the owner-role account, and connection errors mean the tree is unreachable.

- [ ] **Step 3: Type check**

```bash
uv run mypy src/gramps_mcp --ignore-missing-imports
```

Expected: clean.

- [ ] **Step 4: Confirm the tool count end to end**

```bash
rtk grep -n "== 26" tests/test_server.py
```

Expected: three matches, at the sites that were 23.

- [ ] **Step 5: Confirm no new dependency crept in**

```bash
rtk git diff main --stat -- pyproject.toml uv.lock
```

Expected: no output. If either file changed, a dependency was added against the plan - report it rather than committing it.

- [ ] **Step 6: Confirm every copied file carries its provenance**

```bash
rtk grep -rLn "crewai-custom-tools v0.31.1" src/gramps_mcp/genealogy/
```

Expected: only `__init__.py`, `geo/__init__.py` and `collect.py` - the two markers and the one module written from scratch. Any other file listed is missing its provenance header.

- [ ] **Step 7: Report**

State: tests run and their real output, the final tool count, and anything left undone. If a step was skipped, say which and why.

---

## Self-Review

**Spec coverage.** Every section of the spec maps to a task: the detection layer to Tasks 1-6, `collect.py` to Task 7, the two detection tools to Tasks 8-9, the geo layer to Tasks 10-18 (rate limiter, parse, score, transitions, France, Switzerland, SPARQL, ex-communes, Nominatim, registry), `geocode_place` to Task 19, and the documentation and egress sections to Task 20. The spec's error-handling requirements are pinned by tests in Tasks 7, 8, 9 and 19; its "partial scan must say so" requirement by Task 7 Step 2 and Task 8 Step 1.

**Known deviation from the spec.** The spec's ported-test figure is wrong; Task 20 Step 4 corrects it in the spec itself rather than leaving the two documents disagreeing.

**Type consistency.** `CollectResult` is defined in Task 7 and consumed by Tasks 8, 9 with the same field names (`people`, `families`, `skipped`, `partial`, `error`). `etager` returns `(pairs, ignored)` in Task 3 and is unpacked that way in Task 8. `plan_fusions(paires, par_handle)` in Task 4 is called with that argument order in Task 8. `decide_action` returns the three literal strings in Task 18 and Task 19 renders all three.

**Two interface risks flagged in-plan rather than hidden.** Task 11 may find a circular import between `places_parse` and `suisse`, which changes Task 14's interface; the step says so and tells the implementer to report it. Task 17 may find `user_agent` is a function rather than a constant; the step says so.
