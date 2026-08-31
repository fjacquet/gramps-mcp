# MCP client configuration

This page covers connecting an MCP client to a running Gramps MCP server:
Claude Desktop, OpenWebUI, Claude Code, and any other MCP client that speaks
the standard protocol. It assumes the server is already installed and
configured - see [Installation](installation.md) and
[Configuration](configuration.md) if it is not.

The server supports two transports:

- **HTTP** - the default, served at `http://localhost:8000/mcp`. Needed by
  clients that connect over the network or expect a web endpoint.
- **stdio** - a direct process connection, more efficient for CLI tools that
  can launch the server themselves.

Each section below states which transport it uses.

## Claude Desktop

Claude Desktop connects over stdio - it launches the server as a subprocess
rather than talking to the HTTP endpoint.

Add to your Claude Desktop MCP configuration file (`claude_desktop_config.json`):

**Using Docker** (works with both pre-built and local images):
```json
{
  "mcpServers": {
    "gramps": {
      "command": "docker",
      "args": ["exec", "-i", "gramps-mcp-gramps-mcp-1", "python", "-m", "src.gramps_mcp.server", "stdio"]
    }
  }
}
```

**Using uv directly** (if running without Docker):
```json
{
  "mcpServers": {
    "gramps": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.gramps_mcp.server", "stdio"],
      "cwd": "/path/to/gramps-mcp"
    }
  }
}
```

## OpenWebUI

OpenWebUI expects an OpenAPI endpoint, not a raw MCP transport. Get there by
running the server over stdio and wrapping it with the
[mcpo proxy](https://docs.openwebui.com/openapi-servers/mcp/), which is what
exposes port 8000 for OpenWebUI to call.

**With uv:**
```bash
uvx mcpo --port 8000 -- uv run python -m src.gramps_mcp.server stdio
```

**With Docker:**
```bash
uvx mcpo --port 8000 -- docker exec -i gramps-mcp-gramps-mcp-1 python -m src.gramps_mcp.server stdio
```

## Claude Code

Claude Code can use either transport.

**HTTP Transport:**
```bash
claude mcp add --transport http gramps http://localhost:8000/mcp
```

**Stdio Transport** (direct connection, more efficient):
```bash
# Using Docker
claude mcp add --transport stdio gramps "docker exec -i gramps-mcp-gramps-mcp-1 sh -c 'cd /app && python -m src.gramps_mcp.server stdio'"

# Using uv directly (requires local setup)
claude mcp add --transport stdio gramps "uv run python -m src.gramps_mcp.server stdio"
```

Use **stdio** for better performance and direct integration with CLI tools
like Claude Code. Use **HTTP** when you need the server to handle multiple
clients or prefer web-based access.

## Other MCP Clients

Any other MCP client should use the HTTP transport endpoint:

```json
{
  "mcpServers": {
    "gramps": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```
