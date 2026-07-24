# Python >=3.12 Bump and Ruff `UP` Modernization — Design

Date: 2026-07-22
Status: Approved

## Context

The project declares `requires-python = ">=3.10"` in `pyproject.toml`, but
Python 3.10 is not exercised anywhere. Four different versions are in play and
none of them is 3.10:

| Location | Version |
| --- | --- |
| `pyproject.toml:5` `requires-python` | `>=3.10` |
| `.github/workflows/ci.yml` (setup-uv) | `3.12` — single version, no matrix |
| `Dockerfile:1` | `python:3.11-slim` — the shipped artifact |
| Local `.venv` | 3.13.5 |
| `README.md:3` badge | `Python-3.10+` |

The single-version CI was a deliberate choice, already recorded in
`docs/superpowers/specs/2026-07-18-ci-badges-readme-design.md`. The
consequence is that the declared floor is an unverified promise, and the
version that ships in Docker (3.11) is not the version that CI tests (3.12).

This work aligns the declared version with the tested one, then adopts ruff's
`UP` (pyupgrade) rule set to modernize the type annotations.

Decided with the user during brainstorming:

- Scope is the version bump plus the `UP` adoption. Nothing else.
- Docker base image goes to 3.12, matching CI exactly, rather than 3.13.
- The two changes ship as two separate commits.

## Goals

1. `requires-python`, the Docker base image, the README badge, and CI all
   agree on Python 3.12.
2. The shipped Docker artifact runs the same Python version CI tests.
3. Legacy `typing` generics are replaced with the modern builtin/PEP 604
   spellings, enforced by ruff going forward.

## Non-Goals

- A multi-version CI matrix. CI stays on 3.12 only.
- Any code sharing, client unification, or model unification with the
  `crewai_custom_tools` project. The bump removes a version blocker to that
  work but does not start it.
- Any behavioral change to the server, tools, handlers, or client.

## Measurements

All numbers below were produced by copying `src/`, `tests/`, `pyproject.toml`,
and `pytest.ini` into a scratch directory and running ruff there. The working
tree was not modified.

### Ruff `UP` violations at `--target-version py312`

| Rule | Description | Count | Auto-fixable |
| --- | --- | --- | --- |
| UP045 | `Optional[X]` -> `X \| None` | 202 | yes |
| UP006 | `Dict`/`List` -> `dict`/`list` | 158 | yes |
| UP035 | deprecated `typing` import | 46 | reported as no |
| UP017 | `timezone.utc` -> `datetime.UTC` | 4 | yes |
| UP007 | `Union[A, B]` -> `A \| B` | 2 | yes |
| UP015 | redundant `open(..., "r")` | 1 | yes |

Total 413. After `ruff check --select E,F,I,UP --fix`, the residual count
across `E`, `F`, `I`, and `UP` combined is **zero**. No `--unsafe-fixes`
required.

The 46 UP035 violations resolve without manual work: once UP006 and UP045
rewrite the annotations, the `from typing import Dict, List, Optional` lines
become unused, and F401 — already in the project's `select` — removes them.
This was verified by running the fix, not inferred.

### Only UP017 depends on the bump

At `--target-version py310`, ruff reports **zero** UP017 violations, because
`datetime.UTC` is a 3.11+ alias. The other 409 violations are reported
identically at py310 and py312.

The two changes are therefore independent: the annotation modernization was
already available at 3.10, and the bump only adds these four fixes. They are
sequenced together for convenience, not necessity.

### Diff scale and validation

- 38 files change: 36 under `src/`, 2 under `tests/`.
- 652 changed lines in `src/`.
- `mypy src/gramps_mcp --ignore-missing-imports`: `Success: no issues found in
  57 source files`, with 0 errors, both before and after the fix.
- The four offline test files (21 tests) pass against the fixed copy.

The diff touches pydantic model fields (`Optional[str]` -> `str | None`).
Pydantic 2.11.7 handles PEP 604 unions natively on 3.12; the passing tests
confirm this.

## Changes

### Commit 1 — version bump

| File | From | To |
| --- | --- | --- |
| `pyproject.toml:5` | `requires-python = ">=3.10"` | `">=3.12"` |
| `Dockerfile:1` | `FROM python:3.11-slim` | `FROM python:3.12-slim` |
| `README.md:3` | badge `Python-3.10+` | badge `Python-3.12+` |
| `uv.lock` | `requires-python = ">=3.10"` | regenerated via `uv lock` |

`.github/workflows/ci.yml` is not modified — it is already on 3.12 and serves
as the source of truth the other files align to.

The base image moves to 3.12 rather than 3.13 so the shipped artifact matches
the CI-tested version exactly. The local 3.13.5 virtualenv remains valid under
`>=3.12`.

Files under `docs/superpowers/` are not modified. Existing specs and plans are
dated records of past decisions, not living documentation.

### Commit 2 — adopt `UP`

1. `pyproject.toml`: `select = ["E", "F", "I"]` becomes
   `select = ["E", "F", "I", "UP"]`.
2. Run `uv run ruff check --fix src/ tests/`.
3. Run `uv run ruff format src/ tests/`.

Ruff infers `target-version` from `requires-python`, so no explicit
`target-version` key is added; commit 1 makes it `py312` implicitly.

### Why two commits

Commit 1 is four small, reviewable edits. Folding 652 lines of mechanical
rewrites into it would bury them. Splitting also allows reverting the `UP`
adoption independently if it causes friction.

## Risks

**Source installs on older distributions.** Anyone installing from source on
Debian bookworm (3.11) or Ubuntu 22.04 (3.10) will be blocked. Impact is
low: `pyproject.toml` has no `[build-system]`, no `[project.scripts]`, and no
classifiers — this repo is a Docker-shipped application, not a PyPI library.
There are no downstream package consumers to break.

**Merge conflicts.** The 652-line diff would conflict with in-flight work.
There are no open pull requests, and the three remote-only branches are stale,
so the risk is negligible.

**Docker image bloat.** If the base image were left at 3.11 while
`requires-python` demanded 3.12, `uv sync --frozen` would either fail or
silently download a second interpreter into the image. Bumping the base image
in the same commit prevents this; the build check below confirms it.

## Verification

Run after each commit:

1. `uv lock && uv sync`
2. `uv run ruff check src/ tests/`
3. `uv run ruff format --check src/ tests/`
4. `uv run mypy src/gramps_mcp --ignore-missing-imports` — expect
   `Success: no issues found in 57 source files`
5. `uv run pytest tests/test_merge.py tests/test_config.py
   tests/test_client_merge.py tests/test_utils.py` — expect 21 passed
6. `docker build .` — confirm the build succeeds and `uv sync --frozen` does
   not download an extra interpreter (a noticeably larger image indicates it
   did)

Tests outside the four offline files require a live Gramps Web server and are
expected to fail with connection errors when run without one. That is not a
regression.
