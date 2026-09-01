---
name: release-checklist
description: Cut a release of gramps-mcp — bump version, update the lockfile, verify CI stays green, tag. Use only when the user explicitly asks to release/publish/cut a version, never automatically.
disable-model-invocation: true
---

# Release Checklist

`gramps-mcp`'s CI runs `uv sync --locked`, and the Docker publish step is a
separate pipeline from the test suite. A version bump without `uv lock` in
the same commit turns `main` red on the next `uv sync --locked` while the
Docker image keeps publishing — the breakage is invisible from the release
page itself. Follow this order every time; don't split it across commits.

## Steps

1. **Confirm the version bump.** Ask the user for the target version if not
   given (semver — check `pyproject.toml`'s current `version` first).

2. **Bump both files in the same edit pass:**
   - `pyproject.toml` → `[project] version = "X.Y.Z"`
   - `src/gramps_mcp/__init__.py` → wherever `__version__` is defined

3. **Regenerate the lockfile:**
   ```bash
   uv lock
   ```
   This must be staged in the *same commit* as the version bump. `uv.lock`
   pins this project's own version; a mismatch is what CI's
   `uv sync --locked` rejects.

4. **Run the full local check before committing** — don't rely on CI to
   catch what a local run would:
   ```bash
   uv run ruff check src/ tests/
   uv run ruff format --check src/ tests/
   uv run mypy src/gramps_mcp --ignore-missing-imports
   uv run pytest -m "not integration"
   ```

5. **Commit** with both files (`pyproject.toml`, `__init__.py`) and
   `uv.lock` staged together. Do not amend a prior commit to add a
   forgotten `uv lock` — that's exactly the failure mode this checklist
   exists to prevent; make a new commit if something was missed.

6. **Push and confirm CI is green** before telling the user the release is
   done. If `uv sync --locked` fails in CI despite step 3, the lockfile
   wasn't actually regenerated against the bumped `pyproject.toml` — redo
   step 3, don't patch around it.

7. **Docs site**: if anything under `docs/` changed as part of this release,
   `uv run --with mkdocs-material mkdocs build --strict` before pushing —
   strict mode is the only thing that catches a broken internal link before
   the published site does.

8. **Tag/PR** per the user's usual flow (this repo is a fork — `gh pr
   create` needs `--repo fjacquet/gramps-mcp` explicitly, and merges use
   `--merge`, never `--squash`, per the project's own `CLAUDE.md`).
