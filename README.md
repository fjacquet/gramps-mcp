# Gramps MCP - AI-Powered Genealogy Research & Management

[![License](https://img.shields.io/badge/License-AGPL--3.0-blue)](./LICENSE) [![Python](https://img.shields.io/badge/Python-3.12+-brightgreen)](https://python.org) [![MCP](https://img.shields.io/badge/MCP-2.0.0+-orange)](https://modelcontextprotocol.io) [![Release](https://img.shields.io/github/v/release/fjacquet/gramps-mcp)](https://github.com/fjacquet/gramps-mcp/releases)
[![CI](https://github.com/fjacquet/gramps-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/fjacquet/gramps-mcp/actions/workflows/ci.yml) [![Docker Build](https://github.com/fjacquet/gramps-mcp/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/fjacquet/gramps-mcp/actions/workflows/docker-publish.yml) [![codecov](https://codecov.io/gh/fjacquet/gramps-mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/fjacquet/gramps-mcp) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Without Gramps MCP

Genealogy research with AI assistants is limited and frustrating:

- No direct access to your family tree data
- Manual data entry and research across multiple platforms
- Generic genealogy advice without context of your specific family
- No ability to automatically update or maintain your research

## With Gramps MCP

Gramps MCP provides AI assistants with direct access to your Gramps genealogy database through a comprehensive set of tools. Your AI assistant can now:

- **Smart Search**: Find people, families, events, places, and sources across your entire database
- **Data Management**: Create and update genealogy records with proper validation
- **Tree Analysis**: Trace descendants, ancestors, and family connections
- **Relationship Discovery**: Explore family connections and research gaps
- **Tree Information**: Get comprehensive tree statistics and track changes

Add Gramps MCP to your AI assistant and transform how you research family history:

```txt
Search for all descendants of John Smith born in Ireland before 1850
```

```txt
Create a new person record for Mary O'Connor with birth date 1823 in County Cork
```

```txt
Find all families missing marriage dates and suggest research priorities
```

No more manual data entry, no context switching between apps, no generic genealogy advice.

- Connect to your Gramps Web API
- Install Gramps MCP in your AI assistant
- Start intelligent genealogy research with natural language

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [MCP Client Configuration](#mcp-client-configuration)
- [Architecture](#architecture)
- [Development](#development)
- [Usage Examples](#usage-examples)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [License](#license)
- [Related Projects](#related-projects)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)

## Features

### 27 Genealogy Tools

#### Search & Retrieval (3 tools)
- **find_type** - Universal search for any entity type (person, family, event, place, source, citation, media, repository) using Gramps Query Language
- **find_anything** - Text search across all genealogy data (matches literal text, not logical combinations)
- **get_type** - Get comprehensive information about specific persons or families by ID

#### Data Management (10 tools)
- **create_person** - Create or update person records
- **create_family** - Create or update family units
- **create_event** - Create or update life events
- **create_place** - Create or update geographic locations
- **create_source** - Create or update source documents
- **create_citation** - Create or update citations
- **create_note** - Create or update textual notes
- **create_media** - Create or update media files
- **create_repository** - Create or update repository records
- **create_sourced_event** - Create a fully sourced event (event, citation, and source) in one call

#### Analysis Tools (4 tools)
- **tree_stats** - Get tree statistics and information
- **get_descendants** - Find all descendants of a person
- **get_ancestors** - Find all ancestors of a person
- **recent_changes** - Track recent modifications to your data

#### Extended Analysis Tools (6 tools)
- **get_relationship** - Calculate how two people are related
- **check_living** - Check living status and estimated birth/death dates
- **get_timeline** - Build a chronological timeline for a person, family, or group
- **manage_tags** - List, get, or create/update tags
- **manage_users** - List, get, or create Gramps Web accounts with generated passwords (owner or admin rights required, see [docs/user-management.md](docs/user-management.md))
- **get_facts** - Get interesting facts and statistics about the tree

#### Destructive Operations (4 tools)
- **delete_type** - Delete a single record; refuses while it is still referenced unless `force=true`
- **merge_type** - Merge two records of the same type; previews unless `confirm=true` (tags cannot be merged)
- **detach_reference** - Remove one element from one named list on a record, leaving every other list untouched
- **undo_change** - Reverse a recorded transaction by id (the recovery path for `delete_type` and `merge_type`)

## Installation

### Requirements

- **Gramps Web server** with your family tree data - [Setup Guide](https://www.grampsweb.org/install_setup/setup/)
- Docker and Docker Compose
- MCP-compatible AI assistant (Claude Desktop, Cursor, etc.)

### Quick Start

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

### Alternative: Run Without Docker

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

### Environment Configuration

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

## MCP Client Configuration

### Claude Desktop

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

### OpenWebUI

OpenWebUI recommends using the [mcpo proxy](https://docs.openwebui.com/openapi-servers/mcp/) to expose MCP servers as OpenAPI endpoints.

**With uv:**
```bash
uvx mcpo --port 8000 -- uv run python -m src.gramps_mcp.server stdio
```

**With Docker:**
```bash
uvx mcpo --port 8000 -- docker exec -i gramps-mcp-gramps-mcp-1 python -m src.gramps_mcp.server stdio
```

### Claude Code

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

> **Transport Choice:** Use **stdio** for better performance and direct integration with CLI tools like Claude Code. Use **HTTP** when you need the server to handle multiple clients or prefer web-based access.

### Other MCP Clients

For any other MCP client, use the HTTP transport endpoint:

```json
{
  "mcpServers": {
    "gramps": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Architecture

### Core Components

```
src/gramps_mcp/
|-- server.py           # MCP server, tool registry, HTTP/stdio transports
|-- client.py           # Unified Gramps Web API client
|-- merge.py            # Pure merge logic for PUT updates
|-- destructive.py      # Pure decision logic for delete/detach
|-- auth.py             # JWT authentication (singleton)
|-- config.py           # Configuration management
|-- utils.py            # Shared helpers
|-- models/             # Pydantic models
|   |-- api_calls.py    # API endpoint definitions
|   |-- api_mapping.py  # API call to parameter model mapping
|   `-- parameters/     # Parameter models per domain
|-- tools/              # MCP tool implementations
|   |-- search_basic.py
|   |-- search_details.py
|   |-- data_management.py
|   |-- analysis.py
|   |-- relationship_tools.py
|   |-- records_tools.py
|   |-- media_upload.py
|   |-- sourced_event.py
|   |-- destructive.py  # delete_type, merge_type, detach_reference, undo_change
|   `-- user_tools.py
|-- handlers/           # Data formatting handlers
`-- resources/          # MCP resources (GQL docs, usage guide)
```

### Technology Stack

- **MCP Python SDK**: Model Context Protocol implementation
- **FastAPI**: HTTP server for MCP transport
- **Pydantic**: Data validation and serialization
- **httpx**: Async HTTP client for API communication
- **PyJWT**: JWT token authentication
- **python-dotenv**: Environment configuration

## Development

Requires [uv](https://docs.astral.sh/uv/). See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor guide.

```bash
uv sync --all-extras --dev                               # install dependencies
uv run ruff check src/                                    # lint
uv run ruff format --check src/ tests/                    # formatting check
uv run mypy src/gramps_mcp --ignore-missing-imports        # type check
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py tests/test_http_error_detail.py  # offline-safe tests
```

Most tests in `tests/` require a live Gramps Web server (see [CONTRIBUTING.md](CONTRIBUTING.md)
for setup); the command above runs a subset of the ones that work offline, matching what CI checks.
This is the same file list CI runs (`.github/workflows/ci.yml`); see `CLAUDE.md` for the fuller
`-m "not integration"` marker-based story, including why CI does not use that marker directly.

## Usage Examples

### Basic Search Operations

```txt
Find all people with the surname "Smith" born in Ireland
```

```txt
Show me recent changes to the family tree in the last 30 days
```

### Data Creation and Updates

```txt
Create a new person record for Patrick O'Brien, born 1845 in Cork, Ireland
```

```txt
Add a marriage event for John and Mary Smith on June 15, 1870 in Boston
```

### Genealogy Analysis

```txt
Find all descendants of Margaret Kelly and show their birth locations
```


### Tree Information & Statistics

```txt
Show me statistics about my family tree - how many people, families, and events
```

```txt
What recent changes have been made to my family tree in the last week?
```

## Security

- JWT token authentication with automatic refresh
- Environment-based credential management
- Input validation using Pydantic models
- Secure HTTP transport with proper error handling
- No sensitive data exposed in tool responses

### MCP Server Network Access

The MCP server has **no authentication of its own**. It uses the Gramps Web credentials from your `.env` file (owner or admin role) and assumes the caller is authorized. This is by design - MCP servers are meant to be embedded in applications your user controls.

**Important**: Do not publish the MCP server port (`8000` by default) to untrusted networks. The compose files bind it to `127.0.0.1` (loopback only) by default. If you need to access it from other machines:

1. **Use an authenticating reverse proxy** (nginx, Caddy, etc.) in front of the MCP server
2. Require authentication before requests reach port 8000
3. Run the proxy on a public-facing port instead

If you have changed the port binding in your compose file, verify it only listens on trusted interfaces:

```bash
docker compose ps --format "{{.Names}}\t{{.Ports}}" | grep mcp
```

Look for bindings like `127.0.0.1:8000->8000/tcp` (safe) or loopback IPv6 equivalents, not `0.0.0.0:8000->8000/tcp` (unsafe). See [CONTRIBUTING.md](CONTRIBUTING.md) for the recommended production setup.


## Troubleshooting

### Common Issues

**Connection refused errors**: Ensure your Gramps Web API server is running and accessible at the configured URL.

**Authentication failures**: Verify your username and password are correct and the user has appropriate permissions.

**Tool timeout errors**: Check your network connection and consider increasing timeout values for large datasets.

**Docker issues**: Ensure Docker and Docker Compose are installed and running.

### Reading error messages

Since v1.7.0, a failed call reports a generic sentence categorising the failure
followed by the server's own explanation, truncated to 300 characters. A rejected
create or update usually names the offending field in that fragment. The bound
exists because Gramps can echo the submitted payload, which may hold data about
living people.

Media upload failures now raise the same error type as every other tool. Code
that caught `httpx.HTTPStatusError` around an upload no longer catches it.

### Result counts and ordering

Search results report the true number of matches, read from the API's
`X-Total-Count` header, which may exceed the number displayed. `recent_changes`
honours a caller-supplied `sort` instead of always returning newest-first, and
its response is bounded.

### Debug Mode

To enable debug logging, check your application logs with:

```bash
docker-compose logs -f
```

## Documentation

- [User guide](docs/user-guide/index.md) - how to work with the tools through an
  assistant: searching, reading records, the source-citation-event chain,
  attaching media, relationships and timelines.
- [Product requirements](docs/prd.md) - what the product is as of v1.7.0, what
  it deliberately does not do, and its known limitations.
- [Architecture decision records](docs/adr/) - the six structural decisions
  behind the project, with the costs each one carries.
- [User management](docs/user-management.md) - creating and listing Gramps Web
  accounts with the `manage_users` tool.
- [Contributing](CONTRIBUTING.md) - development setup, testing and conventions.

## License

This project is licensed under the GNU Affero General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Related Projects

- [Gramps](https://gramps-project.org/) - Free genealogy software
- [Gramps Web API](https://github.com/gramps-project/gramps-web-api) - Web API for Gramps
- [Model Context Protocol](https://modelcontextprotocol.io/) - Standard for AI tool integration

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on:

- Setting up the development environment
- Running tests and maintaining code quality
- Submitting pull requests
- Reporting issues and requesting features

### Community & Support

- **Bug Reports & Feature Requests**: [GitHub Issues](https://github.com/fjacquet/gramps-mcp/issues)
- **Questions & Discussions**: [GitHub Discussions](https://github.com/fjacquet/gramps-mcp/discussions)
- **Documentation**: [Project Wiki](https://github.com/fjacquet/gramps-mcp/wiki)

## Acknowledgments

- The Gramps Project team for creating excellent genealogy software
- Anthropic for developing the Model Context Protocol
- The genealogy research community for inspiration and feedback