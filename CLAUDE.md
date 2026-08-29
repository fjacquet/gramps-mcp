### Project Awareness & Context
- **Always read `README.md`** at the start of a new conversation to understand the project's setup, features, and usage.
- **Use consistent naming conventions, file structure, and architecture patterns** following Python and MCP best practices.
- **Use uv** for all Python dependency management and command execution.
  - **Commands**: Use `uv run python` or `uv run <command>` for executing Python scripts and tests
  - **Dependencies**: Use `uv add <package>` to add dependencies, `uv sync` to install
  - **Git commits**: Use `uv run git commit` to ensure pre-commit hooks run correctly
  - **Run the server**: `uv run python -m src.gramps_mcp.server` (HTTP, port 8000) or
    `uv run python -m src.gramps_mcp.server stdio` (stdio transport)
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

### Code Structure & Modularity
- **Never create a file longer than 500 lines of code.** If a file approaches this limit, refactor by splitting it into modules or helper files.
- **Organize code into clearly separated modules**, grouped by feature or responsibility.
  For this MCP server project:
    - `server.py` - Main MCP server setup, tool registry, and routing
    - `tools/` directory - MCP tool implementations organized by feature
    - `handlers/` directory - Formats raw API responses into tool output
    - `client.py` - Gramps Web API client
    - `merge.py` - Pure merge logic for PUT updates (preserves existing
      fields/lists not mentioned in a change) - unit-tested without a live server
    - `destructive.py` - Pure decision logic for deletions/list-element removal
      (same unit-testable pattern as merge.py)
    - `auth.py` - JWT authentication handling (singleton `AuthManager`)
    - `models/` directory - Pydantic models for validation (`parameters/` per domain)
    - `config.py` - Configuration management
    - `utils.py` - Shared helpers
    - `resources/` directory - MCP resources (GQL docs, usage guide)
    - `tool_registry.py` - Single source of truth mapping tool name -> description/
      schema/handler; split out of server.py to stay under the 500-line limit
    - `traversal.py` - Pure breadth-first graph traversal of the family tree
      (rendering lives in `handlers/traversal_handler.py`)
- **Use clear, consistent imports** (prefer relative imports within packages).
- **Use python_dotenv and load_dotenv()** for environment variables.

### Testing & Reliability (TDD Approach)
- **This project follows Test-Driven Development (TDD) practices**.
- **Write tests FIRST before implementing functionality** - red, green, refactor cycle.
- **Always create Pytest integration tests for new features** (functions, classes, routes, etc).
- **Test against the real Gramps API - do not fake its behaviour.** No test
  clients and no stubbed responses standing in for the server. Setup that
  creates real records against the real server is not faking - that is what
  `tests/conftest.py` does, and tests take those records as fixture arguments
  rather than depending on another test having run. Replacing the transport
  seam alone is permitted in offline unit tests, and is what
  `tests/test_client_merge.py` and `tests/test_http_error_detail.py` do.
  Assertions must read the output of the code under test, never the stub's
  call arguments - a test that asserts on its own mock proves nothing.
- **After updating any logic**, check whether existing tests need to be updated. If so, do it.
- **Tests should live in a `/tests` folder** mirroring the main app structure.
- **Run tests frequently during development** using `uv run pytest` or `uv run pytest -xvs` for verbose output.
- **Most tests need a live Gramps Web server** (`GRAMPS_API_URL` etc. from `.env`)
  and fail with connection errors offline - this is expected, not a regression.
  Server-dependent test modules (or, within a mixed module, the classes that
  need it) carry `pytestmark = pytest.mark.integration`. To run only the
  tests that work offline: `uv run pytest -m "not integration"`. That selection
  is green. CI still runs a narrower explicit file list in
  `.github/workflows/ci.yml`, a strict subset of what the marker selects.
- **Live tests run from the macOS host need `GRAMPS_API_URL=http://localhost:80`**
  as an env override, not the `.env` value. `.env` points at
  `host.docker.internal`, which only resolves inside the container. Do not
  edit `.env` and do not commit the override.
- **`tree_stats` returns a permission error even for the owner-role account
  in `.env`.** A `tree_stats` failure ("Permission denied for this
  operation") is an environment fact, not a regression.
- **The running server comes from `docker-compose-sqllite.yml`**, on the
  upstream `ghcr.io/gramps-project/grampsweb:latest` image - *not* the local
  build in `docker/grampsweb/` (that one belongs to the pgsql compose, which
  is not running). Confirm with `docker inspect gramps-mcp-grampsweb-1
  --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'`
  before reasoning about what is installed server-side.
- **Back up the live tree before any risky change.** The client has no export
  support, so GET `/api/exporters/gramps/file` with a bearer token from
  `AuthManager`. Gzipped Gramps XML, lossless, ~500 KB. Media files are *not*
  included - the XML carries only `<object>` references.
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
- **The 500-line rule is enforced in `tests/` as well as `src/`.**
  `.pre-commit-config.yaml`'s `check-file-length` hook covers the whole tree;
  there is no exclusion for tests.


### Style & Conventions
- Use type hints throughout, format with `ruff format`, lint with `ruff`.
- **Use `pydantic` for data validation**.
- Use `httpx` for async HTTP client (no FastAPI needed for MCP servers).
- Use `MCP Python SDK` for MCP server implementation.
- **Raw Gramps object fields are not localised; profile fields are.** With
  `locale=fr`, `profile.relationship` becomes `Maries` and
  `profile.events[].type` becomes `Naissance`, while raw `family.type` stays
  `Married` and `child_ref_list[].frel` stays `Birth`. Compare against
  English constants only on raw fields, never on profile fields.
- Write **docstrings for every function** using the Google style:
  ```python
  def example():
      """
      Brief summary.

      Args:
          param1 (type): Description.

      Returns:
          type: Description.
      """
  ```

### Genealogy Data Entry Workflow
- See the `genealogiste` skill (`.claude/skills/genealogiste/`) for the full
  research/data-entry workflow (sourcing chain, media attachment, match vs.
  hypothesis handling, homonym hygiene).
- **Never pass a `gramps_id` string (e.g. `"C0619"`) into a `*_list` field
  (`citation_list`, `note_list`, etc.).** The API stores it literally as a
  broken pseudo-handle, invisible until GEDCOM export crashes with
  `HandleError`. Always copy the real handle from the tool's own return
  value. To audit the whole tree for this: fetch every entity via the REST
  API, collect all real handles, then walk every `*_list` field checking
  each ref against that set - `0 broken references found` is the target.
- **`create_sourced_event` always creates a brand-new event** - it never
  matches an existing one for the person/family. To add a corroborating
  citation or correct a date on an event that already exists, call
  `create_event` with that event's real `handle` instead, or you end up
  with an orphan duplicate event alongside the original.
- **`create_family`'s `child_handles`/`father_handle`/`mother_handle` only
  link the family side.** The child person record's own
  `parent_family_list` is not set automatically - call `create_person` with
  `parent_family_list: [<family handle>]` separately, or ancestor lookups
  from the child fail silently.
- **Surname casing: no international standard mandates uppercase.** GEDCOM
  5.5.1 explicitly says the opposite - "capitalize the first letter of each
  part and lowercase the other letters" - and FamilySearch follows that.
  ALL-CAPS surname (`JACQUET`) is a French-specific formal/international-
  correspondence convention, not a universal genealogy rule. Do not write
  surnames upper-case against Gramps to "fix" casing; store Title Case
  (`Jacquet`), matching GEDCOM and the sibling `genecrew` repo's tested
  `GrampsUpdateNameTool` invariant (recases `JACQUET`->`Jacquet`, never the
  reverse). Verified 2026-08-16 via GEDCOM spec + MyHeritage/tamurajones
  naming-convention references.

### Documentation & Explainability
- **Update `README.md`** when new features are added, dependencies change, or setup steps are modified.
- **Comment non-obvious code** and ensure everything is understandable to a mid-level developer.
- When writing complex logic, **add an inline `# Reason:` comment** explaining the why, not just the what.

### AI Behavior Rules
- **Never assume missing context. Ask questions if uncertain.**
- **Never hallucinate libraries or functions** – only use known, verified Python packages.
- **Always confirm file paths and module names** exist before referencing them in code or tests.
- **Never delete or overwrite existing code** unless explicitly instructed to
- **Do not use emojis in the code** to maintain a clean and professional coding style.
- **Never use `git stash` or `git reset --hard`.** Both have destroyed
  uncommitted work in this repo. Compare against `main` with `git show
  main:<path>`; move a misplaced commit with `git branch <name> <sha>` then
  `git reset --keep`. If work is lost anyway, pre-commit archives unstaged
  files at every commit: `ls -lat ~/.cache/pre-commit/patch*`, then
  `git apply <patch>`.