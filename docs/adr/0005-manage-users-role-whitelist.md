# 5. Cap `manage_users` below owner and admin

Date: 2026-08-11

## Status

Accepted

## Context

The `manage_users` tool exists to solve a clerical problem: onboarding a
batch of relatives onto a family tree meant creating accounts one form at a
time in the Gramps Web UI, inventing a password for each. The design spec
(`docs/superpowers/specs/2026-08-11-user-management-tool-design.md`) scopes
the tool to list, get, and create.

Gramps Web roles are ordered and inherit: guest (0), member (1),
contributor (2), editor (3), owner (4), admin (5). Owner and admin can
manage users, alter the tree's configuration, and grant roles further -
including to themselves.

The tool runs inside an MCP server. Its arguments come from a language model
acting on a natural-language instruction, over a transport that a prompt in
a genealogy note could plausibly reach. Account creation with a role
attached is a privilege-granting operation; the difference between a bad
`create_person` call and a bad `create_user(role=admin)` call is that the
first is fixable and the second is a persistent escalation. The spec also
places updating a user, changing a password, and creating owner or admin
accounts explicitly out of scope, as "rare, high-consequence administrative
acts" that stay in the Gramps Web UI.

## Decision

`ROLE_IDS` in `src/gramps_mcp/tools/user_tools.py` maps only
`{"guest": 0, "member": 1, "contributor": 2, "editor": 3}`, and
`NewUser.role` is a `Literal` over those four names. Owner and admin are
absent by construction: a request naming either fails Pydantic validation
before any network call. There is no flag, env var, or argument that lifts
the cap.

The reverse direction is not restricted. `_role_name` rebuilds a wider map
including owner, admin, disabled and unconfirmed, because existing accounts
hold those roles and `list` must display them. Reading a privileged role is
fine; minting one is not.

Passwords are generated with `secrets.token_urlsafe(16)` - a CSPRNG, about
128 bits, URL-safe so it survives copy-paste - never chosen by the caller
and never derived from anything in the request.

## Consequences

The tool cannot be used to bootstrap an instance or to promote a
co-administrator. Those go through the Gramps Web UI. That is the point, but
it is a real limitation for anyone hoping this tool covers user
administration generally.

The `.env` account must itself be owner or admin for any create to work, so
the credentials the server holds are more privileged than anything the tool
will grant. The cap constrains the tool, not the credential. Anyone who can
reach the server's `.env` is past this control entirely.

The generated passwords are returned in the tool result, which the spec
records as an accepted risk: they enter the model's context and the session
transcript. The mitigation is that these are first-login credentials
expected to be changed, and that the tool has no reset path - a forgotten
password is resolved through the Gramps Web UI or the API's password-reset
endpoint. The passwords are also the only copy; if a batch aborts mid-way,
the tool has to tell the caller to capture what it already printed.
