# Architecture

The module layout, the two transports the server speaks, and the shape of a
request from an MCP client through to the Gramps Web REST API. This page
describes structure, not rationale - the "why" behind each choice lives in
`docs/adr/`, and this page points at the relevant record instead of
restating it.

## Layout

```
src/gramps_mcp/
|-- server.py           # entry point: FastAPI/MCPServer app, HTTP + stdio transports
|-- tool_registry.py     # tool name -> description, schema, handler (pure data)
|-- client.py            # unified Gramps Web API client
|-- auth.py              # JWT authentication (singleton)
|-- config.py            # configuration management
|-- merge.py             # pure merge logic for PUT updates
|-- destructive.py       # pure decision logic for delete/detach
|-- traversal.py         # pure breadth-first family-graph traversal
|-- utils.py             # shared helpers
|-- models/
|   |-- api_calls.py     # API endpoint definitions (the ApiCalls enum)
|   |-- api_mapping.py   # ApiCalls -> parameter model mapping
|   `-- parameters/      # one Pydantic parameter module per domain
|-- tools/                # one MCP tool implementation module per domain
|-- handlers/             # response formatting, one handler module per domain
|-- genealogy/            # duplicate/consistency/completeness detection logic
`-- resources/             # MCP resources served to clients (GQL docs, usage guide)
```

`tools/` currently holds `search_basic.py`, `search_details.py`,
`data_management.py`, `analysis.py`, `relationship_tools.py`,
`records_tools.py`, `media_upload.py`, `sourced_event.py`, `detection.py`
(`find_duplicates`, `audit_quality`, `geocode_place`), `destructive.py`
(`delete_type`, `merge_type`, `detach_reference`, `undo_change`), and `user_tools.py`.

## Modules whose names do not say what they do

- **`merge.py`** - Gramps Web API `PUT` replaces the whole object. To avoid
  silently dropping fields a caller did not mention, the client fetches the
  existing record and merges the requested change into it before sending.
  Pure, side-effect-free, unit-tested without a live server
  (`tests/test_merge.py`, `tests/test_client_merge.py`). ADR 0003, ADR 0007.
- **`destructive.py`** (top-level, not `tools/destructive.py`) - the same
  unit-testable pattern applied to deletions and to removing one element
  from a list: a pure decision function computes whether a deletion may
  proceed and what the list looks like afterwards, with no request sent.
  ADR 0007.
- **`tool_registry.py`** - `TOOL_REGISTRY`, a dict mapping each tool name to
  its description, parameter schema, and handler function. Split out of
  `server.py` to keep that file under the repository's 500-line limit; both
  transports import it as their shared source of truth. ADR 0006.
- **`traversal.py`** - breadth-first traversal of the family graph (people
  and the family links between them). Pure graph logic that formats
  nothing; rendering lives separately in `handlers/traversal_handler.py`.
- **`genealogy/`** - duplicate-blocking, consistency rules (R1-R9),
  completeness rules (D1-D3), merge planning, and place resolvers
  (`genealogy/geo/`). Deliberately duplicated from another repository under
  the same owner rather than shared; the reasoning for that duplication
  belongs to its own ADR, not to this page.

## Technology stack

- **MCP Python SDK** (`mcp`, pinned `>=2.0.0,<3`) - protocol implementation
  for both transports. See ADR 0001.
- **FastAPI** / **uvicorn** - the HTTP transport's ASGI app and server.
- **Pydantic** - parameter validation and serialization for every tool's
  arguments (`models/parameters/`).
- **httpx** - async client `client.py` uses to call the Gramps Web API.
- **PyJWT** - JWT handling in `auth.py`.
- **python-dotenv** - loads `.env` for configuration.

## Transports

`server.py` is the single entry point. It picks a transport from
`sys.argv[1]`. No argument (or anything other than `stdio`) runs the
FastAPI-backed `MCPServer` over streamable HTTP, stateless with JSON
responses, on `/mcp` (port 8000 by default); `/` and `/health` are plain
Starlette routes alongside it. `stdio` runs the low-level `Server` over
`stdio_server()`, for clients that launch the process directly (Claude
Desktop, Claude Code).

Both paths register tools from the same `TOOL_REGISTRY`, but through
different SDK entry points (`app.tool()` decoration for HTTP,
`handle_list_tools`/`handle_call_tool` injection for stdio), and the two do
not share error handling. See ADR 0004 for what that costs.

## Request flow

1. An MCP client calls a tool by name with arguments matching that tool's
   Pydantic schema.
2. `server.py`'s transport layer looks the tool up in `TOOL_REGISTRY`
   (`tool_registry.py`) and validates the arguments against its schema.
3. The handler, in `tools/`, builds one or more `ApiCalls` requests
   (validated against `models/api_mapping.py`); an update routes through
   `merge.py` or `destructive.py` first to compute the full payload.
4. `client.py` sends the request to the Gramps Web REST API over `httpx`,
   authenticated by a bearer token that `auth.py` obtains and refreshes.
5. The raw response goes to a formatter in `handlers/` (one module per
   domain: person, family, event, place, source, citation, and so on),
   which shapes it into the tool's return content.

Detection tools (`find_duplicates`, `audit_quality`) and graph tools
(`get_ancestors`, `get_descendants`) follow the same shape, but their
handler calls into `genealogy/` or `traversal.py` for the pure logic step
instead of `merge.py`/`destructive.py`.

To find where a behavior lives: the tool name and schema are in
`tool_registry.py`; request-building and business logic are in the matching
`tools/*.py` module; response shaping is in the matching `handlers/*.py`
module; and how a `PUT` or delete is decided is in `merge.py` or
`destructive.py`.

## See also

`docs/adr/` for why each choice was made (0001, 0003, 0004, 0006, 0007
above; also 0002 - testing against a real server, 0005 - the `manage_users`
role whitelist). `docs/reference/gramps-web-api.md` for which of the
underlying API's 193 operations this server actually calls.
