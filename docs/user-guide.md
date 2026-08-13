# User guide

This guide is for someone who already has the server running and wants to get
good results out of it through an AI assistant. Installation, configuration and
the full tool inventory live in [README.md](https://github.com/fjacquet/gramps-mcp#readme); nothing here repeats
them.

Everything below is phrased as tool calls because that is what the assistant
issues on your behalf. You will normally type ordinary sentences ("find the
Vilpellet marriage in 1885 and source it from this scan"); knowing the tool
names is what lets you tell whether the assistant did the right thing, and
correct it when it did not.

## Two resources to read first

The server ships two MCP resources, and a session that has not read them tends
to guess:

- `gramps://usage-guide` - the sourcing workflow the tools expect. Ask the
  assistant to read it before any data entry session.
- `gql://documentation` - the Gramps Query Language syntax and the full
  property list. Required before writing anything but the simplest `find_type`
  filter.

Both are also useful to you directly. If a search keeps returning nothing, the
property list in the GQL resource is usually the reason.

## Finding people and families

There are two search tools and they answer different questions.

`find_anything` is a plain full-text search across every record type. It
matches literal text inside records, not logical combinations, so give it one
distinctive string rather than a sentence:

```
find_anything(query="Vilpellet", max_results=20)
```

`find_type` searches one record type with a GQL filter, which is what you want
as soon as the question has structure - a surname plus an era, people with no
media, events in a given place:

```
find_type(type="person",
          gql='class = person and primary_name.surname_list.any.surname = "Pagan"',
          max_results=20)

find_type(type="event",
          gql='class = event and place.get_place.name.value ~ Verrens',
          max_results=20)
```

`type` accepts `person`, `family`, `event`, `place`, `source`, `citation`,
`media`, `repository` and `note`. Both tools take `max_results` (default 20)
and `page` for walking through a large result set.

Search on name plus era plus place, never name alone. In a small village the
same given name and surname recur across generations, and merging two people
who were not the same person is far more expensive to undo than leaving them
unlinked - see the surprises section on why removal is hard.

## Reading a record in depth

`get_type` returns the full formatted record, and it takes either identifier:

```
get_type(type="person", gramps_id="I0123")
get_type(type="family", handle="6a4f2b1c9d8e7f0a1b2c3d4e5f")
```

Only `person` and `family` are supported here; for the other types, `find_type`
with a filter on `gramps_id` or `handle` is the way in.

Two tools give context around a record rather than the record itself.
`get_timeline` builds a chronology, and `get_facts` returns tree-wide
statistics:

```
get_timeline(scope="person", target="I0123")
get_timeline(scope="family", target="F0044", discard_empty=true)
get_timeline(scope="person", target="I0123", dates="1850/1/1-1900/1/1")
get_facts(living="LastNameOnly", rank=3)
get_facts(person="Ancestors", gramps_id="I0123")
```

`scope` is one of `person`, `family`, `people` or `families`. The last two take
a comma-delimited `handles` string instead of a single target. `dates` bounds
the chronology (`y/m/d-y/m/d`, and either end may be left open), and `events`
or `event_classes` restrict it to given event types.

`get_facts` is tree-wide by default. Narrowing it to one branch needs both
halves: a filter name in `person` - the built-ins are `Ancestors`,
`Descendants`, `DescendantFamilies` and `CommonAncestor` - and the
`gramps_id` or `handle` the filter applies to. A `gramps_id` on its own
changes nothing. `living` controls how living people appear
(`IncludeAll`, `FullNameOnly`, `LastNameOnly`, `ReplaceCompleteName`,
`ExcludeAll`), `private=true` drops records marked private, and `rank` sets
how many entries each ranked statistic returns.

## Adding a sourced fact

This is the part people get wrong, so it is worth being precise about the
shape. Gramps records a fact as a chain:

```
repository -> source -> citation -> event -> person or family
```

A fact bolted straight onto a person with no citation behind it is, as far as
Gramps is concerned, an assertion nobody made. Every step of the chain is a
separate record with its own handle, and each step needs the handle of the one
before it.

### The composite tool

`create_sourced_event` collapses the middle three steps into a single call and
wires the citation onto the event for you. This is the recommended path,
because the classic failure mode is retyping a handle between two calls and
silently producing an event with no citation attached:

```
create_sourced_event(
    source_title="Registre des mariages, Verrens-Arvey, 1885",
    source_author="Mairie de Verrens-Arvey",
    citation_page="acte no 7, vue 12",
    event_type="Marriage",
    event_date={"dateval": [14, 4, 1885, false], "modifier": 0, "quality": 0},
    event_place="6a4f2b1c9d8e7f0a1b2c3d4e5f",
    media_path="/tmp/acte-mariage-vilpellet-cocu-1885.jpg")
```

It creates the source, uploads and attaches the media to the citation, creates
the citation against that source, and creates the event carrying that citation.
It returns all three records, handles included. It does not create or link a
repository; if you want the source filed under an archive, create the
repository separately with `create_repository` and add the reference with
`create_source`.

### The chain by hand

When you need something the composite tool does not cover - reusing an existing
source, several citations from one register, a repository link - build it step
by step, and copy each handle from the tool result you just received rather
than from earlier in the conversation:

```
create_repository(name="Archives departementales de la Savoie", type="Archive")
create_source(title="Registre paroissial, Verrens-Arvey, 1856",
              reporef_list=[{"ref": "<repository handle>"}])
create_citation(source_handle="<source handle>", page="vue 34",
                media_path="/tmp/acte-deces-raucaz-1856.jpg")
create_event(type="Death", citation_list=["<citation handle>"],
             place="<place handle>",
             date={"dateval": [3, 11, 1856, false], "modifier": 0, "quality": 0})
```

`citation_list` on `create_event` is required, which is the tooling enforcing
the rule that events are sourced.

### Attaching the event to people

Events are linked to people, not people to events, and the link is an update to
the person carrying a role:

```
create_person(handle="<person handle>",
              primary_name={"first_name": "Joseph",
                            "surname_list": [{"surname": "Raucaz"}]},
              gender=1,
              event_ref_list=[{"ref": "<event handle>", "role": "Primary"}])
```

Individual events - birth, death, baptism, burial - go on the person. Family
events - marriage, divorce, engagement - go on the family, through
`create_family`'s `event_ref_list`. `create_family` also takes
`father_handle`, `mother_handle` and `child_handles`.

The same tool creates and updates: pass `handle` to update an existing record,
omit it to create a new one. Always search first. Creating a second record for
someone who is already in the tree is the most common way to make a mess.

### Dates

Every date field takes the same object:

```
{"dateval": [day, month, year, false], "modifier": 0, "quality": 0}
```

Use `0` for an unknown day or month. `modifier` is `0` regular, `1` before,
`2` after, `3` about, `4` range, `5` span, `6` text-only, `7` from, `8` to.
`quality` is `0` regular, `1` estimated, `2` calculated. Ranges and spans
(`4` and `5`) need eight entries - both brackets - and text-only (`6`) puts
the date in `text` and can omit `dateval` entirely.

### Places are handles, not names

`create_event`'s `place` and `create_sourced_event`'s `event_place` take a
place handle. Passing a name is refused outright with a message pointing at
`find_type`, because the earlier behaviour was to accept the name and overwrite
the event's real place with text that resolved to nothing. Find the place
first:

```
find_type(type="place", gql='class = place and name.value = "Verrens-Arvey"')
create_place(name={"value": "Verrens-Arvey"}, place_type="Town",
             placeref_list=[{"ref": "<parent place handle>"}])
```

Always supply `place_type` when creating; omitting it is accepted, and Gramps
then records the type as "Unknown" forever. Build the hierarchy upward -
church inside town inside department inside country.

## Attaching media

Any scan, photograph or PDF should end up attached to the record it documents,
usually the citation. Three tools take a `media_path` and do the upload inline:
`create_source`, `create_citation` and `create_sourced_event`. `create_media`
does it as a standalone record:

```
create_media(desc="Acte de mariage Vilpellet x Cocu, 1885",
             media_path="/tmp/acte-mariage-vilpellet-cocu-1885.jpg",
             citation_list=["<citation handle>"])
```

`media_path` is read from the filesystem of the process running the MCP server,
not from your laptop. If the server runs in a container without a mount onto
your files, copy the file into the container first - `docker cp` into the
gramps-mcp container's `/tmp/` is the usual move. A path that exists on your
machine but not the server's fails with a file-not-found error.

An upload always appends. The resulting reference is added to `media_list`,
never replacing entries that were already there.

## Exploring relationships and timelines

```
get_relationship(person1="I0123", person2="I0456")
check_living(person="I0123")
get_ancestors(gramps_id="I0123", max_generations=4)
get_descendants(gramps_id="I0123", max_generations=4)
```

`get_relationship` and `check_living` accept a handle or a `gramps_id`;
`get_ancestors` and `get_descendants` take `gramps_id` only.

`get_relationship` returns the most direct relationship by default. Pass
`all_relationships=true` when two people are related by more than one path -
common in a village tree - and `depth` to change how many generations the
search walks (the API default is 15).

`check_living` does not report a recorded fact. It asks Gramps whether the
person is *probably* alive, which is a calculation from the surrounding dates:
their own, their relatives', and three tunable bounds -
`max_age_probably_alive`, `average_generation_gap` and
`max_sibling_age_difference`. The answer comes back as Living yes/no with
estimated birth and death dates and a line explaining which record drove the
estimate; `include_dates=false` suppresses the estimates and returns the
verdict alone. Someone with no death event and no dated descendants will be
reported as living. Use it before publishing or exporting anything, because
that verdict is what the privacy proxies elsewhere - `get_facts`'s `living`
argument, for instance - act on.

Treat the two traversal tools with care. They render a full Gramps ancestor or
descendant report, and they are token-heavy - the default of five generations
already returns a large amount of text. `max_generations` is not capped, so
raising it can consume the whole context window on one call. When you only want
to know how two people connect, `get_relationship` answers that directly and
cheaply.

## Reviewing recent changes

`recent_changes` reads the tree's transaction history, which is the fastest way
to audit a data-entry session or find what a previous session did:

```
recent_changes(pagesize=20, sort="-id")
recent_changes(after=1754870400)
```

`before` and `after` are Unix timestamps. `old=true` and `new=true` include the
raw object data on either side of each change, which is verbose but is how you
see exactly what a call wrote.

Two defaults are applied for you when you do not set them: `sort="-id"`, so
the newest transactions come first, and `page=1`, which bounds the answer to
one page instead of rendering the tree's entire history. Both give way to a
value you supply - `sort="id"` walks forward from the oldest change, and
`pagesize` only takes effect alongside a `page`.

`manage_tags` covers the other half of housekeeping:

```
manage_tags(action="list")
manage_tags(action="get", handle="<tag handle>")
manage_tags(action="create", name="A verifier", color="#FF0000", priority=1)
```

`action` is `list`, `get` or `create`. `get` requires a `handle`. On `create`,
supplying a `handle` updates that tag instead of making a new one, and `name`
is otherwise required. There is no delete. Tags are attached to records through
the `tag_list` of the create tools, and like every list field that attachment
only ever adds.

## Managing accounts

`manage_users` is the one administrative tool in the set. It exists because
opening a tree to a family means creating accounts one web form at a time, and
a batch of thirty is a tedious afternoon:

```
manage_users(action="list")
manage_users(action="get", name="jdupont")
manage_users(action="create",
             users=[{"name": "jdupont",
                     "email": "j.dupont@example.org",
                     "full_name": "Jeanne Dupont",
                     "role": "contributor"}])
```

`action` is `list`, `get` or `create`; `get` needs a `name`, and `create` needs
`users`, up to fifty per call. Each entry needs `name` and `email`; `full_name`
is optional and `role` defaults to `member`. The four roles it will grant are
`guest`, `member`, `contributor` and `editor` - owner and admin are refused by
design, so this tool cannot escalate anyone to its own level. The account in
your `.env` must itself be owner or admin, or every action returns a permission
error.

There is no update, no delete and no password reset: correcting a role or
retiring an account is Gramps Web UI work. The password generated for each new
account is printed in the tool result, which means it lands in the session
transcript - treat those as first-login credentials and have people change
them.

[User management](user-management.md) covers the roles, the batch behaviour and
the failure modes in full.

## Things that will surprise you

**Updates merge, and nothing can be removed from a list.** A write is a read
followed by a full replacement, so the client fetches the current record and
merges your changes into it before sending. Fields you did not mention keep
their values, and list fields ending in `_list` are unioned with what is
already stored rather than replaced. That protects you from silently wiping
data - but it also means no tool can take an item out of a list. There is no
path through this server to detach an event reference, remove a child from a
family, or drop a media reference. Removal requires the Gramps Web UI. Check
`child_handles`, `father_handle` and `mother_handle` before submitting a
family; a wrong child cannot be taken back out here.

The one escape hatch is `replace_lists` on `create_place`, which names list
fields to overwrite rather than add to - `replace_lists=["placeref_list"]` to
move a place to a different parent instead of giving it a second one.

**`get_type` does not error on an unknown identifier.** Ask for a
`gramps_id` that does not exist and you get a plain message saying no record
was found and suggesting `find_type`, not a failure. If the assistant reports
"no person found with I9999", that is the record being absent, not the server
being broken.

**Search results report the true total, not what you were shown.** The count in
"Found 312 people (showing 20)" comes from the server's own total-match header.
The number in the header is the size of the answer; the records below it are
one page of it. Use `page` to walk through the rest.

**Error messages carry a fragment of the server's explanation.** When Gramps
rejects a call, the message includes the server's own text - usually naming the
offending field, which is what makes the error actionable - truncated to 300
characters. The truncation is deliberate: Gramps echoes the submitted payload
on some errors, and that payload can hold genealogy data about living people.
A message ending in an ellipsis is not a bug.

**`tree_stats` fails even for an owner account.** It is registered, it takes an
`include_statistics` flag, and on the reference deployment it answers
"Permission denied for this operation" whatever role the configured account
holds. That is an environment fact about Gramps Web, not something wrong with
your setup, and no argument works around it. Use `get_facts` when you want
tree-level numbers.
