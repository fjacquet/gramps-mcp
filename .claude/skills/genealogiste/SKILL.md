---
name: genealogiste
description: Workflow for entering genealogy research into a live Gramps Web family tree via the gramps MCP tools. Use this whenever the user pastes a source document (Geneanet profile, FamilySearch entry, civil-registry act image, census record, newspaper clipping, PDF) and wants it cross-checked against the tree and recorded — even if they don't say "genealogy" or name the skill explicitly. Also use when the user asks to source/cite an existing person or event, resolve a research note, reconcile conflicting records, or untangle same-named relatives across generations.
---

# Genealogiste

Turns a pasted source document into sourced Gramps records: matched to the
existing tree where possible, always cited, never overwriting what's already
there.

## Why this matters

Gramps Web's PUT-based update merges list fields (`*_list`) automatically but
replaces everything else outright. A careless `create_person` or
`create_family` call can silently drop data the user already entered. Treat
every write as additive: read what exists first, and only add.

## Per-document loop

For each document the user pastes, work through these steps in order. Don't
re-ask for confirmation between documents unless the new material is
unusually large or clearly off-topic — the user wants a steady one-by-one
pace, not a checkpoint every time.

### 1. Search the existing tree first

Use `find_anything` (free text) or `find_type` (GQL, e.g. `class = person and
primary_name.surname_list.any.surname = "Pagan"`) before creating anything.
Match on name + era + place, not name alone — the same given name and
surname recurs across centuries in small villages, and merging two different
people is worse than leaving them unlinked.

If age/date arithmetic implied by one record contradicts another (e.g. a
birth record says an infant died weeks later, but a separate index card
implies that same name married 20 years on), trust the record with the more
specific, primary detail and treat the other name as a *different* person —
don't force a single identity just because names match. This exact
contradiction has happened in this project (an "infant died 1877" record vs.
a "married 1901" record, both naming a "Marie X") — the fix was creating two
distinct people and re-pointing the marriage event.

### 2. Source everything

Every fact that comes from a document gets a citation chain, never a bare
fact bolted onto a person or event:

```
create_source   (title = publication/register + date/act number)
create_citation (source_handle, page = transcribed detail/quote, date)
create_event    (citation_list = [citation handle], place, date)
create_media    (upload the scan/screenshot itself)
```

**Always call `create_media` and attach it** — to the citation via its
`media_list`, or the source, whichever the record is really documenting.
Skipping this step was a repeated mistake before this skill existed: the
transcription got recorded but the actual scan never did. If the user pasted
an image alongside the text, that image is the media to upload — don't
treat the transcription as sufficient on its own.

After each `create_citation` / `create_event` call, re-read the tool's own
return value for the handle you're about to reuse in the next call. Do not
retype or remember a handle from earlier in the conversation — copy it
fresh from the result. Mismatched/stale handles silently produce an event
with no citation attached, and the only way to catch it is noticing the
citation list came back empty.

### 3. Place is not optional

Every `create_event` needs `place` — a real Place handle, never a name
string (the tool rejects raw text outright: `place must be a place handle,
not a name`). Skipping it was a repeated mistake before this rule existed:
dozens of events got created with the citation naming a commune and the
event itself carrying no location at all, only caught when the user noticed
an empty location on a rendered page.

- Before creating an event, `find_type(type='place', ...)` for the commune
  the citation names, and reuse that handle. Most communes already exist in
  the tree from earlier acts — check before creating a duplicate.
- If it doesn't exist yet, `geocode_place` then `create_place` — and in that
  same call set `placeref_list` to the parent (canton/state, then country;
  `find_type(type='place', ...)` again to find those handles too). A place
  created without `placeref_list` is a floating leaf with no hierarchy: it
  renders as a bare name ("Los Angeles") instead of "Commune, Canton,
  Country" like every other place in the tree, and nothing flags this
  automatically.
- `code` on `create_place` is a free-text field (postal code, department
  number) — it is *not* a substitute for `placeref_list` and does not link
  a parent place. Don't confuse the two.

### 4. Match vs. create vs. hypothesize

- **Solid match** (name + era + place + relationship all consistent): enrich
  the existing person/family. Add events, don't replace existing ones wholesale.
- **No match**: create the new person/family as its own record.
- **Plausible but not proven** (age arithmetic, geography, name pattern,
  without any document naming the actual relationship): create the record,
  but log the connection as a `create_note` of type "Research" attached to
  the person, not as a direct family link. State the reasoning and what
  would confirm or refute it. Never assert an unproven hypothesis as fact in
  the primary family structure — a wrong guess baked into `child_ref_list`
  can't be removed later (see Known limitation below).
- If a pasted document has **no connection** to the family(ies) being
  researched, say so plainly and ask whether it's the wrong attachment,
  rather than forcing a link.

### 5. Numbering and generational hygiene

Sosa-Stradonitz numbers ("sosa 249") on a Geneanet paste mark a *direct*,
already-confirmed ancestral line — treat that lineage with more confidence
than a lateral relative reached by inference, but still verify era/dates
before attaching to a specific existing branch.

When several same-named people exist in the same small area across
generations (multiple "Abraham Pagan" in one village, for instance), check
existing Research Notes first — a prior session may have already flagged
that exact ambiguity. Cross-check birth/death year windows before deciding
whether a new record is the same individual or a new one.

## Known limitation: children can't be removed via these tools

`create_family`'s `child_handles` is translated into `child_ref_list`, which
merges and only grows — a child added to the wrong family by mistake cannot
be removed through the MCP tools. Double-check `father_handle`/
`mother_handle`/`child_handles` before submitting `create_family`; if a
wrong child does get added, tell the user directly that a manual fix in the
Gramps Web UI is required rather than attempting workarounds.

## Filing scans on disk: `~/Downloads/gramps/prooves`

Every scan the user pastes or downloads ends up here. Keeping it tidy is part
of the job, not an afterthought — an unfiled scan with an archive-default
name (`i4071353-02115.jpg`, `téléchargement (4).png`, `12d_312_5.jpg`,
`WhatsApp Image ... .jpeg`) is effectively lost.

### Folders = family dossiers

One folder per researched branch, kebab-case, named after the two main
surnames that meet in it:

```
jacquet-vasselay/    rippert-mariaud/    villaudy-massicot/
pagan/               raucaz/             kochkat-algerie/
autres/              a-trier/
```

- `autres/` — filed and correctly named, but not tied to one of the branch
  dossiers (Cher/Savoie/Algérie mixed, postcards, succession tables).
- `a-trier/` — only for scans whose content could not be identified after
  actually opening the image. Not a dumping ground for "not looked at yet".
- Root holds `A-SAISIR.md` (the backlog) and nothing else. Any image sitting
  at root is unfinished work.

### File naming

```
<type>-<noms>-<lieu>-<annee>[-N].<ext>
```

`<type>` is one of the observed set — stick to it, don't invent variants:
`acte-naissance`, `acte-mariage`, `acte-deces`, `acte-bapteme`,
`promesse-mariage` (singular = one act on the view; plural `actes-deces`,
`actes-naissance` when the view carries several), `registre-paroissial`,
`registre-naissances`, `registre-mariages`, `recensement`,
`table-successions`, `fiche-matricule`, `livret-famille`, `carte-postale`,
`arbre-manuscrit`.

Names lowercase, unaccented, hyphen-separated, surname before given name.
`-2`, `-3` suffix = additional *pages/views of the same act*, never a copy of
the same image. Keep the source extension; never rename `.jpg` to `.png`.

### Deduplication

Run `md5` over the whole tree before filing anything:

```bash
cd ~/Downloads/gramps/prooves
find . -type f ! -name '.DS_Store' -exec md5 -r {} \; | sort | uniq -D -w32
```

- **Identical md5** — delete the copy, keep the one already inside a branch
  folder with a descriptive name. A root file duplicating a filed one is
  always the one to delete.
- **Same act, different md5** (a re-crop, a `(1)`/`(2)` browser download, two
  photos of the same paper chart): open both, keep the most legible/complete
  single view, delete the rest. Don't keep five angles of one document.
- Duplicates *inside* a branch folder happen too (`...-1874.jpeg` vs
  `...-1874-2.jpeg` with the same md5) — the `-2` suffix was misused for a
  copy. Delete the copy.
- Always confirm the delete list with the user before removing anything; the
  scans may be the only surviving copy.

### Verify the name against the content

Filenames already on disk can be wrong. Before trusting one as evidence,
open the image. This has already bitten: `autres/registre-paroissial-
verreux-1823-raucaz-hugonier.jpg` is in fact the 1856 death record of Joseph
RAUCAZ at Verrens-Arvey. When a stored name contradicts the image, rename
the file rather than propagating the wrong label into a citation.

macOS `sips -s format jpeg -Z 1400 <in> --out <out>` gives a readable
thumbnail cheaply — batch-convert before reading, don't read 5 MB scans.

## Style

Keep per-record confirmations short — one or two lines naming who was
added/updated and what was sourced. Save the longer explanation for when a
hypothesis, contradiction, or the child-removal limitation is actually in
play.
