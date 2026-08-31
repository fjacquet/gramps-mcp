# Environment variables

This page documents every environment variable the server reads, which ones
are required, and what each does. It is the reference to check against
`src/gramps_mcp/config.py`, the authority for these names and defaults.

## The `.env` file

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

# Optional: directory that media_path values must resolve inside (default shown)
GRAMPS_MEDIA_IMPORT_ROOT=/tmp
```

## Required

- **`GRAMPS_API_URL`** - base URL of your Gramps Web instance. Give it
  without the `/api` suffix; the server appends `/api` itself to build the
  REST base. Passing a URL that already ends in `/api` does not fail loudly -
  it returns the web app's HTML page with HTTP 200 instead of an API
  response, so a mistake here looks like success until a call breaks later.
- **`GRAMPS_USERNAME`** - username for the Gramps Web API.
- **`GRAMPS_PASSWORD`** - password for the Gramps Web API.
- **`GRAMPS_TREE_ID`** - the family tree identifier. Find it under System
  Information in the Gramps Web interface.

The server fails to start if any of these four are missing.

## Optional

- **`GRAMPS_MCP_HOST`** - interface the MCP HTTP server binds to. Default
  `0.0.0.0`.
- **`GRAMPS_MCP_PORT`** - port the MCP HTTP server listens on. Default
  `8000`.
- **`GRAMPS_MEDIA_IMPORT_ROOT`** - directory that every `media_path` value
  passed to the media, source, citation and sourced-event tools must resolve
  inside. A path resolving outside it - through `..` or through a symlink -
  is refused before any upload. Default `/tmp`.

The MCP server itself has no mount of the host filesystem, so files have to
be staged inside the container, conventionally into `/tmp`, before a tool
call can reference them:

```bash
docker cp ~/Desktop/acte-1878.jpg gramps-mcp-gramps-mcp-1:/tmp/
```

For the full list of tools this constrains and the tree back-up workflow, see
[Security](../operations/security.md). For the tool inventory, see
[Tool reference](../reference/tools.md).
