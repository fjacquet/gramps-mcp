# 3. Merge changes into the existing record before a PUT

Date: 2025-09-11

## Status

Superseded by ADR 0007

## Context

**Scope of the supersession.** The union-on-update behaviour described below
is unchanged and remains the default for every write. Only this record's
claim that removal is impossible through this server is superseded - removal
now happens through the one explicitly named door `detach_reference` adds. A
reader who takes ADR 0007 as "union semantics were abandoned" has read it
wrong, and acting on that reading would cause the data loss this record
exists to prevent.

The Gramps Web API's `PUT /objects/{handle}` replaces the whole object with
the submitted body. An MCP tool call, by contrast, is almost always partial:
the model says "add this event reference to this person" and sends only the
new reference. Sent straight through, that PUT would delete the person's
name, birth, every other event, every note and every media reference.

This was not theoretical. The behaviour was fixed in b1438df
(2025-09-11, "Fix person event reference update merging - Issue #9"), which
put a merge block inline in `client.py`. The commit that introduced the pure
module (3d7c8cc, 2026-07-18) was a refactor that changed no behaviour;
its spec states that it "reproduces, unchanged, the current inline logic".
So the decision is dated to the fix, not the extraction.

## Decision

Before any PUT with a body, `client.make_api_call` GETs the current record
by handle and calls `merge_put_data(existing, changes, replace_lists)`. The
merged record is what goes on the wire.

`merge.py` is pure and side-effect-free, so it is unit-testable without a
server - the one deliberate exemption from the live-server testing rule
(see ADR 0002). The rule it implements, as of the `fix/merge-semantics`
branch (2026-08-26), is dispatch by value type rather than by key name:

- A value that is a list, whose key is present as a list in the existing
  record, and which is not named in `replace_lists`, is merged as a union
  with existing items first. This replaced the earlier `_list`-suffix
  check, which missed `urls` and `alt_names` - writable lists whose names
  do not end in `_list` - and sent them down the replace branch, destroying
  entries the caller never mentioned.
- A value that is a dict, whose key is present as a dict in the existing
  record, and which is not named in `replace_lists`, merges sub-key by
  sub-key, recursively, applying the same two rules one level down: a
  nested dict merges, a nested list replaces. This covers `primary_name`,
  which is required on every `PersonData` PUT and so is resent on updates
  that have nothing to do with the name; replacing it wholesale used to
  destroy `surname_list`, `suffix`, `type` and the name's own citations.
  The same rule now also applies inside a reference-list entry (a
  `placeref_list` item's `date`, for instance) - the in-place entry merge
  used to replace a nested object wholesale one level deeper than the
  top-level merge did, which was corrected once found.
- Every other value replaces the existing value outright.
- Neither input is mutated.

Deduplication inside a merged list depends on the item type. Dicts carrying
a `ref` (`event_ref_list`, `media_list`) dedupe on identity, not on the
whole dict: `(ref, role, rect)`, the fields Gramps uses to express
multiplicity in a list - same person, different role, is two entries; same
photo with an updated privacy flag is one entry with new metadata merged
in. `role` and `rect` are normalised to `None` when falsy, because the live
server always sends `"rect": []` on a media reference rather than omitting
the key, and that must resolve to the same identity as the bare
`{"ref": ...}` shape the codebase's own tools send back - otherwise a
resent reference is appended as a duplicate instead of recognised as the
same entry. When `role` or `rect` arrives as an unhashable shape (a dict, or
a list of lists - reachable because the caller is an LLM composing
arguments), identity falls back to a JSON-based key so the entry is treated
as distinct rather than crashing the write - the same protection the
original `json.dumps`-based implementation carried before the `(ref, role,
rect)` rewrite. Dicts without a `ref` (`attribute_list`, which is `{type,
value}`) dedupe on whole content, added in 2a42d00 after N identical
updates were found to leave N copies. Strings dedupe by value. Mixed or
unknown item types are concatenated as-is, the safe fallback. An empty
existing list short-circuits to concatenation, except for ref-less dicts,
which still route through content dedup because a single incoming list can
carry the same dict twice (6d69545).

`replace_lists` (ae0e308, 2026-08-13) is the opt-out. Union is wrong when
the list expresses a single-valued relationship: moving a place to a new
parent means replacing `placeref_list`, not giving the place two parents.
Replacement is named per key at the call site rather than inferred from the
key, so the intent is visible.

## Consequences

Every write costs a read. A PUT is two round trips, always.

Union-by-default means a tool cannot remove an item from a list. There is no
"delete this event reference" path through the MCP surface at all; removal
requires the Gramps Web UI. This is the accepted price of never silently
destroying data, but it is a real functional hole.

`replace_lists` leaks awkwardly through the parameter models. It is popped
out of the raw tool arguments before the Pydantic model is built, so
`validated_params.replace_lists` is always `None` at runtime; the field is
declared on `PlaceSaveParams` purely so it appears in the advertised input
schema. `data_management.py` carries a hand-written `_validate_replace_lists`
because a bare string would be silently expanded into single characters by
`set()`. That is a workaround for a parameter that does not fit the model
pipeline the rest of the tool arguments use.

The type-dispatch in `_merge_list` is heuristic - it samples the first item
of each list. A list whose first element is unrepresentative of the rest
will take the wrong branch.
