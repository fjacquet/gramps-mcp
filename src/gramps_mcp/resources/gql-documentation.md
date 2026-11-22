# GOQL - the Gramps Object Query Language

`find_type(type=..., gql=...)` filters ONE record type with a GOQL expression.
The argument is still named `gql`; the language is GOQL ("almost Python"), the
only one gramps-webapi 3.26 accepts. The old Gramps QL dialect (`=`, `~`,
`class = person`, `.any`, `.length`) is gone and is rejected with an error.

The endpoint already fixes the record type, so there is no `class` field:
`type="person"` is what selects people. The expression is evaluated once per
record, with the record's fields as bare names.

## Syntax

- Fields are Python-style attribute paths: `gramps_id`, `primary_name.first_name`.
- Strings use double quotes inside the expression, the whole expression is
  wrapped in single quotes: `gql='gramps_id == "I0001"'`.
- Operators: `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `and`, `or`, parentheses.
- Containment is `"text" in field` (substring match on a string field).
- Lists: index with `[0]`, count with `len(...)`, test with `any(... for x in ...)`.
- Enumerations are compared through their `.value` with a Python-style constant
  (`EventType.BIRTH`, `Person.MALE`).

<!-- rows -->
`find_type(type="person", gql='gramps_id == "I0001"')`

<!-- rows -->
`find_type(type="person", gql='primary_name.first_name == "Jean"')`

<!-- rows -->
`find_type(type="person", gql='"Jean" in primary_name.first_name')`

<!-- rows -->
`find_type(type="person", gql='primary_name.first_name == "Jean" or primary_name.first_name == "Pierre"')`

## Lists

<!-- rows -->
`find_type(type="person", gql='primary_name.surname_list[0].surname == "Méléo"')`

<!-- rows -->
`find_type(type="person", gql='len(primary_name.surname_list) == 1')`

<!-- rows -->
`find_type(type="family", gql='len(child_ref_list) > 1')`

<!-- rows -->
`find_type(type="person", gql='any(s.surname == "Méléo" for s in primary_name.surname_list)')`

<!-- rows -->
`find_type(type="person", gql='len([s for s in primary_name.surname_list if s.surname == "Méléo"]) > 0')`

## Enumerations, dates and flags

Event type: compare `type.value`, not `type`, `type.string` or a literal string.
Those parse but silently match nothing.

<!-- rows -->
`find_type(type="event", gql='type.value == EventType.BIRTH')`

<!-- rows -->
`find_type(type="event", gql='type.value == EventType.BIRTH and date.sortval > 0')`

<!-- rows -->
`find_type(type="event", gql='date.dateval[2] > 1800')`

`date.dateval` is `(day, month, year, slash)`, so `[2]` is the year.

<!-- rows -->
`find_type(type="person", gql='gender == Person.MALE')`

<!-- rows -->
`find_type(type="person", gql='private == True')`

<!-- rows -->
`find_type(type="person", gql='private == False')`

## Related records

A handle field is followed by its relation name: `father`, `mother`, `birth`,
`death`, `place`, `source`. Follow a relation, then use the target's fields.

<!-- rows -->
`find_type(type="family", gql='father.primary_name.surname_list[0].surname == "Méléo"')`

<!-- rows -->
`find_type(type="person", gql='birth.date.sortval > 0')`

<!-- rows -->
`find_type(type="event", gql='place.name.value != ""')`

After a relation, reach a list with an index (`[0]`), not a comprehension.

## Other record types

Notes filter normally, on `text.string`.

<!-- rows -->
`find_type(type="note", gql='"a" in text.string')`

<!-- rows -->
`find_type(type="source", gql='"a" in title')`

<!-- rows -->
`find_type(type="repository", gql='"a" in name')`

<!-- rows -->
`find_type(type="media", gql='"a" in desc')`

<!-- rows -->
`find_type(type="citation", gql='"1" in page')`

<!-- rows -->
`find_type(type="place", gql='"a" in name.value')`

<!-- rows -->
`find_type(type="person", gql='gramps_id != ""')`

## Common fields per record type

| Type | Useful fields |
|---|---|
| person | `gramps_id`, `gender`, `private`, `primary_name.first_name`, `primary_name.surname_list`, `birth`, `death`, `event_ref_list`, `family_list`, `note_list`, `citation_list` |
| family | `gramps_id`, `father_handle`, `mother_handle` (relations `father`, `mother`), `child_ref_list`, `type`, `event_ref_list` |
| event | `gramps_id`, `type.value`, `date.sortval`, `date.dateval`, `place`, `description` |
| place | `gramps_id`, `name.value`, `title`, `place_type`, `placeref_list` |
| source | `gramps_id`, `title`, `author`, `pubinfo`, `abbrev` |
| citation | `gramps_id`, `page`, `date`, `confidence`, `source_handle` |
| repository | `gramps_id`, `name`, `type` |
| media | `gramps_id`, `desc`, `path`, `mime`, `checksum` |
| note | `gramps_id`, `text.string`, `type` |

An unknown field is rejected with the list of the known fields of that type:
read it, it is the authoritative inventory for the server you are talking to.

## Forms that fail

These are rejected with a readable GOQL error:

| Do not write | Write instead |
|---|---|
| `gramps_id = "x"`, `name ~ "x"` | `gramps_id == "x"`, `"x" in name` |
| `class = person` | nothing, the `type` argument selects the record type |
| `primary_name.surname_list.length > 0` | `len(primary_name.surname_list) > 0` |
| `primary_name.surname_list.any.surname = "x"` | `any(s.surname == "x" for s in primary_name.surname_list)` |
| `len(surname_list) > 0` on people | `len(primary_name.surname_list) > 0` |
| `not private`, bare `private` | `private == False` |
| `date.year` | `date.dateval[2]` |
| `father_handle.get_person...` | `father.<field>` |

Two forms parse and return nothing, so they look like a clean search:
`type.string == "Birth"` or `type == "Birth"` on events (use `type.value ==
EventType.BIRTH`), and `title != ""` on places (places carry `name.value`).

The plain `gramps_id=...` URL parameter is not a filter and must never be used
to find a record: always filter with `gql='gramps_id == "..."'`.
