# Product requirements: gramps-mcp v1.7.0

This document describes what gramps-mcp is as of v1.7.0 - its scope, its
boundaries, and the constraints it operates under. It is descriptive, not a
roadmap: everything here is true of the code today. [README.md](https://github.com/fjacquet/gramps-mcp#readme)
covers what the product offers and lists the tools; the architecture decisions
behind the boundaries are recorded in [docs/adr/](adr/README.md).

## Problem

Gramps Web holds a genealogy database and offers a competent web UI for editing
it. Entering research into that UI is slow and unforgiving in a specific way:
recording one civil-registry act correctly means creating a repository, a
source, a citation, an event and a media object, then attaching the event to
the right people with the right roles, and doing all of it without duplicating
records that already exist. The work is mechanical, the correctness rules are
strict, and the cost of getting it wrong - two records for one person, an event
with no citation - is paid later, by hand.

An AI assistant is well suited to that work if it can read and write the tree.
Gramps Web exposes a REST API, but pointing an assistant at a raw REST surface
puts the burden of the correctness rules on the model: which order to create
things in, which fields must carry handles rather than names, how not to
destroy existing data on an update.

gramps-mcp is the layer in between. It exposes the Gramps Web API to an MCP
client as a small set of task-shaped tools that encode those rules, so the
assistant reasons about the genealogy and the server takes care of the data
model.

The users are genealogists who already run a Gramps Web instance and want to
work through an assistant instead of the UI, and the developers maintaining
that setup.

## Scope

The product is an MCP server. It speaks the Model Context Protocol to a client
and the Gramps Web REST API to a server, and it holds no data of its own.

What it does:

- **Search and retrieval.** Full-text search across all record types, and
  structured search per type through Gramps Query Language, with pagination.
  Full formatted detail for people and families.
- **Data entry across the whole genealogical object model.** People, families,
  events, places, sources, citations, repositories, notes and media. The same
  tool creates and updates: supply a handle to update, omit it to create.
- **Sourcing as a first-class operation.** Events require a citation. A
  composite tool creates the source, citation and event in one call and wires
  the citation onto the event, removing the step where a handle is retyped
  and the link silently fails to form.
- **Media upload from a local path**, attachable inline to a source, a
  citation or a sourced event, or as a standalone media record.
- **Analysis over the tree.** Ancestor and descendant traversal, relationship
  calculation, living-status estimation, timelines for a person, a family or a
  group, and tree-wide statistics.
- **Housekeeping.** Tag listing and creation, transaction history for auditing
  recent changes, and limited user-account creation.
- **Guidance shipped with the server.** Two MCP resources - the GQL reference
  and the sourcing workflow - so a client can learn the query language and the
  intended order of operations without external documentation.

It runs over two transports: streamable HTTP for web-based clients and stdio
for CLI clients (ADR 0004).

## Non-scope

These are boundaries, not gaps waiting to be filled. Each one is a consequence
of a decision recorded elsewhere in the repository.

**It does not replace the Gramps Web UI.** It is a second way into the same
database, deliberately narrower than the first. Several ordinary operations
are only possible in the UI, and the sections below name them.

**It cannot remove anything from a list.** Updates are performed by reading
the current record, merging the requested changes into it, and writing the
whole thing back; list fields ending in `_list` are unioned rather than
replaced (ADR 0003). That is what stops a partial update from wiping data the
caller did not mention - but the same property means there is no path through
this server to detach an event reference, remove a child from a family, or
drop a media reference. Removal requires the Gramps Web UI. The single
exception is an opt-in `replace_lists` on `create_place`, which exists because
a place's parent is a single-valued relationship expressed as a list.

**It does not delete records.** No tool maps to a DELETE endpoint, for any
object type, including tags.

**It does not implement authentication.** It holds one set of credentials from
its environment, obtains a JWT from Gramps Web and refreshes it on a 401. There
is no per-user identity, no session model and no authorization of its own:
every call to the tree is made as the configured account, and anything that
account can do, any client of this server can do.

**It cannot mint owner or admin accounts.** `manage_users` supports list, get
and create, with roles capped at editor (ADR 0005). Bootstrapping an instance
or promoting a co-administrator goes through the Gramps Web UI. It has no
update, no delete and no password-reset path either; the generated password is
the only copy, and it is returned in the tool result.

**It is not a genealogy reasoning engine.** It does not decide whether two
records are the same person, adjudicate conflicting dates, or infer
relationships that no document states. It exposes data and enforces the shape
of a write; the assistant does the reasoning, and the user confirms it. The
project's own research workflow - matching versus hypothesising, homonym
hygiene, how to record an unproven connection - lives in the `genealogiste`
skill, outside the server.

**It does not manage the Gramps Web deployment.** No backup, restore, import,
export, tree creation or configuration. One tree per configured server.

## Constraints and dependencies

**A live Gramps Web instance is required** - at runtime and in the test suite
alike. The server is a client with no local store and no offline mode; it
cannot start usefully without a reachable API URL and credentials for an
account on it. Testing is done against a real server with no mocks (ADR 0002),
so most of the suite cannot run offline at all.

**The API surface depended on** is the Gramps Web REST API: the object
collection and single-object endpoints for the nine record types, the search
endpoint, the media upload endpoint, the timeline, relation, living, facts and
statistics endpoints, the transaction history endpoint, and the users and
token endpoints. Gramps Query Language is passed through to the server rather
than interpreted here, so the queries a client can express are exactly the
queries the deployed Gramps Web version supports.

**MCP Python SDK 2.x, pinned `>=2.0.0,<3`** (ADR 0001). The ceiling is
deliberate: the SDK moved handler registration into constructor arguments and
renamed response fields between majors, and both transports touch that surface.
A future major upgrade is a deliberate piece of work with no incremental path.

**Python 3.12 or newer.** Runtime dependencies are httpx, pydantic, pyjwt,
python-dotenv, uvicorn and fastapi.

**Source files are capped at 500 lines**, enforced by a pre-commit hook
alongside ruff, formatting, copyright-header and no-emoji hooks (ADR 0006).

## Known limitations as of v1.7.0

These are specific, current and unfixed.

- Three tests in `tests/test_parameter_alignment.py` fail offline - the source,
  citation and media alignment cases - on a `media_path` mismatch between the
  parameter models and what the alignment check expects. The offline suite is
  otherwise green.
- `tests/test_server.py:82` still asserts `result.serverInfo.name`, which SDK
  2.x renamed to `server_info`. It has been failing since the migration on
  2026-08-02 and is carried as a known failure rather than fixed.
- `upload_media_file` in the client bypasses `_make_request`, so it has neither
  the shared 401 refresh-and-retry nor the connection and timeout wrapping every
  other call gets. A media upload that hits an expired token fails instead of
  retrying, and a network failure surfaces as a raw httpx exception.
- The file-length pre-commit hook carries `exclude: ^tests/`, so the 500-line
  rule that CLAUDE.md and CONTRIBUTING.md both state without qualification is
  unenforced there. Three test files exceed it today.
- `tree_stats` returns a permission error even for the owner-role account used
  in the reference deployment. `get_facts` is the working alternative for
  tree-level numbers.
- The two transports do not share a code path and nothing tests that they
  expose the same tool set. They also differ on error handling: the stdio path
  catches every exception and returns an error result, while the HTTP
  registration wrapper has no equivalent catch. `/` and `/health` exist on HTTP
  only, so a stdio deployment has no liveness probe.
- The list-merge type dispatch is heuristic: it samples the first item of each
  list to decide how to deduplicate. A list whose first element is
  unrepresentative of the rest takes the wrong branch.
- The sourcing workflow shipped as the `gramps://usage-guide` resource still
  names per-type tools (`find_person`, `find_source`, `find_repository`) that
  the current tool registry does not expose; the equivalents are `find_type`
  and `find_anything`. The workflow it describes is correct, the tool names in
  it are not.
