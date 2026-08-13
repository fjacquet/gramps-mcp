# Design: quality improvements, lot 2 — data fidelity

Date: 2026-08-13
Status: approved, not yet implemented
Branch: `fix/quality-lot2-data-fidelity`

## Context

This is the second of four lots of quality work arising from a full review of
`src/gramps_mcp`. Lot 1 (correctness and stability) merged as pull request #8.
Lot 3 covers ergonomics, lot 4 test debt. No release tag is cut until all four
have landed.

Where lot 1 fixed crashes and wrong endpoints, lot 2 concerns defects that let
the server store or display the wrong thing without ever raising an error. Each
one is silent by nature, which is what makes them worth fixing together.

## Scope

Six defects across five areas.

| Defect | Files |
|---|---|
| A list can be added to but never replaced | `merge.py:52`, `client.py:252`, the tool models that need it |
| `attribute_list` accumulates duplicates | `merge.py:90` |
| Range, span and free-text dates render wrongly | `handlers/date_handler.py:48,54` |
| The `date` field is unvalidated and accepts structures that break the XML export | new `DateValue` model; the five date fields in `event_params.py:51`, `citation_params.py:46`, `media_params.py:77`, `sourced_event_params.py:41,55` |
| `place` accepts a name and silently overwrites a valid handle | `models/parameters/event_params.py:61` |
| `place_params` declares list types the API rejects | `models/parameters/place_params.py:59,63` |
| `place_type` is required even for a partial update | `models/parameters/place_params.py:55` |

Out of scope, belonging to later lots: search result totals, the 422 error
messages that discard the response body, `sort` handling in `analysis.py`, and
the test-debt items the lot 1 ledger deferred.

## The defects

### 1. Lists can be added to but never replaced

`merge_put_data` merges any key ending in `_list` by union, deduplicating on
`ref`. Existing entries always come first, so a caller can add to a list but can
never remove from or replace one.

The consequence in practice: moving a place to a new parent by PUTting
`placeref_list=[{"ref": B}]` over an existing `[{"ref": A}]` yields `[A, B]`.
Gramps uses the first entry, so the move silently does nothing and the place
gains a second enclosure.

**Decision: union stays the default; replacement is requested explicitly.**

The union is load-bearing. A partial update must not wipe lists the caller did
not mention, and the genealogy data-entry workflow relies on
`media_list=[new_ref]` meaning "attach this", not "this is now the only media".
Flipping the default would turn every attach into a read-modify-write and make
data loss the failure mode.

Replacement therefore becomes an explicit, visible request. `merge_put_data`
grows a `replace_lists: list[str] | None` parameter naming the keys that should
be replaced rather than merged; `make_api_call` grows the same parameter and
passes it through; the tools that need it expose it.

Two alternatives were rejected. Deciding per key inside `merge.py` — placeref
replaces, media appends — makes the behaviour implicit and forces every reader
to memorise a table. Threading the intent through a reserved key inside the
payload, or through a context variable, hides a control instruction inside data
or inside implicit async state; lot 1 has just finished removing one piece of
implicit shared state and should not add another.

### 2. `attribute_list` accumulates duplicates

`_merge_list` deduplicates lists of `ref`-carrying dicts and lists of strings.
`attribute_list` entries are `{"type": ..., "value": ...}` dicts with no `ref`,
so they match neither branch and fall through to plain concatenation at
`merge.py:95`. Sending the same attribute on two updates stores it twice; N
apparently idempotent updates leave N copies.

Fix: deduplicate dict items on their full content when they carry no `ref`, so
an identical attribute is not appended twice.

### 3. Range, span and free-text dates render wrongly

`format_date` reads only `dateval[0:3]`. Range and span dates (modifiers 4, 5,
7, 8) carry an eight-element `dateval` — `(d1, m1, y1, s1, d2, m2, y2, s2)` —
so the second date is dropped. A banns range of 12 to 26 March 1885 renders as
`between 12 March 1885`, which is not merely incomplete but actively
misleading: "between" with one date reads as a different claim.

Free-text dates (modifier 6) keep their content in `date_obj["text"]`, which
nothing reads. Their `dateval` is `[0, 0, 0, False]`, so the `year <= 0` guard
fires first and every free-text date displays as `date unknown`.

Note on blast radius: `format_date` returns `date_obj["string"]` when Gramps
supplies it, and Gramps usually does. These defects bite when that preformatted
string is absent, not on every date.

Fix: render both endpoints for the range and span modifiers, and read `text`
for the free-text modifier before the year guard rejects it.

### 4. The `date` field accepts structures that break the XML export

The five date fields are `dict[str, Any]`, so nothing checks that a modifier
promising two dates carries two. `CLAUDE.md` records the consequence from
experience: a modifier 4 or 5 with a four-element `dateval` saves without
error and later crashes the XML export with `IndexError: tuple index out of
range` in `exportxml.py`.

**Decision: replace `dict[str, Any]` with a `DateValue` Pydantic model** that
rejects the malformed combination before it reaches the server. A validator on
the raw dict would protect this one case with a smaller change, but leaves the
rest of the structure untyped and undocumented; the model also gives the tool
schema something honest to advertise, which is what the calling model reads
before constructing a date.

`DateValue` carries `dateval`, `modifier`, `quality` and `text`, and enforces
that modifiers 4, 5, 7 and 8 supply an eight-element `dateval`.

### 5. `place` accepts a name and overwrites a valid handle

`event_params.py:61` declares `place: str | None` with no shape validation, and
`merge_put_data` replaces non-`_list` keys outright. Passing a place *name*
therefore overwrites the event's valid place handle with text that resolves to
nothing. `CLAUDE.md` documents this trap, which means it has already cost
someone real data.

**Decision: reject anything that is not handle-shaped**, in the schema, before
any network call, with a message naming `find_type` as the way to obtain a
handle. Resolving names automatically was considered and rejected: a wrong
match is worse than a refusal, and the ambiguity rules would have to be
invented here rather than left to the caller who knows which Lyon they mean.

### 6. `place_params` declares list types the API rejects

`place_params.py:63` declares `media_list: list[str]` while the API expects
MediaRef objects — which is what `BaseDataModel.media_list` (`list[dict[str,
Any]]`) and the media-attach hook both use. Attaching a photo to a place is
therefore impossible in both directions: the correct dict shape is rejected by
Pydantic, and the advertised string shape is rejected by Gramps. `alt_names:
list[str]` at line 59 has the same mismatch, the API expecting PlaceName
objects.

Fix: align both declarations with what the API accepts and with the rest of the
models.

### 7. `place_type` is required even for a partial update

Added during execution, not present when this spec was first approved.

`place_params.py:55` declares `place_type: str = Field(...)`, and `PUT_PLACE`
shares `PlaceSaveParams` with `POST_PLACES`. A field that a creation genuinely
needs is therefore demanded of every update too: changing one field of a place
means resupplying its type, or the call fails validation before it leaves the
process.

This surfaced while implementing defect 1: the list replacement had just made
moving a place possible, and the move still failed unless the caller also sent
`place_type`. The repository owner approved folding the fix into this lot
rather than deferring it, on the grounds that it is the same class of defect as
the two above — a model that does not match what the API accepts.

Fix: make the field optional, so it is supplied on creation and omitted on a
partial update.

## Testing

The project forbids mocks, fixtures and test clients. Each defect gets one
test, written first and observed failing before the fix.

Two are pure functions and need no server, which makes them the strongest tests
in the lot:

| Defect | Test |
|---|---|
| Replace versus union | `merge_put_data` called with and without `replace_lists`, on plain dicts. |
| Attribute duplication | The same attribute merged twice must appear once. |
| Date rendering | `format_date` on a range, a span and a free-text date object, as plain dicts. |

Three need the live server:

| Defect | Test |
|---|---|
| Date validation | A modifier 4 date with a four-element `dateval` must raise before any request. |
| `place` validation | A place name must raise; a handle must pass. |
| `place_params` types | Attaching a media object to a place must succeed. |

The date and place validation tests assert a `ValidationError` and make no
network call at all, so only the last genuinely needs the server.

Tests that write to the tree clean up in a `finally` block. Live tests need a
URL override from the macOS host, because `.env` targets
`host.docker.internal`, which only resolves inside the container:

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest ...
```

## Integration

Branch `fix/quality-lot2-data-fidelity`. One atomic commit per defect, each
carrying its fix and its test, so a single correction can be read or reverted
alone. One pull request for the lot. No release tag: lots 3 and 4 follow, and
the version is cut once at the end.

## Accepted risk

**This lot makes calls that succeed today start failing.** That is its purpose,
but it is a behaviour change and not merely a fix:

- A `place` given as a name now raises instead of silently destroying the
  event's location.
- A range or span date without its second endpoint now raises instead of saving
  a record that breaks the next backup.

Anything that relied on the permissive behaviour — a saved prompt, a habit, a
script — stops working and must pass a handle or a complete date. The failure
is loud and immediate, which is the improvement, but it is still a break.

Tests that write to the tree write to a real genealogy database, not a scratch
one. As in lot 1, a run killed outright can leave a `Pytest`-prefixed object
behind.
