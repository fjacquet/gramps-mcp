### Project Awareness & Context
- **Use uv** for all Python dependency management and command execution.
  - **Commands**: `uv run python` / `uv run <command>`. Run them **from the repo
    root**: a `cd` elsewhere in the same compound command selects another project
    and breaks the venv (`ModuleNotFoundError: httpx`).
  - **Dependencies**: `uv add <package>` to add, `uv sync` to install
  - **Git commits**: `uv run git commit`, so pre-commit hooks run correctly
  - **Run the server**: `uv run python -m src.gramps_mcp.server` (HTTP, port 8000)
    or `uv run python -m src.gramps_mcp.server stdio` (stdio transport)
  - **Type check**: `uv run mypy src/gramps_mcp --ignore-missing-imports`
  - **First-time setup**: `uv run pre-commit install` so ruff/ruff-format/copyright/
    file-length/no-emoji hooks run automatically on commit
  - **Docs site**: `uv run --with mkdocs-material mkdocs build --strict` before
    pushing anything under `docs/`. Strict mode fails on broken internal links,
    which is the usual way a docs change breaks the published site.
  - **Release**: bump `pyproject.toml` and `src/gramps_mcp/__init__.py`, then run
    `uv lock` **in the same commit**. `uv.lock` pins the project's own version and
    CI runs `uv sync --locked`, so a bump without it turns `main` red while the
    Docker publish stays green - the breakage is invisible from the release page.
  - **Pull requests**: this is a fork, so `gh pr create` needs
    `--repo fjacquet/gramps-mcp`; without it the error names a token problem,
    which is misleading. Merge with `--merge`, never `--squash`.

### Code Structure & Modularity
- **Never create a file longer than 500 lines.** Enforced in `tests/` as well as
  `src/`: `.pre-commit-config.yaml`'s `check-file-length` hook covers the whole
  tree, with no exclusion for tests.
- Layout is `ls src/gramps_mcp/`; only these carry non-obvious intent:
  - `merge.py` - pure merge logic for PUT updates, preserving fields and lists a
    change does not mention; unit-tested without a live server
  - `destructive.py` - same unit-testable pattern for deletions and list-element
    removal
  - `tool_registry.py` - tool name -> description/schema/handler, split out of
    `server.py` to stay under the 500-line limit
  - `traversal.py` - pure breadth-first graph traversal; rendering lives apart in
    `handlers/traversal_handler.py`

### Testing & Reliability (TDD Approach)
- **Write tests first**, red-green-refactor, and update existing tests when the
  logic they cover changes. Tests live in `/tests`, mirroring the app structure.
- **Test against the real Gramps API - do not fake its behaviour.** No test
  clients and no stubbed responses standing in for the server. Setup that
  creates real records against the real server is not faking - that is what
  `tests/conftest.py` does, and tests take those records as fixture arguments
  rather than depending on another test having run. Replacing the transport
  seam alone is permitted in offline unit tests, and is what
  `tests/test_client_merge.py` and `tests/test_http_error_detail.py` do.
  Assertions must read the output of the code under test, never the stub's
  call arguments - a test that asserts on its own mock proves nothing.
- **Most tests need a live Gramps Web server** (`GRAMPS_API_URL` etc. from `.env`)
  and fail with connection errors offline - this is expected, not a regression.
  Server-dependent test modules (or, within a mixed module, the classes that
  need it) carry `pytestmark = pytest.mark.integration`. To run only the
  tests that work offline: `uv run pytest -m "not integration"`. That selection
  is green. CI still runs a narrower explicit file list in
  `.github/workflows/ci.yml`, a strict subset of what the marker selects.
- **The Gramps Web server is remote** (`GRAMPS_API_URL` in `.env` points at a
  hosted instance). Live tests run from the macOS host against it with no env
  override - do not edit `.env`. An empty `docker ps` says nothing about
  whether the tree is reachable; check the API itself.
- **`GRAMPS_API_URL` has no `/api` suffix.** The REST base is
  `${GRAMPS_API_URL%/}/api`; calling it without the suffix returns the app's HTML
  page with HTTP 200, not an error.
- **`tree_stats` returns a permission error even for the owner-role account
  in `.env`.** A `tree_stats` failure ("Permission denied for this
  operation") is an environment fact, not a regression.
- **The MCP server runs in Docker**, container `gramps-mcp-gramps-mcp-1` on the
  published image `ghcr.io/fjacquet/gramps-mcp:latest`, exposed on
  `http://localhost:8000/mcp` (what `.mcp.json` targets). So it executes the
  image, not the working tree - verify a fix from source - and any `media_path`
  must be staged inside it first
  (`docker cp <file> gramps-mcp-gramps-mcp-1:/tmp/`). The repo's compose files
  describe the old local-backend setup and do not serve the live tree.
- **Reading the API directly is fine; a raw `PUT` is not.** For counts, audits and
  exports, `POST /api/token/` with the `.env` credentials then
  `Authorization: Bearer <access_token>` - per-category totals come back in the
  `X-Total-Count` header with `pagesize=1`, no pagination needed. Never write with
  a raw `PUT`: it bypasses `merge.py` and drops every field the payload omits.
- **Access tokens expire mid-session**, and a failed `curl -o` leaves its target
  untouched - so a stale dump passes for a fresh one. Check the token response,
  and validate a snapshot before `mv`.
- **For a bulk lot, a one-off script calling
  `GrampsWebAPIClient.make_api_call(ApiCalls.PUT_*)` is the right tool** - it goes
  through `merge_put_data()`, so semantics match the MCP tools, which do not scale
  to hundreds of calls. Make it idempotent (source by exact title, media by md5
  against `checksum`, citation by source+page) or a rerun after a partial failure
  duplicates everything.
- **Parameter models require fields even for a one-field update**:
  `EventSaveParams` needs `type` and `citation_list` to change only `place`;
  `PersonData` needs `primary_name` and `gender`; `DateValue` accepts only
  `dateval`/`modifier`/`quality`/`text` - there is no `year`.
- **Back up the live tree before any risky change.** The client has no export
  support, so GET `/api/exporters/gramps/file` with a bearer token from
  `AuthManager`. Gzipped Gramps XML, lossless, ~600 KB. Media files are *not*
  included - the XML carries only `<object>` references.
- **The API exposes more than this server uses: 96 of 193 operations.**
  `docs/reference/gramps-web-api.md` lists every operation against the
  `ApiCalls` member that reaches it, generated from the vendored
  `docs/reference/openapi.json` (Gramps Web API 3.21.1) by
  `uv run python scripts/gen_api_reference.py`. Regenerate it after replacing
  the spec. Every `ApiCalls` entry matches a real spec path, so the client
  invents no endpoint; `AuthManager`'s `POST /token/` (`auth.py:128`) is the
  only call that bypasses the enum. Five unused capabilities are worth knowing
  before writing a workaround:
  - **`POST /api/transactions`** commits a batch atomically. The bulk-lot advice
    above predates this knowledge: a one-off script issuing hundreds of `PUT`s
    is still the tested path, but this endpoint is why "hundreds of calls" need
    not be the only shape.
  - **`POST /api/<type>/query`** exists for every record type. The tools go
    through GQL over `GET` instead, which is what returns 500 on notes. Try the
    `POST` body before concluding a query cannot be expressed.
  - **`GET /api/exporters/<id>/file`** is the export the backup note below calls
    missing from the client. It is missing from `ApiCalls`, not from the API.
  - **`POST /api/trees/<id>/verify` and `/repair`** run Check and Repair over
    the API. Worth reaching for before repairing dead handles by hand - though
    Check and Repair is itself what materialises some of them.
  - **`POST /api/media/<handle>/ocr`** exists, and is very likely useless here.
    Reading the scan directly beats it on this corpus: the registers are
    handwritten, pre-1950, in French and German hands. Treat the endpoint as
    unproven on anything older than typescript, and do not route a register
    through it in place of reading it.
- **Traversal tests must assert on the rendered output, not only on
  `TraversalResult.edges`.** Two defects shipped in #27 because the tests
  checked the graph and never called `format_traversal` on the tree they had
  just built. The renderer is where the output lies to the reader.
- **The `tests/test_alignment_*.py` modules hold hardcoded field inventories
  that must track `src/gramps_mcp/resources/gramps-usage-guide.md`.** Adding a
  field to a parameter model without documenting it in that guide fails these
  tests. They are doing their job: the guide is served to MCP clients, so an
  undocumented parameter is one the assistant can pass but was never told
  about. Fix the guide, then the inventory - not the inventory alone.
- **The parameter models ignore unknown keys.** Pydantic's default
  `extra="ignore"` applies, so a test passing a field name a model does not
  declare has that field silently dropped - the call still succeeds and the
  test can still pass while exercising nothing. Check a key against the model
  in `src/gramps_mcp/models/parameters/` before trusting a test that uses it.

### Style & Conventions
- Type hints throughout, Google-style docstrings on every function, `ruff format`
  and `ruff` clean, no emoji in code.
- **Raw Gramps object fields are not localised; profile fields are.** With
  `locale=fr`, `profile.relationship` becomes `Maries` and
  `profile.events[].type` becomes `Naissance`, while raw `family.type` stays
  `Married` and `child_ref_list[].frel` stays `Birth`. Compare against
  English constants only on raw fields, never on profile fields.
- When writing complex logic, add an inline `# Reason:` comment explaining the
  why, not the what. Update `README.md` when features, dependencies or setup
  steps change.

### Genealogy Data Entry Workflow
- See the `genealogiste` skill (`.claude/skills/genealogiste/`) for the full
  research/data-entry workflow (sourcing chain, media attachment, match vs.
  hypothesis handling, homonym hygiene).
- **Never pass a `gramps_id` string (e.g. `"C0619"`) into a `*_list` field
  (`citation_list`, `note_list`, etc.).** The API stores it literally as a
  broken pseudo-handle, invisible until GEDCOM export crashes with
  `HandleError`. Always copy the real handle from the tool's own return
  value. To audit the whole tree for this: fetch every entity via the REST
  API, collect all real handles, then walk every `*_list` field checking
  each ref against that set - `0 broken references found` is the target.
- **`create_sourced_event` always creates a brand-new event** - it never
  matches an existing one for the person/family. To add a corroborating
  citation or correct a date on an event that already exists, call
  `create_event` with that event's real `handle` instead, or you end up
  with an orphan duplicate event alongside the original. It also does **not**
  attach the event to anyone: follow it with
  `create_person(handle=..., event_ref_list=[{ref, role}])`. A `source_title`
  that already exists is refused, and the error names the handle to reuse via
  `source_handle`.
- **`create_family`'s `child_handles`/`father_handle`/`mother_handle` only
  link the family side.** The child person record's own
  `parent_family_list` is not set automatically - call `create_person` with
  `parent_family_list: [<family handle>]` separately, or ancestor lookups
  from the child fail silently.
- **The citation `page` outranks the source `title` for an event's place.** A
  title names the register or the archive's seat, not where the act happened:
  "Table des successions, Bourges" covers deaths at Saint-Martin-d'Auxigny.
  Measured corollaries: match place names on word boundaries ("genevoises"
  matched Genève by substring, 35 events); take the act type named **first** in
  the page, since "mariage ... ne le ..." is a marriage act; and "von X" / "de X"
  in Swiss registers is bourgeois origin, not birthplace.
- **Verify a gazetteer QID against the nearest identified ancestor**, never
  against a region or country: "Le Rocher" (Cher) matched Saint-Antoine-du-Rocher
  (Indre-et-Loire) on the region alone, and "le rocher" is a genuine alias of that
  commune - the label is no protection.
- **`Unknown` places created by Check and Repair are usually not orphans**: 8 of 9
  were the parent of a real commune. Repoint the children onto the right parent
  and check backlinks record by record before deleting anything.
- **Surname casing: store Title Case (`Jacquet`), never ALL-CAPS.** GEDCOM 5.5.1
  mandates the opposite of upper-case ("capitalize the first letter of each part
  and lowercase the other letters") and FamilySearch follows it; ALL-CAPS is a
  French correspondence convention, not a genealogy rule. Matches the sibling
  `genecrew` repo's tested `GrampsUpdateNameTool` invariant, which recases
  `JACQUET` -> `Jacquet` and never the reverse.

### AI Behavior Rules
- **Never use `git stash` or `git reset --hard`.** Both have destroyed
  uncommitted work in this repo. Compare against `main` with `git show
  main:<path>`; move a misplaced commit with `git branch <name> <sha>` then
  `git reset --keep`. If work is lost anyway, pre-commit archives unstaged
  files at every commit: `ls -lat ~/.cache/pre-commit/patch*`, then
  `git apply <patch>`.
