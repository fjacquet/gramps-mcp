# Searching and reading records

Every session starts here. This page covers the two search tools that locate a
record and the three tools that read one out in full once you have found it.
The [guide index](index.md) lists the two MCP resources worth reading before
any of this.

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
unlinked - see [Things that will surprise you](gotchas.md) on why removal is
hard.

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
