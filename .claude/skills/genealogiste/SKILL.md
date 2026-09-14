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

**Search every person the document names, not just its subject.** A death
act names the deceased, the surviving spouse, the previous spouse and both
parents - five people, and each one needs its own lookup before anything is
written. On 2026-09-04 three clusters had to be merged (12 people, 6
families, 4 events) because acts from Breitenbach 1819, Plou 1825 and Tarsul
1870 were each entered by creating the subject *and the whole surrounding
family* in one go. Nothing in the tree flags this: two same-named records
coexist silently, and the newer one, carrying the better citation, looks
like the right one.

The only reliable proof of identity is **two dates coinciding** - birth and
death, to the day. A shared name proves nothing in these parishes. The tell
that a duplicate slipped through is a person whose events split across two
records, or a family whose parents repeat under a spelling variant
(Hadler/Stadler, Gaudicher/Gaudichet, Demoulier/Demouliere). Variants are
what an external duplicate report can see; identical spellings it cannot -
`scratchpad/sweep_recent.py` groups the whole tree by normalised name and
reports only the groups touching recently created `gramps_id`s, which is
the bounded way to catch those.

If age/date arithmetic implied by one record contradicts another (e.g. a
birth record says an infant died weeks later, but a separate index card
implies that same name married 20 years on), trust the record with the more
specific, primary detail and treat the other name as a *different* person —
don't force a single identity just because names match. This exact
contradiction has happened in this project (an "infant died 1877" record vs.
a "married 1901" record, both naming a "Marie X") — the fix was creating two
distinct people and re-pointing the marriage event.

### 2. Source everything

**Not every source is worth the same, and the citation must say which it
is.** Three tiers, decided on 2026-09-06:

1. **Official document** — parish or civil register, the archive's own scan.
   This is the only thing that *proves* a fact.
2. **Associative index** (CGHB relevés on Filae, Geneanet dépouillements) —
   a finding aid. Use it to locate the date and the reference, never to
   establish the fact.
3. **Online tree** (Geneanet, Geni, MyHeritage, FamilySearch Family Tree or
   Pedigree Resource File) — **never a proof**. At best a lead; mark the
   citation `SOURCE DÉRIVÉE` and say what is uncorroborated.

Demonstrated on this tree: the PRF file `S0279` dates `I1516`'s birth to
26/03/1731; that act belongs to a namesake who died at three days. A
confident file, and wrong. Two official acts likewise overturned a given
name the tree had carried for months (`I1485` Marthe → Marie Larpent).

**Finding the official act — Filae, `img=true`.** The source line
"Etat civil - Archives du Cher" returns the register view itself,
readable and downloadable. The search URL is fully parameterised, so skip
the form:

```
https://www.filae.com/search?ln=<NAME>&fn=<Given>&sy=<from>&ey=<to>
  &pn=<Commune>%2C+<Dept>%2C+<Region>%2C+France&fc=PPL&di=<id>
  &lat=<lat>&lon=<lon>&gid=<id>&ri=<id>&tab=0&ps=50&pi=0&img=true
```

`img=false` adds the associative relevés — useful as an index, never as
proof. Wildcards work in the surname and are often mandatory: the index
spells VILLAUDY as *VILLANDY*, and `Cam*at` found CAMUZAT where the
handwriting was ambiguous. **Never conclude a record is absent without
trying a wildcard.** Allow ~5 seconds for the page to compute before
reading it. Downloading the view is a user-authorised action — ask first.

**Filae's index has its own blind spots, distinct from wildcard coverage:**
- **`ffn`/`fln` (father's given name/surname) return zero results on Cher
  civil registration, even under the exact spelling, though the same acts
  exist.** Parents are only readable on the image itself. To search *by
  filiation* instead of by the subject's own name, query the **CGH-B**
  (genea18.fr) instead — see below, its listing carries a `Mère, nom Prénom`
  column that Filae's own search fields cannot filter on.
- **`pn=<commune>` alone is silently ignored without its geo quadruplet**
  (`di=`/`lat=`/`lon=`/`gid=`/`ri=`) — it falls back to a nationwide search
  (thousands of results instead of a few dozen) with no warning that the
  place filter didn't apply. Worked example, Saint-Martin-d'Auxigny (Cher):
  `di=3025480&lat=47.20371&lon=2.41553&gid=2978420&ri=3027939` — its 20 km
  radius also covers Vignoux-sous-les-Aix, Saint-Georges-sur-Moulon and
  Pigny, so the same quadruplet serves searches in those communes too.

**The CGH-B (genea18.fr) is a second, URL-driven index — use it for filiation
searches Filae can't do, never as proof:**

```
https://www.genea18.fr/p/ActeRi.php?Act=R&iNom1=<nom>&iPrenom1=<prenom>
  &iMotReq=<mots>&iDateActe=<de>&iDateActeF=<a>&iParoiss=<code>&iRayon=&iLigne=50
```

`iParoiss` is a commune code (e.g. `18223` = Saint-Martin-d'Auxigny,
`18189` = Quantilly); leaving `iRayon=` empty restricts to that commune,
filling it widens the radius and dilutes the result list. The name match is
**phonetic**; a trailing `*` means "starts with" and turns phonetic matching
off — try both before concluding a name is absent. The `iMotReq=` field
(*Mot(s)*) searches the whole record, so `iMotReq=Paul` against a surname
returns every act where a Paul appears as a parent — this is the filiation
search Filae's `ffn`/`fln` cannot do. The listing's `Mère, nom` column names
the mother **of the first-listed person only**; open the actual fiche (click
"Acte") for father, mother, and the free-text *Informations* field, which
carries hamlets, parents' ages, and stated relationships ("gd-onc.",
"cousin", "ami du défunt"). A fiche's "leurs enfants" link re-searches at a
15 km radius, too wide to be useful — prefer `iMotReq=<mother's full name>`
scoped to the single commune instead. **The tooltip that lists a person's
parents on the results listing does not refresh row to row** — it can go on
showing the previous row's parents on a later row with a different mother
in its own `Mère` column. Never trust the tooltip as the discriminant; only
the listing's own column, or the opened fiche, is authoritative.

**genea18.fr masks names/dates behind asterisks unless logged in** — a plain
`WebFetch` sees the masked table (counts are still correct, but no dates, no
parents). If the shared Chrome tab already has a CGH-B session (check for
the account name in the top bar), navigate that tab to the search URL and
`get_page_text` instead of `WebFetch` — same URL, unmasked. `iParoiss` codes
are INSEE commune codes (confirmed: `18279` = Vasselay).

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

**One citation per fact, and check the ones already there.** Reusing a
single citation for everything drawn from one file is the mirror image of
that mistake, and worse because it looks correct: `C0659` states its own
scope ("il s'agit de Jacques VILLAUDY I0754") yet sourced five events
about three other people; `C0658` carries seventeen. A reference audit
sees nothing — every handle is valid. The only test is reading a
citation's `page` against each event it sources. Before trusting an
existing citation, read it.

`FamilySaveParams` and `PersonData` reject `citation_list`. A filiation is
therefore sourced on the `child_ref_list` entry
(`{"ref": <child>, "citation_list": [<cit>]}`) — which is right anyway: the
act proves the parent-child link, not the couple.

#### Iconography: one citation per lot

Images from Wikimedia follow a convention set by citations C1542, C1666,
C1667: **one citation for the whole lot**, not one per file. Its `page` is a
prose note in unaccented French naming every file, its licence, its painter
and an explicit `IDENTITE CERTAINE / PROBABLE / NON CERTAINE` verdict,
followed by `PIEGES ECARTES` naming the homonym files rejected and why. The
citation hangs on the media objects, not on the people — it records where a
file came from, not what it proves. The media `desc` is in accented French,
as the reader sees it. Sources are per branch: S0190 (Cœur/Bochetel), S0191
(Potocki-Branicki). Don't create a generic "Wikimedia Commons" source.

An image only shows on a person page if it is in that person's own
`media_list` — media on a citation or a place never surface there.

#### Finding a portrait: two separate claims

Matching a person to a Wikidata entity and matching a *file* to that person
are different claims, and both must be checked.

- **Identity**: require **both** birth and death years to agree. One agreeing
  year is never enough. The first hit for "Zofia Branicka" is a woman born
  1790; the right one (1821-1886) is filed under her married name Odescalchi.
  Noble women are routinely under the husband's surname.
- **Search spelling**: Wikidata files a noble under the forenames they were
  known by, rarely all of them. "Stanisław Kostka Franciszek Zamoyski"
  returns nothing; "Stanisław Kostka Zamoyski" finds the man. Drop forenames
  from the right.
- **File content**: a P18 claim says a file depicts someone of that name, not
  that it is a painted portrait of *your* person. Read the Commons file page
  (`extmetadata`: `ObjectName`, `ImageDescription`, `Artist`, `Categories`)
  and say plainly what it is — a group portrait, an engraving, a bust, a
  monument.
- **Licence**: an 1853 painting is public domain; the photograph of it may
  not be. `LicenseShortName` from the file page decides. An unreadable
  licence means not a candidate.
- **A work predating its sitter is a misattribution.** Grassi's 1799 portrait
  hung on a Zamoyski born 1820. Compare the artwork's date to the person's
  dates before trusting an existing attachment.
- **Living people are out of scope**, as they are for LinkedIn or any other
  social profile: no death date recorded, or a recent one, means don't look.

### 3. Place is not optional

Every `create_event` needs `place` — a real Place handle, never a name
string (the tool rejects raw text outright: `place must be a place handle,
not a name`). Skipping it was a repeated mistake before this rule existed:
dozens of events got created with the citation naming a commune and the
event itself carrying no location at all, only caught when the user noticed
an empty location on a rendered page.

- Before creating an event, `find_type(type='place', ...)` for the commune
  the citation names, and reuse that handle. Most communes already exist in
  the tree from earlier acts — check before creating a duplicate. The GQL
  property is `name.value`, not `name` or `title` — both return "no places
  found" even when the place exists.
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
`table-successions`, `fiche-matricule`, `fiche-parlementaire`, `livret-famille`,
`carte-postale`, `arbre-manuscrit`, `portrait`.

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

**That same `sips` output breaks Gramps Web's thumbnail if uploaded as-is.**
`sips` preserves the source's colorspace, and old scans (Ancestry/
FamilySearch exports especially) are often already grayscale — `sips`
keeps them grayscale (JPEG mode `L`), sometimes with an embedded gray ICC
profile. The full file uploads and downloads fine, but the server's AVIF
thumbnail generator produces a corrupt/undecodable thumbnail from a
grayscale source: the media page shows a broken-image icon even though the
underlying file is intact. 44 of 55 uploads in one session broke this way
before it was caught.

**Measured on 2026-09-04: grayscale alone does not reproduce it.** Five
media whose stored file is a mode-`L` JPEG **with no ICC profile** (AD18
IIPImage exports, O1092-O1095 and O1255) all return a valid thumbnail:
`GET /api/media/<handle>/thumbnail/300` yields bytes beginning
`\x00\x00\x00 ftypavif` that decode to `AVIF RGB (300, ...)`. So the
failing input was the *other* half of the description above - `sips`
output carrying an **embedded gray ICC profile** - and that case has not
been retested. Convert when the file came through `sips`; a scan
downloaded straight from an archive viewer can go up as-is.

Do not diagnose a broken thumbnail from the page's broken-image icon
alone - fetch `/api/media/<handle>/thumbnail/300` and look at the first
bytes. That is the only test that distinguishes a bad stored thumbnail
from a rendering or caching problem in the browser.

Before `create_media`, force RGB on the file that will actually be
uploaded (the `sips` thumbnail is fine to read from, but don't upload that
same file if it came out grayscale **with an ICC profile**):

```python
from PIL import Image
Image.open(path).convert("RGB").save(path, "JPEG", quality=90)
```

If a broken thumbnail turns up later (page shows a broken-image icon, full
file downloads fine via `.../media/<handle>/file`), fix it in place rather
than re-uploading as a new record: convert to RGB, then `PUT
/api/media/<handle>/file` with the fixed bytes - handle, `gramps_id`, and
every citation's `media_list` link stay intact, only the stored file and
its checksum change. See the `gramps-rest-recovery` skill for the batch
version of this fix.

**A failed `create_media(media_path=...)` may still have created the
record.** The upload and the metadata PUT are two calls: the file is
uploaded first, and only then is `desc`/`citation_list` attached. Any
error raised after the upload leaves a media record behind. Before
retrying, look for it:
`find_type(type="media", gql='checksum = "<md5 of the local file>"')`.
One clean upload yields exactly one match; a blind retry yields two or
more with identical checksums - `DELETE /api/media/<extra-handle>` the
duplicates via REST, keep one. Then attach `desc` and `citation_list`
with `create_media(handle=...)` and **no** `media_path`.

Never conclude a scan failed to upload just because the tool call errored -
check by checksum before retrying, or duplicate media records pile up.

(The systematic crash on every upload - `date._class` / `date.calendar` /
`date.format` / `date.newyear` / `date.sortval` "Extra inputs are not
permitted" - was a defect in `create_media_tool`, fixed in the source on
2026-09-02. It echoed the server's own record back into the PUT, where
the raw `date` object failed revalidation. The image was rebuilt and the
container recreated the same day, so the tool no longer crashes. The
duplicates that year of crashes left behind - 60 media records holding a
file another record already referenced - were merged on 2026-09-02 by
`scripts/dedupe_media.py`, leaving 1171 objects and no broken reference.)

## Style

Keep per-record confirmations short — one or two lines naming who was
added/updated and what was sourced. Save the longer explanation for when a
hypothesis, contradiction, or the child-removal limitation is actually in
play.

## Research method: reading the evidence

Moved here from the root `CLAUDE.md` on 2026-09-09: these are research
method, not tool contracts, so they only need to be in context while this
skill is running. The tool-behaviour prohibitions (`gramps_id` in a
`*_list`, raw `PUT`, `create_sourced_event` orphans, one-sided
`create_family` links) stay in `CLAUDE.md` because they fire on any stray
MCP call.

- **Do not bulk-promote a place or a date out of citation text.** Measured on
  2026-09-01: of 12 events whose citation named a known place next to a word
  for that event's own act type, **1** was right. The source title is the
  trap - every `K Nidau ...` citation contains "Nidau", so the register's name
  matches as if it were the location, while the actual place sits later in the
  page (Biel, Genève, Gorgier, Rueggisberg). The rest attached a *birth* place
  to a death ("née à Bourges" on a death act) or a relative's place to the
  wrong person. Dates fail the same way: a year in an occupation citation is
  the person's birth year, not the year of the trade. Promote these one at a
  time, reading the page, never in a lot.
- **Reading the tree over REST: `?page=1` is the first page** (`page=0` returns
  HTTP 422), and `?gql=` silently returns 0 for any `attribute_list.any.*`
  filter - page through and filter in Python instead. An audit scoped to an ID
  range or a hand-picked sample will miss records; scope it to the whole tree
  or say plainly that it did not.
- **A citation reused across events it does not cover is invisible to a
  reference audit.** `C0659` declared its own scope ("il s'agit de Jacques
  VILLAUDY I0754") yet carried five events; `C0658` carries 17. Read a
  citation's `page` against every event it sources - `0 broken references`
  says nothing about this.
- **The citation `page` outranks the source `title` for an event's place.** A
  title names the register or the archive's seat, not where the act happened:
  "Table des successions, Bourges" covers deaths at Saint-Martin-d'Auxigny.
  Measured corollaries: match place names on word boundaries ("genevoises"
  matched Genève by substring, 35 events); take the act type named **first** in
  the page, since "mariage ... ne le ..." is a marriage act; and "von X" / "de X"
  in Swiss registers is bourgeois origin, not birthplace.
- **Verify a gazetteer QID against the nearest identified ancestor**, never
  against a region or country: "Le Rocher" (Cher) matched Saint-Antoine-du-Rocher
  (Indre-et-Loire) on the region alone, and "le rocher" is a genuine alias of that
  commune - the label is no protection.
- **`Unknown` places created by Check and Repair are usually not orphans**: 8 of 9
  were the parent of a real commune. Repoint the children onto the right parent
  and check backlinks record by record before deleting anything.
- **Surname casing: store Title Case (`Jacquet`), never ALL-CAPS.** GEDCOM 5.5.1
  mandates the opposite of upper-case ("capitalize the first letter of each part
  and lowercase the other letters") and FamilySearch follows it; ALL-CAPS is a
  French correspondence convention, not a genealogy rule. Matches the sibling
  `genecrew` repo's tested `GrampsUpdateNameTool` invariant, which recases
  `JACQUET` -> `Jacquet` and never the reverse.
- **Filae indexes the register's own spelling, not the tree's modern one.**
  Searching surname `Villaudy` (double-L, the tree's spelling) returned
  nothing at Saint-Martin-d'Auxigny; the same search under `Vilaudy`
  (single-L, matching the period register) returned exact-match results for
  every year tried. A zero-result Filae search is not proof of absence until
  it has been retried under the plausible period spellings, not just the
  tree's own.
- **A baptism act's own date is not the birth date - read the formula.**
  Saint-Martin-d'Auxigny's curés wrote one of several set phrases after the
  child's name: "né(e) d'aujourd'huy" / "né(e) de ce jour" / "né(e) du jour"
  (born same day - baptism date = birth date) versus "né(e) d'hier [à telle
  heure]" (born the day before - baptism date minus one). Measured on a
  14-act batch (11/09/2026): 2 of 14 used "d'hier", both silently one day off
  if the baptism date had been recorded as the birth date. Check this phrase
  on every baptism act before setting the Birth event's date; when it gives
  an hour, put it in the citation `page`.
- **archives18.fr's page-to-date mapping is not linear across a register.**
  Extrapolating a target date from the register's stated year span and image
  count (e.g. "195 images / 10 years") lands on the wrong act - annual recap
  tables and separately-bound sub-volumes make page density uneven within a
  single register. Once one page/date pair is confirmed, anchor there and
  navigate by short forward/backward hops reading marginal dates, rather than
  re-extrapolating linearly for the next target.
- **A CGHB relevé can mark an act "non obtenu" and still be wrong about that.**
  The Etienne VILAUDY (F0790) birth of 03/10/1772 was recorded by the CGHB
  index as an act it could not find; it was sitting in archives18.fr's
  EDEPOT508 dépôt communal register the whole time, a copy independent of
  whatever Filae/greffe copy the CGHB relevé was built from. When Filae
  itself returns zero results (even `img=false`) for an act the relevé says
  should exist, that is a genuine Filae-corpus gap for that register/period,
  not proof the act itself is lost - try the archive's direct viewer
  (archives18.fr or equivalent) before concluding a primary act is
  unrecoverable.
