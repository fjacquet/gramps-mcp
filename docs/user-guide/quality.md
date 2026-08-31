# Finding problems: duplicates, quality, and unresolved places

Three tools look for defects instead of waiting for you to find them:
`find_duplicates`, `audit_quality` and `geocode_place`. All three are
read-only - none of them writes to the tree, and none of them updates a
record on your behalf, even when the finding looks solid. What comes back is
a judgement, not a fact. Acting on it - merging two people, correcting a
date, filing a place - is always a separate, deliberate step with the write
tools covered elsewhere in this guide.

## Finding duplicate people

```
find_duplicates(limit=200)
```

`find_duplicates` blocks people into candidate pairs by shared name,
phonetic surname, birth-year window, or shared family, then sorts the result
into two groups that must never be read as equivalent:

- **Proved duplicates** - clusters the rules are confident about. Each
  cluster names a phoenix (the record that survives, chosen by a
  completeness score) and one or more titanics (the records that would
  merge into it). A cluster is only proved this way when the pair rests on
  matching given names, not merely a shared surname or a shared family - two
  siblings, or a married couple, land somewhere else entirely, never here.
  Some clusters also carry a gender-patch note: `Person.merge()` does not
  carry gender across, so the phoenix needs that field set by hand before
  the merge runs.
- **Needs human arbitration** - pairs that share enough to be worth a look,
  but that the rules did not prove. These are listed under their own
  heading with the blocking keys that connected them, and nothing more. Do
  not feed one of these straight to `merge_type`; read the two records
  yourself first.

Only the proved section is a candidate for `merge_type`. The arbitration
section is a worklist, not a finding.

`limit` bounds how many people are scanned, cheaply - it changes the API
request itself rather than fetching everyone and trimming afterward. A
bounded scan says so, on a `Scope:` line naming how many people it looked
at. Read that line before reading the findings: "no duplicate candidates"
under a `Scope:` line is a clearance for those people, not for the tree.
It is distinct from `**Partial scan**: ...`, which means something went
wrong - the people or families request errored out mid-scan - rather than
that you asked for less. The output states a third kind of narrowing too:
when a blocking key covers more people
than the tool is willing to compare pairwise, it is dropped, and the count
of dropped keys is reported - any pair findable only through one of those
keys is missing from both sections above.

## Auditing consistency

```
audit_quality(limit=500, severity="haute")
```

`audit_quality` runs the deterministic rules (R1-R9 for internal
consistency - a birth after a death, a marriage before either spouse was
born - plus D1-D3 for completeness, such as a person with no vital date at
all) over every person and family in scope, and groups the findings by
severity: `haute`, `moyenne`, `basse`. A rule that needs a date it does not
have is skipped rather than guessed at, so a record with an unknown day or
month never produces a false anomaly.

Both `limit` and `severity` narrow the scan, and the output states the
scope it actually covered right before the findings - a line reading, for
example, "Scope: the first 500 people scanned, severity='haute' only." A clean result echoes that same scope
rather than declaring the whole tree clean: "None found within this scope
(...)" when you narrowed it, "None found - the tree is clean" only when you
did not. Read the scope line before trusting either message.

Each severity group is also capped at 50 findings per call. On this
project's own tree that cap bites hard - a whole-tree audit runs well past a
thousand `basse` findings, mostly missing dates and missing citations - and
past the cap there is currently no way to page further in: a smaller `limit`
returns a different-sized prefix of the same people, not a different slice,
and `severity` only removes other groups, not entries within the one already
capped. The rendered output says this plainly when it applies; take it at
face value rather than trying `limit` or `severity` to reach the rest.

## Resolving a place name

```
geocode_place(query="Verrens-Arvey, Savoie, France")
```

`geocode_place` is the one tool of the three that leaves the server: it
queries France's `geo.api.gouv.fr`, Switzerland's geo-admin gazetteer, and
falls back to worldwide Nominatim coverage when neither matches. The other
two tools touch only data already fetched from Gramps and make no outbound
call. That means `geocode_place` can fail in a way the others cannot - a
gazetteer being unreachable - and the tool is careful to say so distinctly
from "nothing matched": an unreachable-provider result reads as
`**Gazetteer unreachable**`, never as `## No match`. Treat the two as
different claims; only the second one means the place genuinely was not
found.

When a gazetteer does answer, the result carries a score and one of three
readings, worded so that none of them can be mistaken for a write: a solid
match above `min_score` (default 0.90) is rendered as "solid match - nothing
has been written"; a weaker one as "proposal to review"; and a resolution
the score cannot support as "could not be decided confidently." Every one of
the three names `create_place` as the next step you would take yourself -
the tool never calls it. An ambiguous resolution - more than one candidate
scoring close together - is called out immediately under the heading, before
the coordinates or the administrative chain, and must be treated as
unresolved rather than picked for you.

A resolved name is a candidate, not a proof, even at a high score. Verify
it against the nearest identified ancestor in the record you are sourcing -
never against a region or a country. This tree has already produced the
failure mode directly: "Le Rocher" in the Cher matched a commune roughly
150 km away in Indre-et-Loire, on the strength of the region alone, and the
wrong commune turned out to genuinely carry "le rocher" as an alias - so the
label offered no protection either. Anchor to the nearest place you have
already confirmed, not to the name on its own.
