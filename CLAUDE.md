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
    - `auth.py` - JWT authentication handling (singleton `AuthManager`)
    - `models/` directory - Pydantic models for validation (`parameters/` per domain)
    - `config.py` - Configuration management
    - `utils.py` - Shared helpers
    - `resources/` directory - MCP resources (GQL docs, usage guide)
- **Use clear, consistent imports** (prefer relative imports within packages).
- **Use python_dotenv and load_dotenv()** for environment variables.

### Testing & Reliability (TDD Approach)
- **This project follows Test-Driven Development (TDD) practices**.
- **Write tests FIRST before implementing functionality** - red, green, refactor cycle.
- **Always create Pytest integration tests for new features** (functions, classes, routes, etc).
- **Test against the real Gramps API - do not fake its behaviour.** No
  fixtures, no test clients, no stubbed responses standing in for the server.
  Replacing the transport seam alone is permitted in offline unit tests, and is
  what `tests/test_client_merge.py` and `tests/test_http_error_detail.py` do.
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
- **`tests/test_parameter_alignment.py` holds hardcoded field inventories that
  must track `src/gramps_mcp/resources/gramps-usage-guide.md`.** Adding a field
  to a parameter model without documenting it in that guide fails this test.
  It is doing its job: the guide is served to MCP clients, so an undocumented
  parameter is one the assistant can pass but was never told about. Fix the
  guide, then the inventory - not the inventory alone.
- **Several `tests/test_data_management.py` tests depend on running in order**,
  passing handles from one to the next. Run alone they fail with "No repository
  handle available from previous test". Run the module, not the single test.
- **The 500-line rule is not enforced in `tests/`.** `.pre-commit-config.yaml`
  excludes `^tests/` from `check_file_length`, and three test files already
  exceed it. The rule still applies when you write there; nothing will stop you.


### Style & Conventions
- Use type hints throughout, format with `ruff format`, lint with `ruff`.
- **Use `pydantic` for data validation**.
- Use `httpx` for async HTTP client (no FastAPI needed for MCP servers).
- Use `MCP Python SDK` for MCP server implementation.
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
- **Never use `git stash`.** Compare against `main` with `git show
  main:<path>` instead. An uncommitted change was lost in this repo, most
  likely to a stash cycle.