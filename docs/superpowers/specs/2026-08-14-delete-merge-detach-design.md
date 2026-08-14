# Design: destructive operations - `delete_type`, `merge_type`, `detach_reference`, `undo_change`

Date: 2026-08-14
Status: approved, not yet implemented

## Problem

The server is deliberately narrower than the Gramps Web UI: it creates and
updates, but it cannot delete a record, cannot remove an element from a list,
and cannot merge two records. Every cleanup therefore leaves the MCP client and
lands on a human clicking through the UI.

That gap has a cost the project can now measure. A cleanup backlog
(`~/Downloads/gramps/prooves/MENAGE-ARBRE.md`) has accumulated 79 junk records
from the test suite plus, as of the 2026-08-14 duplicate audit, an orphan media
object, a duplicate family, three duplicate source pairs, 22 titleless sources
each carrying an empty citation, three duplicate places, two duplicate
occupation events and 16 participantless events. None of it is genealogy. None
of it can be removed through this server.

The gap is also wider than documented. Two facts found while scoping this work:

- The eleven `DELETE_*` endpoints are **already declared** in
  `models/api_calls.py` and mapped in `models/api_mapping.py`. No tool calls
  them, but `tests/conftest.py` does, on every suite run, through
  `delete_entity`. The DELETE path is exercised code, not new code.
- Gramps Web **does expose merge**, at
  `POST /api/{type}/{phoenix_handle}/merge/{titanic_handle}`, for person,
  family, event, place, source, citation, repository, media and note. The PRD
  never mentions it, and the cleanup backlog asserts the opposite.

So the product boundary was real, but the inventory of what lay behind it was
wrong.

## Goal

Full parity with the Gramps Web UI for destructive operations on tree records:
delete, merge, and removal of a single element from a list, plus an undo path.

## Non-goals

- **User account deletion.** `manage_users` keeps its ceiling. ADR 0005 caps it
  for identity reasons, not data reasons, and deleting an account has nothing
  to do with parity on the tree. `DELETE_USER` stays unexposed.
- **Deployment operations.** No backup, restore, import or export.
- **Bulk deletion.** One object per call. There is no "delete everything
  matching this query" tool; the 79-record backlog is executed one handle at a
  time, deliberately.

## Decisions

| Question | Decision |
|---|---|
| Tool shape | Generic dispatch on a `type` parameter, mirroring `find_type` / `get_type` |
| Tool count | Four: `delete_type`, `merge_type`, `detach_reference`, `undo_change` |
| Delete guard | Refuse while backlinks exist; `force=true` overrides |
| Merge guard | `confirm=false` by default; first call previews, second executes |
| Detach guard | Refuse if the target handle is absent from the named list |
| Recovery | Expose `POST transactions/history/{id}/undo` as `undo_change` |
| List removal | Targeted `replace_lists` on one named list, not a global semantics change |
| ADR | New ADR 0007 supersedes ADR 0003 |
| Rejected | Preview tokens, env-var gating, per-type delete tools |

## Architecture

New files, following the project's usual split:

- `models/parameters/destructive_params.py` - the four Pydantic schemas
- `tools/destructive.py` - the four tool handlers
- `handlers/destructive_handler.py` - formatting of refusals and previews

`tools/data_management.py` is already 18 KB and the project caps files at 500
lines (ADR 0006), so this does not go there.

Two pure functions carry the decision logic, in the spirit of `merge.py`, so
that they are unit-testable without a server:

- `should_refuse_delete(backlinks) -> refusal | None`
- `remove_from_list(obj, list_name, ref_handle) -> obj`

`TOOL_REGISTRY` in `server.py` grows from 23 entries to 27. Registration is
already data-driven, so no change to `register_tools()`.

New `ApiCalls` entries: nine `MERGE_*` and one `POST_TRANSACTION_UNDO`. The
`DELETE_*` entries already exist and need no change.

## Tool surface

### `delete_type`

Parameters: `type` (the nine record types plus `tag`), `handle` or `gramps_id`,
`force: bool = False`.

Flow: resolve the handle, `GET {type}/{handle}?backlinks=1`, then

- no backlinks - delete, and report what was deleted;
- backlinks present and `force` unset - **refuse**, listing every referencing
  object with its type and gramps_id;
- backlinks present and `force=true` - delete, and report both the deletion and
  the references that were severed.

The refusal message is the design's dry run. It names exactly what is attached,
which is the information a preview would have carried, without a second call or
any server state.

### `merge_type`

Parameters: `type`, `phoenix_handle`, `titanic_handle`, `confirm: bool = False`,
plus the type-specific extras the API accepts (`phoenix_father_handle` and
`phoenix_mother_handle` for families).

Accepted types are the nine the API offers a merge endpoint for: person,
family, event, place, source, citation, repository, media, note. `tag` is
deletable but not mergeable, and the schema rejects it here.

The phoenix survives; the titanic is absorbed and disappears. With `confirm`
unset, the tool fetches both records and returns a comparison - what each one
holds, what the titanic contributes, what disappears - and executes nothing.

Merge is the one case where the backlink guard cannot help: both records are
legitimately referenced, so there is nothing to refuse. A phoenix/titanic
inversion silently keeps the wrong record, which is why this tool alone keeps a
confirmation step.

### `detach_reference`

Parameters: `type`, `handle`, `list_name`, `ref_handle`.

`type` accepts any record type that carries lists, which is all nine plus tag.
`list_name` is validated against the fields the target type actually declares,
so a typo is refused rather than silently doing nothing. The lists this is
expected to serve are `event_ref_list`, `child_ref_list`, `media_list`,
`note_list`, `citation_list` and `tag_list`.

No Gramps Web endpoint removes a list element. The tool reads the object,
removes the handle from the named list, and writes it back requesting
replacement of **that one list**. Every other list stays in union mode, so no
unrelated data can be lost by this call.

If `ref_handle` is not in `list_name`, the tool refuses rather than succeeding
while doing nothing.

### `undo_change`

Parameters: `transaction_id`.

Calls `POST transactions/history/{id}/undo`. The existing `recent_changes` tool
already reads the history that supplies the id.

## What changes about ADR 0003

ADR 0003 makes PUT updates merge into the existing record, unioning `*_list`
fields, so that a partial update cannot wipe data the caller did not mention.
That behaviour stays exactly as it is, and it is what made the 2026-08-14
data-entry session safe: attaching note N0121 to person I0166 sent one handle
and preserved N0043 through the union.

What changes is the ADR's scope. It currently reads as "removal is impossible
through this server". ADR 0007 supersedes it with "removal happens through an
explicit, separately named path". Union stays the default for every write;
`detach_reference` is the one door, and it is a door you have to name.

Global replacement semantics were considered and rejected: they would make
every partial call destructive, against a production tree, with silent data
loss on the first omission.

## Testing

The suite tests against a real server with no mocks (ADR 0002), and the
reference tree is production data.

**Offline** (`pytest -m "not integration"`), the two pure functions above:
refusal decisions and list surgery. Following `tests/test_client_merge.py`,
only the transport seam may be replaced, and assertions read the output of the
code under test, never a stub's call arguments.

**Online**, what cannot be simulated: refusal while referenced, deletion once
free, merge, undo. Each test creates its own records through the `Pytest Lot5`
prefixed fixtures and destroys them **with the tool under test**, so the tests
are self-cleaning by construction and a killed run leaves findable debris.

Two hard rules in the destructive test module, because the tree is production:

1. A test never passes a handle it did not create in that same test.
2. `force=true` is never used on anything but a record the test created.

Regression guard: the per-category record count before and after the suite, the
method that measured the existing leaks. A delete tool that over-reaches shows
up in that count, not in a green test.

## Documentation to update

- **ADR 0007**, superseding ADR 0003.
- **`docs/prd.md`**, three claims that become false - "It does not delete
  records", "It cannot remove anything from a list", and the issue #12 note
  about "duplicate sources that no tool can merge or delete" - plus the
  omission that merge exists server-side.
- **`resources/gramps-usage-guide.md`**, served to MCP clients. The
  `tests/test_alignment_*.py` field inventories track it, so the guide is
  updated first and the inventory second.
- **`README.md`**, per the project's own rule for new features.
- Release hygiene: `pyproject.toml`, `src/gramps_mcp/__init__.py` and
  `uv lock` in the same commit, or CI fails on `--locked`.

## Accepted risks

**A caller can skip the preview.** `confirm=true` on the first merge call
executes immediately, as does `force=true` on a first delete. This is the same
level of deliberateness as any other explicit flag; a client that sets both
without reading gets `undo_change`, not a third lock.

**Undo depends on transaction history.** It covers writes made through the API,
which is where these tools write. It is a real net, not an absolute one.

**Deleting a referenced object severs references.** That is what `force` means,
and Gramps Web's own per-type delete functions handle the reference cleanup
(`delete_person` removes the person from families, `delete_event` walks Person
and Family backlinks). The server-side behaviour is the UI's behaviour.

**Permissions are verified, not assumed.** The configured account holds
`PERM_DEL_OBJ`: `conftest.py` deletes successfully on every run. Unlike
`tree_stats`, there is no permission surprise waiting here.
