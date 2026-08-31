# Troubleshooting

This page covers the server and the connection failing - the MCP server won't
start, a tool call can't reach Gramps Web, or a request comes back with an
error you need to categorise. For the data itself doing something
unexpected - merge semantics, search totals, `tree_stats` permission denials -
see [Things that will surprise you](../user-guide/gotchas.md) instead.

## `GRAMPS_API_URL` and the `/api` suffix

**Symptom**: a request against the Gramps Web API returns HTTP 200, but the
body is the web app's HTML page rather than JSON.

**Cause**: `GRAMPS_API_URL` in `.env` must **not** include the `/api` suffix -
the client appends it itself (`get_api_base_url` in `src/gramps_mcp/config.py`
checks whether the URL already ends in `/api` before adding it, so the MCP
server's own requests are not at risk of doubling it). The failure shows up
when you build a request by hand - a `curl` command against
`$GRAMPS_API_URL` for a manual check or bulk operation, as described in
`CLAUDE.md` - and forget to add `/api` yourself. There is no error to catch:
the app server answers any path with its HTML shell and a 200, so the
request looks like it succeeded.

**Fix**: when constructing a URL manually, always use
`${GRAMPS_API_URL%/}/api` as the base, not `GRAMPS_API_URL` alone. If a tool
call through the MCP server itself returns HTML, check `GRAMPS_API_URL` for
an unrelated path segment or port that isn't actually reaching the Gramps
Web instance.

## Cannot connect to the Gramps API

**Symptom**: a tool call fails immediately with `Cannot connect to Gramps
API: ...`.

**Cause**: `httpx.ConnectError` - the configured `GRAMPS_API_URL` host is
unreachable from wherever the MCP server is running. The Gramps Web server
in this project is a remote, hosted instance, not a local container - an
empty `docker ps` on your machine says nothing about whether it is
reachable.

**Fix**: check `GRAMPS_API_URL` in `.env` and confirm the host answers at
all (`curl -I <url>`). If the MCP server runs in Docker, also confirm the
container has egress to that host - a container can be up and healthy while
still unable to reach an external API.

## Request timeout

**Symptom**: a tool call fails with `Request timeout: ...`.

**Cause**: `httpx.TimeoutException` - the network round trip to Gramps Web
did not complete in time, usually on a large result set or a slow link.

**Fix**: retry, narrow the query (smaller `pagesize`, more specific filter),
or check the network path to the host named in `GRAMPS_API_URL`.

## Reading the failure category in an error message

A failed call raises `GrampsAPIError` with a generic sentence naming the
category, built from the HTTP status code in `_format_http_error`
(`src/gramps_mcp/client.py`):

| Status | Message prefix |
| --- | --- |
| 401 | `Authentication failed. Please check your credentials.` |
| 403 | `Permission denied for this operation.` |
| 404 | `Record not found.` |
| 422 | `Invalid data provided.` |
| 500+ | `Server error. Please try again later.` |
| other | `Request failed with status <code>` |

The server's own explanation follows that sentence when it sent one - this
is the part that usually names the offending field on a rejected create or
update. For why that fragment is truncated to 300 characters rather than
shown in full, see
[gotchas.md](../user-guide/gotchas.md#things-that-will-surprise-you).

**401** means the username or password in `.env` is wrong, or the account
lost its session - check `GRAMPS_USERNAME` and `GRAMPS_PASSWORD`.

**403** means the account authenticated fine but lacks permission for that
specific operation. This is not always a misconfiguration: `tree_stats`
returns 403 for every role on the reference deployment, which is an
environment fact, not something to fix - see gotchas.md for that case
specifically and for the substitute call.

**422** almost always means a parameter model field is missing or malformed;
read the trailing detail for the field name before assuming the server is at
fault.

## `geocode_place` fails while other tools keep working

**Symptom**: `geocode_place` errors or returns nothing, while
`find_duplicates`, `audit_quality`, and record-management tools continue to
work normally.

**Cause**: `geocode_place` is the only tool that calls out to third-party
gazetteers - `geo.api.gouv.fr`, `api3.geo.admin.ch`, `query.wikidata.org`,
and `nominatim.openstreetmap.org` - separately from the Gramps Web API
itself. `find_duplicates` and `audit_quality` make no outbound calls beyond
your own Gramps Web API and keep working even when every gazetteer above is
unreachable. A single failing gazetteer-dependent tool is evidence of an
egress or third-party outage, not evidence the MCP server or Gramps Web is
broken.

**Fix**: check that the host running the MCP server (the Docker container,
if that's where it runs) has outbound network access to those four hosts.
Nominatim in particular enforces 1 request per second with no burst,
per its ODbL licence terms - a burst of geocoding calls will see requests
queue or fail there specifically, which is expected, not a bug.

## GEDCOM export crashes with `HandleError`

**Symptom**: everyday read and write tool calls succeed with no errors, but
a GEDCOM export crashes later with `HandleError`.

**Cause**: a `*_list` field (`citation_list`, `note_list`, `event_ref_list`,
and similar) expects a real object **handle**, not a `gramps_id` string like
`"C0619"`. The API accepts a `gramps_id` in that position without
complaint and stores it literally as a broken pseudo-handle - nothing about
the write fails, and the record looks normal in every read until GEDCOM
export walks the reference and cannot resolve it.

**Fix**: always copy the handle from the return value of the tool call that
created the record, never from a `gramps_id` you already have on hand. To
audit an existing tree for this defect: fetch every entity via the REST
API, collect the full set of real handles, then check every `*_list` field
against that set - the target is `0 broken references found`.

## Docker container issues

**Symptom**: the MCP server is unreachable at `http://localhost:8000/mcp`,
or tool calls fail before ever reaching Gramps Web.

**Cause**: the container itself - `gramps-mcp-gramps-mcp-1`, running
`ghcr.io/fjacquet/gramps-mcp:latest` - is not up, not healthy, or was
started from a stale image. Because the server executes the published
image rather than the working tree, a fix committed to source is not live
until the container is rebuilt or repulled.

**Fix**:

```bash
docker compose ps
docker compose logs -f gramps-mcp
```

The compose file defines a healthcheck against `http://localhost:8000/health`
with a 30-second interval - a container stuck in `unhealthy` is a stronger
signal than the port simply not answering yet during startup. If a code
fix should already be live, confirm the image was pulled again
(`pull_policy: always` in `docker-compose.yml` pulls on `docker compose up`,
not automatically in the background).

## Logging

`src/gramps_mcp/server.py` calls `logging.basicConfig(level=logging.INFO)`
at import time - the log level is fixed at INFO and is not controlled by an
environment variable. There is no `DEBUG` or `LOG_LEVEL` setting to enable
verbose output; `docker compose logs -f gramps-mcp` (or `-f` against
whichever compose project name is in use) is the available view into what
the server logged at INFO level for a given request.
