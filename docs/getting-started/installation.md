# Installation

This page covers what you need before running the server and the two ways to
run it: Docker (recommended) or a plain Python install with uv.

## Requirements

- **Gramps Web server** with your family tree data - [Setup Guide](https://www.grampsweb.org/install_setup/setup/)
- Docker and Docker Compose
- MCP-compatible AI assistant (Claude Desktop, Cursor, etc.)

## Quick Start

1. **Ensure Gramps Web is Running**:
   - Follow the [Gramps Web setup guide](https://www.grampsweb.org/install_setup/setup/) to get your family tree online
   - Note your Gramps Web URL, username, and password
   - Find your tree ID under System Information in your Gramps Web interface

2. **Start the Server**:

```bash
# Download the configuration
curl -O https://raw.githubusercontent.com/fjacquet/gramps-mcp/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/fjacquet/gramps-mcp/main/.env.example
cp .env.example .env
# Edit .env with your Gramps Web API credentials

# Start the server
docker-compose up -d
```

That's it! The MCP server will be running at `http://localhost:8000/mcp`

See [Environment variables](configuration.md) for what goes in `.env`, and
[Connecting an MCP client](mcp-clients.md) for wiring the server into Claude
Desktop, Cursor, or another assistant.

## Alternative: Run Without Docker

If you prefer to run the server directly with Python:

1. **Setup Python Environment**:
```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

2. **Run the Server**:
```bash
# HTTP transport (for web-based MCP clients)
uv run python -m src.gramps_mcp.server

# Stdio transport (for CLI-based MCP clients)
uv run python -m src.gramps_mcp.server stdio
```

The HTTP server will be available at `http://localhost:8000/mcp`, while stdio runs directly in the terminal.

If something does not come up as expected, see
[Troubleshooting](../operations/troubleshooting.md).
