# GOQL migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the MCP server work on gramps-webapi 3.25.2 and 3.26.0 by replacing every `gql` request with a `rules=MatchesQuery` GOQL filter.

**Architecture:** One pure function `build_rules(expr)` produces the `rules` parameter; `GrampsWebAPIClient.make_api_call` swaps a `gql` param for `rules` on GET calls, so callers keep passing an expression. Lookups, traversal and `find_type` change only their expression text (`=` becomes `==`). No version detection.

**Tech Stack:** Python 3.13, httpx2, pydantic, pytest against the local Gramps Web stack (`docker-compose.test.yml`), mkdocs.

**Spec:** `docs/superpowers/specs/2026-11-22-goql-migration-design.md`

## Global Constraints

- Tests run against the real local server; no fakes (CLAUDE.md). Offline unit tests only for pure functions.
- Never write a file over 500 lines (pre-commit hook covers `tests/`).
- Google-style docstrings, type hints, no emoji, `ruff` and `ruff format` clean.
- Use `uv run ...` from the repo root; commit with `uv run git commit -F <file>`.
- `gramps_id=` as a query parameter is not a filter; never use it to resolve a record.
- Test stack: `docker compose -f docker-compose.test.yml up -d`, then `uv run python scripts/seed_test_tree.py` (re-seed after switching image).
- Work on branch `feat/goql-migration`, not `main`. Merge with `--merge`.

## Review Focus

- Hostile id (`X" or gramps_id != "X`) must not widen a lookup that feeds delete: Task 4.
- Missing id returns an empty list, never an error or an arbitrary record: Task 4.
- Accented names (`Müller`, `Raucaz-Étienne`) survive the JSON-encoded `rules`: Task 3.
- `X-Total-Count` still comes back with `pagesize=1`, so totals tests keep working: Task 3.
- An expression in the old dialect (`class = person`, `~`) gives a readable error naming GOQL, not a raw 422: Task 5.

---

### Task 1: Image tag variable and baseline

**Files:**
- Modify: `docker-compose.test.yml:16`
- Test: none (infrastructure)

**Interfaces:**
- Produces: env var `GRAMPSWEB_TAG` selecting the server image; default is the 3.25.2 tag.

- [ ] **Step 1: Find the real tag names**: `docker manifest inspect ghcr.io/gramps-project/grampsweb:v3.25.2` (try `3.25.2` if it fails). Record the working form.
- [ ] **Step 2: Change line 16 to** `image: ghcr.io/gramps-project/grampsweb:${GRAMPSWEB_TAG:-<working 3.25.2 tag>}`. Note: the celery service in the same file uses the same image; give it the same variable.
- [ ] **Step 3: Verify both versions start**: `GRAMPSWEB_TAG=<3.25.2 tag> docker compose -f docker-compose.test.yml up -d --force-recreate`, seed, then `docker exec grampsweb_test pip show gramps-webapi | grep Version` prints `3.25.2`. Repeat with the 3.26.0 tag and expect `3.26.0`.
- [ ] **Step 4: Baseline**: on 3.26.0 run `uv run pytest -q -p no:warnings 2>&1 | tail -3`; save the failing count (about 40) in the commit message.
- [ ] **Step 5: Commit** `chore(test): parameterise the Gramps Web image tag`.

### Task 2: `build_rules`

**Files:**
- Create: `src/gramps_mcp/goql.py`
- Test: `tests/test_goql.py`

**Interfaces:**
- Produces: `build_rules(expr: str) -> str` returning the JSON text of `{"function":"and","rules":[{"name":"MatchesQuery","values":[expr]}]}`.

- [ ] **Step 1: Write failing tests** in `tests/test_goql.py` (offline, pure): `test_build_rules_shape` loads the result with `json.loads` and asserts `["rules"][0]["name"] == "MatchesQuery"`, `["rules"][0]["values"] == ['gramps_id == "I0001"']`, `["function"] == "and"`; `test_build_rules_keeps_unicode` asserts `json.loads(build_rules('surname == "Müller"'))["rules"][0]["values"][0] == 'surname == "Müller"'`.
- [ ] **Step 2: Run** `uv run pytest tests/test_goql.py -v`; expect ImportError.
- [ ] **Step 3: Implement** `build_rules` with `json.dumps(..., ensure_ascii=False)`.
- [ ] **Step 4: Run again**; expect 2 passed.
- [ ] **Step 5: Commit** `feat(goql): add build_rules for the 3.26 MatchesQuery filter`.

### Task 3: Client sends `rules` instead of `gql`

**Files:**
- Modify: `src/gramps_mcp/client.py` (in `make_api_call`, where `request_params = params_dict`, about line 428)
- Test: `tests/test_client_rules.py` (integration)

**Interfaces:**
- Consumes: `build_rules` from Task 2.
- Produces: any GET call whose params include `gql: str` is sent with `rules=<build_rules(gql)>` and no `gql`; callers and parameter models are unchanged.

- [ ] **Step 1: Write failing integration tests** (`pytestmark = pytest.mark.integration`, use the existing `client` fixture style from `tests/test_client.py`): `test_gql_param_filters_people` calls `ApiCalls.GET_PEOPLE` with `{"gql": 'gramps_id == "I0001"', "pagesize": 1}` and asserts the single result's `gramps_id == "I0001"`; `test_total_count_header_survives` uses `with_headers=True` and asserts `X-Total-Count == "1"`; `test_unicode_expression` queries `primary_name.surname_list.any.surname == "Raucaz"` (pick a surname that exists in the seeded tree, found with one `find_type` read) and asserts at least one hit.
- [ ] **Step 2: Run on the 3.26 stack**; expect 422 `Unknown field`.
- [ ] **Step 3: Implement**: after `request_params = params_dict`, if `"gql"` is in it, pop it and set `request_params["rules"] = build_rules(expr)`. One comment (`# Reason:`) naming 3.26 removing `gql`.
- [ ] **Step 4: Run on 3.26 and on 3.25.2** (Task 1 variable); expect pass on both.
- [ ] **Step 5: Commit** `feat(client): send gql expressions as MatchesQuery rules`.

### Task 4: Lookups and delete safety

**Files:**
- Modify: `src/gramps_mcp/utils.py:181,211,240`, `src/gramps_mcp/traversal.py:94`, `src/gramps_mcp/tools/search_details.py:146`, `src/gramps_mcp/tools/destructive.py:111`
- Test: `tests/test_destructive_resolve.py`, `tests/test_get_type_resolution.py`, `tests/test_traversal.py`

**Interfaces:**
- Consumes: Task 3 client behaviour.

- [ ] **Step 1: Write failing tests** in `tests/test_destructive_resolve.py`: `test_hostile_id_matches_nothing` resolves the id `X" or gramps_id != "X` for a person and asserts it raises the existing not-found error; `test_missing_id_is_empty_not_error` resolves `I9999999` and asserts the existing "no match" outcome rather than an arbitrary record.
- [ ] **Step 2: Run**; expect failures from the `=` dialect (422).
- [ ] **Step 3: Change the five expressions** from `gramps_id="..."` / `gramps_id = "..."` / `title="..."` to `==`. Keep `escape_gql_literal`. Replace the stale `Reason:` comment in `search_details.py:128-139` so it says why `gramps_id=` is not used (it does not filter).
- [ ] **Step 4: Run** `uv run pytest tests/test_destructive_resolve.py tests/test_get_type_resolution.py tests/test_traversal.py tests/test_traversal_relationships.py -v` on both servers; expect pass.
- [ ] **Step 5: Commit** `fix(lookups): use GOQL equality in resolvers`.

### Task 5: `find_type` and the readable error

**Files:**
- Modify: `src/gramps_mcp/tools/search_basic.py:382-390`, `src/gramps_mcp/client.py` (error path), `src/gramps_mcp/models/parameters/base_params.py:174-215`, `src/gramps_mcp/models/parameters/simple_params.py:51`, `src/gramps_mcp/tool_registry.py:110`
- Test: `tests/test_search_find_type.py`, `tests/test_search_totals.py`, `tests/test_search_basic.py`, `tests/test_strict_params.py`

**Interfaces:**
- Consumes: Task 3. Produces: a `GrampsAPIError` whose message contains `GOQL` and `gql://documentation` when the server rejects an expression with 422 `invalid_query` or `unknown field`.

- [ ] **Step 1: Rewrite the `gql=` expressions in the four test files** to GOQL (`=` to `==`, `~ "x"` to `"x" in field`, drop `class = x and`, replace `.length` with the working form found in Task 7 step 1). Add `test_old_dialect_gives_goql_hint`: `find_type(type="person", gql='class = person')` returns text containing `GOQL`.
- [ ] **Step 2: Run**; expect failures.
- [ ] **Step 3: Update Field descriptions and the tool description** to say GOQL; add the hint in the client's 422 branch (reuse the existing error-detail path in `_make_request`).
- [ ] **Step 4: Run the four files on both servers**; expect pass.
- [ ] **Step 5: Commit** `feat(find_type): GOQL expressions and a readable rejection`.

### Task 6: Remaining test files

**Files:**
- Modify: `tests/test_workflow_marriage.py`, `tests/workflow_helpers.py`, `tests/test_server.py`, `tests/test_workflow_attributes.py`, `tests/test_create_people.py`, `tests/test_create_sourced_event.py`, `tests/test_relationship_tools.py`, `tests/test_analysis.py`, `tests/test_user_tools.py`

- [ ] **Step 1: Run the suite on 3.26** and list the files still failing with `gql` 422.
- [ ] **Step 2: Rewrite each `gql` expression** the way Task 5 does.
- [ ] **Step 3: Run the full suite** `uv run pytest -q -p no:warnings`; the only failures left must be the `urls` and media ones (Tasks 9 and 10).
- [ ] **Step 4: Commit** `test: move gql expressions to GOQL`.

### Task 7: Documentation rewrite with doc-as-test

**Files:**
- Modify: `src/gramps_mcp/resources/gql-documentation.md`, `src/gramps_mcp/resources/gramps-usage-guide.md`, `docs/user-guide/searching.md`, `.claude/skills/genealogiste/SKILL.md`
- Create: `tests/test_doc_examples.py`
- Modify: `tests/test_alignment_*.py` inventories if the guide gains or loses fields

- [ ] **Step 1: Establish the grammar**: read `gramps_object_query_language/query_lang.py` and the per-type specs in the container (`docker exec grampsweb_test sh -c 'sed -n 1,200p /venv/lib/python3.13/site-packages/gramps_object_query_language/query_lang.py'`). Find the working forms for: event type (`type.string == "Birth"` returns 0 today), list length, `any`/`all`, containment. Record each as a verified example.
- [ ] **Step 2: Write `tests/test_doc_examples.py`** (integration): extract every `gql='...'` and `gql="..."` example from the two resource files with a regex; skip examples containing `<` (placeholders); run each through `find_type`-equivalent `client.make_api_call(GET_<plural>, {"gql": expr, "pagesize": 1})`; assert it does not raise. Examples marked with the HTML comment `<!-- rows -->` on the line above must also return at least 1 row. (Adjusted from the spec's "more than 0 rows": names such as "Smith" cannot hit the seeded tree, so parse-validity is required for all and a row is required for the marked ones.)
- [ ] **Step 3: Run**; expect the old-dialect examples to fail.
- [ ] **Step 4: Rewrite the 413-line `gql-documentation.md` as GOQL** (syntax, operators, properties per type from Step 1) and every example in the usage guide; mark generic examples with `<!-- rows -->`.
- [ ] **Step 5: Run `uv run pytest tests/test_doc_examples.py tests/test_alignment_*.py -v`**; expect pass.
- [ ] **Step 6: Commit** `docs: teach GOQL in the usage guide and resource`.

### Task 8: Spec drift check and refreshed reference

**Files:**
- Create: `scripts/check_spec_drift.py`, `tests/test_spec_drift.py`
- Modify: `docs/reference/openapi.json`, `docs/reference/gramps-web-api.md`

**Interfaces:**
- Produces: `diff_specs(old: dict, new: dict) -> dict[str, list[str]]` with keys `removed_params`, `added_params`, `removed_paths`, `added_paths`, each entries like `GET /api/people/:gql`.

- [ ] **Step 1: Write failing tests** `tests/test_spec_drift.py` (pure): two small spec dicts where `new` drops `gql` from `/api/people/` GET and adds a path; assert `removed_params == ["GET /api/people/:gql"]` and `added_paths == ["/api/x/"]`.
- [ ] **Step 2: Run**; expect ImportError.
- [ ] **Step 3: Implement** `diff_specs` plus a `main(url)` that logs in with `AuthManager`, GETs `/api/openapi.json`, loads the vendored file and prints the report.
- [ ] **Step 4: Run tests**; expect pass.
- [ ] **Step 5: Refresh the vendored spec** from the test stack on 3.26.0 (GET with a token, write `docs/reference/openapi.json`), run `uv run python scripts/gen_api_reference.py`, then `uv run --with mkdocs-material mkdocs build --strict`; expect success.
- [ ] **Step 6: Commit** `feat(scripts): spec drift check; vendor the 3.26.0 spec`.

### Task 9: `urls` rejections (investigation first)

**Files:**
- Modify: whichever model or `merge.py` path injects `description` into Url or `urls` into Family (find in step 2)
- Test: `tests/test_create_people.py`, `tests/test_create_records.py`, `tests/test_workflow_attributes.py`

- [ ] **Step 1: Reproduce**: run `uv run pytest tests/test_create_people.py tests/test_create_records.py -q -p no:warnings` on 3.26 and copy the two 400 messages (`unknown Url keys: 'description'`, `unknown Family keys: 'urls'`).
- [ ] **Step 2: Find the cause**: grep `description` and `urls` in `src/gramps_mcp/models/` and `merge.py`; compare with the 3.26 `Url` and `Family` schemas (`jq '.components.schemas|keys' ` on the saved spec). Decide: drop the field, or send it only when the server supports it. Record the decision in the commit message.
- [ ] **Step 3: Fix with a failing test first** (existing tests are the red); run on 3.25.2 and 3.26.0; expect pass on both.
- [ ] **Step 4: Commit** `fix(models): stop sending urls keys the 3.26 server rejects`.

### Task 10: Media 415

**Files:**
- Modify: `src/gramps_mcp/client.py` (`upload_media_file`, about line 469) or the test, per findings
- Test: `tests/test_client.py`, `tests/test_upload_request_path.py`

- [ ] **Step 1: Reproduce**: run both tests on 3.26; one expects "Server error" but gets `415 Media type not supported`.
- [ ] **Step 2: Decide whether the test or the client is wrong**: the test deliberately posts a bad media type; if 3.26 now answers 415 for it, update the assertion to the new status and keep a comment citing the change. If a real upload now fails, fix the content type handling.
- [ ] **Step 3: Run on both servers**; expect pass.
- [ ] **Step 4: Commit** with the decision in the message.

### Task 11: Final docs and full verification

**Files:**
- Modify: `README.md`, `CLAUDE.md` (stack versions, test counts, pinned tag note), `docs/` pages that mention the server version

- [ ] **Step 1: Update** README (tested server versions 3.25.2 and 3.26.0, `GRAMPSWEB_TAG`) and CLAUDE.md (the "813 passed" line, the 3.21.1 mentions, the `gramps_id=` warning).
- [ ] **Step 2: Decide `grampsweb-docs/apispec.yaml`**: `git log -- grampsweb-docs/apispec.yaml` and grep for references; if nothing references it, delete it in its own commit.
- [ ] **Step 3: Full verification**: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/gramps_mcp --ignore-missing-imports`; the suite on 3.25.2 then on 3.26.0 (`uv run pytest -q -p no:warnings`), both fully green; `mkdocs build --strict`.
- [ ] **Step 4: Open the PR** with `gh pr create --repo fjacquet/gramps-mcp`; merge with `--merge` after review. Bump the version (`pyproject.toml`, `__init__.py`, `uv lock` in one commit) only when releasing.
