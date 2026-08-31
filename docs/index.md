# Gramps MCP

An MCP server that gives an AI assistant read and write access to a
[Gramps Web](https://www.gramps-project.org/wiki/index.php/Gramps_Web) genealogy
database. It exposes 30 tools for searching, reading and recording family
history, and runs either over HTTP or on stdio.

The assistant does the reasoning. This server does the data.

## Where to start

- **[Installation](getting-started/installation.md)** - Docker or uv, then
  [configuration](getting-started/configuration.md) and
  [connecting your MCP client](getting-started/mcp-clients.md).
- **[User guide](user-guide/index.md)** - working with the tools through an assistant:
  finding people and families, reading a record in depth, recording a sourced
  fact, attaching media, exploring relationships and timelines, and
  [auditing the tree for duplicates and inconsistencies](user-guide/quality.md).
- **[Tools](reference/tools.md)** - what each of the 30 tools does, and what it
  deliberately does not do.
- **[Security](operations/security.md)** - what this server stores, and the four
  third-party hosts one of its tools reaches.
- **[Troubleshooting](operations/troubleshooting.md)** - when the server or the
  connection fails, as opposed to when the data surprises you.
- **[Product requirements](prd.md)** - what the product is as of v1.11.0, what it
  deliberately does not do, and its known limitations.
- **[User management](user-management.md)** - creating and listing Gramps Web
  accounts with `manage_users`.
- **[Decisions](adr/README.md)** - the nine structural decisions behind the
  project, each recorded with the cost it carries.

## Requirements

A running Gramps Web instance is required; this server holds a JWT against it
and speaks its REST API. Python 3.12 or later, and the MCP Python SDK 2.x.

## License

GNU Affero General Public License v3.0.
