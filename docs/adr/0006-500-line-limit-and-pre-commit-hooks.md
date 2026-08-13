# 6. Enforce a 500-line file limit and a local pre-commit hook chain

Date: 2025-09-11

## Status

Accepted

## Context

`CLAUDE.md` line 15 states: "Never create a file longer than 500 lines of
code. If a file approaches this limit, refactor by splitting it into modules
or helper files." The rule and its enforcing script are both present in the
initial commit (d27134a, 2025-09-11), alongside a copyright-header hook and
an emoji ban. No spec argues for the specific number; 500 was asserted, not
derived.

The rule's practical purpose is legible in the history: this codebase is
largely written by an agent, and a file an agent must read whole before
editing is a file whose size is a per-edit cost. Commit 9ee009d is explicit -
"Extracted analysis query-param models into their own module to keep
server.py under the 500-line limit" - and bd6c44f split `test_search_basic.py`
for the same reason. The limit is what has produced the `models/parameters/`,
`handlers/` and `tools/` decomposition, rather than one large server module.

The emoji ban has the same origin: `CLAUDE.md` states it as a style rule, and
`scripts/check_no_emojis.py` enforces it across all files, not just Python.

## Decision

`.pre-commit-config.yaml` runs, on every commit:

- `ruff --fix` and `ruff-format`, pinned to `v0.13.0` with a comment
  requiring it to track the dev-group version, because a version skew here
  produces files that CI's `ruff format --check` then rejects.
- `scripts/add_copyright_notice.py` on `.py` files, excluding `tests/` and
  `examples/` - hence the AGPL header on every source file.
- `scripts/check_file_length.py` on `.py` files, `exclude: ^tests/`.
- `scripts/check_no_emojis.py` on all files, no exclusions.

Contributors run `uv run pre-commit install` and commit through
`uv run git commit` so the hooks fire.

## Consequences

The source tree does hold the line. `server.py`, the largest and most
pressured file, sits at 439 lines, and the split that keeps it there is
visible in the parameter-model modules. The decomposition is a genuine
byproduct rather than an aspiration.

The costs are ordinary: the limit counts lines, not complexity, so a file
can be split on an arbitrary seam purely to satisfy it, and the copyright
hook rewrites files under the committer without asking.

The gap worth recording is in `tests/`. The file-length hook carries
`exclude: ^tests/`, so the 500-line rule - which `CLAUDE.md` and
`CONTRIBUTING.md` both state without qualification - is unenforced there.
Three test files exceed it today: `tests/test_data_management.py` at 1139
lines, `tests/test_complete_workflow.py` at 800, and
`tests/test_parameter_alignment.py` at 605. This was found during the v1.7.0
quality work. `pyproject.toml` separately exempts `tests/*` from ruff's E501
with a stated reason, so the exclusion may be intentional inheritance from
that stance - but nothing records it as a decision, and the two documents
that state the rule do not mention an exception. Either the exclusion should
be justified in `CLAUDE.md` or the three files should be split; as it
stands, the rule and its enforcement disagree.

## Update, 2026-08-13

The gap recorded above is closed. On branch
`fix/quality-lot5a-test-structure`, commit 50112b3 removed `exclude:
^tests/` from the `check-file-length` hook, so the 500-line rule now applies
to `tests/` exactly as `CLAUDE.md` and `CONTRIBUTING.md` state it. The
`exclude: ^(tests/|examples/)` that remains in `.pre-commit-config.yaml`
belongs to the copyright hook, not this one.

The three files named above no longer exist. The same branch split
`tests/test_data_management.py` and `tests/test_parameter_alignment.py` into
the `test_create_*` and `test_alignment_*` modules, and
`tests/test_complete_workflow.py` into `tests/test_workflow_marriage.py` and
`tests/test_workflow_attributes.py`. The largest file under `tests/` is now
`tests/test_workflow_marriage.py` at 472 lines. The choice the paragraph
posed - justify the exclusion or split the files - was resolved by splitting
the files.

`pyproject.toml` still exempts `tests/*` from ruff's E501. That is a line
*width* exemption and is unaffected by this; the two rules were only ever
related by analogy.
