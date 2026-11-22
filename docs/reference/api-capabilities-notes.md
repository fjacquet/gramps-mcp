# Gramps Web API: capabilities this server does not use

The API exposes more than this server uses: 96 of 193 operations.
  `docs/reference/gramps-web-api.md` lists every operation against the
  `ApiCalls` member that reaches it, generated from the vendored
  `docs/reference/openapi.json` (Gramps Web API 3.21.1) by
  `uv run python scripts/gen_api_reference.py`. Regenerate it after replacing
  the spec. Every `ApiCalls` entry matches a real spec path, so the client
  invents no endpoint; `AuthManager`'s `POST /token/` (`auth.py:128`) is the
  only call that bypasses the enum. Five unused capabilities are worth knowing
  before writing a workaround:
  - **`POST /api/transactions`** commits a batch atomically. The usual bulk-lot
    advice predates this knowledge: a one-off script issuing hundreds of `PUT`s
    is still the tested path, but this endpoint is why "hundreds of calls" need
    not be the only shape.
  - **`POST /api/<type>/query`** exists for every record type, but it does
    **not** take a `gql` or `query` field - both are rejected with HTTP 422,
    `"Unknown field"`. Read its schema in `docs/reference/openapi.json` before
    reaching for it. An earlier version of this note suggested it as a
    workaround for the notes GQL bug (issue #28); that was written without trying it.
  - **The notes GQL bug is fixed upstream** (issue #28). On
    gramps-webapi 3.21.1 with gramps 6.0.8, all four reproductions from that
    issue return HTTP 200: `gramps_id="N0216"`, `class = note and private`,
    `text.string ~ "Nidau"` and the people control. `find_type` on notes works.
    Verify against the running server before assuming otherwise - the failure
    was a server-side defect, so it comes and goes with the deployment, not
    with this repo.
  - **`GET /api/exporters/<id>/file`** is the export that backing up the live tree
    relies on, which the client lacks. It is missing from `ApiCalls`, not from the API.
  - **`POST /api/trees/<id>/verify` and `/repair`** run Check and Repair over
    the API. Worth reaching for before repairing dead handles by hand - though
    Check and Repair is itself what materialises some of them.
  - **`POST /api/media/<handle>/ocr`** exists, and is very likely useless here.
    Reading the scan directly beats it on this corpus: the registers are
    handwritten, pre-1950, in French and German hands. Treat the endpoint as
    unproven on anything older than typescript, and do not route a register
    through it in place of reading it.
  - **`DELETE /api/<type>/<handle>`** exists for every entity type
    (people, events, notes, citations, ...) though nothing in `ApiCalls`
    wraps it and no MCP tool exposes it. It is the only way to remove a
    record created by mistake - e.g. a `create_person` fired before checking
    whether the person already existed. A raw PUT is still forbidden
    (bypasses `merge.py`); DELETE is not a PUT and carries no such caveat.
