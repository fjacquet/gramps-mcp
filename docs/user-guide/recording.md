# Recording a sourced fact

This is the writing half of the guide: how a fact read off a register ends up
in the tree with a citation behind it, and how the scan it came from gets
attached. Find the people and places involved first, with the tools on
[Searching and reading records](searching.md).

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
gramps-mcp container's `/tmp/` is the usual move. The destination must be
inside `GRAMPS_MEDIA_IMPORT_ROOT` (defaults to `/tmp`); a path that resolves
outside it is refused, and a path that exists on your machine but not the
server's fails with a file-not-found error.

An upload always appends. The resulting reference is added to `media_list`,
never replacing entries that were already there.
