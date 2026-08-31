# Product requirements: gramps-mcp v1.11.0

This document describes what gramps-mcp is as of v1.11.0 - its scope, its
boundaries, and the constraints it operates under. It is descriptive, not a
roadmap: everything here is true of the code today. [Tools](reference/tools.md)
lists what the server exposes; the architecture decisions behind the
boundaries are recorded in [Decisions](adr/README.md).

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
- **Analysis over the tree.** Breadth-first ancestor and descendant traversal,
  relationship calculation, living-status estimation, timelines for a person,
  a family or a group, and tree-wide statistics.
- **Detection, read-only.** `find_duplicates` clusters candidate duplicate
  people on structural signals - an exact shared birth date, shared parents,
  or a shared spouse and child - and names the record that would survive a
  merge, splitting proved pairs from ones needing human arbitration.
  `audit_quality` runs deterministic consistency rules (R1-R9) and
  completeness rules (D1-D3) across the tree and reports anomalies by
  severity; a rule needing a date is skipped when that date is unknown rather
  than guessed. `geocode_place` resolves a free-text place name against
  gazetteers for France and Switzerland, with Nominatim as a worldwide
  fallback - Germany and the US have no dedicated resolver, matching the
  French/Swiss tree this targets - and reports an ambiguous match instead of
  picking one. None of the three writes; they hand handles and fields to
  `merge_type` and `create_place`.
- **Housekeeping.** Tag listing and creation, transaction history for auditing
  recent changes, and limited user-account creation.
- **Destructive operations, deliberately guarded.** Delete one record
  (`delete_type`, refused while it is still referenced unless `force=true`),
  merge two records of the same type (`merge_type`, previewed unless
  `confirm=true`), remove one element from one named list
  (`detach_reference`), and undo a recorded transaction (`undo_change`). See
  ADR 0007.
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

**Ordinary updates still cannot remove anything from a list.** Updates are
performed by reading the current record, merging the requested changes into
it, and writing the whole thing back; list fields ending in `_list` are
unioned rather than replaced (ADR 0003). That is what stops a partial update
from wiping data the caller did not mention. `create_place` has long carried
an opt-in `replace_lists` for the one case where a list is really a
single-valued relationship (a place's parent). Beyond that, removal is not a
side effect of any `create_*` tool - it goes through `detach_reference`
instead (ADR 0007), which reads a record, drops one handle from one named
list, and writes back with `replace_lists` scoped to exactly that list. Every
other list on the record keeps the union behaviour. `detach_reference` cannot
reach every list the read side exposes - the write models were built for
creation, not full GET parity, so combinations like `media_list` on an event
or `person_ref_list` on a person are refused rather than silently doing
nothing. The per-type reachable set is listed in the usage guide's
Destructive Operations section and pinned against the models by
`tests/test_alignment_destructive.py`.

**It can delete and merge records, one at a time.** `delete_type` deletes a
single record by handle or `gramps_id` and refuses while other records still
reference it, listing them, unless `force=true`. `merge_type` merges two
records of the same type - the nine Gramps Web offers a merge endpoint for;
tags cannot be merged - previewing what would be lost unless `confirm=true`.
Both are recoverable through `undo_change`, which reverses a transaction by
id, though undoing a deletion currently requires `force=true` because of an
upstream Gramps Web bug (see ADR 0007). There is still no bulk deletion: one
object per call, deliberately.

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
collection and single-object endpoints for the nine record types, the delete
endpoint for those types plus tags, the merge endpoint for the nine types
that offer one, the search endpoint, the media upload endpoint, the timeline,
relation, living, facts and statistics endpoints, the transaction history
endpoint and its undo action, and the users and token endpoints. Gramps Query
Language is passed through to the server rather than interpreted here, so the
queries a client can express are exactly the queries the deployed Gramps Web
version supports.

**MCP Python SDK 2.x, pinned `>=2.0.0,<3`** (ADR 0001). The ceiling is
deliberate: the SDK moved handler registration into constructor arguments and
renamed response fields between majors, and both transports touch that surface.
A future major upgrade is a deliberate piece of work with no incremental path.

**Python 3.12 or newer.** Runtime dependencies are httpx, pydantic, pyjwt,
python-dotenv, uvicorn and fastapi.

**Source files are capped at 500 lines**, enforced by a pre-commit hook
alongside ruff, formatting, copyright-header and no-emoji hooks (ADR 0006).

## Known limitations as of v1.11.0

These are specific, current and unfixed.

- `create_sourced_event` always creates a brand-new event; it has no way to
  reuse one that already exists for the person or family. Recording a second
  corroborating citation for the same event produces a duplicate event
  alongside the original. `source_handle` closed the equivalent gap on the
  source side (issue #12) - a duplicate `source_title` is now refused and the
  error names the handle to reuse - but the event side has no such option. To
  add a citation or correct a date on an event that already exists, call
  `create_event` with that event's real handle instead.
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
- `audit_quality` caps its rendered output at 50 findings per severity group.
  Measured against the live tree (~1 736 people), a whole-tree audit with no
  filter produced 1 403 anomalies, 1 392 of them severity `basse`, which would
  render as 1 411 lines. No combination of `limit` and `severity` reaches
  finding 51 of an already-capped group: `limit` is a prefix of the people
  fetched, not an offset, and `severity` only drops other severity groups.
  There is currently no way to page past the cap.
- `find_duplicates` and `audit_quality` scan the whole tree; neither exposes a
  `scope` parameter, and `find_duplicates` has no tunable similarity
  threshold - clustering runs on structural signals alone (an exact shared
  birth date, shared parents, or a shared spouse and child).
- `geocode_place` is the server's first outbound dependency beyond the
  configured Gramps Web instance: it reaches `geo.api.gouv.fr`,
  `api3.geo.admin.ch`, `query.wikidata.org` and `nominatim.openstreetmap.org`.
  A container with no egress to those hosts makes the tool fail outright.
  `find_duplicates` and `audit_quality` make no outbound calls beyond Gramps
  Web and are unaffected. See [Security](operations/security.md) for the
  egress and rate-limit details.
