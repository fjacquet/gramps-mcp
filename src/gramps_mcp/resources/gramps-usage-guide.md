# Gramps MCP Tools - Proper Usage Guide

## Understanding Gramps Data Structure

Gramps is fundamentally **source-focused** and **event-focused**. All genealogical information should be properly sourced and linked to verifiable events. This guide explains the correct order of operations when entering data.

## The Proper Workflow

### **FUNDAMENTAL RULE: Always Find First**
**Before creating ANY entity, always search first.**

There are exactly two search tools:

- `find_type(type=..., gql=..., max_results=20, page=None)` searches ONE record
  type with a GQL filter. `type` accepts `person`, `family`, `event`, `place`,
  `source`, `citation`, `media`, `repository`, `note`. Read the
  `gql://documentation` resource for the filter syntax and the full property list.
- `find_anything(query=..., max_results=20, page=None)` is a plain full-text
  search across every record type. It matches literal text inside records, not
  logical combinations, so give it one distinctive string.

There is no `find_person`, `find_source`, `find_place` or any other per-type
find tool - every type-scoped search goes through `find_type`.

To read one record in full, use `get_type(type=..., handle=...)` or
`get_type(type=..., gramps_id=...)`. `get_type` supports `person` and `family`
only; for the other types use `find_type` with a filter on `gramps_id` or
`handle`.

**Notes cannot be filtered with GQL.** `find_type(type="note", gql=...)`
returns HTTP 500 for *every* filter, whatever the left-hand side - including
`gramps_id = "N0216"`. This is a server-side bug in `gramps-ql` 0.4.0, which
converts an object to a dict only for `PrimaryObject` subclasses; `Note` is
the one primary record type in Gramps that is not one, so a raw `Note`
reaches a matcher expecting a dict and raises. It is fixed upstream in
`gramps-ql` 0.5.0, but no published `grampsweb` image ships that version yet,
so the failure stands on this server.

Until then, to find a note:
- `find_anything(query="...")` - works, but truncates note text at 500
  characters, so use it to locate the note, not to read it.
- `get_type` does not accept `note`, so once you have the handle, read the
  note through `find_type(type="note")` **without** a `gql` argument and page
  through the results, or ask the user to query the REST API directly.

Every other record type filters normally; notes are the sole exception.

- If entity exists and **already contains all the new info**: Use the existing entity as-is (no update needed)
- If entity exists but **missing some of the new info**: Use `create_X` with the existing handle to **update** it
- If entity doesn't exist: Use `create_X` without handle to **create** new entity

**What an update preserves.** A `create_X` call carrying a handle is an
update, and it merges rather than overwrites: any field you do not mention is
kept, lists you supply are added to the existing ones, and a nested object
such as `primary_name` merges sub-key by sub-key. So sending
`primary_name={"first_name": "Jean"}` changes the first name and leaves the
surname, suffix and name type alone.

Three consequences worth knowing:

- **Adding an entry to a top-level list never removes one.** To remove one,
  use `detach_reference`. Supplying an empty top-level list does nothing.
- **A list nested inside an object states that list.** Sending
  `primary_name={"surname_list": [...]}` replaces the stored surnames rather
  than adding to them, so a correction works - but a second surname you omit
  is lost. Send the whole list. Unlike a top-level list, an empty nested
  list is not a no-op: sending `primary_name={"surname_list": []}` clears
  the stored surnames.
- **A reference is identified by its handle plus its role and region.** The
  same person on one event as Primary and again as Family is two entries and
  both are kept. Re-sending the same reference with a changed detail that is
  not role or region - a privacy flag, for instance - updates the entry that
  is already there instead of adding a second one.

### 1. Repository First
When you have a source document, start with the repository (archive, library, courthouse, etc.):

**Repository requires:**
- **Name** (required): "National Archives", "City Hall Records", "St. Mary's Church"
- **Type** (required): Archive, Library, Church, etc.
- **URL** (optional): If present, create with type, path, and description
- **Note** (optional): If present, use `create_note` tool first, then link to repository

**Process:**
- **First**: Search for an existing repository with
  `find_type(type="repository", gql='class = repository and name ~ "St. Mary"')`
- **If found and complete**: Use existing repository as-is
- **If found but missing info**: Use `create_repository` with existing handle to update repository
- **If not found**: Use `create_repository` without handle to create new repository

### 2. Create the Source
Create the actual source document within the repository:

**Source requires:**
- **Title** (required): "Birth Register 1850-1860", "Marriage Book Vol. 3", "Death Certificates"
- **Repository link** (required): Handle of the repository created in step 1
- **Author** (optional): Author or compiler of the source
- **Publication info** (optional): Publisher, publication date, edition, etc.
- **Media** (optional): If present, use `create_media` tool first, then link to source
- **`media_path`** (optional): Path to a file to upload and attach in one
  step, instead of calling `create_media` first. The path must resolve inside
  `GRAMPS_MEDIA_IMPORT_ROOT` (default `/tmp`) - see "Where `media_path` must
  point" below. The resulting reference is appended to `media_list`; the path
  is cleared after upload, so pass it only when the file is not already in the
  tree
- **Note** (optional): If present, use `create_note` tool first, then link to source

**Process:**
- **First**: Search for an existing source document with
  `find_type(type="source", gql='class = source and title ~ "Marriage Register"')`
- **If found and complete**: Use existing source as-is
- **If found but missing info**: Use `create_source` with existing handle to update source
- **If not found**: Use `create_source` without handle to create new source

### 3. Create the Citation
Create a citation that references the specific page/entry in the source:

**Citation requires:**
- **Source link** (required): Handle of the source created in step 2
- **Page** (optional): "Page 45, Entry 23", "Certificate #1234", specific page reference
- **Date** (optional): Date when the citation was accessed or created
- **Media** (optional): If present, use `create_media` tool first, then link to citation
- **`media_path`** (optional): Path to a file to upload and attach in one
  step, instead of calling `create_media` first. The path must resolve inside
  `GRAMPS_MEDIA_IMPORT_ROOT` (default `/tmp`) - see "Where `media_path` must
  point" below. The resulting reference is appended to `media_list`; the path
  is cleared after upload, so pass it only when the file is not already in the
  tree
- **Notes** (optional): If present, use `create_note` tool first, then link to citation

**Process:**
- **First**: Search for an existing citation with
  `find_type(type="citation", gql='class = citation and source_handle = "<source handle>" and page ~ "Page 67"')`
- **If found and complete**: Use existing citation as-is
- **If found but missing info**: Use `create_citation` with existing handle to update citation
- **If not found**: Use `create_citation` without handle to create new citation

### 4. Create the Event
Now create the life event that was documented in that citation:

**Event requires:**
- **Type** (required): birth, death, marriage, baptism, burial, etc.
- **Citation** (required): Handle of the citation created in step 3
- **Date** (optional): Date when the event occurred
- **Description** (optional): Additional details about the event
- **Place** (optional): If present, search with
  `find_type(type="place", gql='class = place and name.value = "Boston"')` first,
  then `create_place` if not found

**Process:**
- **First**: Search for an existing event with
  `find_type(type="event", gql='class = event and type.string = "Marriage" and description ~ "Smith"')`
- **If found and complete**: Use existing event as-is
- **If found but missing info**: Use `create_event` with existing handle to update event
- **If not found**: Use `create_event` without handle to create new event

### 5. Link People to Events
**CRITICAL**: Events are linked TO people, not people to events.

#### Person Creation Attributes:
**Person requires:**
- **Given name** (required): First name(s)
- **Surname** (required): Last name(s)  
- **Gender** (required): Female, Male, or Unknown
- **Notes** (optional): If present, use `create_note` tool first, then link to person
- **Media** (optional): If present, use `create_media` tool first, then link to person
- **URLs** (optional): Web links with type, path, and description
- **Birth/Death info**: Should be added as separate birth/death events, NOT directly to person

#### For Each Person Involved:
- **First**: Search for existing records with
  `find_type(type="person", gql='class = person and primary_name.surname_list.any.surname = "Smith"')`
  (or `find_anything(query="John Smith")` for a loose text sweep)
- Search by name, approximate dates, and locations - never on a name alone
- **Always notify the user** if potential matches are found
- Ask the user to confirm if it's the same person or should be a new record

**Then for each person:**
- **If same person**: Use `create_person` with existing handle to update person AND add event with role
- **If new person**: Use `create_person` without handle to create new person (given name, surname, gender) AND add event with role

**Note**: Adding an event to a person is always an update operation using `create_person` with the person's handle.

**Person-Event linking requires:**
- **Person handle**: From find/create person process
- **Event handle**: From step 4 (the event created)
- **Role**: The person's role in the event (bride, groom, witness, child, parent, etc.)

**Important**: Birth dates, birth places, death dates, and death places should be created as separate birth/death events and linked to the person, not stored directly in the person record.

### 6. Create Family Units (when relationships exist)
**CRITICAL**: Family relationships must be supported by sourced events.

#### Family Creation Attributes:
**Family requires:**
- **Type** (optional): Relationship type (`Married`, `Unmarried`, `Civil Union`,
  etc.). Gramps Web displays "Unknown" in the UI when this is left unset -
  set it explicitly for any family representing an actual marriage.
- **Father handle** (optional): Handle of the father person
- **Mother handle** (optional): Handle of the mother person  
- **Children handles** (optional): List of handles of child persons
- **Notes** (optional): If present, use `create_note` tool first, then link to family
- **Media** (optional): If present, use `create_media` tool first, then link to family
- **URLs** (optional): Web links with type, path, and description
- **Family events**: Marriage, divorce events are added to the family unit
- **All relationships must be supported by sourced events**

#### Event Distribution:
- **Individual events** (birth, death, baptism, burial): Added to person records
- **Family events** (marriage, divorce, engagement): Added to family records

#### Process:
- **First**: Search for an existing family unit with
  `find_type(type="family", gql='class = family and father_handle = "<father handle>" and mother_handle = "<mother handle>"')`
- **If found and complete**: Use existing family as-is
- **If found but missing info**: Use `create_family` with existing handle to update family
- **If not found**: Use `create_family` without handle to create new family

## Example Workflow: Processing a Marriage Record

```
1. Repository: "St. Mary's Catholic Church, Boston"
   → If repository has note: create_note first, get note handle
   → find_type(type="repository", gql='class = repository and name ~ "St. Mary"')
   → If found and complete: use existing repository
   → If found but missing info: create_repository with handle (update repository)
   → If not found: create_repository without handle (create repository with name, type, optional URL, optional note handle)

2. Source: "Marriage Register 1875-1880"  
   → If source has media: create_media first, get media handle
   → If source has note: create_note first, get note handle
   → find_type(type="source", gql='class = source and title ~ "Marriage Register"')
   → If found and complete: use existing source
   → If found but missing info: create_source with handle (update source)
   → If not found: create_source without handle (create source with title, repo link, optional author/pubinfo/abbrev/media/note handles)

3. Citation: "Page 67, Entry 15, Marriage of John Smith and Mary Jones, June 15, 1878"
   → If citation has media: create_media first, get media handle
   → If citation has notes: create_note first, get note handle
   → find_type(type="citation", gql='class = citation and source_handle = "<source handle>" and page ~ "Page 67"')
   → If found and complete: use existing citation
   → If found but missing info: create_citation with handle (update citation)
   → If not found: create_citation without handle (create citation with source link, optional page/date/media/notes)

4. Event: Marriage event on June 15, 1878
   → If event has place: find_type(type="place", gql='class = place and name.value = "Boston"') first,
     create_place if not found, get place handle
   → find_type(type="event", gql='class = event and type.string = "Marriage" and description ~ "Smith"')
   → If found and complete: use existing event
   → If found but missing info: create_event with handle (update event)
   → If not found: create_event without handle (create event with type, citation handle, optional date/description/place handle)

5. Link People to Event:
   → If person has notes: create_note first, get note handle
   → If person has media: create_media first, get media handle
   → find_type(type="person", gql='class = person and primary_name.surname_list.any.surname = "Smith" and primary_name.first_name = "John"')
     (John Smith, born ~1850, Boston area)
   → If matches found: Ask user to confirm identity
   → If same person: create_person with handle (update existing person) AND add event with role "groom"
   → If new person: create_person without handle (create new person with given name, surname, gender, optional notes/media/URLs) AND add event with role "groom"
   
   → If person has notes: create_note first, get note handle  
   → If person has media: create_media first, get media handle
   → find_type(type="person", gql='class = person and primary_name.surname_list.any.surname = "Jones" and primary_name.first_name = "Mary"')
     (Mary Jones, born ~1855, Boston area)
   → If matches found: Ask user to confirm identity
   → If same person: create_person with handle (update existing person) AND add event with role "bride"
   → If new person: create_person without handle (create new person with given name, surname, gender, optional notes/media/URLs) AND add event with role "bride"

6. Create Family Units (when applicable):
   → If family has notes: create_note first, get note handle
   → If family has media: create_media first, get media handle
   → If creating family relationships: find_type(type="family", gql='class = family and father_handle = "<father handle>"')
     first to check for existing family
   → If family exists and complete: use existing family
   → If family exists but missing info: create_family with handle (update family) AND add family events
   → If family doesn't exist: create_family without handle (create with father/mother/children handles, optional notes/media/URLs) AND add family events
   
   → Family events (marriage, divorce) are added to the family, not individual people
   → Individual events (birth, death) are added to people
   → All family relationships must be supported by sourced events

7. All entities now properly linked: Repository → Source → Citation → Event ← People/Families (with roles)
```

## Key Principles

### Always Source First
- Never create unsourced information
- Every fact should trace back to a citation
- Citations should reference specific pages or entries

### Check Before Creating
- **Always search before creating new people**
- Use `find_type` (with `type="person"`, `"place"`, `"source"`, etc.) and
  `find_anything` extensively
- Present potential matches to the user for verification
- Prevent duplicate entries through careful checking

### Maintain Data Integrity
- Link events to citations
- Link citations to sources  
- Link sources to repositories
- Connect people to events with proper roles

### User Confirmation Required
When potential duplicates are found:
- Show the user the existing record details
- Ask "Is this the same person/place, or should I create a new record?"
- Proceed based on user's decision
- Document the decision in notes if necessary

## Tool Usage Order Summary

1. `find_type(type="repository", ...)` → `create_repository` (repository: with handle to update, without handle to create)
2. `find_type(type="source", ...)` → `create_source` (source document: with handle to update, without handle to create)
3. `find_type(type="citation", ...)` → `create_citation` (with handle to update, without handle to create)
4. `find_type(type="event", ...)` → `create_event` (with handle to update, without handle to create)
5. `find_type(type="person", ...)` → `create_person` (with handle to update, without handle to create) + link individual events
6. `find_type(type="place", ...)` → `create_place` (with handle to update, without handle to create)
7. `find_type(type="family", ...)` → `create_family` (with handle to update, without handle to create) + link family events

**Remember: ALWAYS find first, then create with handle to UPDATE or without handle to CREATE.**

**Shortcut**: `create_sourced_event` performs steps 2 to 4 in a single call -
it creates the source, the citation and the event together and wires the
citation to the event, which avoids copy-pasting handles between calls. Pass
`media_path` to upload a file and attach it to the citation in the same
call - the path must resolve inside `GRAMPS_MEDIA_IMPORT_ROOT` (default
`/tmp`), see "Where `media_path` must point" below. The find-first rule still
applies before you call it.

Pass exactly one of `source_title` (creates a new source) or `source_handle`
(attaches the new citation to an existing source) - the two are mutually
exclusive. Use `source_handle` when recording a second fact from a document
already sourced in this tree, so the same document does not get a duplicate
source per fact. If `source_title` collides with a title already in the
tree, the call is refused rather than silently reused or duplicated; the
error names the colliding handles so you can retry with `source_handle`.

**Event Distribution:**
- **Individual events** → Person records (birth, death, baptism, burial)
- **Family events** → Family records (marriage, divorce, engagement)
- **All relationships must be supported by sourced events**

## Entity Creation Details

### Creating Places
**Place requires:**
- **Name** (required): "Boston", "Massachusetts", "United States"
- **Type** (strongly recommended when creating): City, County, State, Country, Church, Cemetery, etc. Omitting it is accepted, not rejected, but Gramps then records the type as "Unknown" - always supply it on creation. It can be omitted when only updating other fields on an existing place.
- **Enclosed by** (required): Handle of the higher-level place that contains this place
  - Example hierarchy: Church → City → County → State → Country
  - Continue until you reach Country type (top level)
- **URLs** (optional): Web links with type, path, and description

**Place Process:**
- **First**: Search for an existing place with
  `find_type(type="place", gql='class = place and name.value = "Boston"')`
- **If found and complete**: Use existing place as-is
- **If found but missing info**: Use `create_place` with existing handle to update place
- **If not found**: Use `create_place` without handle to create new place

**Place Hierarchy Example:**
```
Country: "United States" (type: Country, no enclosing place)
State: "Massachusetts" (type: State, enclosed by: United States handle)
City: "Boston" (type: City, enclosed by: Massachusetts handle)
Church: "St. Mary's Catholic Church" (type: Church, enclosed by: Boston handle)
```

### Creating Notes
**Note requires:**
- **Text** (required): The actual note content/text
- **Type** (required): General, Research, Transcript, etc.

**Note Process:**
- **First**: Search for an existing note (if applicable) with
  `find_anything(query="marriage contract")`. Do **not** use
  `find_type(type="note", gql=...)` - see the note-search limitation below;
  every GQL filter on notes fails.
- **If found and complete**: Use existing note as-is
- **If found but missing info**: Use `create_note` with existing handle to update note
- **If not found**: Use `create_note` without handle to create new note

### Creating Media
**Media requires:**
- **`desc`** (required): Descriptive title for the media
- **`media_path`** (required when creating): Path to the file to upload
  (image, document, etc.); it is uploaded and then cleared, so it is only
  needed when no handle is given. See "Where `media_path` must point" below
- **`date`** (optional): Date when the media was created or taken

**Media Process:**
- **First**: Search for existing media with
  `find_type(type="media", gql='class = media and desc ~ "marriage 1878"')`
- **If found and complete**: Use existing media as-is
- **If found but missing info**: Use `create_media` with existing handle to update media
- **If not found**: Use `create_media` without handle to create new media

### Where `media_path` must point

`media_path` is read by the MCP server, not by the machine you are talking
from, and it is confined: the path must resolve inside the directory named by
the `GRAMPS_MEDIA_IMPORT_ROOT` environment variable, which defaults to `/tmp`.
A path outside that root is refused before any upload is attempted, and so is
a symlink that points out of it.

The MCP server runs in a container with no mount of the host filesystem, so a
path that exists on the host does not exist for the server. Stage the file
inside the import root first:

```bash
docker cp ~/Desktop/acte-1878.jpg gramps-mcp-grampsweb_mcp-1:/tmp/
```

then pass `media_path="/tmp/acte-1878.jpg"`. This applies to every tool that
takes `media_path`: `create_media`, `create_source`, `create_citation` and
`create_sourced_event`.

## Analysis and Administration Tools

The tools above write data. The tools below read and analyse what is already in
the tree, plus two that manage tags and accounts. Use the read tools **before**
writing: a timeline or a relationship check is how you confirm that the person
in front of you is the person in the record.

### `get_timeline` - what already happened to a person or family

`get_timeline(scope=..., target=...)`. `scope` is required and must be one of
`person`, `family`, `people`, `families`.

- `target` (handle or gramps_id) is **required** for `scope="person"` and
  `scope="family"`. For `scope="people"` it is the optional anchor person. It is
  ignored for `scope="families"`.
- `handles`: comma-delimited handles, for `scope="people"` and
  `scope="families"` only.
- `dates`: range filter, e.g. `"1900/1/1-1950/1/1"` (also `"-1950/1/1"` and
  `"1900/1/1-"`).
- `events` / `event_classes`: comma-delimited lists to restrict which events
  appear.
- `first` / `last`: include events before/after the anchor's own first/last
  event. `scope="person"` and `scope="people"` only.
- `precision` (1-3): `scope="people"` only.
- `ratings`, `discard_empty`, `page`, `pagesize`: not used for
  `scope="person"`.

**Run `get_timeline(scope="person", target=...)` on every candidate match before
you decide two records are the same person.** The event sequence disambiguates
homonyms far more reliably than a name search does.

### `get_facts` - tree statistics. Do not use `tree_stats`

`tree_stats` returns "Permission denied for this operation" for every account,
including the owner role. Do not call it. Use `get_facts` instead.

`get_facts()` with no arguments reports on the whole tree.

- `rank` (default 1): how many objects to return per ranked statistic. Raise it
  to see the top N rather than only the top one.
- `living` (default `IncludeAll`): how living people are handled. One of
  `IncludeAll`, `FullNameOnly`, `LastNameOnly`, `ReplaceCompleteName`,
  `ExcludeAll`.
- `private` (default false): set true to exclude records marked private.
- **Narrowing requires two arguments together.** Pass `person` with a filter
  name **and** `gramps_id` (or `handle`) identifying the person the filter
  applies to. The built-in filter names are `Ancestors`, `Descendants`,
  `DescendantFamilies` and `CommonAncestor`; a custom filter name defined in the
  tree is also accepted. A bare `gramps_id` with no `person` filter narrows
  nothing - you get whole-tree statistics back. When both `gramps_id` and
  `handle` are given, `gramps_id` wins.

### `find_duplicates` - candidate duplicate people, clustered

`find_duplicates()` with no arguments scans the whole tree. Read-only: it
never writes anything, and never merges - it only reports.

- `limit` (default: unset): stop after this many people, for a cheap probe on
  a large tree. Omit to scan everyone.

There is no similarity-threshold parameter: clustering runs on structural
rules only (matching normalized name plus an exact shared birth date, shared
parents, or a shared spouse and child), never on a tunable similarity score.

The output has two parts, never merged under one heading:

- **Proved duplicates**: clusters the rules could establish with structural
  evidence (an exact date match, shared parents, or a shared spouse and
  child). Each cluster names the record that would survive a merge (the most
  complete one) and the records that would merge into it. When the surviving
  record's gender is unknown, the cluster also states which gender to patch
  onto it first - `merge_type` does not carry gender across a merge, so
  applying the patch before merging is the only way it is not silently lost.
- **Needs human arbitration**: pairs that share enough to be worth a look
  (for example, a phonetic name match plus some shared context) but that the
  rules did not prove. These are never presented as duplicates - review each
  one yourself before doing anything with it. Pairs matched on name
  resemblance alone are dropped entirely, not reported here: a name
  resemblance is never proof.

If the tree scan could not finish, the output says so first, naming the
error, before any finding - do not read a result with no "partial scan"
warning as a completed scan otherwise. Records the collector could not parse
are also reported by count.

Feed a proved pair's handles to `merge_type` to actually merge; this tool
never does it for you.

### `audit_quality` - deterministic consistency anomalies

`audit_quality()` with no arguments scans the whole tree and reports every
anomaly the deterministic rules find. Read-only: it never writes anything.

- `limit` (default: unset): stop after this many people, for a cheap probe on
  a large tree. Omit to scan everyone.
- `severity` (default: unset): report only anomalies at this severity - one
  of `haute`, `moyenne` or `basse`. Omit to report every severity.

Anomalies are grouped by severity, highest (`haute`) first. Each one names
the rule that fired (for example `R1`, `R3`), the `gramps_id` it is attached
to, and a human-readable message. A rule needing a date is skipped when that
date is unknown, so unknown data never produces a false positive.

If the tree scan could not finish, the output says so first, naming the
error, before any finding. Records the collector could not parse are also
reported by count. A clean tree renders an explicit "no anomalies found"
line rather than an empty response.

### `get_relationship` - how two people are related

`get_relationship(person1=..., person2=...)`. Each accepts a handle or a
gramps_id.

- `all_relationships` (default false): false returns only the most direct
  relationship; true returns every path found.
- `depth`: search depth in generations. Omit it to use the API default of 15.

### `check_living` - probably-alive estimate, not a fact

`check_living(person=...)` accepts a handle or a gramps_id.

This is a **computed estimate** derived from the dates around the person, not a
recorded status. A person with no death event reads as living, however old the
birth date is. Never report the result to the user as established fact; if it
matters, look for a death event and source it.

- `include_dates` (default true): also returns estimated birth and death dates
  with the reasoning behind them.
- `average_generation_gap`, `max_age_probably_alive`,
  `max_sibling_age_difference`: tune the estimate. Leave them unset unless the
  user asks for a specific assumption.

### `get_ancestors` / `get_descendants` - token-heavy, start small

`get_ancestors(gramps_id=..., max_generations=5)` and
`get_descendants(gramps_id=..., max_generations=5)`.

- `gramps_id` is **required** and is the only accepted identifier - these two
  tools do not take a handle.
- `max_generations` defaults to 5 and the parameter model declares a 1-20
  bound; that bound is enforced when a client validates arguments against the
  schema (for example over HTTP), but the stdio transport passes arguments
  straight through without Pydantic validation, so it is advisory there. In
  every case the walk also stops after 500 people - the output says so when
  it happens, with an unexplored-branch count.
- Output is an indented markdown tree, one line per person, depth-first: each
  line carries the person's name, `gramps_id`, and birth/death dates when
  known, for example `- JACQUET, Yvan (I0042), b. 1948 Lyon, d. 2011`. A
  person reached a second time by a different path is listed again with
  `[already listed above]` instead of being repeated in full. A person the
  walk could not fetch shows as `[unavailable: <reason>]`.
- **Only birth links continue a lineage.** Gramps records a relationship on
  each parent separately (`frel` for the father, `mrel` for the mother):
  Birth, Adopted, Stepchild, Foster, Sponsored, None, Unknown, or a custom
  type. A non-birth relative is named on its own line and marked
  `[Adopted, line not followed]` - the relative is real, but their own
  ancestors are not the subject's, so the walk stops there. When any such
  line appears, a `**Non-birth links**` footer states the rule. Do not
  describe a marked relative as a birth parent or birth child, and do not
  assume a marked line means "no further relatives recorded".
- A parent from a parent family beyond the first is marked
  `[other parents family]`. Gramps treats the first parent family as the
  main one, the one its own reports and charts follow.
- Still start small: a large `max_generations` on a well-populated tree can
  overflow the context window well before it hits either cap.

### `recent_changes` - what was modified lately

`recent_changes()` with no arguments returns the most recent transactions.

- `sort` defaults to `-id` (newest first); pass `id` for oldest first.
- `page` defaults to 1. `pagesize` only reaches the API alongside `page`, and
  because `page` is defaulted for you, `pagesize` alone applies to page 1.
- `before` / `after`: Unix timestamps bounding the commit time.
- `old` / `new`: include the raw object data before/after each change. Both are
  very token-heavy - set them only when you need to inspect one specific edit.

Use it to check what your own previous calls actually wrote before reporting
back to the user.

### `manage_tags` - list, read, create and update tags

`manage_tags(action=...)` where `action` is `list`, `get` or `create`. **There is
no delete.**

- `list`: optional `page`, `pagesize` (1-100), `sort` (a list of field names).
- `get`: `handle` is required.
- `create`: `name` is required for a new tag. Pass `handle` as well to update an
  existing tag instead of creating a second one with the same name - always
  `list` first and reuse the handle.
- `color` and `priority` are optional on both create and update.

### `manage_users` - account administration

`manage_users(action=...)` where `action` is `list`, `get` or `create`.

- **Requires an owner or admin account.** With any lesser role every action
  fails with a permission error. Do not retry - report it to the user.
- `get` requires `name`. Usernames must match `^[A-Za-z0-9_.-]{2,64}$`.
- `create` requires `users`, a list of objects with `name`, `email`, optional
  `full_name`, and `role` (default `member`). **Roles are capped at editor**: only
  `guest`, `member`, `contributor` and `editor` can be granted - this tool cannot
  create an owner or an admin. Up to 50 accounts per call.
- **There is no update, no delete and no password reset.** A mistyped account
  cannot be corrected through this server.
- Passwords are generated and appear in the response. That is the only copy.
  Relay them to the user immediately and tell them to change the password on
  first login.

## Destructive Operations

Four tools can remove data: `delete_type`, `merge_type`, `detach_reference`
and `undo_change`. Each one is guarded, and each guard is documented below -
read it before calling with `force=true` or `confirm=true`. `recent_changes`
is how you find a transaction id afterwards, for `undo_change` or just to
confirm what actually happened.

### `delete_type` - delete one record

`delete_type(type=..., handle=... or gramps_id=..., force=False)`.

- `type`: one of `person`, `family`, `event`, `place`, `source`, `citation`,
  `repository`, `media`, `note`, `tag`.
- `handle` or `gramps_id` identifies the record; give one.
- The tool reads the record's backlinks first. If anything still references
  it, the call is **refused** and every referencing object is listed by type
  and gramps_id - nothing is deleted.
- `force=true` deletes anyway and severs those references, the same
  behaviour the Gramps Web UI has when it deletes a referenced record. Use it
  deliberately, having read what it says it will sever.
- Recoverable with `undo_change`, subject to the `force` requirement
  described there.

### `merge_type` - merge two records of the same type

`merge_type(type=..., phoenix_handle=... or phoenix_gramps_id=...,
titanic_handle=... or titanic_gramps_id=..., confirm=False)`.

- `type`: `person`, `family`, `event`, `place`, `source`, `citation`,
  `repository`, `media`, `note`. **Tags cannot be merged** - Gramps Web has no
  tag-merge endpoint; use `delete_type` on the duplicate instead.
- The **phoenix** survives; the **titanic** is absorbed and every reference to
  it is repointed to the phoenix. Order matters - decide which record should
  survive before calling.
- With `confirm` unset (the default), the call changes nothing and returns a
  preview of both records so you can check the phoenix/titanic choice before
  committing. Call again with `confirm=true` to execute.
- Family merges only: `phoenix_father_handle` / `phoenix_mother_handle`
  choose which parent the merged family keeps, when the two families being
  merged disagree. Omit either to keep the phoenix family's existing parent.
- There is no backlink guard here - both records are legitimately referenced
  right up to the merge, so `confirm` is the only checkpoint. Recoverable
  with `undo_change`, subject to the `force` requirement described there.

### `detach_reference` - remove one element from one list

`detach_reference(type=..., handle=... or gramps_id=..., list_name=...,
ref_handle=...)`.

- Removes `ref_handle` from `list_name` on the named record, and rewrites
  only that one list. Every other list on the record keeps the normal
  merge-on-update behaviour (ADR 0003) - this is the one place removal
  happens through this server.
- Refuses rather than silently doing nothing if `ref_handle` is not actually
  in `list_name`.
- **Not every (type, list_name) pair is reachable.** The write model for each
  type has to declare the list before this tool can edit it, and the write
  models were built for creation, not full read/write parity. This is the
  complete reachable set, one line per type, derived from the write models
  and pinned by `tests/test_alignment_destructive.py` - that test fails if
  this list and the models ever disagree:

  - `person`: `attribute_list`, `event_ref_list`, `family_list`, `media_list`, `note_list`, `parent_family_list`, `tag_list`
  - `family`: `child_ref_list`, `event_ref_list`, `media_list`, `note_list`
  - `event`: `citation_list`, `note_list`
  - `place`: `citation_list`, `media_list`, `note_list`, `placeref_list`, `tag_list`
  - `source`: `attribute_list`, `media_list`, `note_list`, `reporef_list`, `tag_list`
  - `citation`: `attribute_list`, `media_list`, `note_list`, `tag_list`
  - `repository`: `attribute_list`, `media_list`, `note_list`, `tag_list`
  - `media`: `citation_list`, `note_list`
  - `note`: none
  - `tag`: none

  The gaps that remain, all of them lists the read side exposes but the
  write model does not declare: a person's person_ref_list, citation_list,
  address_list and lds_ord_list; an event's media_list, attribute_list and
  tag_list; a family's tag_list, attribute_list and citation_list; a media
  object's attribute_list and tag_list; and notes and tags, which declare no
  list fields at all, so a detach against either is always refused.

  A refusal names the reason (the write model does not declare that list),
  so a call against an unsupported combination fails loudly rather than
  reporting success while changing nothing.

### `undo_change` - reverse a recorded transaction

`undo_change(transaction_id=..., force=False)`.

- `transaction_id` comes from `recent_changes`.
- Undoing reverses every object change that transaction made.
- **`force=true` is currently required to undo a deletion.** This is an
  upstream Gramps Web defect, not a gramps-mcp choice: the server records the
  deleted side of a delete/add change as `{}` rather than `None`, and its
  own conflict check treats `{}` as "the object has changed", so it refuses
  every non-forced undo of a deletion with a false "Object has changed"
  error - even when nothing else touched the record. `force=true` bypasses
  that check and reliably restores the record. The risk `force` carries: if
  the object genuinely *was* changed again after the transaction you are
  undoing, forcing discards that later change without warning - so use it
  because the delete-undo bug makes it necessary, not as a reflex.
  `delete_type` and `merge_type` both point here as their recovery path, so
  this applies whenever you are undoing either of them.
  - The tool polls the background task the server queues for the undo and
    reports what it actually observes (success, failure with the server's
    own error text, or "still processing" after 5 seconds) rather than
    claiming success the moment the request is accepted.

## Date Format Specification

**IMPORTANT**: All dates in Gramps use a specific structure with multiple components:

**Date Components:**
- **Year** (required): Four-digit year (e.g., 1878)
- **Month** (optional): Month number (1-12)
- **Day** (optional): Day of month (1-31)
- **Type** (required): Date precision/range type
  - `regular`: Exact date
  - `before`: Before this date
  - `after`: After this date
  - `about`: Approximate date (circa)
  - `range`: Between two dates
  - `span`: Duration/period
  - `from`: From this date onward
  - `to`: Up to this date
- **Quality** (required): Date reliability
  - `regular`: Normal/certain date
  - `estimated`: Estimated date (circa)
  - `calculated`: Calculated from other information

**Date Examples:**
- Exact date: Year=1878, Month=6, Day=15, Type=regular, Quality=regular
- Estimated: Year=1850, Type=regular, Quality=estimated
- Before date: Year=1860, Type=before, Quality=regular
- Date range: Start(Year=1875), End(Year=1880), Type=range, Quality=regular

This date structure applies to ALL date fields throughout the system: events, media, citations, etc.

This workflow ensures proper genealogical methodology and maintains the integrity of the family tree data.