# User Management

The `manage_users` MCP tool creates and inspects Gramps Web accounts. It wraps
the `/api/users/` endpoints of the Gramps Web REST API and supports three
actions: `list`, `get`, and `create`.

## Purpose

- **`list`** returns every account on the instance: username, e-mail, full
  name, and role.
- **`get`** returns a single account by username.
- **`create`** creates a batch of up to 50 accounts in one call, generating a
  random password for each and assigning one of four roles. This is the
  action that replaces creating ~30 accounts by hand through the web UI, one
  form at a time.

There is no `update`, `delete`, or password-reset action. See
"What the tool cannot do" below.

## Prerequisite: owner or admin rights

The account configured in `.env` (`GRAMPS_USERNAME` / the JWT it authenticates
with) must itself hold the `owner` or `admin` role on the target tree. If it
does not, every `create` call fails with a `403` — the tool detects this case
and reports it explicitly rather than repeating the client's generic
"Permission denied" message.

Check your own role before relying on `create`:

```json
{"action": "get", "name": "<your-.env-username>"}
```

The `role` column in the result must read `owner` or `admin`. If it reads
anything else (`editor`, `contributor`, `member`, `guest`), account creation
will fail until an existing owner promotes it through the Gramps Web UI.

## Roles

Role IDs come from the Gramps Web source
(`gramps_webapi/auth/const.py`). Each role inherits the permissions of the
ones below it.

| Name | ID | Exposed by this tool |
|---|---|---|
| `unconfirmed` | -2 | no |
| `disabled` | -1 | no |
| `guest` | 0 | yes |
| `member` | 1 | yes (default) |
| `contributor` | 2 | yes |
| `editor` | 3 | yes |
| `owner` | 4 | no |
| `admin` | 5 | no |

`owner` and `admin` cannot be assigned through this tool. They are rejected by
the Pydantic parameter schema (a `Literal` of the four permitted role names)
before any network request is made — the model sees this restriction in the
tool's JSON schema up front, rather than discovering it from a runtime error
after a call has already gone out. Granting `owner` or `admin` remains a
manual act in the Gramps Web UI.

## Usage

### `list`

```json
{"action": "list"}
```

Real output from a live instance (e-mail addresses below are illustrative
`example.org` placeholders, not the actual accounts on that server):

```
mcp                  mcp@example.org                MCP User                  owner
fjacquet             fjacquet@example.org           Fred Jacquet              admin
```

Columns are username, e-mail, full name, and role, left-aligned and
space-padded.

### `get`

```json
{"action": "get", "name": "fjacquet"}
```

Returns the same single-row format as `list`, for one account.

### `create`

```json
{
  "action": "create",
  "users": [
    {"name": "alice", "email": "alice@example.org", "role": "editor"},
    {"name": "bob", "email": "bob@example.org", "role": "member"}
  ]
}
```

`full_name` is optional per user (it falls back to `name` if omitted); `role`
defaults to `member` if omitted.

If `alice` is a new account, `bob` is a new account, and `carol` (not shown
above, included for illustration) already exists, the result looks like this:

```
Created 2, skipped 1, failed 0

alice                alice@example.org              editor       kJ3n8QvR2mTpW9xF1cQeZg
bob                  bob@example.org                member       Zm1pR7tWx4NcB8yD5sHqKf
carol                skipped: already exists
```

The header line always reports all three counters, even when one is zero.
Created rows show name, e-mail, role, and the generated password. Skipped and
failed rows show name and a reason instead.

Before creating anything, the tool fetches the existing username list once
and skips any name already present — no `POST` is sent for it and no password
is generated. This makes `create` safe to re-run after a partial failure:
accounts already created (or that already existed) are skipped on the next
attempt, and only the remaining ones are attempted.

Requests are sent one at a time, not in parallel, so a batch of 30 accounts
takes a few seconds and a single account's failure does not abort the rest of
the batch.

## Passwords

Passwords are generated with `secrets.token_urlsafe(16)` — about 128 bits of
entropy — one per created account, and returned as plain text in the tool
result.

**Treat every generated password as exposed from the moment it is created.**
It is returned to the calling model, which means it enters the model's
context and is written to the on-disk session transcript along with
everything else in that conversation. This is a deliberate, accepted
trade-off (documented in the design spec's "Accepted risks" section), not an
oversight: writing passwords to a private server-side file was considered
and rejected in favor of a simpler, visible flow.

The mitigation is operational, not technical: hand each new account out for a
first login and have the password changed immediately. Do not treat a
tool-generated password as a long-term credential.

The tool result is the only copy of a generated password. It is not logged,
stored, or retrievable through any other action in this tool - there is no
`get`-the-password, no reset, no re-issue. If that message is lost (scrolled
past, the transcript truncated, the client crashes before it is read), the
account it describes is still live on the server with no way to recover or
delete it through this tool. Treat losing the message as equivalent to
losing the password permanently, not as an inconvenience to be retried.

The exposure is also wider than "this tool's context and this session's
transcript." Once a password is relayed into a chat reply to satisfy the
user's request, it also lands in the client application's own chat history,
and from there in whatever that client does with its history - local
storage, cloud sync, export, backup. Assume the password is now present
everywhere that conversation is, not just in the two places this tool
directly touches.

The "change on first login" mitigation above is trust-based, not enforced:
Gramps Web has no force-password-change-on-first-login flag, and the account
this tool creates is fully live and usable with the generated password from
the moment `create` returns - there is no intermediate "pending" state. The
least-privilege hedge, when the recipient's discipline about changing the
password promptly cannot be guaranteed, is to create the account at the
`guest` role and have an owner promote it to its intended role through the
Gramps Web UI only after the password change is confirmed, rather than
creating it at its final role up front.

## What the tool cannot do

There is no `update` action (changing e-mail, full name, or role on an
existing account), no `delete` action, and no password-reset action. These
stay in the Gramps Web UI, where they require a deliberate human click rather
than a tool call — they are rare, high-consequence administrative acts.

One consequence worth planning around: an account created with a placeholder
e-mail address (for example, one that is not a real, deliverable mailbox) has
no working password-reset path, because Gramps Web's self-service reset sends
a link to that address. If the first-login password change described above
does not happen and the user later forgets the password, there is no
self-service recovery — the account owner has to resolve it manually in the
Gramps Web UI (or through the API's password-reset-trigger endpoint, which
still requires a real, working e-mail address to be useful). Use real,
reachable e-mail addresses when creating accounts, especially if the
immediate password change cannot be guaranteed.
