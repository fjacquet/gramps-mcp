# Detection Tools - `find_duplicates` and `audit_quality`

**Date:** 2026-08-30
**Repo state:** `main` (723cca1)
**Source of the copied logic:** `fjacquet/crewai-custom-tools` at `v0.31.1`
(19d78f7), subtree `src/crewai_custom_tools/tools/genealogy/`

## The gap

The server can merge two records the caller names (`merge_type`), and it can
delete, detach and undo. It cannot *find* anything wrong on its own. Every
duplicate person and every inconsistency in the tree is found by a human
reading records, or by running `genecrew` from a terminal and reading a
Markdown report afterwards.

That asymmetry is the whole problem: the assistant holds the write tools and
none of the detection. It can act on a defect only once the user has already
found it.

Two read-only tools close it:

- `find_duplicates` - candidate duplicate people, clustered, with the pair
  that would survive a merge already chosen
- `audit_quality` - deterministic consistency anomalies (rules R1-R9)

Neither writes. Both feed tools that already exist: `find_duplicates` hands
handles to `merge_type`, `audit_quality` hands them to `create_*`.

## Decision: the logic is copied, not shared

The rules, the phonetic keys, the blocking and the merge planner already
exist, pure and tested, in `crewai-custom-tools`. Three routes were weighed:
depend on that package, extract a shared `genealogy-core` distribution, or
copy the modules into this repo.

**Copy is the chosen route, decided by the repo owner.** All three
repositories are his; the decision is deliberate, not a workaround.

What that buys: no cross-repo release coupling, no packaging work, no
dependency added to `pyproject.toml`, and an MCP server that stays
installable from its own source alone.

What it costs, stated plainly so no future session mistakes it for an
accident: **the same rule will exist in two places and will drift.** A
correction to `check_person` here does not reach `genecrew`. This is accepted.
`CLAUDE.md` records it (see "Documentation" below) so that a later reader does
not "fix" the duplication by re-unifying it.

Every copied file carries a provenance header naming the source repo, the
original path, the version and the sha. Without it the drift becomes
invisible within months.

### What is *not* copied

The wider inventory of `genecrew` (~7 500 lines) and of the genealogy subtree
(~7 300 lines) stays where it is. Taking all of it would roughly triple this
repository (12 003 lines of source, 11 978 of tests today) and duplicate
3.4 MB of CSV data.

Excluded deliberately:

- **Bulk write passes** - `apply case/gender/places`, `deces_apply`,
  `referentiel_apply`, `apply_all`, `batching`, `checkpoint`. These are
  hundreds of PUTs gated by a human reading a YAML file before anything is
  written. That review *is* the safety property. Moved behind an MCP tool it
  disappears, and the assistant becomes something that writes in bulk
  unreviewed. `genecrew`'s stated first principle is deterministic-first; this
  is that principle.
- **`geo/`** - 1 022 lines plus 3.4 MB of CSV to support a `geocode_place`
  tool. Poor ratio, and deferrable.
- **`releves_import.py`** - 1 420 lines, over this repo's 500-line file limit,
  so it cannot be copied without being re-cut. The pasted-record path already
  goes through the assistant.
- **`identity.py`** - excluded specifically because it imports
  `geo.score.similarity`, which would drag `geo/` in. Nothing in the chosen
  scope needs it.
- **`pistes/`** (Wikidata, DHS) - 398 lines, read-only, one call one answer, so
  the shape fits. Deferred only because it would be the server's first
  outbound call to a non-Gramps service, which deserves its own decision.

## What is copied

New package `src/gramps_mcp/genealogy/`. Files copied from the subtree named
above, each trimmed to what the two tools need:

| Target | Source | Notes |
|---|---|---|
| `domain.py` | `models/domain.py` | Only `EventFact`, `PersonFacts`, `FamilyFacts`, `Anomaly`, `DuplicateCandidate`, `MergePair`, `MergeCluster`. The place, piste and subdivision models are dropped - roughly 180 of the original 378 lines survive. Pure pydantic, no other import. |
| `phonetics.py` | `analysis/phonetics.py` | 57 lines, `unicodedata` only. |
| `duplicates.py` | `analysis/duplicates.py` | 222 lines. Imports `phonetics` and `domain`, nothing else. |
| `rules.py` | `analysis/rules.py` | 174 lines. Imports `domain` only. |
| `merge_plan.py` | `analysis/merge_plan.py` | 102 lines. Imports `domain` only. |
| `facts.py` | `gramps/facts.py` | Only the two pure converters, `person_from_json(raw: dict)` and `family_from_json(raw: dict)`, plus `_event_from_raw`. The `GrampsClient`-bound collector class is **not** copied - this repo has its own client. |

Total copied: roughly 830 lines - 180 + 57 + 222 + 174 + 102 + ~90. The
dependency graph is closed: nothing reaches outside these six files except
`pydantic`, already a dependency.

One genuinely new module:

- `collect.py` (~80 lines) - paginates `/people/` and `/families/` through the
  existing `GrampsWebAPIClient` and feeds each raw record to the converters in
  `facts.py`. This is the only code written from scratch.

## The two tools

### `find_duplicates`

Wraps `etager()` then `plan_fusions()` - the blocking path `genecrew`'s
`people_merge.py:240-242` uses in production, not the naive O(n²)
`find_duplicates()` function that shares its name.

**Naming hazard, called out deliberately:** the MCP tool `find_duplicates` does
*not* wrap the copied function `find_duplicates`. The function is the quadratic
scan `audit.py` uses over an already-small batch; `etager` is the scalable
one, with blocking keys and a `MAX_BLOC = 60` guard (without it a surname like
`Pagan`, 151 people, alone yields 11 325 pairs). The copied function keeps its
name so its tests port unchanged; the tool's docstring states which it calls.

Parameters: `scope` (whole tree or a subset), `limit`, `threshold`
(default 0.85), `confirm`-free because it never writes.

Returns, per cluster: the members, the chosen phoenix and why (completeness
score), the pairs the rules proved, and separately the pairs that need human
arbitration. The proved/unproved split is preserved from the source; collapsing
it would let the assistant treat a guess as a proof.

### `audit_quality`

Wraps `check_person()` and `check_family()` - rules R1-R9. Each rule is skipped
when the dates it needs are unknown (`sortval` 0), so unknown data never
produces a false positive; that property comes from the source and is worth
keeping visible in the rendered output.

Parameters: `scope`, `limit`, optional `severity` filter.

Returns anomalies grouped by severity, each naming the rule, the person or
family, and the detail fields.

### Rendering

`handlers/duplicates_handler.py` and `handlers/audit_handler.py`, matching the
existing handler split - pure logic in one place, rendering in another, as
`traversal.py` and `handlers/traversal_handler.py` already do.

The renderer is where output lies to the reader: #27 shipped two defects
because traversal tests asserted on the graph and never called the formatter.
Both handlers get tests that assert on rendered text.

## Data flow

```
MCP call
  -> collect.py: paginate /people/, /families/ via GrampsWebAPIClient
  -> facts.py:   raw dict -> PersonFacts / FamilyFacts
  -> duplicates.py etager() -> MergePair[]        | rules.py check_*() -> Anomaly[]
  -> merge_plan.py plan_fusions() -> MergeCluster[]
  -> handler: rendered text
```

Nothing in this path writes. `collect.py` is the only component touching the
network.

## Error handling

- A record the converters cannot parse is skipped and counted, not fatal. The
  rendered output states how many were skipped - a silent skip would let a
  partial scan read as a complete one.
- Pagination failure mid-scan aborts and reports how far it got. Reporting
  partial results as complete is the failure mode that matters here: "no
  duplicates found" over half a tree is worse than an error.
- Both tools follow the existing `_format_error_response` shape.

## Testing

TDD, tests before the copied code is wired in.

Ported with the code, 1 075 lines across ten files:
`test_genealogy_duplicates.py` (55), `test_genealogy_blocking.py` (94),
`test_genealogy_merge_tiers.py` (240), `test_genealogy_merge_plan.py` (110),
`test_genealogy_merge_models.py` (63), `test_genealogy_phonetics.py` (48),
`test_genealogy_rules_person.py` (136), `test_genealogy_rules_family.py` (66),
`test_genealogy_facts.py` (145), `test_genealogy_domain.py` (118, trimmed to
the models kept).

Copying 830 lines without their tests would put unverified code into a repo
whose first rule is TDD. The tests come with the code, non-negotiably.

They are pure and run offline, so they land in the `-m "not integration"`
selection. Two additions are needed beyond the port:

- `collect.py` against the live tree, using `conftest.py` fixtures - it is the
  only new code and the only networked component.
- Handler rendering tests, per the #27 lesson above.

File-length: every copied file is under the 500-line hook limit; the trimmed
`domain.py` is the largest at roughly 180 lines. Test files likewise.

## Documentation

- `resources/gramps-usage-guide.md` gains a section per tool. This is not
  optional: `tests/test_alignment_*.py` hold hardcoded field inventories that
  fail when a parameter model is undocumented, and the guide is served to MCP
  clients - an undocumented parameter is one the assistant can pass but was
  never told about.
- `CLAUDE.md` records the copy decision, the provenance sha, and the fact that
  drift from `crewai-custom-tools` is expected rather than a defect to repair.
- `README.md` tool list.

## Out of scope

`merge_person` / `merge_family` - a separate design, already discussed and
approved, that splits `merge_type` into type-specific tools. It pairs
naturally with `find_duplicates` (detect, then merge) but is a distinct change
and stays a distinct commit series.

## Open question for review

`find_duplicates` currently scans a scope and returns everything above the
threshold. For a tree of ~1 426 people the blocking keeps this tractable, but
the rendered output for a whole-tree scan may be long enough to be unusable in
a chat context. If that proves true in practice the answer is a summary-first
render with per-cluster detail on request - noted here rather than designed
now, because the real output length is not yet known.
