# 4. Carry both HTTP and stdio transports

Date: 2025-09-11

## Status

Accepted

## Context

MCP clients do not agree on how to reach a server. Claude Desktop and Claude
Code launch a subprocess and speak over stdin/stdout. Web-facing clients and
proxies want an HTTP endpoint. The initial commit (d27134a, 2025-09-11)
listed "Support for multiple MCP clients (Claude Desktop, OpenWebUI, Claude
Code)" among the project's features, and both transports were present from
that commit onward.

No commit or spec debates dropping either one, so there is no record of the
alternatives being weighed. What the evidence supports is that the client
list came first and the two transports followed from it.

## Decision

`src/gramps_mcp/server.py` is the single entry point and selects its
transport from `sys.argv[1]`, defaulting to `streamable-http`:

- `python -m src.gramps_mcp.server` runs `app.run(transport="streamable-http",
  host=..., port=..., stateless_http=True, json_response=True)`, serving
  `/mcp` on port 8000 by default, with host and port from env vars. The HTTP
  path also carries two custom Starlette routes, `/` and `/health`, that stdio
  has no equivalent of.
- `python -m src.gramps_mcp.server stdio` runs the low-level `Server` over
  `stdio_server()`.

HTTP is stateless with JSON responses rather than SSE. That is what makes the
containerised deployment viable: `Dockerfile` exposes 8000, and any number of
clients can hit one container without per-client session state.

stdio is what the README recommends for CLI clients, on performance grounds,
and it is how Claude Desktop and Claude Code are documented to connect -
usually as `docker exec -i` into the running container rather than a separate
process. OpenWebUI is documented via `mcpo`, which wraps the stdio server as
OpenAPI rather than using the native HTTP endpoint.

## Consequences

Both transports must be kept working, and they do not share a code path.
HTTP goes through `MCPServer` and `register_tools()`, which synthesises a
decorated handler per registry entry; stdio goes through `Server` with
`handle_list_tools` / `handle_call_tool` injected. `TOOL_REGISTRY` is the
only thing they have in common. A change to how tools are exposed has to be
made twice, and the SDK 2.x migration (ADR 0001) had to fix both shapes.

The two paths do not behave identically on error. `handle_call_tool` catches
every exception and returns `CallToolResult(is_error=True)`; the HTTP
registration wrapper has no such catch of its own. `/health` and `/` exist on
HTTP only, so a stdio deployment has no liveness probe.

There is no test that both transports expose the same tool set. Nothing
would catch a registry change that landed on one path and not the other.
