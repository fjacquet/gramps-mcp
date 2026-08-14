# 3. Merge changes into the existing record before a PUT

Date: 2025-09-11

## Status

Superseded by ADR 0007. The union-on-update behaviour described below is
unchanged and remains the default for every write; only this record's claim
that removal is impossible through this server is superseded - removal now
happens through the one explicitly named door `detach_reference` adds.

## Context

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
(see ADR 0002). The rule it implements:

- A key ending in `_list`, whose value is a list, which is present in the
  existing record, and which is not named in `replace_lists`, is merged as a
  union with existing items first.
- Every other key replaces the existing value outright.
- Neither input is mutated.

Deduplication inside a merged list depends on the item type. Dicts carrying
a `ref` (`event_ref_list`, `media_list`) dedupe on `ref`. Dicts without one
(`attribute_list`, which is `{type, value}`) dedupe on whole content, added
in 2a42d00 after N identical updates were found to leave N copies. Strings
dedupe by value. Mixed or unknown item types are concatenated as-is, the
safe fallback. An empty existing list short-circuits to concatenation, except
for ref-less dicts, which still route through content dedup because a single
incoming list can carry the same dict twice (6d69545).

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
