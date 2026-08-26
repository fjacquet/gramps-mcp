# Relationships, timelines and recent changes

Once records exist, these tools answer questions about how they connect and
about what a session did to them. The first half is reading the tree sideways
rather than record by record; the second half is auditing your own work.

## Exploring relationships and timelines

```
get_relationship(person1="I0123", person2="I0456")
check_living(person="I0123")
get_ancestors(gramps_id="I0123", max_generations=4)
get_descendants(gramps_id="I0123", max_generations=4)
```

`get_relationship` and `check_living` accept a handle or a `gramps_id`;
`get_ancestors` and `get_descendants` take `gramps_id` only.

`get_ancestors` and `get_descendants` walk the **birth line only**. Gramps
records a relationship on each parent separately, and any value other than
Birth - Adopted, Stepchild, Foster, Sponsored, None, Unknown, or a custom
type - names a relationship that is real but not biological. Such a relative
is listed and named, marked `[Adopted, line not followed]`, and the walk
stops there: their own ancestors are not yours. A parent from a parent
family beyond the first is marked `[other parents family]`, since Gramps
treats the first as the main one. Both markers are explained in a footer
under the tree whenever they appear.

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
that verdict is what the privacy proxies elsewhere -
[`get_facts`](searching.md#reading-a-record-in-depth)'s `living` argument, for
instance - act on.

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
