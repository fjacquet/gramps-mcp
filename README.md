# Gramps MCP - AI-Powered Genealogy Research & Management

[![License](https://img.shields.io/badge/License-AGPL--3.0-blue)](./LICENSE) [![Python](https://img.shields.io/badge/Python-3.12+-brightgreen)](https://python.org) [![MCP](https://img.shields.io/badge/MCP-2.0.0+-orange)](https://modelcontextprotocol.io) [![Release](https://img.shields.io/github/v/release/fjacquet/gramps-mcp)](https://github.com/fjacquet/gramps-mcp/releases)
[![CI](https://github.com/fjacquet/gramps-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/fjacquet/gramps-mcp/actions/workflows/ci.yml) [![Docker Build](https://github.com/fjacquet/gramps-mcp/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/fjacquet/gramps-mcp/actions/workflows/docker-publish.yml) [![codecov](https://codecov.io/gh/fjacquet/gramps-mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/fjacquet/gramps-mcp) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

An MCP server that gives an AI assistant read and write access to a
[Gramps Web](https://www.gramps-project.org/wiki/index.php/Gramps_Web) genealogy
database. It exposes 30 tools for searching, reading and recording family
history, and runs either over HTTP or on stdio.

The assistant does the reasoning. This server does the data.

**[Full documentation](https://fjacquet.github.io/gramps-mcp/)**

## What it changes

Recording one civil-registry act correctly means creating a repository, a
source, a citation, an event and a media object, then attaching the event to
the right people with the right roles - without duplicating records that
already exist. The work is mechanical, the correctness rules are strict, and
the cost of getting it wrong is paid later, by hand.

Pointing an assistant at the raw REST API moves that burden onto the model.
This server encodes the rules instead, as task-shaped tools:

```txt
Search for all descendants of John Smith born in Ireland before 1850
```

```txt
Record Mary O'Connor's 1823 baptism at Cork, sourced to the parish register
```

```txt
Find people entered twice, and list the ones the rules can prove
```

## Quick start

You need a running Gramps Web instance. Note its URL, your username and
password, and your tree ID (under System Information in the Gramps Web
interface).

```bash
# Download the configuration
curl -O https://raw.githubusercontent.com/fjacquet/gramps-mcp/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/fjacquet/gramps-mcp/main/.env.example
cp .env.example .env
# Edit .env with your Gramps Web API credentials

# Start the server
docker-compose up -d
```

The server runs at `http://localhost:8000/mcp`.

`GRAMPS_API_URL` carries no `/api` suffix. Getting this wrong fails as
success: the request returns the web app's HTML page with HTTP 200 rather
than an error.

Next: [connect your MCP client](https://fjacquet.github.io/gramps-mcp/getting-started/mcp-clients/),
or run [without Docker](https://fjacquet.github.io/gramps-mcp/getting-started/installation/).

## Documentation

Everything below lives on the [documentation site](https://fjacquet.github.io/gramps-mcp/):

- **[Installation](https://fjacquet.github.io/gramps-mcp/getting-started/installation/)**,
  [configuration](https://fjacquet.github.io/gramps-mcp/getting-started/configuration/) and
  [MCP client setup](https://fjacquet.github.io/gramps-mcp/getting-started/mcp-clients/) - Claude Desktop, Claude Code, OpenWebUI and others.
- **[User guide](https://fjacquet.github.io/gramps-mcp/user-guide/)** - working through an
  assistant: searching, the source-citation-event chain, media, relationships,
  timelines, and auditing the tree for duplicates and inconsistencies.
- **[Tools](https://fjacquet.github.io/gramps-mcp/reference/tools/)** - what each of the 30
  tools does, and what it deliberately does not do.
- **[Architecture](https://fjacquet.github.io/gramps-mcp/reference/architecture/)** and the
  [Gramps Web API coverage](https://fjacquet.github.io/gramps-mcp/reference/gramps-web-api/) this server reaches.
- **[Security](https://fjacquet.github.io/gramps-mcp/operations/security/)** - what is
  stored where, and the four third-party hosts one tool reaches.
- **[Troubleshooting](https://fjacquet.github.io/gramps-mcp/operations/troubleshooting/)**.
- **[Decisions](https://fjacquet.github.io/gramps-mcp/adr/)** - the nine structural
  decisions behind the project, each recorded with the cost it carries.

## Contributing

See the [Contributing Guide](CONTRIBUTING.md) for development setup, testing
and conventions. Bug reports and feature requests go to
[GitHub Issues](https://github.com/fjacquet/gramps-mcp/issues); questions to
[GitHub Discussions](https://github.com/fjacquet/gramps-mcp/discussions).

## Related projects

- [Gramps](https://gramps-project.org/) - free genealogy software
- [Gramps Web API](https://github.com/gramps-project/gramps-web-api) - the REST API this server speaks to
- [Model Context Protocol](https://modelcontextprotocol.io/) - the standard this server implements

## License

GNU Affero General Public License v3.0 - see [LICENSE](LICENSE).

## Acknowledgments

The Gramps Project team, for genealogy software that has outlasted most of its
commercial contemporaries, and Anthropic, for the Model Context Protocol.
