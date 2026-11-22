---
name: gramps-rest-recovery
description: Direct REST access to the Gramps Web API for operations the MCP tools don't cover — auditing broken *_list references, bulk place/hierarchy backfills, and deleting records (people, events, notes) that the MCP layer has no delete_* tool for. Use this when an MCP create_* call has already gone out with a mismatched handle, when the user reports a page giving a 500 error or an empty field that should be populated, or when cleanup requires DELETE. Also load it before any raw REST call, make_api_call script, bulk lot, backup/export, or when a create_*/PUT params model rejects a field (required fields, extra_forbidden, handle-vs-name errors).
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
but **drop the `isinstance(ref, str)` guard when you do**. It is correct
above only because `citation_list` holds bare handle strings. `media_list`,
`child_ref_list`, `event_ref_list`, `placeref_list`, `personref_list` and
`reporef_list` hold dicts, resolved through `el["ref"]`, and that guard skips
every one of them in silence — the audit then prints `TOTAL: 0` because it
checked nothing. Walk their nested `citation_list`/`note_list` too, and treat
a missing or empty `ref` inside an entry as a defect rather than skipping it.
Before trusting a clean result, assert that the collection endpoint actually
returned those fields —
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

## Grayscale JPEGs break the server-side thumbnail

If a media page shows a broken-image icon but `GET
/api/media/<handle>/file` downloads a perfectly valid file, the upload was
almost certainly a grayscale JPEG (mode `L`, sometimes with an embedded
gray ICC profile) — the server's AVIF thumbnail generator produces a
corrupt thumbnail from grayscale source, even though the full-size file is
fine. This happens whenever a scan gets staged via `sips -s format jpeg`
without forcing RGB (see the `genealogiste` skill's disk-filing section).

Find every recent grayscale upload in one pass:

```bash
curl -s "$BASE/media/?pagesize=3000" -H "Authorization: Bearer $TOKEN" > "$SCRATCH/all-media.json"
python3 -c "
import json
data = json.load(open('$SCRATCH/all-media.json'))
recent = [m for m in data if m.get('mime') == 'image/jpeg' and m.get('change', 0) > <since-epoch>]
json.dump({m['gramps_id']: m['handle'] for m in recent}, open('$SCRATCH/gid-to-handle.json', 'w'))
print(len(recent), 'jpeg uploads to check')
"
mkdir -p "$SCRATCH/mediacheck"
python3 -c "
import json
for gid, h in json.load(open('$SCRATCH/gid-to-handle.json')).items():
    print(gid, h)
" | while read -r gid h; do
  curl -s "$BASE/media/$h/file" -H "Authorization: Bearer $TOKEN" -o "$SCRATCH/mediacheck/$gid.jpg"
done
python3 -c "
from PIL import Image
import os
for f in sorted(os.listdir('$SCRATCH/mediacheck')):
    im = Image.open(f'$SCRATCH/mediacheck/{f}')
    if im.mode == 'L':
        print('GRAYSCALE', f)
"
```

Fix each one found the same way as any other file replacement — convert to
RGB, `PUT /api/media/<handle>/file`, handle/links untouched:

```bash
python3 -c "
from PIL import Image
Image.open('$SCRATCH/mediacheck/<gid>.jpg').convert('RGB').save('$SCRATCH/mediacheck/<gid>-fixed.jpg', 'JPEG', quality=90)
"
curl -s -X PUT "$BASE/media/<handle>/file" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: image/jpeg" --data-binary @"$SCRATCH/mediacheck/<gid>-fixed.jpg"
```

Verify by pulling the thumbnail back and decoding it (`GET
/api/media/<handle>/thumbnail/250`, then `Image.open(...).load()` should not
raise) — a 200 status alone doesn't prove the bytes are valid, that's
exactly the failure mode being fixed.

## Missing-field backfills

The same fetch-modify-PUT pattern handles bulk backfills the MCP tools
weren't used for consistently — e.g. every `create_event` in a batch missing
`place` because the citation named a commune but the field was never set.
Match each event's citation back to its source title (source titles follow
`"État civil — ..., <Commune>, registre des décès <year>"`), map commune
name to an existing Place handle via `find_type`, and PUT the `place` field
across the whole batch in one pass rather than one MCP call per record.

## Gotchas moved from CLAUDE.md

- **`GRAMPS_API_URL` has no `/api` suffix.** The REST base is
  `${GRAMPS_API_URL%/}/api`; calling it without the suffix returns the app's HTML
  page with HTTP 200, not an error.
- **`tree_stats` fails against the live tree** ("Permission denied for this
  operation"): the account in `.env` has the owner role, and the tool reads
  `/trees/<id>`, which only an admin may do. Not a regression. The test
  stack's account is created with the admin role precisely so the tool can
  be tested, so `tree_stats` passes there and fails in production.
- **The token endpoint is capped at one request per second.** `AuthManager`
  retries a 429 up to five times, 1.2 s apart (`auth.py`). Without that,
  a burst of clients authenticating together - which the suite does - fails
  with "Authentication failed: HTTP 429", an error about nothing being wrong.
- **The server now calls third-party hosts, separately from the Gramps Web
  API above.** `geocode_place` reaches `geo.api.gouv.fr`, `api3.geo.admin.ch`,
  `query.wikidata.org` and `nominatim.openstreetmap.org`; the Docker
  container needs egress to them. The two detection tools (`find_duplicates`,
  `audit_quality`) do not - they keep working when a gazetteer is
  unreachable. Nominatim's 1 request per second with no burst is an ODbL
  licence obligation encoded in `genealogy/rate_limit.py`, not a courtesy.
- **Reading the API directly is fine; a raw `PUT` is not.** For counts, audits and
  exports, `POST /api/token/` with the `.env` credentials then
  `Authorization: Bearer <access_token>` - per-category totals come back in the
  `X-Total-Count` header with `pagesize=1`, no pagination needed. Never write with
  a raw `PUT`: it bypasses `merge.py` and drops every field the payload omits.
- **Access tokens expire mid-session**, and a failed `curl -o` leaves its target
  untouched - so a stale dump passes for a fresh one. Check the token response,
  and validate a snapshot before `mv`.
- **`AuthManager.get_token()`** is the accessor for raw REST calls (thumbnail
  checks, `X-Total-Count` counts) - there is no `get_access_token`.
- **For a bulk lot, a one-off script calling
  `GrampsWebAPIClient.make_api_call(ApiCalls.PUT_*)` is the right tool** - it goes
  through `merge_put_data()`, so semantics match the MCP tools, which do not scale
  to hundreds of calls. Make it idempotent (source by exact title, media by md5
  against `checksum`, citation by source+page) or a rerun after a partial failure
  duplicates everything.
- **Only `person.media_list` renders on a person page.** Verified 14/09/2026 on
  I1751 (media shown) against I1201 (scan on an event's citation, nothing
  shown). Media on citations and places never surface on the person: the tree
  held 1290 media of which 652 sat on places and 562 on citations, while 63
  people carried one. An image meant to be seen on a person must be in that
  person's own `media_list`.
- **Uploading a media file needs no `docker cp` over REST.**
  `client.upload_media_file(bytes, mime)` POSTs to `media/` and the server
  computes the checksum. The `docker cp` note above applies only to the MCP
  tools' `media_path`, which resolves inside the container.
- **`ApiCalls` is plural for collections, singular for one record**: `POST_PEOPLE`,
  `POST_FAMILIES`, `POST_EVENTS`, `POST_CITATIONS`, `POST_SOURCES`, `POST_NOTES`,
  but `PUT_PERSON`, `PUT_FAMILY`, `PUT_EVENT`, `PUT_NOTE`.
- **POST/PUT return a *list* of transaction entries** `[{_class, handle, new, old,
  type}]`, not the record. Select by `_class`, **never by position** -
  `POST_FAMILIES` returns the father's Person update first.
- **Parameter models require fields even for a one-field update**:
  `EventSaveParams` needs `type` and `citation_list` to change only `place`;
  `PersonData` needs `primary_name` and `gender`; `DateValue` accepts only
  `dateval`/`modifier`/`quality`/`text` - there is no `year`.
  `FamilySaveParams` and `PersonData` reject `citation_list` outright
  (`extra_forbidden`): source a filiation on the `child_ref_list` entry
  (`{"ref": ..., "citation_list": [...]}`), and a corrected name in a note.
  `MediaSaveParams` needs `desc` to add a `note_list` or `citation_list`;
  `CitationData` rejects `confidence` outright and requires `source_handle`
  even to change only a citation's `page` or `media_list`;
  `PlaceSaveParams` rejects `title` (the server derives it). `media_list` is declared on
  `BaseDataModel`, so `PUT_PERSON` accepts it despite `PersonData` not naming
  it, and `replace_lists=["media_list"]` detaches one.
- **`create_event`'s `place` is required, and must be a Place handle, not a
  name** - passing a commune name string is rejected outright
  (`place must be a place handle, not a name`). `find_type(type='place',
  ...)` first; if it doesn't exist, `geocode_place` then `create_place`
  **with `placeref_list` set to the parent** (canton/state, then country)
  in the same call. `code` on `create_place` is a free-text field (postal
  code) - it does not link a parent and is not a substitute for
  `placeref_list`. A place created without one renders as a bare name with
  no hierarchy, and nothing catches this automatically.
- **Back up the live tree before any risky change.** The client has no export
  support, so GET `/api/exporters/gramps/file` with a bearer token from
  `AuthManager`. Gzipped Gramps XML, lossless, ~600 KB. Media files are *not*
  included - the XML carries only `<object>` references.
- **GEDCOM export is extension `ged`, not `gedcom`.** `GET
  /api/exporters/ged/file` (not `.../exporters/gedcom/...`, which 404s).
  `GET /api/exporters/` lists every valid extension if in doubt.
- **The API exposes more than this server uses** (96 of 193 operations; `POST /api/transactions`, `/query`, exporters, `/verify`, `/repair`, `DELETE`). Details: `docs/reference/api-capabilities-notes.md`.
