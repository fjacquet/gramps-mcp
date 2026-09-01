---
name: gramps-rest-recovery
description: Direct REST access to the Gramps Web API for operations the MCP tools don't cover — auditing broken *_list references, bulk place/hierarchy backfills, and deleting records (people, events, notes) that the MCP layer has no delete_* tool for. Use this when an MCP create_* call has already gone out with a mismatched handle, when the user reports a page giving a 500 error or an empty field that should be populated, or when cleanup requires DELETE.
---

# Gramps REST Recovery

The `mcp__gramps__*` tools cover create/update and read-only lookups. They do
not cover repair. When a bad write already happened — a broken reference, an
orphaned record, a field that should never have been left empty across many
records — go around the MCP layer and hit the REST API directly with a
bearer token, per `CLAUDE.md`'s documented flow (`POST /api/token/` with
`.env` credentials, then `Authorization: Bearer <token>`).

## The one bug this exists to catch

**Never pass a `gramps_id` string (e.g. `"C0868"`) where a `*_list` field
expects a handle.** `citation_list`, `note_list`, `family_list`, etc. store
whatever string you give them — a `create_event` call that mixes
`citation_list: ["C0868", "<real-handle>"]` stores `"C0868"` literally,
producing a broken pseudo-reference invisible until something tries to
render it and gets a 500. This exact mistake happened seven separate times
in one session (2026-08-31/09-01) before being caught by a user-reported
error page, not by the tool. The fix is always: resolve the `gramps_id` to
its real handle with `find_type` *before* the `create_*` call — never pass
the ID string itself into a list field, even mixed in with good handles.

The same class of bug: passing a citation's/event's own handle into the
*wrong* field (e.g. `source_handle` equal to the citation's own `handle`,
or an event's handle landing in another record's `citation_list` by
copy-paste error). The audit script below catches all of these uniformly —
it doesn't matter which field or which record type produced the dangling
reference.

## Getting a token

```bash
set -a; source .env; set +a
BASE="${GRAMPS_API_URL%/}/api"
TOKEN=$(curl -s -X POST "$BASE/token/" -H "Content-Type: application/json" \
  -d "{\"username\":\"$GRAMPS_USERNAME\",\"password\":\"$GRAMPS_PASSWORD\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

Tokens expire mid-session. If a call returns `{"message": "Token has
expired"}`, re-run the block above before retrying — don't assume a fresh
500 means new data corruption.

## Full cross-reference audit

Run this after any batch of `create_event`/`create_citation`/`create_person`
calls that touched more than a handful of records, and always before telling
the user a batch is "done." It has caught real corruption every time it's
been run.

```bash
SCRATCH=/tmp/gramps-audit  # or the session scratchpad dir
mkdir -p "$SCRATCH"
for t in events citations sources media notes people families places; do
  curl -s "$BASE/$t/?pagesize=5000" -H "Authorization: Bearer $TOKEN" > "$SCRATCH/all-$t.json"
done
python3 << 'PYEOF'
import json, re
SCRATCH = "/tmp/gramps-audit"
def load(name): return json.load(open(f"{SCRATCH}/{name}.json"))
events, citations, sources = load("all-events"), load("all-citations"), load("all-sources")
cit_handles = {c['handle'] for c in citations}
src_handles = {s['handle'] for s in sources}
bad = re.compile(r'^[A-Z]\d+$')  # looks like a gramps_id, not a handle
count = 0
for e in events:
    for ref in e.get('citation_list') or []:
        if isinstance(ref, str) and (bad.match(ref) or ref not in cit_handles):
            print('EVENT', e.get('gramps_id'), e['handle'], ref); count += 1
for c in citations:
    sh = c.get('source_handle')
    if sh and (bad.match(sh) or sh not in src_handles):
        print('CITATION-SOURCE', c.get('gramps_id'), c['handle'], sh); count += 1
print('TOTAL:', count)
PYEOF
```

Zero output under `TOTAL:` is the only acceptable result. Extend the same
pattern (`bad.match(ref) or ref not in <handle_set>`) to `note_list`,
`media_list`, `family_list`, `parent_family_list`, `child_ref_list`,
`father_handle`/`mother_handle` when the batch touched people or families —
see the full version used in this project's `catalog.md` audit for the
person/family field list.

## Fixing a broken reference

Fetch the full record, strip the bad entry, PUT the rest back verbatim —
never a partial PUT, the API is not additive-merge on a raw PUT the way the
MCP tools' `create_*` calls are:

```bash
curl -s "$BASE/events/<handle>" -H "Authorization: Bearer $TOKEN" > "$SCRATCH/rec.json"
python3 -c "
import json
d = json.load(open('$SCRATCH/rec.json'))
d['citation_list'] = [c for c in d['citation_list'] if c != '<bad-ref>']
d.pop('change', None)
json.dump(d, open('$SCRATCH/rec-fixed.json', 'w'))
"
curl -s -X PUT "$BASE/events/<handle>" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d @"$SCRATCH/rec-fixed.json"
```

## Deleting a record

`mcp__gramps__*` has no `delete_person`/`delete_event`/`delete_note` — but
the REST API does, at `DELETE /api/{type}/{handle}` for every entity type.
Use it for a genuine duplicate (e.g. a `create_person` fired before checking
the tree, discovering the person already existed) or a stray orphaned
record with no useful data. Confirm with the user before deleting anything
that isn't your own same-session mistake — per the project's general
"never destroy data without checking" rule.

```bash
curl -s -X DELETE "$BASE/people/<handle>" -H "Authorization: Bearer $TOKEN"
```

## Missing-field backfills

The same fetch-modify-PUT pattern handles bulk backfills the MCP tools
weren't used for consistently — e.g. every `create_event` in a batch missing
`place` because the citation named a commune but the field was never set.
Match each event's citation back to its source title (source titles follow
`"État civil — ..., <Commune>, registre des décès <year>"`), map commune
name to an existing Place handle via `find_type`, and PUT the `place` field
across the whole batch in one pass rather than one MCP call per record.
