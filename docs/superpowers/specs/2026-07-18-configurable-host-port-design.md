# Configurable HTTP Host/Port — Design

Date: 2026-07-18
Status: Approved

## Context

`server.py` hardcodes the streamable-HTTP transport's bind address:

```python
app.settings.host = "0.0.0.0"  # Listen on all interfaces for Docker
app.settings.port = 8000
```

(lines 360-361). This is fine for the shipped `Dockerfile`/`docker-compose.yml`
(which map port 8000), but anyone running the server directly, behind a
different port mapping, or wanting to bind to localhost only, cannot without
editing source. Two new optional environment variables fix this.

Decided with the user: same mechanism already used for the four required
`GRAMPS_*` settings — `load_dotenv()` (already called at import time in
`config.py`) populates `os.environ` from `.env`, and the getter reads with
`os.environ.get(KEY, default)` so an unset variable falls back to today's
hardcoded values with zero behavior change for existing deployments.

## Changes

### `src/gramps_mcp/config.py`

Add two fields to `Settings`, and read them with defaults (not `os.environ[...]`
— these are optional, unlike the four required Gramps API settings):

```python
class Settings(BaseModel):
    ...
    gramps_mcp_host: str = Field("0.0.0.0", description="Host/interface for the MCP HTTP server to bind to")
    gramps_mcp_port: int = Field(8000, description="Port for the MCP HTTP server to listen on")
```

`get_settings()` adds:

```python
gramps_mcp_host=os.environ.get("GRAMPS_MCP_HOST", "0.0.0.0"),
gramps_mcp_port=int(os.environ.get("GRAMPS_MCP_PORT", "8000")),
```

`int(...)` conversion happens here so a malformed value (e.g. `GRAMPS_MCP_PORT=abc`)
raises a clear `ValueError` from `get_settings()`'s existing exception handling,
rather than a confusing pydantic error deeper in `Settings`.

### `src/gramps_mcp/server.py`

Replace the hardcoded lines (360-361) with:

```python
settings = get_settings()
app.settings.host = settings.gramps_mcp_host
app.settings.port = settings.gramps_mcp_port
```

`get_settings` is already imported in `server.py` (used elsewhere in the
file). No change to the `stdio` transport path — host/port only apply to
`streamable-http`.

### `.env.example`

Append (as optional, matching the existing comment style):

```
# Optional: HTTP server bind address (defaults shown)
GRAMPS_MCP_HOST=0.0.0.0
GRAMPS_MCP_PORT=8000
```

### `README.md`

The existing "Environment Configuration" `.env` code block gets the same two
lines appended, marked optional.

## Testing

`tests/test_utils.py`/existing config-adjacent offline tests are unaffected
(they don't touch `Settings`, per the current test suite). Add
`tests/test_config.py` cases (this file already exists, holds
`get_api_base_url` tests from the prior cleanup work):

- default host/port when `GRAMPS_MCP_HOST`/`GRAMPS_MCP_PORT` are unset →
  `"0.0.0.0"` / `8000`.
- explicit values are read and the port is coerced to `int`.
- a non-numeric `GRAMPS_MCP_PORT` raises `ValueError` via `get_settings()`.

These are pure environment/pydantic tests, no live server needed — they join
the existing offline-safe test file already covered by CI.

## Verification

- `uv run pytest tests/test_config.py -q` — new cases pass alongside the
  existing ones.
- `uv run ruff check src/`, `uv run mypy src/gramps_mcp --ignore-missing-imports`
  clean.
- Manual: `GRAMPS_MCP_PORT=9000 uv run python -m src.gramps_mcp.server` binds
  on 9000 instead of 8000 (spot-checked by the implementer, not automated —
  starting the HTTP server is outside the pytest suite's scope).

## Risks

None of note — additive, defaulted, and covered by the existing CI-run
`test_config.py` file.
