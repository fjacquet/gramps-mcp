# Detection Tools - `find_duplicates`, `audit_quality`, `geocode_place`

**Date:** 2026-08-30
**Repo state:** `main` (723cca1)
**Source of the copied logic:** `fjacquet/crewai-custom-tools` at `v0.31.1`
(19d78f7), subtree `src/crewai_custom_tools/tools/genealogy/`

## The gap

The server can merge two records the caller names (`merge_type`), and it can
delete, detach and undo. It cannot *find* anything wrong on its own. Every
duplicate person, every inconsistency, every unresolved place name is found by
a human reading records, or by running `genecrew` from a terminal and reading a
Markdown report afterwards.

That asymmetry is the whole problem: the assistant holds the write tools and
none of the detection. It can act on a defect only once the user has already
found it.

Three read-only tools close it:

- `find_duplicates` - candidate duplicate people, clustered, with the record
  that would survive a merge already chosen
- `audit_quality` - deterministic consistency anomalies (rules R1-R9)
- `geocode_place` - a free-text place name resolved against authoritative
  gazetteers, scored, with ambiguity reported rather than hidden

None of them writes. All three feed tools that already exist: `find_duplicates`
hands handles to `merge_type`, `audit_quality` and `geocode_place` hand fields
to `create_*`.

## Decision: the logic is copied, not shared

The rules, the phonetic keys, the blocking, the merge planner and the place
resolvers already exist, pure and tested, in `crewai-custom-tools`. Three
routes were weighed: depend on that package, extract a shared `genealogy-core`
distribution, or copy the modules into this repo.

**Copy is the chosen route, decided by the repo owner.** All three
repositories are his; the decision is deliberate, not a workaround.

What that buys: no cross-repo release coupling, no packaging work, no new
runtime dependency, and an MCP server that stays installable from its own
source alone.

What it costs, stated plainly so no future session mistakes it for an
accident: **the same rule will exist in two places and will drift.** A
correction to `check_person` here does not reach `genecrew`. This is accepted.
`CLAUDE.md` records it (see "Documentation" below) so that a later reader does
not "fix" the duplication by re-unifying it.

Every copied file carries a provenance header naming the source repo, the
original path, the version and the sha. Without it the drift becomes
invisible within months.

### What is *not* copied

The wider inventory of `genecrew` (~7 500 lines) stays where it is. Taking all
of it would roughly triple this repository (12 003 lines of source, 11 978 of
tests today).

Excluded deliberately:

- **Bulk write passes** - `apply case/gender/places`, `deces_apply`,
  `referentiel_apply`, `apply_all`, `batching`, `checkpoint`. These are
  hundreds of PUTs gated by a human reading a YAML file before anything is
  written. That review *is* the safety property. Moved behind an MCP tool it
  disappears, and the assistant becomes something that writes in bulk
  unreviewed. `genecrew`'s stated first principle is deterministic-first; this
  is that principle.
- **The German and US place resolvers** - `allemagne.py` and `usa.py`, and with
  them `de_communes.csv` (789 KB) and `us_places.csv` (1.56 MB). The tree is
  French and Swiss. They are dropped from `registry.py`'s `_BY_COUNTRY` table,
  which is the single edit that removes them.
- **`analysis/gender.py`** - and its `prenoms_sexe.csv` (1.16 MB). Gender
  inference is a write pass, excluded on the rule above.
- **`releves_import.py`** - 1 420 lines, over this repo's 500-line file limit,
  so it cannot be copied without being re-cut. The pasted-record path already
  goes through the assistant.
- **`identity.py`** - nothing in scope needs it.
- **`pistes/`** (Wikidata notable people, DHS) - 398 lines. Read-only and the
  right shape, but a separate concern; deferred.

The three CSV files excluded above are why an earlier estimate priced the geo
subtree at 3.4 MB of data. **The France and Switzerland resolvers load no CSV
at all** - they call `geo.api.gouv.fr` and `api3.geo.admin.ch`. The only data
file in scope is `transitions.csv`, at 3.5 KB.

## What is copied

New package `src/gramps_mcp/genealogy/`. Each file trimmed to what the three
tools need.

### Detection layer (~830 lines)

| Target | Source | Notes |
|---|---|---|
| `domain.py` | `models/domain.py` | Only the models in scope: `EventFact`, `PersonFacts`, `FamilyFacts`, `Anomaly`, `DuplicateCandidate`, `MergePair`, `MergeCluster`, plus the place models below. Pure pydantic. |
| `phonetics.py` | `analysis/phonetics.py` | 57 lines, `unicodedata` only. |
| `duplicates.py` | `analysis/duplicates.py` | 222 lines. Imports `phonetics` and `domain`. |
| `rules.py` | `analysis/rules.py` | 174 lines. Imports `domain`. |
| `merge_plan.py` | `analysis/merge_plan.py` | 102 lines. Imports `domain`. |
| `facts.py` | `gramps/facts.py` | The two pure converters `person_from_json` / `family_from_json` plus `_event_from_raw`. The `GrampsClient`-bound collector is **not** copied - this repo has its own client. |

### Geo layer (~950 lines + 3.5 KB)

| Target | Source | Notes |
|---|---|---|
| `geo/places_parse.py` | `standardize/places.py` | 129 lines, `parse_pname`. |
| `geo/france.py` | `geo/france.py` | 98 lines. Already `httpx`, with `_http_get` written as a replaceable seam. |
| `geo/suisse.py` | `geo/suisse.py` | 90 lines, Swisstopo. |
| `geo/france_ex_communes.py` | same | 243 lines. Merged and renamed communes - frequent in the 19th-century Cher, which is why it is in scope and not dropped. |
| `geo/score.py` | `geo/score.py` | 70 lines, `best_similarity` / `is_ambiguous`. |
| `geo/transitions.py` | `geo/transitions.py` | 67 lines + `transitions.csv` (3.5 KB). |
| `geo/nominatim.py` | `geo/nominatim.py` | 60 lines, world fallback. |
| `geo/registry.py` | `geo/registry.py` | 57 lines, trimmed: `_BY_COUNTRY` loses the DE and US entries and their imports. |
| `geo/sparql.py` | `tools/web/wikidata.py` | Only `sparql_rows`, 17 lines, **ported from `requests` to `httpx`**. Its own docstring calls it "free transport ... which must not depend on a BaseTool", so this is its intended use. |
| `rate_limit.py` | `core/rate_limiter.py` | Trimmed from ~140 lines to the four providers in scope: `Nominatim`, `Swisstopo`, `GeoApiGouvFr`, `Wikidata`. The finance and OSINT entries are dropped. |

`requests` is **not** added as a dependency: `sparql_rows` is the only caller
and it is ported to `httpx`, which the repo already uses. `rate_limiter.py`
never imported `requests` - the name appears only as a `requests_per_minute`
field.

**Nominatim's limit is a licence obligation, not a courtesy.** ODbL terms cap
it at 1 request per second with no burst; the copied table encodes that. It
must survive the trim.

### Written from scratch

- `collect.py` (~80 lines) - paginates `/people/` and `/families/` through the
  existing `GrampsWebAPIClient` and feeds each raw record to the converters in
  `facts.py`. The only genuinely new component.

Total: roughly **1 780 lines copied**, one new module, one 3.5 KB data file.

## The three tools

### `find_duplicates`

Wraps `etager()` then `plan_fusions()` - the blocking path
`genecrew/people_merge.py:240-242` uses in production.

**Naming hazard, called out deliberately:** the MCP tool `find_duplicates` does
*not* wrap the copied function `find_duplicates`. That function is a quadratic
scan used over an already-small batch; `etager` is the scalable one, with
blocking keys and a `MAX_BLOC = 60` guard (without it a surname like `Pagan`,
151 people, alone yields 11 325 pairs). The copied function keeps its name so
its tests port unchanged; the tool's docstring states which it calls.

Parameters: `scope`, `limit`, `threshold` (default 0.85). No `confirm` - it
never writes.

Returns, per cluster: the members, the chosen phoenix and why (completeness
score), the pairs the rules proved, and separately the pairs needing human
arbitration. That split is preserved from the source; collapsing it would let
the assistant treat a guess as a proof.

### `audit_quality`

Wraps `check_person()` and `check_family()` - rules R1-R9. Each rule is skipped
when the dates it needs are unknown (`sortval` 0), so unknown data never
produces a false positive. That property is worth keeping visible in the
rendered output.

Parameters: `scope`, `limit`, optional `severity` filter.

Returns anomalies grouped by severity, each naming the rule, the person or
family, and the detail fields.

### `geocode_place`

Wraps `parse_pname()` then `resolve_place()` then `decide_action()`.

Parameters: `query` (free text), `min_score` (default 0.90).

Returns the resolved candidate with its administrative chain, coordinates,
INSEE or Swiss code, the score, and the action the score implies - **but never
performs it.** `genecrew`'s `lieu_import` writes when the score allows; here
the tool proposes and the assistant chains to `create_place`. Same reason as
everywhere else in this design: the write path stays under review.

Ambiguity is reported, not resolved. `is_ambiguous` exists precisely so a
near-tie surfaces as a question instead of a silent pick. `CLAUDE.md` records
what happens otherwise: "Le Rocher" (Cher) matched Saint-Antoine-du-Rocher
(Indre-et-Loire) on the region alone, and "le rocher" is a genuine alias of
that commune. The rule that a QID is verified against the nearest identified
ancestor still applies - this tool supplies candidates, it does not replace
that check.

### Rendering

`handlers/duplicates_handler.py`, `handlers/audit_handler.py`,
`handlers/geocode_handler.py`, matching the existing split - pure logic in one
place, rendering in another, as `traversal.py` and
`handlers/traversal_handler.py` already do.

The renderer is where output lies to the reader: #27 shipped two defects
because traversal tests asserted on the graph and never called the formatter.
Every handler here gets tests asserting on rendered text.

## Data flow

```
find_duplicates / audit_quality
  -> collect.py: paginate /people/, /families/ via GrampsWebAPIClient
  -> facts.py:   raw dict -> PersonFacts / FamilyFacts
  -> duplicates.etager() -> MergePair[]      | rules.check_*() -> Anomaly[]
  -> merge_plan.plan_fusions() -> MergeCluster[]
  -> handler: rendered text

geocode_place
  -> places_parse.parse_pname() -> ParsedPlace
  -> registry.resolve_place() -> france | suisse | ex_communes | nominatim
  -> registry.decide_action() -> ResolvedPlace + action
  -> handler: rendered text
```

Nothing in either path writes to the tree.

## New: the server makes third-party network calls

Until now this server talked to one host, the Gramps Web API. `geocode_place`
adds `geo.api.gouv.fr`, `api3.geo.admin.ch`, `query.wikidata.org` and
`nominatim.openstreetmap.org`.

Consequences to handle rather than discover:

- **Container egress.** The MCP server runs in Docker; these hosts must be
  reachable from inside it. A blocked egress makes the tool fail, not the
  server.
- **Timeouts are per-provider**, inherited from the copied resolvers (15 s for
  `geo.api.gouv.fr`), and a slow gazetteer must not stall an MCP call
  indefinitely.
- **Rate limits are enforced locally** by `rate_limit.py`, Nominatim's for
  licence reasons.
- **Offline is a normal state.** The two detection tools keep working when a
  gazetteer is unreachable; only `geocode_place` degrades, and it must say so
  rather than return nothing.

## Error handling

- A record the converters cannot parse is skipped and counted, not fatal. The
  rendered output states how many were skipped - a silent skip would let a
  partial scan read as a complete one.
- Pagination failure mid-scan aborts and reports how far it got. "No duplicates
  found" over half a tree is worse than an error.
- A gazetteer that errors or times out is reported as such, distinctly from "no
  match found". Those two are different answers and must not render alike.
- All three tools use the existing `_format_error_response` shape.

## Testing

TDD, tests before the copied code is wired in.

**Detection tests, ported (1 075 lines / 10 files):**
`test_genealogy_duplicates.py` (55), `test_genealogy_blocking.py` (94),
`test_genealogy_merge_tiers.py` (240), `test_genealogy_merge_plan.py` (110),
`test_genealogy_merge_models.py` (63), `test_genealogy_phonetics.py` (48),
`test_genealogy_rules_person.py` (136), `test_genealogy_rules_family.py` (66),
`test_genealogy_facts.py` (145), `test_genealogy_domain.py` (118, trimmed).

**Geo tests, ported (859 lines / 7 files):**
`test_genealogy_geo_france.py` (115), `test_genealogy_geo_suisse.py` (93),
`test_genealogy_geo_registry.py` (98), `test_genealogy_geo_transitions.py`
(43), `test_genealogy_geo_nominatim.py` (59),
`test_genealogy_geo_france_ex_communes.py` (411),
`test_genealogy_places_models.py` (40).

Two adjustments during the port: the registry tests reference the DE and US
resolvers that leave `_BY_COUNTRY`, and the ex-communes tests exercise
`sparql_rows` through `requests`, which becomes `httpx`.

Copying 1 780 lines without their tests would put unverified code into a repo
whose first rule is TDD. The tests come with the code, non-negotiably.

The ported tests are offline - they replace the HTTP seam (`_http_get`, written
for exactly that) rather than calling a gazetteer, which is the one mocking
pattern `CLAUDE.md` permits. They land in the `-m "not integration"` selection.

Beyond the port:

- `collect.py` against the live tree, using `conftest.py` fixtures - the only
  new code and the only Gramps-networked component.
- Handler rendering tests, per the #27 lesson above.
- One live test per gazetteer, marked `integration`, so a provider changing its
  response shape is caught rather than silently degrading every resolution.

File-length: every copied file is under the 500-line hook limit; the largest is
`france_ex_communes.py` at 243. `test_genealogy_geo_france_ex_communes.py` at
411 is the largest test file and also fits.

## Documentation

- `resources/gramps-usage-guide.md` gains a section per tool. Not optional:
  `tests/test_alignment_*.py` hold hardcoded field inventories that fail when a
  parameter model is undocumented, and the guide is served to MCP clients - an
  undocumented parameter is one the assistant can pass but was never told
  about.
- `CLAUDE.md` records the copy decision, the provenance sha, the fact that
  drift from `crewai-custom-tools` is expected rather than a defect to repair,
  and the new third-party egress requirement.
- `README.md` tool list and, because egress is now a runtime requirement, the
  setup section.

## Out of scope

`merge_person` / `merge_family` - a separate design, already approved, that
splits `merge_type` into type-specific tools. It pairs naturally with
`find_duplicates` (detect, then merge) but stays a distinct commit series.

## Open question for review

`find_duplicates` and `audit_quality` scan a scope and return everything above
threshold. For ~1 426 people the blocking keeps this tractable, but the
rendered output of a whole-tree scan may be too long to be usable in a chat
context. If that proves true the answer is a summary-first render with
per-cluster detail on request - noted here rather than designed now, because
the real output length is not yet known.
