# Architecture Decision Records

Each file records one structural decision: what was decided, the context that
forced it, and what the project pays for it. The format is Title, Status,
Context, Decision, Consequences, plus a Date line giving the date the
decision took effect, not the date the record was written.

Records 0001-0006 are retroactive. They were reconstructed in August 2026
from the code, the git history, the design specs under
`docs/superpowers/specs/`, `CLAUDE.md`, `README.md` and `CONTRIBUTING.md`.
Where the original reasoning could not be established from that evidence, the
Context section says so rather than inventing a deliberation.

## Index

| ADR | Decision | Status | Date |
|---|---|---|---|
| [0001](0001-mcp-python-sdk-2x.md) | Build on MCP Python SDK 2.x, pinned below 3 | Accepted | 2026-08-02 |
| [0002](0002-test-against-a-real-gramps-web-server.md) | Test against a real Gramps Web server, with no mocks | Accepted | 2025-09-11 |
| [0003](0003-merge-semantics-for-put-updates.md) | Merge changes into the existing record before a PUT | Accepted | 2025-09-11 |
| [0004](0004-two-transports-http-and-stdio.md) | Carry both HTTP and stdio transports | Accepted | 2025-09-11 |
| [0005](0005-manage-users-role-whitelist.md) | Cap `manage_users` below owner and admin | Accepted | 2026-08-11 |
| [0006](0006-500-line-limit-and-pre-commit-hooks.md) | Enforce a 500-line file limit and a pre-commit hook chain | Accepted | 2025-09-11 |

## When to write a new ADR

Write one when a choice constrains work that comes after it and the next
person would otherwise have to reverse-engineer the reasoning: a dependency
whose major version dictates the code's shape, a rule that applies across the
whole tree, a decision about what the server refuses to do. A change that
touches one module and can be undone by editing that module is not an ADR.
Neither is a decision with no rejected alternative - if there was nothing to
choose between, there is nothing to record.

## Superseding

Records are immutable once accepted. To reverse one, add a new ADR whose
Context explains what changed, and edit the old one's Status line to
`Superseded by ADR NNNN` - nothing else in it. Do not delete or rewrite the
superseded record; its value is that it explains code that may still be in
the tree. Update the index table in this file to match.
