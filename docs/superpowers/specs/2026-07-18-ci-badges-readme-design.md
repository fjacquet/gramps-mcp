# CI/CD, Badges, and README Improvements — Design

Date: 2026-07-18
Status: Approved

## Context

The repo has a Docker publish workflow (`.github/workflows/docker-publish.yml`)
but no CI workflow that lints, type-checks, or tests pushes/PRs. The README
has no status badges beyond static License/Python/MCP ones, and the Python
badge itself is stale ("3.9+" vs. the actual `requires-python = ">=3.10"` in
`pyproject.toml`). This work adds a CI workflow, wires up coverage reporting,
adds a badge row, and makes two small targeted README additions.

Decided with the user during brainstorming:

- CI runs only the four offline-safe test files (no live Gramps Web server in
  CI) — `tests/test_merge.py`, `tests/test_config.py`,
  `tests/test_client_merge.py`, `tests/test_utils.py`.
- Single Python version in the CI matrix: 3.12 (not the full 3.10-3.12 range
  a stricter compatibility check would use — the user chose speed/simplicity
  over matrix coverage; noted here as a deliberate choice, not an oversight).
- Coverage reporting via Codecov (not a self-hosted, bot-committed SVG badge).
  This requires a one-time manual step from the user after implementation:
  create a codecov.io account, add the `fjacquet/gramps-mcp` repo, and add the
  resulting token as the `CODECOV_TOKEN` secret in the GitHub repo settings.
  Nothing in this plan can do that step for them.
- README scope is targeted: badge row, a table of contents, and a short
  "Development" section — not a full rewrite. The rest of the README's
  content (features, install, config, architecture, troubleshooting, etc.)
  stays as-is; it was already brought up to date in the prior code-quality
  cleanup.

Out of scope: running integration tests against a live Gramps Web server in
CI (would need a service container or the user's in-progress `docker/grampsweb`
setup — deliberately deferred, not part of this design); branch protection
rules requiring the new CI check to pass (a GitHub repo setting, not a file
in this repo — left to the user to configure if desired); Python version
matrix beyond 3.12.

## Changes

### 1. New workflow: `.github/workflows/ci.yml`

Triggers: `push` to `main`, and `pull_request` (any branch → any base).

Single job `test`, `runs-on: ubuntu-latest`, steps:

1. `actions/checkout@v4` (matches the version already used in
   `docker-publish.yml`).
2. `astral-sh/setup-uv@v6` with `python-version: "3.12"` and
   `enable-cache: true`.
3. `uv sync --locked --all-extras --dev`
4. `uv run ruff check src/`
5. `uv run ruff format --check src/ tests/`
6. `uv run mypy src/gramps_mcp --ignore-missing-imports`
7. `uv run pytest --cov=src/gramps_mcp --cov-report=xml tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py`
8. `codecov/codecov-action@v5` with `token: ${{ secrets.CODECOV_TOKEN }}`,
   `fail_ci_if_error: false` (a missing/invalid token must not fail the whole
   CI run — coverage upload is a nice-to-have, not a merge gate).

Step ordering matters: lint/format/type-check run before the (slower) test
step, so a formatting mistake fails fast without waiting on pytest.

### 2. `pyproject.toml`: add `pytest-cov`

Add `"pytest-cov>=5.0.0"` to the `[dependency-groups] dev` list (alongside
the existing `pytest`, `pytest-asyncio`, etc.).

### 3. Codecov setup (manual, user-performed)

Documented as a follow-up step in the implementation report, not automatable:

1. Sign in to codecov.io with the GitHub account that owns the fork.
2. Add the `fjacquet/gramps-mcp` repository.
3. Copy the repository upload token.
4. In the GitHub repo: Settings → Secrets and variables → Actions → New
   repository secret → name `CODECOV_TOKEN`, paste the token.

Until this is done, the Codecov upload step will fail non-fatally (per
`fail_ci_if_error: false`) and the coverage badge will show "unknown".

### 4. README badge row

Replace the current single badge line (line 3) with two lines: the existing
static badges (with the Python version corrected to `3.10+`) plus a new line
of dynamic/semi-dynamic badges directly beneath:

```
[![License](https://img.shields.io/badge/License-AGPL--3.0-blue)](./LICENSE) [![Python](https://img.shields.io/badge/Python-3.10+-brightgreen)](https://python.org) [![MCP](https://img.shields.io/badge/MCP-1.2.0+-orange)](https://modelcontextprotocol.io)
[![CI](https://github.com/fjacquet/gramps-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/fjacquet/gramps-mcp/actions/workflows/ci.yml) [![Docker Build](https://github.com/fjacquet/gramps-mcp/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/fjacquet/gramps-mcp/actions/workflows/docker-publish.yml) [![codecov](https://codecov.io/gh/fjacquet/gramps-mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/fjacquet/gramps-mcp) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
```

The badge URLs point at `fjacquet/gramps-mcp` (this fork), matching where the
workflows actually run today. If/when this is merged upstream into
`cabout-me/gramps-mcp`, the badge URLs need updating to match — noted as a
follow-up, not handled by this design.

### 5. README table of contents

Inserted immediately after the "With Gramps MCP" intro block (after line 42,
before the `## Features` heading), as a `## Table of Contents` section
linking to every existing `##` heading via standard GitHub anchor links
(lowercased, spaces to hyphens): Features, Installation, MCP Client
Configuration, Architecture, Usage Examples, Development (new, see below),
Security, Troubleshooting, License, Related Projects, Contributing,
Acknowledgments.

### 6. README "Development" section

New `## Development` section inserted between `## Architecture` (currently
ending around line 246) and `## Usage Examples` (currently starting around
line 248) — grouping it with the other "how the project works" content
rather than at the end with License/Acknowledgments:

```markdown
## Development

Requires [uv](https://docs.astral.sh/uv/). See
[CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

```bash
uv sync --all-extras --dev       # install dependencies
uv run ruff check src/           # lint
uv run ruff format --check src/ tests/  # formatting check
uv run mypy src/gramps_mcp --ignore-missing-imports  # type check
uv run pytest tests/test_merge.py tests/test_config.py tests/test_client_merge.py tests/test_utils.py  # offline-safe tests
```

Most tests in `tests/` require a live Gramps Web server (see
[CONTRIBUTING.md](CONTRIBUTING.md)); the command above runs only the ones
that work offline, matching what CI checks.

```

## Verification

- `ci.yml` is valid YAML and mirrors the commands already verified to pass
  locally in the prior cleanup work (ruff check, ruff format --check, mypy,
  the four offline test files).
- After pushing, the Actions tab shows the `CI` workflow running and (once
  `CODECOV_TOKEN` is added) the Codecov upload succeeding.
- README renders correctly on GitHub (badge row, TOC anchors resolve, new
  Development section reads coherently in place).
- `git diff` confirms no unrelated README content changed.

## Risks

- The CI badge and Docker Build badge will show "no status"/gray until the
  workflow has run at least once on the `main` branch of `fjacquet/gramps-mcp`
  after this change is pushed.
- The Codecov badge will show "unknown" until the `CODECOV_TOKEN` secret is
  added — this is expected and documented, not a bug to chase.
- Badge URLs are fork-specific (`fjacquet/gramps-mcp`); merging upstream later
  requires updating them to `cabout-me/gramps-mcp` or removing them if the
  upstream repo doesn't want to adopt Codecov/this CI setup.
