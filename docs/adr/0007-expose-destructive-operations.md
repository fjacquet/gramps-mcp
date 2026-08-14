# 7. Expose destructive operations: delete, merge, detach, undo

Date: 2026-08-14

## Status

Accepted

## Context

Through v1.8.0 the server could create and update, but had no path to
delete a record, merge two records, or remove a single element from a
list. Every cleanup - a duplicate person, a stray note reference, a source
entered twice - had to be finished by a human clicking through the Gramps
Web UI, even though the assistant had done the research that found the
problem.

Two facts, found while scoping this work, showed the gap was wider than
documented:

- The eleven `DELETE_*` endpoints were **already declared** in
  `models/api_calls.py` and mapped in `models/api_mapping.py`. No tool
  called them, but `tests/conftest.py` did, on every suite run, through
  `delete_entity`. The DELETE path was exercised code, not new code.
- Gramps Web **exposes a merge endpoint**, at
  `POST /api/{type}/{phoenix_handle}/merge/{titanic_handle}`, for person,
  family, event, place, source, citation, repository, media and note.
  `docs/prd.md` never mentioned it.

A cleanup backlog had accumulated against the reference tree that no tool
could execute: junk records left by earlier test runs, an orphan media
object, duplicate families, duplicate source pairs, duplicate places, and
participantless events. None of it was genealogy, and none of it could be
removed through this server.

The full design is recorded in
`docs/superpowers/specs/2026-08-14-delete-merge-detach-design.md`.

## Decision

Expose four tools, following the existing generic-dispatch shape of
`find_type` / `get_type`: a `type` parameter selects the record kind, and
`TYPE_ENDPOINTS` in `src/gramps_mcp/destructive.py` maps each type to its
GET/PUT/DELETE/MERGE calls.

- **`delete_type`** deletes one record by handle or `gramps_id`. It reads
  the record with `backlinks=1` first: if other records still reference it,
  the call is refused and every referencing object is listed, unless
  `force=true`, which deletes anyway and reports what was severed.
- **`merge_type`** merges two records of the same type - the nine that
  Gramps Web offers a merge endpoint for; `tag` is excluded, since no such
  endpoint exists for tags. The "phoenix" survives, the "titanic" is
  absorbed. With `confirm` unset (the default) the tool fetches both records
  and returns a preview - what each holds, what would be lost - and writes
  nothing; `confirm=true` executes. Family merges accept
  `phoenix_father_handle` / `phoenix_mother_handle` to choose which parent
  the merged family keeps, mirroring the one case where Gramps Web's own
  merge endpoint takes extra arguments.
- **`detach_reference`** removes one element from one named list on one
  record - `event_ref_list`, `child_ref_list`, `media_list`, `note_list`,
  `citation_list`, `tag_list`, wherever the record's write model declares
  that list. No Gramps Web endpoint does this directly, so the tool reads
  the object, drops the handle from the named list, and writes it back with
  `replace_lists=[list_name]` on that one list only. Every other list on the
  record still goes through the union merge from ADR 0003, so a
  `detach_reference` call cannot lose data outside the list it was told to
  edit. The call is refused, not silently a no-op, if the target handle is
  not actually present in the named list, and refused if the record's write
  model does not declare that list field at all (see Consequences).
- **`undo_change`** reverses one transaction by id, the recovery path for a
  `delete_type` or `merge_type` that named the wrong record. It polls the
  background task Gramps Web queues for the undo and reports the outcome it
  actually observes, not the immediate 200 the POST returns before the
  background work runs.

Bulk deletion, user-account deletion, and deployment operations (backup,
restore, import, export) stay out of scope, unchanged from before this ADR.

## Consequences

**This ADR supersedes ADR 0003 in scope only.** ADR 0003's union-on-update
behaviour is completely unchanged and remains the default for every write
this server makes: a partial update still cannot wipe data the caller did
not mention, because every `_list` field not explicitly named for
replacement is unioned with what is already stored. What changes is a
single claim ADR 0003 made about the consequence of that design - that
removal is impossible through this server. That claim is no longer true.
Removal now happens through exactly one explicitly named door,
`detach_reference`, which replaces exactly the one list it is told to,
leaving union semantics in force everywhere else on the same record and on
every other write in the server. A reader who takes this ADR as "union
semantics were abandoned" has read it wrong - they were not, and treating
every write as freely destructive again would reintroduce the exact data
loss ADR 0003 was written to prevent.

**`detach_reference` cannot reach every list the read side exposes**,
because the write models were built for creation, not for full parity with
GET. The gap is narrower than it looks: `PersonData`, `CitationData`,
`RepositoryData` and `SourceSaveParams` all inherit `BaseDataModel`, which
declares `note_list`, `media_list`, `attribute_list` and `tag_list`, so the
common cleanup cases (detaching a note, a media reference or a tag) work on
those four types. What is genuinely unreachable: `EventSaveParams` declares
no `media_list`, `attribute_list` or `tag_list`; `MediaSaveParams` declares
no `attribute_list` or `tag_list`; `FamilySaveParams` declares no
`tag_list`, `attribute_list` or `citation_list`; `PersonData` declares no
`person_ref_list`, `citation_list`, `address_list` or `lds_ord_list`; and
`NoteSaveParams` and `TagSaveParams` declare no list fields at all.

The authoritative, per-type list lives in the usage guide's Destructive
Operations section, and `tests/test_alignment_destructive.py` derives the
same table from `model_fields` and fails when guide and models disagree - so
this paragraph cannot drift into being wrong again without a red test.
Calling `detach_reference` against an unreachable combination is refused
loudly, with the reason named, rather than appearing to succeed while
touching nothing. Closing the remaining gaps means adding fields to write
models that were deliberately kept minimal; it is not done here.

**`undo_change` needs `force=true` to undo a deletion**, because of a
confirmed upstream defect in `gramps_webapi`. `old_unchanged()`
(`gramps_webapi/api/tasks.py:782-791`) treats the deleted side of a
delete/add change as "changed" whenever the recorded data is not literally
`None` - but the emptied side of that change is recorded as `{}`, and `{}`
is not `None`, so the server refuses every non-forced delete-undo with a
false "Object has changed" conflict, even when nothing else touched the
record. `force=true` bypasses that check and works reliably; the tool
documents the risk (a later legitimate change to the object would be
silently discarded by the force) rather than defaulting to it. Both
`delete_type` and `merge_type` name `undo_change` as their recovery path,
so this limitation reaches every destructive tool, not just deletion
directly.

**Merge has no backlink guard**, unlike delete. Both the phoenix and the
titanic are legitimately referenced right up to the moment of merge, so
there is nothing to refuse on that basis - which is why merge alone keeps a
confirmation step (`confirm`) instead.

**Deleting a referenced object with `force=true` severs those references**,
the same behaviour the Gramps Web UI's own per-type delete functions have
(`delete_person` removes the person from families, `delete_event` walks
Person and Family backlinks). The server does not add a safety net beyond
what `force` already names.
