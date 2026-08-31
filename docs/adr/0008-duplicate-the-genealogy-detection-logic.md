# 8. Duplicate the genealogy detection logic rather than share it

Date: 2026-08-30

## Status

Accepted

## Context

The detection tools shipped in v1.11.0 - `find_duplicates`, `audit_quality`
and `geocode_place` - are built on roughly 1860 lines of pure logic that
already existed, and had already been tested, in another repository owned by
the same person: `fjacquet/crewai-custom-tools`, at v0.31.1 (`19d78f7`), under
`src/crewai_custom_tools/tools/genealogy/`. Blocking-key duplicate detection,
the consistency rules R1-R9 and completeness rules D1-D3, merge planning, and
the France and Switzerland place resolvers were all there, none of them
touching a network or a database.

Three ways to reach that code from this server were considered.

- **Extract a shared package.** The textbook answer: lift the pure logic into
  `genealogy-core`, publish it, and depend on it from both repositories. One
  copy, one bug fix, one test suite.
- **A git submodule or a path dependency.** No publishing, but the two
  repositories become coupled at the filesystem or the commit level, and every
  contributor and every CI job has to know about it.
- **Copy the files in.** No coupling, no packaging, and two copies that will
  drift.

The packaging option carries costs this project does not want to pay for two
consumers: a third repository to create and maintain, a release process for a
library nobody outside these two repositories will ever install, and a version
pin that turns any change into a coordinated release across three places.
Those costs are real, but they are not rules - they are defaults, and the
person who owns both repositories is the one entitled to override them. The
decision to copy was made explicitly by the repository owner, against the
recommendation recorded in the design spec, and is recorded here so that it is
not silently reversed by someone who reads the duplication as an accident.

The full design is recorded in
`docs/superpowers/specs/2026-08-30-detection-tools-design.md`.

## Decision

Copy the pure logic into `src/gramps_mcp/genealogy/`. Do not share it.

Every copied file's module docstring names its origin: the source repository,
the version, the commit sha, and the original path. Where a file diverges from
its origin, the docstring names each divergence and why it exists - the copies
made for this server are typing annotations and a `requests` to `httpx` port,
not behaviour changes.

Only pure logic was copied. Anything that reaches a network or a data store
was left behind and rewritten here: `collect.py`, which fetches the tree
through this server's own client, is the one module written from scratch.

## Consequences

**Divergence between the two copies is expected and accepted.** It is not a
defect to repair. A contributor who notices the duplication and "fixes" it by
re-unifying the two copies is undoing a deliberate decision, which is the
specific outcome this record exists to prevent.

**A bug found in one copy is not fixed in the other.** Nothing propagates.
Whoever fixes a defect in the detection logic has to decide, each time,
whether the other repository needs the same fix, and carry it there by hand if
so. This is the price of the decision and it is paid on every fix, forever.

**The two repositories stay independent.** No shared release, no version pin,
no third repository, and each side is free to change its copy without
coordinating. This is the benefit, and it is the reason the price above is
worth paying at two consumers. It would not be at five.

**The provenance lives in the code, not only here.** The docstrings are what a
contributor actually reads. If a future copy is added without one, the
duplication becomes indistinguishable from an accident and this decision
stops being enforceable.
