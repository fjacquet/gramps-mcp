# Security

This page states what the server actually does, verified against the code
that enforces it - not aspirational claims. Read it before deciding what to
expose the MCP server to.

## Authentication to Gramps Web

The server authenticates to your Gramps Web instance with the credentials in
`.env` (`GRAMPS_USERNAME` / `GRAMPS_PASSWORD`), owner or admin role. On first
use it posts to `/token/` and receives a JWT access token
(`src/gramps_mcp/auth.py`, `AuthManager.authenticate`). The token's expiry is
read from the JWT's own `exp` claim; if the response carries no `exp`, the
client assumes a 15-minute lifetime. The token is held in process memory only
and is never written to disk. When it expires, the server re-authenticates
automatically on the next call.

Nothing else is stored: no session cookie, no refresh token, no credential
caching beyond `.env` itself.

## MCP server has no authentication of its own

The MCP server does not authenticate its own callers. It trusts whoever can
reach it on its port and acts using the Gramps Web credentials from `.env`.
This is deliberate - MCP servers are meant to be embedded in applications the
operator controls, not exposed as a public endpoint.

Consequences:

- Do not publish the MCP server port (`8000` by default) to untrusted
  networks. The compose files (`docker-compose.yml`,
  `docker-compose-sqllite.yml`, `docker-compose-pgsql.yml`,
  `docker-compose.dev.yml`) bind it to `127.0.0.1` (loopback only), but this
  only takes effect when the container is recreated. A container still
  running from before that binding was added is still publishing on
  `0.0.0.0` (all interfaces) until recreated.
- If you need access from other machines, put an authenticating reverse
  proxy (nginx, Caddy, etc.) in front of the server. Do not publish the port
  directly.

## Outbound network access

Every write and read against your own family tree goes to the Gramps Web API
host configured in `GRAMPS_API_URL`. That is the only outbound destination
for most of the server's tools.

One tool is the exception. `geocode_place` reaches four third-party hosts,
confirmed in `src/gramps_mcp/genealogy/geo/`:

- `geo.api.gouv.fr` (France, commune lookups - `geo/france.py`,
  `geo/france_ex_communes.py`)
- `api3.geo.admin.ch` (Switzerland, Swisstopo - `geo/suisse.py`)
- `query.wikidata.org` (merged/renamed commune lookups via SPARQL -
  `geo/sparql.py`)
- `nominatim.openstreetmap.org` (worldwide fallback - `geo/nominatim.py`)

This is the first outbound traffic the server sends anywhere other than your
own Gramps Web instance. A container that previously needed no egress at all
now needs egress to these four hosts if `geocode_place` is used.

`find_duplicates` and `audit_quality` make no outbound calls beyond your own
Gramps Web API. They keep working even when every gazetteer above is
unreachable.

### Nominatim rate limit

Nominatim is rate-limited to 1 request per second with no burst
(`requests_per_minute=60, burst=1` in
`src/gramps_mcp/genealogy/rate_limit.py`). This is an ODbL licence
obligation on Nominatim's usage policy, not a courtesy or a performance
setting. Raising it breaks a licence term. The rate limiter can be disabled
entirely with `GRAMPS_MCP_RATE_LIMIT_DISABLED`, but doing so for Nominatim
specifically puts the operator in breach of that licence, not just at risk
of the service throttling or blocking the container.

## Media path confinement

Media uploads accept a `media_path` naming a file already inside the
container (the container has no host mount, so files arrive via
`docker cp`). That path must resolve inside a configured root:
`GRAMPS_MEDIA_IMPORT_ROOT`, defaulting to `/tmp`
(`src/gramps_mcp/config.py`).

Enforcement is in `resolve_media_path`
(`src/gramps_mcp/tools/media_upload.py`): the caller-supplied path and the
configured root are both passed through `os.path.realpath`, which resolves
symlinks and `..` segments, and the resolved path must be a `commonpath` of
the resolved root. A path that resolves outside the root is refused with
`ValueError`; `os.path.isfile` alone was not enough here, because it follows
symlinks - a symlink inside the root pointing at the server's own `.env`
previously passed that check and would have made the linked file's contents
readable back through the media API. Uploads are also capped at 100 MB per
file (`MAX_MEDIA_BYTES`) to bound memory use on the MCP process.

## Input validation

Every write tool validates its parameters through a Pydantic model in
`src/gramps_mcp/models/parameters/` before any request reaches the Gramps
Web API. Unknown fields are silently ignored (Pydantic's default
`extra="ignore"`), so this is shape and type validation, not a guarantee
that every field a caller passes is recognized or acted on.

## Destructive operations

The server exposes operations that delete or irreversibly alter tree data.
Exposing them was a deliberate decision, with a documented cost - see
[ADR 0007: Expose destructive operations](../adr/0007-expose-destructive-operations.md).
