# Design: `manage_users` MCP tool

Date: 2026-08-11
Status: approved, not yet implemented

## Problem

Onboarding a group onto a Gramps Web instance means creating roughly thirty
accounts by hand through the web UI, one form at a time, inventing a password
for each. The MCP server currently exposes only genealogical tools (persons,
events, sources, media) and has no way to reach `/api/users/`.

## Goal

One MCP tool, `manage_users`, that lists users, fetches one user, and creates a
batch of accounts with randomly generated passwords and an assigned role.

## Non-goals

- Updating an existing user (e-mail, name, role changes).
- Deleting a user.
- Changing or resetting a password.
- Creating `owner` or `admin` accounts.

These are rare, high-consequence administrative acts. They stay in the Gramps
Web UI, where they take a deliberate human click rather than a tool call.

## Decisions

| Question | Decision |
|---|---|
| Operation scope | `list`, `get`, `create` — mirrors the existing `manage_tags` tool |
| Module layout | Single module `tools/user_tools.py` holding schema, handler and formatting |
| Role ceiling | `guest`, `member`, `contributor`, `editor`; `owner` and `admin` rejected by the schema |
| Password delivery | Returned in the tool result (see Accepted risks) |
| E-mail validation | `str` plus a regex — avoids adding the `email-validator` dependency |
| Batch limit | 50 users per call |
| Test cleanup | Tests create uniquely-named accounts and delete them in a `finally` block |

## Architecture

Single module, by explicit choice. The project's usual split
(`models/parameters/` + `handlers/` + `tools/`) is not followed here: the tool
is self-contained and the whole thing fits in roughly 250 lines, well under the
project's 500-line ceiling.

Files:

| File | Change |
|---|---|
| `src/gramps_mcp/tools/user_tools.py` | New. Schema, handler, output formatting. |
| `src/gramps_mcp/models/api_calls.py` | Add `GET_USERS`, `GET_USER`, `POST_USER`, `DELETE_USER`. |
| `src/gramps_mcp/server.py` | Register `manage_users` in `TOOL_REGISTRY`. |
| `tests/test_user_tools.py` | New. |
| `docs/user-management.md` | New. |
| `README.md` | One bullet in the tool list. |

`DELETE_USER` is added to `ApiCalls` but is deliberately **not** reachable
through any tool action. It exists so tests can clean up after themselves.

No change to the HTTP plumbing is needed. `GrampsWebAPIClient._build_url`
ignores `tree_id` — the tree is carried by the JWT — so the non-tree-scoped
`users/` endpoints work through the existing `make_api_call` path.

### API contract

Specified in `grampsweb-docs/apispec.yaml:288`.

```
GET    /api/users/                 -> list of user objects
GET    /api/users/{user_name}/     -> one user object
POST   /api/users/{user_name}/     -> 201 created / 409 exists
DELETE /api/users/{user_name}/     -> 200
```

`POST` body: `{"email": str, "full_name": str, "password": str, "role": int}`.

Role IDs, from `gramps_webapi/auth/const.py`. Each role inherits the
permissions of the ones below it.

| Name | ID | Exposed by the tool |
|---|---|---|
| `unconfirmed` | -2 | no |
| `disabled` | -1 | no |
| `guest` | 0 | yes |
| `member` | 1 | yes (default) |
| `contributor` | 2 | yes |
| `editor` | 3 | yes |
| `owner` | 4 | no |
| `admin` | 5 | no |

The calling account — the one in `.env` — must itself be `owner` or `admin`,
or every write returns `403`.

## Schema

```python
USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{2,64}$"
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class NewUser(BaseModel):
    """One account to create."""

    name: str = Field(..., pattern=USERNAME_PATTERN)
    email: str = Field(..., pattern=EMAIL_PATTERN)
    full_name: str = ""
    role: Literal["guest", "member", "contributor", "editor"] = "member"


class ManageUsersParams(BaseModel):
    """Parameters for the manage_users tool."""

    action: Literal["list", "get", "create"]
    name: str | None = None                      # required for "get"
    users: list[NewUser] | None = None           # required for "create", 1..50
```

The role ceiling is enforced by the `Literal`, so `owner` and `admin` fail with
a `ValidationError` before any network call. This is a schema constraint rather
than a runtime check on purpose: it is visible to the model in the tool's JSON
schema, so the ceiling is known before a call is attempted, not only after it
fails.

`name` and `users` are validated per action inside the handler, matching how
`manage_tags_tool` handles its own conditional arguments.

## Data flow: `create`

1. One `GET users/` to build the set of existing usernames.
2. For each requested user, if the name already exists: record `skipped`, send
   no `POST`, and generate no password.
3. Otherwise generate `secrets.token_urlsafe(16)` (~128 bits of entropy,
   URL-safe so it survives copy-paste) and `POST users/{name}/`.
4. Requests are sequential, and a single failure does not abort the batch.

The existence pre-check is what makes the operation re-runnable after a partial
failure. It also avoids having to detect `409` by pattern-matching an error
string: `GrampsWebAPIClient._format_http_error` flattens every status code into
a human sentence, so "already exists" and "server broke" would otherwise be
indistinguishable to the caller.

Sequential rather than concurrent: thirty parallel writes against one Gramps
Web worker invite rate-limiting and produce interleaved partial failures that
are hard to read back. Thirty sequential requests take a few seconds.

### Output

`list[TextContent]`, consistent with every other tool in the project.

```
Created 2, skipped 1, failed 0

alice     alice@example.org    editor   kJ3n8QvR2mTp...
bob       bob@example.org      member   Zm1pR7tWx4Nc...
carol     -                    -        skipped: already exists
```

## Error handling

- Global failures (authentication, connection, a malformed `action`) go through
  the module's `_format_error_response`, as in `records_tools.py`.
- A `403` on the first `POST` means the `.env` account lacks owner rights. This
  gets a specific message naming the cause, rather than the generic
  "Permission denied for this operation." the client produces.
- Per-user failures appear as a row in the table. The handler does not raise
  part-way through a batch: a caller must be able to see which accounts were
  created before something went wrong.

## Testing

`tests/test_user_tools.py`, against a live server, no mocks — per the project's
TDD rules. Written before the implementation.

| Test | Network | Checks |
|---|---|---|
| `test_list_users` | live | Returns the known accounts |
| `test_get_user` | live | Fetches the `.env` account |
| `test_role_ceiling_rejected` | none | `owner` / `admin` raise `ValidationError` |
| `test_create_requires_users` | none | `create` without `users` is an error |
| `test_create_skips_existing` | live | Re-creating a known account reports `skipped` |
| `test_create_and_delete` | live | Creates `pytest_<uuid8>`, asserts, deletes in `finally` |

`test_create_and_delete` is the only test that writes. It uses a uuid-suffixed
username so parallel or interrupted runs cannot collide, and cleans up through
`DELETE_USER` directly on the client rather than through the tool.

## Accepted risks

**Generated passwords are returned in the tool result.** This was chosen
knowingly over writing them to a server-side file. The consequence is that the
passwords enter the model's context and are written to the session transcript
on disk, so they must be treated as exposed from the moment they are created.
The mitigation is operational, not technical: accounts created this way are
handed out for a first login and the password is expected to be changed
immediately. The documentation states this at the point of use.

**No password rotation path in the tool.** Since `update` and password reset
are out of scope, a forgotten password is resolved by the owner in the Gramps
Web UI, or through the API's `/users/{name}/password/reset/trigger` endpoint if
SMTP is configured. Creating accounts with placeholder e-mail addresses removes
that second option — the documentation warns about it.

## Documentation

`docs/user-management.md` covers the role table, the owner prerequisite, call
examples for the three actions, and an explicit section on the password
exposure above. `README.md` gets one bullet in the tool list near line 90.
