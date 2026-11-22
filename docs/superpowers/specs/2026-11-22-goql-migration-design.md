# GOQL migration: gramps-webapi 3.26 compatibility

## Intent
Keep the MCP server working on the Gramps Web the owner actually uses.
Production is gramps-webapi 3.25.2 and moves to 3.26.0 on 2026-11-23. The
local test stack follows `:latest` and is already on 3.26.0, where about 40
integration tests fail. The goal is a server that works and stays used, not
one that is merely up to date.

## Facts (verified)
- 3.26.0 removes Gramps QL: the `gql` parameter is rejected with 422.
  `oql` is gone from list endpoints too.
- The replacement is the `rules` parameter with a `MatchesQuery` rule:
  `rules={"function":"and","rules":[{"name":"MatchesQuery","values":["<expr>"]}]}`.
- Production 3.25.2 already accepts that form. One code path works on both
  versions, so no version detection and no translator are needed.
- The expression language is GOQL, "almost Python": `==`, `in`
  (`"Nidau" in text.string`). Old `=`, `~`, `class = x` and `.length` are
  rejected with 422.
- Not explained by the release notes, cause still unknown: HTTP 400
  `unknown Url keys: 'description'`, 400 `unknown Family keys: 'urls'`,
  and 415 `Media type not supported` on a media upload.

## Goals
1. Every query the server sends uses `rules=MatchesQuery`.
2. Internal `gramps_id` and title lookups also use `rules=MatchesQuery`.
   The `gramps_id=` parameter is NOT a filter: on 3.26.0 `GET /people/?gramps_id=I9999999`
   returns unrelated records, and delete resolves its targets through these
   lookups. It must never be used to resolve a record.
3. The usage guide and the `gql://documentation` resource teach GOQL;
   every example returns more than 0 rows on the seeded 3.26 stack.
4. The suite passes on 3.25.2 and on 3.26.0.
5. The vendored spec and generated API reference move to 3.26.0.

## Non-goals
- A translator from old GQL to GOQL.
- Version detection, or two query modes.
- Using the `/api/<type>/query/` endpoints (`where_expr`, `select`).

## Anti-goals
- Examples in the guide that parse but return no rows.
- Test fakes standing in for the server.

## Approaches considered
1. Version detection plus translation of old GQL: rejected, a parser for a
   dialect that is gone tomorrow.
2. Version detection, pass the expression unchanged: rejected, the guide
   would fork by version.
3. One path on `rules=MatchesQuery` (chosen): works on 3.25.2 and 3.26.0.

## Design
- `client.py`: callers pass a GOQL string; the client sends it as `rules`.
  The `gql` request parameter is removed from the parameter models.
- `find_type` keeps its `gql` argument name for now (renaming breaks the
  `test_alignment_*` inventories); its documented syntax becomes GOQL.
  Rename to `query` is a follow-up.
- `utils.py`, `traversal.py`, `destructive.py`, `search_details.py`:
  lookup expressions change from `gramps_id="X"` to `gramps_id == "X"`
  and go through the same client seam. `escape_gql_literal` stays: GOQL
  string literals escape quotes and backslashes the same way (verified: a
  hostile id `X\" or gramps_id != \"X` matches nothing).
- Compose image tag becomes a variable (`GRAMPSWEB_TAG`, default 3.25.2).
- Separate investigations: `urls`/`description`, Family `urls`, media 415.

## Left to the builder
- Exact GOQL paths per type (e.g. event type: `type.string == "Birth"`
  returns 0 on both servers, so the path is wrong).
- Error message wording for a rejected expression.
- Whether `merge.py` injects `urls` into Family payloads.

## Additions after review
- `build_rules(expr)`: single seam that turns a GOQL string into the
  `rules` parameter, so the next API change touches one function.
- `scripts/check_spec_drift.py`: compares the vendored spec with a server's
  `/api/openapi.json` and reports removed or added parameters. Run before
  every server upgrade.
- Compose image tag is a variable (`GRAMPSWEB_TAG`, default 3.25.2).

## Tests (TDD, real API, no fakes)
Existing tests that use `gql` and must be rewritten to GOQL:
`test_search_find_type` (19 hits), `test_workflow_marriage` (12),
`test_destructive_resolve` (12), `workflow_helpers` (8), `test_strict_params`
(7), `test_server` (5), `test_traversal` (4), `test_search_basic` (3),
`test_get_type_resolution` (3).
New tests:
- `build_rules` output shape (offline, pure).
- `find_type` with a GOQL filter returns rows for each of the 9 record types.
- Internal lookup (`resolve_*`) for each type returns the right record,
  and an empty list (not an error) for a missing id.
- Hostile id cannot widen a lookup (delete safety).
- Doc-as-test: extract every `find_type(... gql='...')` example from the
  usage guide and the `gql://documentation` resource, run it on the seeded
  stack, assert more than 0 rows.
- Old syntax (`~`, `class = x`, `.length`) produces a readable error naming
  GOQL, not a raw 422.
- Spec-drift logic on two small spec documents (pure, offline).
- `test_alignment_*` inventories follow the guide.
- Whole suite runs on 3.25.2 and on 3.26.0 before merge.

## Docs to update
- `src/gramps_mcp/resources/gramps-usage-guide.md` (24 `gql` mentions) and
  `resources/gql-documentation.md`: GOQL syntax, every example verified.
- `docs/user-guide/searching.md`, `README.md` (tested server versions),
  `CLAUDE.md` (test counts, stack version, pinned tag).
- `docs/reference/openapi.json` and `gramps-web-api.md`: regenerate from
  3.26.0 with `scripts/gen_api_reference.py`.
- `.claude/skills/genealogiste/SKILL.md` (4 `gql` mentions).
- `grampsweb-docs/apispec.yaml` is a stale copy: decide in the plan whether
  to refresh or delete it.
- Old plans and specs under `docs/superpowers/` stay as history.
