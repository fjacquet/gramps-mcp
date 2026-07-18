# Configurable HTTP Host/Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the MCP server's HTTP bind address/port be set via `GRAMPS_MCP_HOST`/`GRAMPS_MCP_PORT` environment variables, defaulting to today's hardcoded `0.0.0.0:8000` when unset.

**Architecture:** Two new optional fields on the existing `Settings` model in `config.py`, read with `os.environ.get(KEY, default)` (unlike the four required `GRAMPS_*` fields, which use `os.environ[KEY]` and raise if missing). `server.py`'s two hardcoded assignment lines are replaced with reads from `get_settings()`.

**Tech Stack:** Python, pydantic, python-dotenv (already in use — no new dependencies).

Spec: `docs/superpowers/specs/2026-07-18-configurable-host-port-design.md`

## Global Constraints

- Run everything through uv. Commit via `uv run git commit` (pre-commit hooks installed: ruff, ruff-format, copyright-notice on `.py` files, file-length check, no-emoji check).
- Never `git add -A` or `git add .` — the working tree may contain the user's unrelated WIP (`docker-compose.yml`, `docker/`). Stage only the files this task names.
- Defaults must be exactly `"0.0.0.0"` (host) and `8000` (port) — matching the current hardcoded values in `server.py`, so existing deployments (Docker, docker-compose) see zero behavior change if they don't set the new variables.
- The four existing required settings (`gramps_api_url`, `gramps_username`, `gramps_password`, `gramps_tree_id`) keep using `os.environ[...]` (raise if missing) — the two new ones use `os.environ.get(..., default)` (never raise for being absent; only raise if the port value present isn't a valid integer).
- `uv run ruff check src/` and `uv run mypy src/gramps_mcp --ignore-missing-imports` must stay clean.

---

### Task 1: Configurable host/port end to end

**Files:**
- Modify: `src/gramps_mcp/config.py` (`Settings` class, `get_settings()`)
- Modify: `src/gramps_mcp/server.py:359-361`
- Modify: `tests/test_config.py` (add 3 new test functions)
- Modify: `.env.example`
- Modify: `README.md` (the "Environment Configuration" section, lines 140-150)

**Interfaces:**
- Consumes: nothing from other work.
- Produces: `Settings.gramps_mcp_host: str`, `Settings.gramps_mcp_port: int` — read by `server.py`'s `if __name__ == "__main__":` block. Nothing else in the codebase consumes these.

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py` currently starts like this:

```python
"""Unit tests for configuration helpers - pure functions, no API needed."""

from pydantic import HttpUrl

from src.gramps_mcp.config import Settings, get_api_base_url
```

Change the import line to also bring in `get_settings`, and add `pytest`:

```python
"""Unit tests for configuration helpers - pure functions, no API needed."""

import pytest
from pydantic import HttpUrl

from src.gramps_mcp.config import Settings, get_api_base_url, get_settings
```

Append these three test functions at the end of the file:

```python
def test_get_settings_defaults_host_and_port(monkeypatch):
    monkeypatch.setenv("GRAMPS_API_URL", "https://gramps.example.com")
    monkeypatch.setenv("GRAMPS_USERNAME", "user")
    monkeypatch.setenv("GRAMPS_PASSWORD", "password")
    monkeypatch.setenv("GRAMPS_TREE_ID", "tree1")
    monkeypatch.delenv("GRAMPS_MCP_HOST", raising=False)
    monkeypatch.delenv("GRAMPS_MCP_PORT", raising=False)

    settings = get_settings()

    assert settings.gramps_mcp_host == "0.0.0.0"
    assert settings.gramps_mcp_port == 8000


def test_get_settings_reads_explicit_host_and_port(monkeypatch):
    monkeypatch.setenv("GRAMPS_API_URL", "https://gramps.example.com")
    monkeypatch.setenv("GRAMPS_USERNAME", "user")
    monkeypatch.setenv("GRAMPS_PASSWORD", "password")
    monkeypatch.setenv("GRAMPS_TREE_ID", "tree1")
    monkeypatch.setenv("GRAMPS_MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("GRAMPS_MCP_PORT", "9000")

    settings = get_settings()

    assert settings.gramps_mcp_host == "127.0.0.1"
    assert settings.gramps_mcp_port == 9000
    assert isinstance(settings.gramps_mcp_port, int)


def test_get_settings_rejects_non_numeric_port(monkeypatch):
    monkeypatch.setenv("GRAMPS_API_URL", "https://gramps.example.com")
    monkeypatch.setenv("GRAMPS_USERNAME", "user")
    monkeypatch.setenv("GRAMPS_PASSWORD", "password")
    monkeypatch.setenv("GRAMPS_TREE_ID", "tree1")
    monkeypatch.setenv("GRAMPS_MCP_PORT", "not-a-number")

    with pytest.raises(ValueError):
        get_settings()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_config.py -q
```

Expected: the 3 new tests fail — `test_get_settings_defaults_host_and_port` and
`test_get_settings_reads_explicit_host_and_port` fail with
`pydantic_core._pydantic_core.ValidationError` (unexpected keyword arguments
`gramps_mcp_host`/`gramps_mcp_port` don't exist yet — actually `get_settings()`
doesn't pass them yet, so instead expect `AttributeError:
'Settings' object has no attribute 'gramps_mcp_host'`); the third test fails
because no `ValueError` is raised (there's nothing yet reading
`GRAMPS_MCP_PORT` at all). The existing 3 tests in the file still pass.

- [ ] **Step 3: Implement the config changes**

In `src/gramps_mcp/config.py`, change the `Settings` class from:

```python
class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # Gramps Web API Configuration
    gramps_api_url: HttpUrl = Field(..., description="Base URL for Gramps Web API")
    gramps_username: str = Field(..., description="Username for Gramps Web API")
    gramps_password: str = Field(..., description="Password for Gramps Web API")
    gramps_tree_id: str = Field(..., description="Family tree identifier")
```

to:

```python
class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # Gramps Web API Configuration
    gramps_api_url: HttpUrl = Field(..., description="Base URL for Gramps Web API")
    gramps_username: str = Field(..., description="Username for Gramps Web API")
    gramps_password: str = Field(..., description="Password for Gramps Web API")
    gramps_tree_id: str = Field(..., description="Family tree identifier")

    # MCP HTTP Server Configuration
    gramps_mcp_host: str = Field(
        "0.0.0.0", description="Host/interface for the MCP HTTP server to bind to"
    )
    gramps_mcp_port: int = Field(
        8000, description="Port for the MCP HTTP server to listen on"
    )
```

Change `get_settings()` from:

```python
def get_settings() -> Settings:
    """Get settings from environment variables."""
    try:
        return Settings(
            gramps_api_url=HttpUrl(os.environ["GRAMPS_API_URL"]),
            gramps_username=os.environ["GRAMPS_USERNAME"],
            gramps_password=os.environ["GRAMPS_PASSWORD"],
            gramps_tree_id=os.environ["GRAMPS_TREE_ID"],
        )
    except KeyError as e:
        raise ValueError(f"Missing required environment variable: {e}")
    except ValidationError as e:
        raise ValueError(f"Invalid configuration: {e}")
```

to:

```python
def get_settings() -> Settings:
    """Get settings from environment variables."""
    try:
        return Settings(
            gramps_api_url=HttpUrl(os.environ["GRAMPS_API_URL"]),
            gramps_username=os.environ["GRAMPS_USERNAME"],
            gramps_password=os.environ["GRAMPS_PASSWORD"],
            gramps_tree_id=os.environ["GRAMPS_TREE_ID"],
            gramps_mcp_host=os.environ.get("GRAMPS_MCP_HOST", "0.0.0.0"),
            gramps_mcp_port=int(os.environ.get("GRAMPS_MCP_PORT", "8000")),
        )
    except KeyError as e:
        raise ValueError(f"Missing required environment variable: {e}")
    except ValidationError as e:
        raise ValueError(f"Invalid configuration: {e}")
```

(The `int(...)` conversion happening inside the `try` means a non-numeric
`GRAMPS_MCP_PORT` raises Python's built-in `ValueError` directly — it isn't a
`KeyError` or a pydantic `ValidationError`, so neither `except` clause
catches it, and it propagates unchanged. Since it's already a `ValueError`,
that's exactly the exception type `get_settings()`'s callers already expect
from this function — no new `except` clause is needed.)

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_config.py -q
```

Expected: `6 passed` (3 existing + 3 new).

- [ ] **Step 5: Wire `server.py`**

In `src/gramps_mcp/server.py`, the block at lines 358-361 currently reads:

```python
    else:
        # Run the FastMCP server with streamable HTTP transport
        # Configure server settings
        app.settings.host = "0.0.0.0"  # Listen on all interfaces for Docker
        app.settings.port = 8000
```

Replace it with:

```python
    else:
        # Run the FastMCP server with streamable HTTP transport
        # Configure server settings
        settings = get_settings()
        app.settings.host = settings.gramps_mcp_host
        app.settings.port = settings.gramps_mcp_port
```

`get_settings` is already imported at the top of `server.py` (it's used
elsewhere in the file, e.g. inside `TreeInfoParams`-adjacent tool code paths)
— no new import needed.

- [ ] **Step 6: Verify the server module still loads**

```bash
uv run python -c "import src.gramps_mcp.server; print('server loads')"
```

Expected: `server loads` (an `INFO` log line about tool registration may
print first; pydantic schema warnings, if any, are pre-existing and
unrelated).

- [ ] **Step 7: Update `.env.example`**

Append to the end of `.env.example` (which currently ends with the
`GRAMPS_TREE_ID=...` line):

```
GRAMPS_TREE_ID=your-tree-id  # Find this under System Information in Gramps Web

# Optional: HTTP server bind address (defaults shown)
GRAMPS_MCP_HOST=0.0.0.0
GRAMPS_MCP_PORT=8000
```

- [ ] **Step 8: Update `README.md`**

Find this exact block (the "Environment Configuration" section):

```
Create a `.env` file with your Gramps Web settings:

```bash
# Your Gramps Web instance (from step 1)
GRAMPS_API_URL=https://your-gramps-web-domain.com  # Without /api suffix - will be added automatically
GRAMPS_USERNAME=your-gramps-web-username
GRAMPS_PASSWORD=your-gramps-web-password
GRAMPS_TREE_ID=your-tree-id  # Find this under System Information in Gramps Web
```
```

Replace it with:

```
Create a `.env` file with your Gramps Web settings:

```bash
# Your Gramps Web instance (from step 1)
GRAMPS_API_URL=https://your-gramps-web-domain.com  # Without /api suffix - will be added automatically
GRAMPS_USERNAME=your-gramps-web-username
GRAMPS_PASSWORD=your-gramps-web-password
GRAMPS_TREE_ID=your-tree-id  # Find this under System Information in Gramps Web

# Optional: HTTP server bind address (defaults shown)
GRAMPS_MCP_HOST=0.0.0.0
GRAMPS_MCP_PORT=8000
```
```

- [ ] **Step 9: Manual spot-check (not part of automated tests)**

```bash
GRAMPS_MCP_PORT=9000 timeout 3 uv run python -m src.gramps_mcp.server; echo "exit code: $?"
```

Expected: the server starts and logs binding on port 9000 (visible in
`uvicorn`/FastMCP startup logs before `timeout` kills it after 3 seconds);
exit code will be non-zero from the `timeout` kill, which is expected and
fine — this step is only to visually confirm the port took effect, not to
assert a specific exit code.

- [ ] **Step 10: Final verification**

```bash
uv run ruff check src/
uv run ruff format --check src/ tests/
uv run mypy src/gramps_mcp --ignore-missing-imports
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py -q
```

Expected: ruff clean, format clean, mypy `Success: no issues found`, `21 passed`
(18 previous + 3 new).

- [ ] **Step 11: Commit**

```bash
git add src/gramps_mcp/config.py src/gramps_mcp/server.py tests/test_config.py .env.example README.md
uv run git commit -m "feat: make MCP HTTP host/port configurable via env vars"
```

---

## Final verification (whole plan)

```bash
uv run ruff check src/
uv run ruff format --check src/ tests/
uv run mypy src/gramps_mcp --ignore-missing-imports
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py -q
uv run python -c "import src.gramps_mcp.server; print('server loads')"
git status --short
```

All clean/passing. `git status --short` should show only the user's
pre-existing, untouched `docker-compose.yml`/`docker/` WIP — nothing from
this plan left uncommitted.
