# Lot 6 - Closing GitHub issues #12, #13, #16, #17

Date: 2026-08-14
Status: approved, ready for implementation planning

## Context

Four issues are open. Three of them (#12, #16, #17) share one root cause:
the parameter models carry Pydantic's default `extra="ignore"`, so any key a
model does not declare is dropped before the request is built. The call
succeeds, nothing is reported, and the caller believes it passed data it did
not pass.

The failure shows up in three directions:

- **#16** - a test passes five keys `PersonData` does not declare. They are
  dropped, the test asserts only that a handle came back, and it goes green
  while linking nothing.
- **#17** - the shipped usage guide names a source field that no model
  declares. An assistant following the guide has the key dropped.
- **#12** - not a dropped key, but the same shape of silent wrong result:
  `create_sourced_event` cannot reuse a source, so one document yields
  duplicate sources with no warning.

**#13** is separate: three tests assert a MIME type that no formatter in the
relevant path can emit, plus one line that prints a raw handle where every
comparable site prints a gramps_id.

### Measured state of the live tree

`tests/test_workflow_marriage.py` has run 18 times against the live
genealogy tree. Each run left behind 2 people, 1 family, 2 notes and 2 media
objects: **36 nameless people, 18 families, 36 notes, 36 media**.

A GQL query on `primary_name.first_name=""` returns 39 people. Three of them
- Pagan (I0466), Stäuble (I0254), Vollmer (I0257) - are legitimate records
with a real surname and no recorded given name. Any cleanup keyed on
`first_name=""` alone would destroy them. The safe discriminator is an empty
given name **and** an empty surname.

**Decision: the 36 orphans are not touched by this work.** Once the test is
fixed the leak stops; the existing records are cleaned by hand in the Gramps
Web UI, at the user's discretion.

## Scope

One branch, four atomic commits. No squash merge - the per-defect commits
must survive.

| Order | Commit | Rationale for the position |
|-------|--------|----------------------------|
| 1 | `fix: #16 marriage workflow test` | Stops the live-tree leak. Highest ongoing cost, so it goes first. |
| 2 | `feat: #17 + root - strict validation` | `extra="forbid"` and `abbrev` must land together, or we ship a window where the guide describes a parameter the server actively rejects. |
| 3 | `feat: #12 source reuse` | |
| 4 | `fix: #13 media assertions + raw handle` | Touches `sourced_event.py` like commit 3; ordered after to avoid a conflict. |

Placing commit 1 before commit 2 means the five bad keys in #16 are corrected
by hand rather than surfaced by `extra="forbid"`. This is a deliberate
trade: the leak stops one commit earlier.

## 1. Root - strict validation

New class in `src/gramps_mcp/models/parameters/base_params.py`:

```python
class StrictModel(BaseModel):
    """Refuse unknown keys instead of silently dropping them."""

    model_config = {"extra": "forbid", "populate_by_name": True}
```

Applied as follows.

**Inherit `StrictModel` through `BaseDataModel`:**

`BaseDataModel(StrictModel)`, which covers `PersonData`, `SourceSaveParams`,
`CitationData` and `RepositoryData` with no further change.

**Newly inherit `BaseDataModel`** - these three are genuine Gramps primary
objects that already redeclare base fields by hand:

- `PlaceSaveParams`
- `FamilySaveParams`
- `EventSaveParams`

Their manual redeclarations of `handle`, `gramps_id`, `note_list`,
`media_list`, `tag_list` and `private` are removed in favour of the inherited
ones. Fields the base does not carry (`father_handle`, `citation_list`,
`lat`/`long`, `replace_lists`, and so on) stay where they are.

**Inherit `StrictModel` directly** - no fields added, because inheriting
`BaseDataModel` would be wrong for each of them:

| Model | Why not `BaseDataModel` |
|-------|-------------------------|
| `NoteSaveParams` | would gain `note_list` - a note referencing notes |
| `MediaSaveParams` | would gain `media_list` - a media referencing media |
| `TagSaveParams`, `ManageTagsParams` | type conflict: the base declares `change: int`, these declare `change: str`. A tag is not a Gramps primary object and has no `tag_list`/`note_list`/`media_list`. |
| `SourcedEventData` | a composite whose fields are prefixed `source_*`/`event_*`/`citation_*`. `private` would have no defined target among the three objects it creates. |

**Nested models** - `DateValue` and `EventReference` inherit `StrictModel`.
Both are write-only: `DateValue`'s four usages are all write models
(`SourcedEventData`, `CitationData`, `MediaSaveParams`, `EventSaveParams`),
and `EventReference` is used only by `PersonData.event_ref_list` - the exact
structure #16 got wrong. `MediaFileParams` is left permissive: it is the one
nested model on a read path (`GET_MEDIA_FILE`).

**Read models are unchanged.** The rule is "harden what writes": a key
dropped on a GET returns a slightly broad result, a key dropped on a write
puts an incomplete record into the tree.

**Side effect, intended:** the JSON schemas published through `TOOL_REGISTRY`
gain `additionalProperties: false`, so the MCP client sees the constraint
rather than only the server enforcing it.

### First task of this commit, before any edit

Run the full suite to inventory existing calls that pass undeclared keys.
`tests/test_workflow_attributes.py` is already known to contain five such
keys, `abbreviation` among them. The inventory determines the real size of
this commit. If it is materially larger than the known cases, report back
before proceeding rather than growing the commit silently.

## 2. #16 - marriage workflow test

In `_create_or_find_person_with_attributes`
(`tests/test_workflow_marriage.py:383-471`):

- `primary_name={"given_name": ..., "surname": ...}` becomes `first_name`
  plus `surname_list`, the shape used by `tests/conftest.py` and every
  handler.
- `event_handle` / `event_role` become
  `event_ref_list=[{"ref": ..., "role": ...}]`.
- `note_handle` becomes `note_list=[...]`.
- `media_handle` becomes `media_list=[{"ref": ...}]`.
- `url` becomes `urls=[...]`.

Both call sites are affected: the update branch (line 442) and the create
branch (line 452).

Assertions are added so the test fails when a link does not form:

- the created people carry their name;
- `Attached notes:` appears in the output;
- the event reference is present.

`PersonData.primary_name` stays `dict[str, Any]`. Tightening it is a
separate issue, out of scope here.

Once the name shape is correct, `find_person_tool` matches on later runs and
the find-or-create branch stops taking the create path every time.

## 3. #12 - source reuse in `create_sourced_event`

`SourcedEventData` gains `source_handle: str | None`, mutually exclusive with
`source_title`. A model validator requires exactly one of the two, which also
makes `source_title` optional - a visible schema change for MCP clients.

`create_sourced_event_tool` behaviour:

- **`source_handle` given** - step 1 (source creation) is skipped and the
  citation attaches to the existing source.
- **`source_title` given** - search for a source with an identical title
  first. On a collision, **refuse**: create nothing, reuse nothing, and
  return an error naming the handles found and inviting the caller to retry
  with `source_handle`.

Implicit dedup by title was considered and rejected. Source titles repeat
heavily in genealogy ("Etat civil, Paris", "Recensement 1911"), and silently
attaching a citation to the wrong source is a worse outcome than a duplicate:
invisible and wrong, rather than visible and redundant.

This makes a previously-succeeding call refuse. No caller in the repository
was found that creates duplicate sources deliberately, but that check was not
exhaustive.

## 4. #13 - media

Two independent parts.

**The raw handle** - `src/gramps_mcp/tools/sourced_event.py:120` emits
`f"Attached media: {media_info.get('handle', 'N/A')}"`. Every comparable site
emits a gramps_id: `source_handler.py:117`, `citation_handler.py:117`,
`person_handler.py:171`, `family_handler.py:206`. Corrected to match.

**The three assertions** - in `tests/test_create_sourcing.py`:

- `TestCreateSourceTool::test_create_source_with_media_path`
- `TestCreateCitationTool::test_create_citation_with_media_path`
- `TestCreateSourcedEventTool::test_create_sourced_event_with_media_path`

The formatters are right, the tests are wrong. `format_media`
(`handlers/media_handler.py:69`) is the only place that emits a MIME type,
and that is coherent: source, citation, person and family formatters list
*references* (`Attached media: O0123`), not full media records. Emitting the
MIME type from `format_source`/`format_citation` would require a
`GET /media/{handle}` per attached media on every format call.

Each assertion becomes a check that the **exact gramps_id of the uploaded
media** appears in the output. This is stronger than checking for an `O`
prefix, and it guards the raw-handle regression above - which a prefix check
would miss, since a raw handle could begin with `O` by chance.

## 5. #17 - `abbrev` on sources

`src/gramps_mcp/resources/gramps-usage-guide.md:186` names **`abbrev`** -
which is the field name on the Gramps `Source` object, not the
`abbreviation` the issue text assumed. The guide names the field correctly;
it is missing from `SourceSaveParams`.

Evidence the field exists: `SOURCE_SORT_KEYS`
(`models/parameters/source_params.py:44-52`) lists `abbrev` among the keys
`GET /sources` accepts for sorting, and an API can only sort on a field it
stores.

Whether `POST /sources` accepts it on write is **not established**. The
Context7 documentation for `gramps-web-api` does not cover request body
schemas.

Test first, per the project's TDD rule: create a source carrying `abbrev`,
read it back through the API, assert the value survives.

- **Value survives** - add `abbrev: str | None` to `SourceSaveParams` and
  pass it through. The guide becomes true; line 186 needs no edit.
- **Value does not survive** - remove the `abbrev` mention from the guide.
  The issue closes on evidence rather than on a guess.

## 6. Testing

The project requires tests against the real Gramps API, with no mocks
standing in for the server. `extra="forbid"` is pure Pydantic validation, so
it is testable offline - the same seam
`tests/test_client_merge.py` already uses.

- **Offline** - one test per hardened model asserting that an unknown key
  raises `ValidationError`. These join the `-m "not integration"` selection,
  which is green.
- **Integration** - #16, #12, #13 and #17 run against the live server.

## 7. Risks and watch items

- **Unknown size of commit 2.** The inventory of calls passing undeclared
  keys may reveal far more than the five known ones. If so, report before
  continuing rather than growing the commit silently.
- **`tests/test_alignment_*.py`** hold hardcoded field inventories that must
  track `gramps-usage-guide.md`. Adding `abbrev` to `SourceSaveParams` will
  likely require updating an inventory - and the guide already documents the
  field, so the update runs in the correct direction.
- **The 500-line rule.** `tests/test_workflow_marriage.py` is 472 lines; the
  #16 assertions will push it past the limit, which
  `.pre-commit-config.yaml`'s `check-file-length` hook enforces on `tests/`
  as well as `src/`. The file must be split in commit 1.
- **`POST /sources` accepting `abbrev`** is unproven; section 5 resolves it
  by test.
- **Visible MCP schema changes** - `additionalProperties: false` across the
  write models, `source_title` becoming optional, `abbrev` added. A client
  that used to send stray keys will now get an error. That is the goal, but
  it belongs in the release notes.
- **The 36 orphan records remain** in the live tree until cleaned by hand.

## Out of scope

- Deleting or tagging the 36 orphan records.
- Tightening `PersonData.primary_name` beyond `dict[str, Any]`.
- Hardening read-path models or `MediaFileParams`.
- Unifying common fields across `NoteSaveParams`, `MediaSaveParams` and the
  tag models.
- Citation reuse in `create_sourced_event` (#12 covers source reuse only).
