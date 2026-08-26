# Whole-Codebase Audit - Findings and Remediation Design

**Date:** 2026-08-26
**Scope:** `src/gramps_mcp/` at `main` (2f70c77), ~11 500 lines
**Method:** Four independent reviewers - core plumbing, tools layer, handlers
and models, and a cross-cutting adversarial audit of the write paths. Every
finding recorded below as Confirmed was reproduced independently before being
accepted; findings the reviewers asserted but that could not be reproduced are
recorded as such.

## Why this audit had unusual stakes

The tree served by this MCP server is the user's real genealogy research:
~1426 people, 1735 events, 629 citations, 1028 media objects, built over
years. Two properties make ordinary defect severity misleading here.

First, **the caller is an LLM**. Arguments are model-generated, so they can be
malformed, hallucinated, or subtly wrong in ways a human caller would not
produce. A validation gap that a human would never trip is reachable here.

Second, **the consumer of the output is also an LLM**, which will state what
it reads as fact to a person. Output that omits a qualifier is not a
formatting nit; it is the assistant asserting something false with no hedge
available to it.

Both properties point the same way: **the system must fail loudly rather than
write or render something plausible-looking.**

## Confirmed findings

Each was reproduced by running the code, not by reading it.

### A. PUT merge semantics - one function, six defects

`merge_put_data` (`src/gramps_mcp/merge.py:30-63`) decides what a partial
update preserves. It reasons only about **top-level** keys, and its list
deduplication keys on `ref` alone. Reproduced:

| input | result | damage |
|---|---|---|
| `urls` existing + new | new only | existing URLs destroyed |
| `alt_names` `[A,B]` + `[C]` | `[C]` only | alternate names destroyed |
| `primary_name` partial | partial only | 13 of 15 sub-keys destroyed |
| `primary_name.surname_list` `[X,Y]` + `[X]` | `[X]` only | second surname destroyed |
| place `name` `{value}` partial | `{value}` only | `lang` and `date` destroyed |
| `event_ref_list` role Primary -> Witness | stays Primary | change silently discarded |
| `tag_list` `[a,b]` + `[]` | `[a,b]` | list cannot be emptied |

Two distinct root causes:

1. **Suffix-based dispatch.** The merge branch requires
   `key.endswith("_list")`. `urls` and `alt_names` are declared writable lists
   that do not match, so they take the replace branch. The condition should
   test the *value's type*, not the key's name.
2. **No recursion into dicts.** A nested object is replaced wholesale.
   `primary_name` is a *required* field on `PersonData`
   (`models/parameters/people_params.py:47`), so it is resent on **every**
   person update - including updates that have nothing to do with the name.
   Live sampling confirms every `primary_name` in this tree carries 15
   sub-keys.

A third, narrower cause produces the role-change defect: `_merge_list`
deduplicates ref-carrying dicts on `ref` only, so an entry whose `ref` matches
but whose `role`, `rel`, or `rect` differs is dropped as a duplicate. The tool
then reports success. Recording someone as a witness on an event where they
already appear in another role is a routine genealogy operation that currently
does nothing and says it worked.

The empty-list case is a design question rather than a bug: there is currently
no way to express "empty this list" except `replace_lists`, which is not
reachable on most tools (see finding D).

### B. Unvalidated handles leave the intended endpoint

`_build_url_with_substitution` (`src/gramps_mcp/client.py:311-327`)
interpolates the handle into the URL path with `str.replace` and no
percent-encoding, then `_build_url` passes the result to `urljoin`, which
normalises `..` segments and treats `?` as a query separator. Reproduced:

| handle | resulting URL for `people/{handle}` |
|---|---|
| `../metadata/` | `http://…/api/metadata/` |
| `../users/someuser` | `http://…/api/users/someuser` |
| `abc?keys=x` | `http://…/api/people/abc?keys=x` |
| `.` | `http://…/api/people/` (collection) |

`HANDLE_PATTERN` (`models/parameters/event_params.py:48`) exists and is
enforced - but only on event and sourced-event models. On
`destructive_params.py`, `handle` is a bare `str | None`. So
`delete_type(type="person", handle="../media/<h>")` issues
`DELETE /api/media/<h>` and reports *"Deleted person"* - a different record
class than the caller named, with a report naming the wrong one. `handle="."`
aims a DELETE at a collection endpoint.

This is reachable in the real threat model: the assistant reads free text
(notes, source titles) out of the tree and feeds it back into its own calls.

The codebase already knows the hazard - `tools/user_tools.py:82` guards
`ManageUsersParams.name` with a pattern whose comment cites `"../metadata"`
explicitly. The same guard was never applied to handles.

### C. Network exposure

`config.py` defaults the MCP HTTP server to binding `0.0.0.0` with no
authentication, while `TOOL_REGISTRY` exposes `delete_type`, `merge_type` and
`manage_users` backed by the server's own owner-role Gramps credentials.
`stateless_http=True` means there is not even a session to steal. Any host
able to open a TCP connection to the port has full control of the tree.

### D. `replace_lists` is transport-dependent

`_handle_crud_operation` (`tools/data_management.py:140`) pops and validates
`replace_lists` for person, event, place, source, citation and note. Only
`PlaceSaveParams` declares the field. Every write model inherits `StrictModel`
(`extra="forbid"`, published as `additionalProperties: false`), and
`server.py:86` validates HTTP-transport arguments against the schema before
the handler runs. Net effect: `replace_lists` works over stdio and is rejected
over streamable-http for five of six tools.

`docs/user-guide/gotchas.md:18` documents create_place as "the one escape
hatch", so the restriction is intentional; what is wrong is that the pop reads
as general support.

### E. Rendering - absence rendered as a value

The handlers were written before the qualifier discipline that
`handlers/traversal_handler.py` now demonstrates, and never revisited.

- **`frel`/`mrel` are read nowhere outside `traversal.py`** (confirmed by
  grep over `src/`). The adoptive-parent defect fixed in #27 is still live in
  `family_handler.py`, `family_detail_handler.py`, `person_detail_handler.py`
  and `person_handler.py`. An adopted child renders identically to a birth
  child, so the assistant states adoptive parentage as biological.
- **Birth and death dates are joined unlabelled** at 8 sites:
  `", ".join(filter(None, [birth, death]))`. A person with no birth event but
  a known death renders a lone date, identical in shape to a birth date. The
  assistant will report a death year as a birth year.
- **`living_handler.py:35-36`** renders `'Yes' if is_living else 'No'`, so a
  missing or null `living` key prints **`Living: No`** - the assistant states
  the person is dead on an absence of data.
- **`person_detail_handler.py:148-176`** nests the children listing inside
  `if spouse:`. A family with a single recorded parent - an unmarried mother,
  an unknown father, exactly what registry research produces - loses every
  child from the detail view with no indication.
- **Citation `confidence` is absent end to end**: never rendered, and not
  declarable on `CitationData`, which is `extra="forbid"`. Every citation this
  server creates takes the Gramps default, and nothing downstream can tell a
  Very Low citation from a Very High one.

### F. Unverified handles become dead references

No write tool except `create_sourced_event` confirms a caller-supplied handle
resolves before writing it. `create_family(father_handle=, mother_handle=,
child_handles=)`, `create_person(family_list=, parent_family_list=)`,
`create_citation(source_handle=)` and every `note_list` / `media_list` /
`citation_list` write the handle through. Gramps Web accepts it, so a
hallucinated handle is stored as a dangling pointer and the tool reports
success. `EventSaveParams.place` is shape-checked only, so a fabricated hex
string of the right length passes.

`tools/sourced_event.py:58-69` already implements the correct pattern, with a
comment explaining why failing late leaves orphaned records.

### G. `media_path` is an unrestricted local-file read

`tools/media_upload.py:50-59` opens any path the caller names, reads it
entirely into memory, and uploads it into the tree, where it becomes
retrievable through the media API. No root allowlist, no `realpath`
containment, no size cap. `os.path.isfile` follows symlinks.

## Reported but not reproduced

Recorded so they are not lost, and marked so they are not treated as
established.

- **`_extract_entity_data` ordering** (`tools/data_management.py:65-84`):
  assumes the requested entity is first in the transaction result, with a
  special case for `family` only. A `create_person` carrying `family_list`
  could return the family's handle reported as the person's. The `family`
  special case suggests this broke once already.
- **`AuthManager` has no async mutual exclusion**: `traversal._fetch_level`
  issues 8 concurrent fetches, each calling `get_token`; on an expired token
  all 8 could enter `authenticate()` and re-post the password. The client is
  also replaced without `aclose()` on an event-loop change, leaking pools.
- **Orphan media on a failed write**: the upload happens before the POST/PUT
  in three places, so a later validation failure leaves an unreferenced file.
  One specific path - `create_media` without an explicit `date` - was shown to
  fail model validation on the server's own date shape, but only the model
  half was verified offline.
- **A 2xx body that will not parse as JSON** becomes an error-shaped dict that
  flows into the PUT pre-merge and into `_format_save_response`, producing a
  "Successfully created" prefix over an error body.
- **Family merge fusing both sets of parents** rather than choosing between
  them, per the user's own prior observation. Confirming requires a write.

## Remediation strategy

Four independent workstreams, ordered by damage-per-line-changed. Each is
separately testable and separately mergeable.

1. **PUT merge semantics** (finding A). Pure logic, no server needed, closes
   six confirmed defects. Highest value and lowest risk - do this first.
2. **Handle safety and network exposure** (findings B, C, D). Small, local,
   and closes the only paths that let a call reach a resource the caller
   never named.
3. **Rendering discipline** (finding E). Larger. The fix is one rule -
   *never render absence as a value* - applied consistently, plus lifting
   `traversal_handler`'s qualifier vocabulary into a shared module the other
   handlers consume.
4. **Handle pre-flight verification and `media_path` containment**
   (findings F, G).

The "reported but not reproduced" items are not scheduled. Each needs to be
either reproduced or dismissed first; scheduling work against an unconfirmed
defect is how a plan acquires tasks nobody can verify.

## Constraints that apply to all four workstreams

- **TDD, strictly.** Every change starts with a test watched failing. The
  audit found two defects in code that shipped with passing tests written
  after the fact.
- **No file over 500 lines**, enforced by pre-commit across `src/` and
  `tests/`. `traversal.py` is at 484 and `data_management.py` at 494 - both
  will need a split before growing.
- **Tests must not fake the Gramps API.** Replacing the transport seam is
  permitted offline; assertions read the output of the code under test, never
  a mock's call arguments.
- **Never write to the live server from a test run by hand.** The backup at
  `~/gramps-backups/2026-08-26-tree.gramps` predates all of this work.
- Google-style docstrings, `# Reason:` comments for non-obvious logic, no
  emojis, `ruff format`.
