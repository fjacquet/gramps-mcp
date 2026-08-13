# 1. Build on MCP Python SDK 2.x

Date: 2026-08-02

## Status

Accepted

## Context

The project shipped on `mcp>=1.2.0` from its first commit (d27134a,
2025-09-11). The HTTP path used `FastMCP("gramps", stateless_http=True,
json_response=True)` and the stdio path used the low-level `Server` with
`@server.list_tools()` and `@server.call_tool()` decorators.

The migration to `mcp>=2.0.0,<3` was not made in a dedicated commit and no
design spec covers it. It was folded into 9ee009d (2026-08-02), a feature
commit adding the `create_sourced_event` and `media_upload` tools, whose
message does not mention the SDK at all. The reasoning behind the timing is
therefore not recoverable from the record: what can be established is that
the dependency floor moved from `1.2.0` to `2.0.0` in that commit, and that
the server was rewritten in the same diff to match. The most likely account -
that the new tools were developed against an already-installed 2.x and the
pin followed the code - is inference, not evidence.

## Decision

Depend on `mcp>=2.0.0,<3` and use the 2.x shapes throughout `server.py`:

- `MCPServer("gramps")` replaces `FastMCP`, with `stateless_http` and
  `json_response` passed to `app.run()` rather than the constructor.
- The stdio `Server` receives its handlers by constructor injection
  (`Server("gramps", on_list_tools=..., on_call_tool=...)`). The decorators
  were removed by the SDK, not deprecated, so there was no gradual path.
- Handlers take the 2.x signatures: `(ctx, params)` in, `ListToolsResult` /
  `CallToolResult` out, in place of the bare list and dict of 1.x.
- `Tool(input_schema=...)`, previously `inputSchema`.

The `<3` upper bound is deliberate. The 1.x-to-2.x step broke four separate
call shapes in one file; the bound makes the next major a decision rather
than a surprise from a fresh `uv sync`.

## Consequences

The rewrite touched only `server.py`, because the tool registry already
isolated the SDK surface behind `TOOL_REGISTRY` - the tool implementations
themselves were untouched. That containment was the payoff of a structure
adopted for unrelated reasons.

`CallToolResult` gave the call path an explicit `is_error` flag, which the
handler now sets rather than raising. This is a genuine improvement in what
a client sees on failure.

Costs currently being paid: the migration left `tests/test_server.py:82`
asserting `result.serverInfo.name`, which 2.x renamed to `server_info`. That
test has been failing since 2026-08-02 and is recorded as a known
pre-existing failure in two implementation plans rather than fixed. Bundling
the migration into a feature commit is why: nothing forced a full-suite
review of the SDK surface. The `<3` bound also means a future major upgrade
will be a deliberate piece of work with no incremental path, exactly as this
one was.

## Update, 2026-08-13

The failing test is fixed. Commit fe7b9e5, on `main`, changed
`tests/test_server.py:82` to assert `result.server_info.name`, the 2.x name,
so the failure recorded above is no longer outstanding and no plan carries
it as known. The account of *why* it survived - a migration bundled into a
feature commit, with nothing forcing a full-suite review of the SDK surface
- is unchanged and is the part of this section still worth reading.

The `<3` upper bound and everything else in the Decision stand as written.
