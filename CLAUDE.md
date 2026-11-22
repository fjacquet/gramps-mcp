### Project Awareness & Context
- **Use uv** for all Python dependency management and command execution.
  - **Commands**: `uv run python` / `uv run <command>`. Run them **from the repo
    root**: a `cd` elsewhere in the same compound command selects another project
    and breaks the venv (`ModuleNotFoundError: httpx`).
  - **Pillow is not a dependency**: `uv run --with pillow python` to read, crop or convert a scan.
  - **Git commits**: `uv run git commit`, so pre-commit hooks run correctly
  - **Run the server**: `uv run python -m src.gramps_mcp.server` (HTTP, port 8000)
    or `uv run python -m src.gramps_mcp.server stdio` (stdio transport)
  - **Type check**: `uv run mypy src/gramps_mcp --ignore-missing-imports`
  - **First-time setup**: `uv run pre-commit install` so ruff/ruff-format/copyright/
    file-length/no-emoji hooks run automatically on commit
  - **Docs site**: `uv run --with mkdocs-material mkdocs build --strict` before
    pushing anything under `docs/`. Strict mode fails on broken internal links,
    which is the usual way a docs change breaks the published site.
  - **Release**: bump `pyproject.toml` and `src/gramps_mcp/__init__.py`, then run
    `uv lock` **in the same commit**. `uv.lock` pins the project's own version and
    CI runs `uv sync --locked`, so a bump without it turns `main` red while the
    Docker publish stays green - the breakage is invisible from the release page.
  - **Pull requests**: this is a fork, so `gh pr create` needs
    `--repo fjacquet/gramps-mcp`; without it the error names a token problem,
    which is misleading. Merge with `--merge`, never `--squash`.
  - **`.mcp.json`** (project-scoped) wires up `context7` and `github` MCP
    servers for every contributor; `.claude/skills,agents,hooks/` are
    tracked too (only `settings.local.json`, `RESUME.md`, `tdd-guard/` stay
    local).

### Code Structure & Modularity
- **Never create a file longer than 500 lines.** Enforced in `tests/` as well as
  `src/`: `.pre-commit-config.yaml`'s `check-file-length` hook covers the whole
  tree, with no exclusion for tests.
- Layout is `ls src/gramps_mcp/`; only these carry non-obvious intent:
  - `merge.py` - pure merge logic for PUT updates, preserving fields and lists a
    change does not mention; unit-tested without a live server
  - `destructive.py` - same unit-testable pattern for deletions and list-element
    removal
  - `tool_registry.py` - tool name -> description/schema/handler, split out of
    `server.py` to stay under the 500-line limit
  - `traversal.py` - pure breadth-first graph traversal; rendering lives apart in
    `handlers/traversal_handler.py`
  - `genealogy/` - pure detection logic (duplicate blocking, consistency
    rules R1-R9 plus completeness rules D1-D3, merge planning, place
    resolvers) **copied** from
    fjacquet/crewai-custom-tools v0.31.1 (19d78f7). The duplication is
    deliberate, decided by the repo owner; divergence from that repo is
    expected and is not a defect to repair. Each file's docstring names its
    origin. Do not "fix" this by re-unifying the two copies.

### Testing & Reliability (TDD Approach)
- **Write tests first**, red-green-refactor, and update existing tests when the
  logic they cover changes. Tests live in `/tests`, mirroring the app structure.
- **Test against the real Gramps API - do not fake its behaviour.** No test
  clients and no stubbed responses standing in for the server. Setup that
  creates real records against the real server is not faking - that is what
  `tests/conftest.py` does, and tests take those records as fixture arguments
  rather than depending on another test having run. Replacing the transport
  seam alone is permitted in offline unit tests, and is what
  `tests/test_client_merge.py` and `tests/test_http_error_detail.py` do.
  Assertions must read the output of the code under test, never the stub's
  call arguments - a test that asserts on its own mock proves nothing.
- **The tests never touch the live tree.** `tests/conftest.py` calls
  `local_stack.apply_test_environment()` at import time, which points
  `GRAMPS_API_URL` at the local stack and refuses any host outside
  `localhost`, `127.0.0.1`, `::1`, `host.docker.internal`. pytest does not
  read `.env` at all. `scripts/backup_prod.py` is the only thing in the
  repository that still talks to the live server.
- **Starting the test environment**, in this order:
  ```bash
  uv run python scripts/backup_prod.py      # once; reads the live tree
  docker compose -f docker-compose.test.yml up -d
  uv run python scripts/seed_test_tree.py   # restores the backup, idempotent
  uv run pytest                             # 813 passed, 1 skipped
  ```
  `backup/` and `tests/.local-tree-id` are gitignored: the first holds real
  data on living people and this repository is public, the second holds a
  UUID minted when the stack's volumes are created. Re-running the seed
  script also wipes whatever residue a failed teardown left behind - the
  restore replaces the tree's contents rather than adding to them.
- **Integration tests still carry `pytestmark = pytest.mark.integration`**
  (32 modules, 157 tests) and still need the stack running.
  `uv run pytest -m "not integration"` (657 tests) passes with the stack
  down, which is what CI runs - `.github/workflows/ci.yml` names the
  `tests/` directory and the marker filter, no allowlist.
- **Raw REST and API-shape gotchas** (no `/api` suffix, token rate limit, raw `PUT` forbidden, POST/PUT return lists, parameter models requiring fields, `create_event` place handle, media on persons, bulk lots, backups, GEDCOM extension, `tree_stats`, third-party hosts): see the `gramps-rest-recovery` skill. Load it before any raw REST call or `make_api_call` script.
- **The MCP server runs in Docker**, container `gramps-mcp-gramps-mcp-1` on the
  published image `ghcr.io/fjacquet/gramps-mcp:latest`, exposed on
  `http://localhost:8000/mcp` (what `.mcp.json` targets). So it executes the
  image, not the working tree - verify a fix from source - and any `media_path`
  must be staged inside it first
  (`docker cp <file> gramps-mcp-gramps-mcp-1:/tmp/`). The repo's compose files
  describe the old local-backend setup and do not serve the live tree.
- **Traversal tests must assert on the rendered output, not only on
  `TraversalResult.edges`.** Two defects shipped in #27 because the tests
  checked the graph and never called `format_traversal` on the tree they had
  just built. The renderer is where the output lies to the reader.
- **The `tests/test_alignment_*.py` modules hold hardcoded field inventories
  that must track `src/gramps_mcp/resources/gramps-usage-guide.md`.** Adding a
  field to a parameter model without documenting it in that guide fails these
  tests. They are doing their job: the guide is served to MCP clients, so an
  undocumented parameter is one the assistant can pass but was never told
  about. Fix the guide, then the inventory - not the inventory alone.
- **The parameter models ignore unknown keys.** Pydantic's default
  `extra="ignore"` applies, so a test passing a field name a model does not
  declare has that field silently dropped - the call still succeeds and the
  test can still pass while exercising nothing. Check a key against the model
  in `src/gramps_mcp/models/parameters/` before trusting a test that uses it.

### Style & Conventions
- Type hints throughout, Google-style docstrings on every function, `ruff format`
  and `ruff` clean, no emoji in code.
- **Raw Gramps object fields are not localised; profile fields are.** With
  `locale=fr`, `profile.relationship` becomes `Maries` and
  `profile.events[].type` becomes `Naissance`, while raw `family.type` stays
  `Married` and `child_ref_list[].frel` stays `Birth`. Compare against
  English constants only on raw fields, never on profile fields.
- When writing complex logic, add an inline `# Reason:` comment explaining the
  why, not the what. Update `README.md` when features, dependencies or setup
  steps change.

### Genealogy Data Entry Workflow
Other data-entry gotchas (occupations as events, bilingual text, `attribute_list`, `create_sourced_event`, `create_family` links): see the `genealogiste` skill.

- **Never pass a `gramps_id` string (e.g. `"C0619"`) into a `*_list` field
  (`citation_list`, `note_list`, etc.).** The API stores it literally as a
  broken pseudo-handle, invisible until GEDCOM export crashes with
  `HandleError`. Always copy the real handle from the tool's own return
  value. The same failure shows up in other shapes too: a citation's
  `source_handle` set to its own handle (copy-paste between two params in
  one call), or another record's handle landing in the wrong field
  entirely - the fix and the audit are identical either way. To audit the
  whole tree: fetch every entity via the REST API, collect all real
  handles, then walk every `*_list` field *and* every single-handle field
  (`source_handle`, `father_handle`, `mother_handle`, `place`) checking
  each ref against the right handle set - `0 broken references found` is
  the target. Packaged as the `gramps-rest-recovery` skill.

### AI Behavior Rules
- **Never use `git stash` or `git reset --hard`.** Both have destroyed
  uncommitted work in this repo. Compare against `main` with `git show
  main:<path>`; move a misplaced commit with `git branch <name> <sha>` then
  `git reset --keep`. If work is lost anyway, pre-commit archives unstaged
  files at every commit: `ls -lat ~/.cache/pre-commit/patch*`, then
  `git apply <patch>`.
