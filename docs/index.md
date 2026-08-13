# Gramps MCP

An MCP server that gives an AI assistant read and write access to a
[Gramps Web](https://www.gramps-project.org/wiki/index.php/Gramps_Web) genealogy
database. It exposes 23 tools for searching, reading and recording family
history, and runs either over HTTP or on stdio.

The assistant does the reasoning. This server does the data.

## Where to start

- **[User guide](user-guide/index.md)** - working with the tools through an assistant:
  finding people and families, reading a record in depth, recording a sourced
  fact, attaching media, exploring relationships and timelines.
- **[Product requirements](prd.md)** - what the product is as of v1.7.0, what it
  deliberately does not do, and its known limitations.
- **[User management](user-management.md)** - creating and listing Gramps Web
  accounts with `manage_users`.
- **[Decisions](adr/README.md)** - the six structural decisions behind the
  project, each recorded with the cost it carries.

Installation, configuration and the full tool inventory live in the
[README](https://github.com/fjacquet/gramps-mcp#readme).

## Requirements

A running Gramps Web instance is required; this server holds a JWT against it
and speaks its REST API. Python 3.12 or later, and the MCP Python SDK 2.x.

## License

GNU Affero General Public License v3.0.
