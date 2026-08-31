# Tool reference

This server registers 30 MCP tools. The count and the names come from
`src/gramps_mcp/tool_registry.py` - `TOOL_REGISTRY` is the single source of
truth; nothing here should ever be trusted over that dict.

Tools are grouped the way a user thinks about them, not the way the code is
laid out: searching and reading, recording, analysis, detection and quality,
housekeeping, destructive.

## The one rule that matters for every write tool

Every `create_*` tool both creates and updates the same record type.
Omit `handle` and it creates a new record; supply an existing `handle` and it
updates that record instead. There is no separate `update_person` or
`update_event` - `create_person` and `create_event` are it.

## Searching and reading

Read-only. Nothing here writes to the tree.

| Tool | What it does |
|---|---|
| `find_type` | Searches any entity type using Gramps Query Language (GQL). Read the `gql://` documentation resource first - the syntax is not guessable. |
| `find_anything` | Text search across all record types. Matches literal text within records; it does not evaluate logical combinations of terms. |
| `get_type` | Gets full details for a person or family by handle or `gramps_id`. |

## Recording

These create or update records. See the rule above: no `handle` creates,
a `handle` updates.

| Tool | What it does |
|---|---|
| `create_person` | Creates or updates a person, including family links and event associations. |
| `create_family` | Creates or updates a family unit, including member relationships. Its `child_handles` / `father_handle` / `mother_handle` link only the family side of the relationship - the child person record's own `parent_family_list` is not set automatically. Follow it with `create_person(handle=..., parent_family_list=[<family handle>])`, or ancestor lookups from the child fail silently. |
| `create_event` | Creates or updates a life event, including person/place associations. |
| `create_place` | Creates or updates a geographic location. |
| `create_source` | Creates or updates a source document. |
| `create_citation` | Creates or updates a citation, including its object associations. |
| `create_note` | Creates or updates a textual note, including its object associations. |
| `create_media` | Creates or updates a media file, including its object associations. |
| `create_repository` | Creates or updates a repository record. |
| `create_sourced_event` | Composite tool: creates a source (or reuses one via `source_handle`), a citation, and an event in one call, auto-wiring the citation onto the event. A `source_title` that matches an existing source's title is refused rather than silently reused or duplicated. It always creates a brand-new event - it never matches an existing person/family event - and it does not attach the event to anyone. Follow it with `create_person(handle=..., event_ref_list=[{ref, role}])` to attach the event. |

## Analysis

Read-only. Derived or computed views over the tree rather than direct lookups.

| Tool | What it does |
|---|---|
| `tree_stats` | Gets tree statistics: counts of people, families, events, etc. In this deployment it returns a permission error even for the owner-role account configured in `.env` - that is an environment fact of the live server, not a bug in this tool. |
| `get_descendants` | Finds all descendants of a person. Token-heavy; keep the generation count low (default 5). |
| `get_ancestors` | Finds all ancestors of a person. Token-heavy; keep the generation count low (default 5). |
| `recent_changes` | Gets recent changes/modifications to the family tree. |
| `get_relationship` | Calculates the relationship between two people. Accepts a handle or `gramps_id` for each. |
| `check_living` | Checks whether a person is living and estimates birth/death dates. Accepts a handle or `gramps_id`. |
| `get_timeline` | Builds a chronological timeline for a person, family, or group (`scope`: person/family/people/families). |
| `get_facts` | Gets interesting facts and statistics about the tree. |

## Detection and quality

Read-only. All three report; none of them write.

| Tool | What it does |
|---|---|
| `find_duplicates` | Finds candidate duplicate people, grouped into clusters with the record that would survive a merge already chosen. Reports pairs the rules proved, separately from pairs that need human arbitration. Feed a proved pair to `merge_type`. |
| `audit_quality` | Runs the deterministic consistency rules over the tree and reports anomalies by severity. Rules that need a date are skipped when the date is unknown, so unknown data never produces a false positive. |
| `geocode_place` | Resolves a free-text place name against authoritative gazetteers (France, Switzerland, worldwide fallback). Returns the administrative chain, coordinates, and a score, and flags an ambiguous match instead of picking one. Pass the result to `create_place` to record it. |

## Housekeeping

Write tools with a deliberately narrow action set - neither supports the
full CRUD surface.

| Tool | What it does |
|---|---|
| `manage_tags` | Lists, gets, or creates/updates tags (`action`: list/get/create). No delete action exists. |
| `manage_users` | Lists, gets, or creates Gramps Web user accounts with generated passwords (`action`: list/get/create - no update or delete). Requires an owner or admin account, and roles it creates are capped at editor. The generated password appears in the response - have the user change it on first login. |

## Destructive

These change or remove data, and two of them are reversible only through a
separate tool.

| Tool | What it does |
|---|---|
| `delete_type` | Deletes one record (person, family, event, place, source, citation, repository, media, note, tag). Refuses while other records still reference it, and lists them; pass `force=true` to delete anyway and sever those references. Reversible with `undo_change`. |
| `detach_reference` | Removes one element from a record's list (`event_ref_list`, `child_ref_list`, `media_list`, `note_list`, `citation_list`, `tag_list`). Only the named list is rewritten - every other list keeps its normal merge-on-update behaviour. Refuses if the element is not in the list. |
| `merge_type` | Merges two records of the same type: the "phoenix" survives, the "titanic" is absorbed, and every reference to the titanic is repointed to the phoenix. Returns a preview and changes nothing unless `confirm=true`. Tags cannot be merged. |
| `undo_change` | Undoes one recorded transaction by id, reversing every object change it made. Use `recent_changes` to find the id. This is the recovery path for a `delete_type` or `merge_type` that went the wrong way. `force=true` is currently required to undo a deletion, because of an upstream Gramps Web bug that misreports the object as changed - see the tool's `force` parameter for the risk this carries. |
