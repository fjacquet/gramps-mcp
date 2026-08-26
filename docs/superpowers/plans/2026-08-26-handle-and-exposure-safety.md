# Handle and Exposure Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop a caller-supplied value from steering a request at an endpoint the tool never named, close the unauthenticated network exposure of the MCP server, and confine the one tool that reads local files.

**Architecture:** Three independent defects that share a threat model. The value that steers the URL comes from an LLM, which reads free text out of the genealogy tree and can be induced to compose a crafted argument; the MCP server that accepts that argument is published on every interface with no authentication; and one tool reads any local file the process can open. Each fix is small and local. Two of them are defence in depth for the same hole - encoding at the single chokepoint every URL parameter passes through, and validating at the model boundary so the caller gets a useful error - and the encoding is the load-bearing one, because it protects tools that do not exist yet.

**Tech Stack:** Python 3.13, pytest, `uv`, Docker Compose. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-26-mcp-audit-design.md` (findings B, C and G)

## Global Constraints

- Run everything through `uv`: `uv run pytest`, `uv run git commit`.
- TDD is mandatory: write the test, watch it fail for the right reason, then implement.
- Google-style docstrings on every function; `# Reason:` comments explain why, not what; no emojis anywhere, including commit messages.
- `uv run ruff format src tests`, `uv run ruff check src tests`, `uv run mypy src/gramps_mcp --ignore-missing-imports` must pass before each commit.
- No file over 500 lines, enforced across `src/` and `tests/`. `client.py` is 446 lines - Task 1 adds to it, so check the count before committing and split if it would cross.
- The offline suite is `uv run pytest -m "not integration" -q`, green at 311 passed.
- Never use `git stash` - forbidden in this repository, uncommitted work has been lost to it.
- **There is a live Gramps server holding the user's real genealogy research. Never issue a POST, PUT, PATCH or DELETE against it**, including to confirm a finding. Read-only GETs only where necessary.
- Do not edit `.env`, and never commit a `GRAMPS_API_URL` override.

## Facts established before this plan, do not re-derive

- `_build_url_with_substitution` (`src/gramps_mcp/client.py:297-327`) substitutes with `str.replace` and no encoding; `_build_url` (`client.py:73-78`) then passes the result to `urljoin`, which resolves `..` segments and treats `?` as a query separator. Reproduced: `handle="../users/someuser"` on `people/{handle}` yields `http://HOST/api/users/someuser`; `handle="."` yields the collection endpoint; `handle="abc?keys=x"` injects a query string.
- A crafted handle **cannot** change the host. `//evil.example.com/x` normalises onto the configured host. The blast radius is the whole Gramps API on that host, not a foreign server.
- `HANDLE_PATTERN = r"[0-9a-f]{16,}"` exists at `src/gramps_mcp/models/parameters/event_params.py:48` and is enforced only in `event_params.py` and `sourced_event_params.py`. Every `handle` field in `destructive_params.py` is a bare `str | None`.
- `docker-compose-sqllite.yml:65-66` publishes `"8000:8000"`, which binds every interface of the host. The `0.0.0.0` default inside the container is correct for Docker networking - the exposure comes from the publish, not from the application default.
- The MCP container declares **no volumes**, so media files reach it by `docker cp`, conventionally into `/tmp`. A containment root that excludes `/tmp` breaks the documented media workflow.
- `tools/media_upload.py:49-53` calls `os.path.isfile` (which follows symlinks) then `open(...).read()` with no root restriction and no size cap.

---

### Task 1: Percent-encode URL parameters at the chokepoint

Every dynamic endpoint's parameters pass through one function. Encoding there protects every tool, including ones not yet written.

**Files:**
- Modify: `src/gramps_mcp/client.py:73-78` and `:311-327`
- Test: `tests/test_client_url_building.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `_build_url_with_substitution(self, tree_id: str, endpoint: str, url_params: dict) -> str` - unchanged signature; the returned URL now always keeps the endpoint's own path shape.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_client_url_building.py`:

```python
"""
URL construction must keep a caller-supplied value inside its path segment.

The value that fills a {handle} placeholder is composed by an LLM, which
reads free text out of the tree and can be induced to craft one. These
tests pin that no such value can move the request to a different endpoint.
Pure string building - no server, no transport.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient


class TestUrlParameterEncoding:
    @pytest.mark.parametrize(
        "crafted",
        [
            "../users/someuser",
            "../metadata/",
            "..%2fusers",
            ".",
            "..",
            "a/../../../",
            "abc?keys=x",
            "abc#frag",
            "//evil.example.com/steal",
        ],
    )
    def test_a_crafted_handle_cannot_leave_its_endpoint(self, crafted):
        # Reason: str.replace plus urljoin resolved ".." and treated "?" as
        # a query separator, so delete_type(handle="../users/x") issued a
        # DELETE against /api/users/x while reporting it deleted a person.
        client = GrampsWebAPIClient()
        url = client._build_url_with_substitution(
            "default", "people/{handle}", {"handle": crafted}
        )
        assert "/api/people/" in url
        assert "/api/users" not in url
        assert "/api/metadata" not in url
        assert "?" not in url
        assert "#" not in url
        # Reason: the whole crafted value must sit in the single segment
        # after /api/people/, so nothing after that prefix may be a slash.
        tail = url.split("/api/people/", 1)[1]
        assert "/" not in tail

    def test_an_ordinary_handle_is_unchanged(self):
        client = GrampsWebAPIClient()
        url = client._build_url_with_substitution(
            "default", "people/{handle}", {"handle": "103bcbfa97824cbb051f1c7a28b"}
        )
        assert url.endswith("/api/people/103bcbfa97824cbb051f1c7a28b")

    def test_the_api_prefix_survives_an_endpoint_with_a_leading_slash(self):
        # Reason: urljoin discards the base path when the second argument
        # starts with "/", silently dropping the /api prefix.
        client = GrampsWebAPIClient()
        assert "/api/people/" in client._build_url("default", "/people/x")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_client_url_building.py -q`

Expected: the parametrised cases for `../users/someuser`, `../metadata/`, `.`, `..`, `a/../../../`, `abc?keys=x` and `abc#frag` FAIL. `test_an_ordinary_handle_is_unchanged` PASSES as a guard. `test_the_api_prefix_survives_an_endpoint_with_a_leading_slash` FAILS.

If a case passes that you expected to fail, say so in your report rather than adjusting the test - it means the behaviour differs from what was measured, and I need to know.

- [ ] **Step 3: Encode the substituted value**

In `src/gramps_mcp/client.py`, add to the imports at the top:

```python
from urllib.parse import quote
```

Then in `_build_url_with_substitution`, replace the substitution loop body:

```python
        for param_name, param_value in url_params.items():
            placeholder = f"{{{param_name}}}"
            if placeholder in substituted_endpoint:
                # Reason: the value filling this placeholder is composed by
                # an LLM that reads free text out of the tree, so it can be
                # induced to carry "../" or "?". Unencoded, urljoin resolved
                # those and aimed the request at an endpoint the tool never
                # named - delete_type(handle="../users/x") issued a DELETE
                # against /api/users/x and reported deleting a person.
                # safe="" encodes the separators too, so the value can only
                # ever be one path segment.
                substituted_endpoint = substituted_endpoint.replace(
                    placeholder, quote(str(param_value), safe="")
                )
```

- [ ] **Step 4: Stop urljoin from reinterpreting the endpoint**

Replace `_build_url` (`client.py:73-78`):

```python
    def _build_url(self, tree_id: str, endpoint: str) -> str:
        """
        Build the complete URL for an API endpoint.

        Args:
            tree_id (str): Family tree identifier. Unused - the tree is
                selected by the authentication token, not by the path.
            endpoint (str): Endpoint path, with any placeholders already
                substituted and encoded.

        Returns:
            str: The absolute URL.
        """
        # Reason: urljoin treats an endpoint starting with "/" as absolute
        # and discards the base's /api prefix, and it resolves ".." even
        # after encoding. Straight concatenation onto the normalised base
        # cannot do either.
        return self.base_url.rstrip("/") + "/" + endpoint.lstrip("/")
```

Remove the now-unused `from urllib.parse import urljoin` import if nothing else in the file uses it - grep before removing.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_client_url_building.py -q`

Expected: all pass.

- [ ] **Step 6: Run the full offline suite**

Run: `uv run pytest -m "not integration" -q`

Expected: 323 passed (311 before, 12 added). If any pre-existing test fails, do NOT adjust it before reporting - a test that depended on `urljoin` semantics is telling you something about a caller.

- [ ] **Step 7: Check the file length**

Run: `wc -l src/gramps_mcp/client.py`

Expected: under 500. It was 446 before this task.

- [ ] **Step 8: Commit**

```bash
uv run git add src/gramps_mcp/client.py tests/test_client_url_building.py
uv run git commit -m "fix: keep a caller-supplied URL parameter inside its path segment

The value filling a {handle} placeholder was substituted with str.replace
and no encoding, then handed to urljoin, which resolves \"..\" and treats
\"?\" as a query separator. delete_type(type=\"person\",
handle=\"../users/someuser\") issued a DELETE against /api/users/someuser
and reported deleting a person. The value is composed by an LLM that reads
free text out of the tree, so it is reachable."
```

---

### Task 2: Validate handle-shaped fields at the model boundary

Encoding stops the exploit; validation gives the caller a useful error and fails before a request is issued. `HANDLE_PATTERN` already exists and is already enforced on two models.

**Files:**
- Modify: `src/gramps_mcp/models/parameters/base_params.py` (add the shared validator)
- Modify: `src/gramps_mcp/models/parameters/destructive_params.py:55, 73, 84, 93, 102`
- Test: `tests/test_handle_validation.py` (create)

**Interfaces:**
- Consumes: `HANDLE_PATTERN` from `event_params.py:48`.
- Produces: `validate_handle_shape(value: str | None) -> str | None` in `base_params.py` - raises `ValueError` naming the field's expected shape, returns the value unchanged when it is None or matches.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_handle_validation.py`:

```python
"""
Handle-shaped fields on destructive tools must reject a non-handle.

A Gramps handle is lowercase hex, at least 16 characters. Anything else
reaching these fields is either a mistake worth naming or a crafted value
worth refusing, and these tools delete and merge records.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.destructive_params import (
    DeleteTypeParams,
    DetachReferenceParams,
    MergeTypeParams,
)


class TestDestructiveHandleValidation:
    @pytest.mark.parametrize(
        "crafted", ["../users/someuser", ".", "..", "abc?keys=x", "I0001", "short"]
    )
    def test_delete_type_refuses_a_non_handle(self, crafted):
        with pytest.raises(ValidationError):
            DeleteTypeParams(type="person", handle=crafted)

    def test_delete_type_accepts_a_real_handle(self):
        params = DeleteTypeParams(
            type="person", handle="103bcbfa97824cbb051f1c7a28b"
        )
        assert params.handle == "103bcbfa97824cbb051f1c7a28b"

    def test_delete_type_still_accepts_a_gramps_id_instead(self):
        # Reason: handle and gramps_id are alternatives; tightening one
        # must not make the other unusable.
        params = DeleteTypeParams(type="person", gramps_id="I0001")
        assert params.handle is None

    @pytest.mark.parametrize("crafted", ["../users/someuser", "."])
    def test_detach_reference_refuses_a_non_handle(self, crafted):
        with pytest.raises(ValidationError):
            DetachReferenceParams(
                type="person",
                handle=crafted,
                list_name="media_list",
                ref_handle="103bcbfa97824cbb051f1c7a28b",
            )

    @pytest.mark.parametrize("crafted", ["../users/someuser", "."])
    def test_detach_reference_refuses_a_non_handle_ref(self, crafted):
        with pytest.raises(ValidationError):
            DetachReferenceParams(
                type="person",
                handle="103bcbfa97824cbb051f1c7a28b",
                list_name="media_list",
                ref_handle=crafted,
            )

    @pytest.mark.parametrize("crafted", ["../users/someuser", "."])
    def test_merge_type_refuses_a_non_handle_on_either_side(self, crafted):
        with pytest.raises(ValidationError):
            MergeTypeParams(
                type="person",
                phoenix_handle=crafted,
                titanic_handle="103bcbfa97824cbb051f1c7a28b",
            )
        with pytest.raises(ValidationError):
            MergeTypeParams(
                type="person",
                phoenix_handle="103bcbfa97824cbb051f1c7a28b",
                titanic_handle=crafted,
            )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_handle_validation.py -q`

Expected: every `refuses` case FAILS (no validation today). The three `accepts` cases PASS as guards.

Before writing the implementation, run `uv run python -c "from src.gramps_mcp.models.parameters.destructive_params import MergeTypeParams; print(MergeTypeParams.model_fields.keys())"` and confirm the field names in the tests match the model. If a name differs, fix the TEST to match the model and say so - the model is the truth.

- [ ] **Step 3: Add the shared validator**

In `src/gramps_mcp/models/parameters/base_params.py`, add near the top-level helpers:

```python
def validate_handle_shape(value: str | None) -> str | None:
    """
    Reject a value that is not shaped like a Gramps handle.

    Args:
        value (str | None): The candidate handle, or None when the field
            is optional and unset.

    Returns:
        str | None: The value unchanged when it is None or well-shaped.

    Raises:
        ValueError: When the value is present and not lowercase hex of at
            least 16 characters.
    """
    # Reason: a handle lands in a URL path segment. Encoding in the client
    # already stops a crafted value from leaving its segment, but refusing
    # it here fails before any request is issued and names the problem,
    # rather than 404ing against an endpoint the caller never meant to hit.
    if value is not None and not re.fullmatch(HANDLE_PATTERN, value):
        raise ValueError(
            f"'{value}' is not a Gramps handle. A handle is lowercase hex, "
            "at least 16 characters, as returned by a find or get call. To "
            "identify a record by its Gramps ID instead, use the gramps_id "
            "field."
        )
    return value
```

Add `import re` at the top of `base_params.py`.

**`HANDLE_PATTERN` must move.** `event_params.py:33` already imports from `base_params.py`, so importing the constant the other way would be circular - this was checked, do not re-derive it. Move the `HANDLE_PATTERN = r"[0-9a-f]{16,}"` definition into `base_params.py`, and in `event_params.py` replace the definition with `from .base_params import HANDLE_PATTERN`. That keeps `event_params.HANDLE_PATTERN` resolvable, which matters because `sourced_event_params.py:30` imports it from there.

- [ ] **Step 4: Apply it to the destructive models**

In `src/gramps_mcp/models/parameters/destructive_params.py`, add a `field_validator` to each model carrying a handle-shaped field - `DeleteTypeParams.handle`, `DetachReferenceParams.handle` and `.ref_handle`, `MergeTypeParams.phoenix_handle` and `.titanic_handle`:

```python
    @field_validator("handle")
    @classmethod
    def _check_handle_shape(cls, value: str | None) -> str | None:
        """Reject a handle that is not shaped like a Gramps handle."""
        return validate_handle_shape(value)
```

Use one validator per model listing all of that model's handle fields in the decorator, rather than one per field. Import `field_validator` from `pydantic` and `validate_handle_shape` from `.base_params`.

**Do NOT touch `phoenix_father_handle` / `phoenix_mother_handle`** (`destructive_params.py:119-142`) in this task. Confirm from the model's own description whether those accept a handle or something else before constraining them; if they are handles, note it in your report as a follow-up rather than widening this task.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_handle_validation.py -q`

Expected: all pass.

- [ ] **Step 6: Run the full offline suite**

Run: `uv run pytest -m "not integration" -q`

Expected: 334 passed (323 after Task 1, 11 added). A pre-existing test that now fails is likely passing a fake handle - report it, do not silently loosen the validator.

- [ ] **Step 7: Commit**

```bash
uv run git add src/gramps_mcp/models/parameters/ tests/test_handle_validation.py
uv run git commit -m "fix: refuse a non-handle on the destructive tools

HANDLE_PATTERN existed but was enforced only on the event models, so
handle on delete_type, detach_reference and merge_type was a bare str.
Encoding in the client stops a crafted value from leaving its path
segment; this refuses it before a request is issued and names the fix."
```

---

### Task 3: Stop publishing the MCP server on every interface

**Files:**
- Modify: `docker-compose-sqllite.yml:65-66`
- Modify: `docker-compose-pgsql.yml`, `docker-compose.yml`, `docker-compose.dev.yml` - the same `"8000:8000"` publish. These four are the complete list; `docker-compose-homelab.yml` does not publish the MCP port and must not be touched.
- Modify: `docs/user-guide/` - the page describing deployment, or `README.md` if none covers it
- Test: none. This is configuration; a test would assert Docker's behaviour, not the project's.

**Interfaces:**
- Consumes: nothing.
- Produces: nothing later tasks rely on.

- [ ] **Step 1: Confirm the current exposure**

Run: `rtk docker ps --format "{{.Names}}\t{{.Ports}}" | grep mcp`

Record the output in your report. Expect a mapping like `0.0.0.0:8000->8000/tcp`, which means every interface of the host.

- [ ] **Step 2: Bind the published port to the loopback interface**

In `docker-compose-sqllite.yml`, change:

```yaml
    ports:
      - "8000:8000"
```

to:

```yaml
    ports:
      # Reason: every tool in the registry - including delete_type,
      # merge_type and manage_users - is reachable by anyone who can open
      # this port, with the server's own owner-role Gramps credentials,
      # and the MCP server performs no authentication of its own. Bind the
      # publish to the loopback interface; to reach it from elsewhere, put
      # an authenticating reverse proxy in front rather than widening this.
      - "127.0.0.1:8000:8000"
```

Apply the same change to the other three compose files listed above. Verify the list is still complete with `rtk grep -ln "8000:8000" docker-compose*.yml` before you start. **Leave `GRAMPS_MCP_HOST` alone** - `0.0.0.0` inside the container is correct for Docker's network namespace, and changing the application default would break the container while doing nothing about the publish.

- [ ] **Step 3: Document it where a deployer will look**

Add a short section to the deployment documentation stating that the MCP server has no authentication of its own, that its port must not be published to an untrusted network, and that an authenticating reverse proxy is the way to expose it deliberately. Find the right page with `rtk grep -rn "8000" docs/ README.md` and put it where deployment is already discussed.

- [ ] **Step 4: Verify the docs build**

Run: `uv run --with mkdocs-material mkdocs build --strict`

Expected: no errors.

- [ ] **Step 5: Verify the compose files still parse**

Run: `docker compose -f docker-compose-sqllite.yml config > /dev/null && echo ok`

Expected: `ok`. Do NOT run `docker compose up` or restart anything - the running container is serving the user's production tree, and restarting it is the user's call, not yours.

- [ ] **Step 6: Commit**

```bash
uv run git add docker-compose-*.yml docs README.md
uv run git commit -m "fix: publish the MCP port on loopback only

The compose files published 8000 on every interface of the host. The MCP
server performs no authentication of its own and stateless_http means
there is not even a session, so anyone able to open that port drove
delete_type, merge_type and manage_users with the server's owner-role
credentials. GRAMPS_MCP_HOST stays 0.0.0.0 - that is correct inside the
container's network namespace; the exposure was the publish."
```

---

### Task 4: Confine what media_path may read

**Files:**
- Modify: `src/gramps_mcp/tools/media_upload.py:49-53`
- Modify: `src/gramps_mcp/config.py` (add the root setting)
- Modify: `.env.example` (document the new variable)
- Test: `tests/test_media_path_containment.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `Settings.gramps_media_import_root: str` - the directory `media_path` values must resolve inside, defaulting to `/tmp`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_media_path_containment.py`:

```python
"""
media_path must not read outside the configured import root.

The tool opens a local path named by the caller and uploads its bytes
into the tree, where the media API can read them back. Unconfined, that
turns any file the server process can open - including its own .env,
which holds owner-role credentials - into tree content.
"""

import os

import pytest

from src.gramps_mcp.tools.media_upload import resolve_media_path


class TestMediaPathContainment:
    def test_a_path_inside_the_root_resolves(self, tmp_path):
        target = tmp_path / "scan.jpg"
        target.write_bytes(b"x")
        assert resolve_media_path(str(target), str(tmp_path)) == str(target.resolve())

    def test_a_path_outside_the_root_is_refused(self, tmp_path):
        outside = tmp_path.parent / "outside.txt"
        outside.write_bytes(b"x")
        with pytest.raises(ValueError) as exc:
            resolve_media_path(str(outside), str(tmp_path))
        assert "import root" in str(exc.value)

    def test_a_traversal_out_of_the_root_is_refused(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_media_path(str(tmp_path / ".." / "etc" / "passwd"), str(tmp_path))

    def test_a_symlink_pointing_out_of_the_root_is_refused(self, tmp_path):
        # Reason: os.path.isfile follows symlinks, so a link inside the
        # root pointing at /app/.env passed the old check.
        outside = tmp_path.parent / "secret.txt"
        outside.write_bytes(b"x")
        link = tmp_path / "innocent.jpg"
        os.symlink(outside, link)
        with pytest.raises(ValueError):
            resolve_media_path(str(link), str(tmp_path))

    def test_a_missing_file_still_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_media_path(str(tmp_path / "absent.jpg"), str(tmp_path))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_media_path_containment.py -q`

Expected: all FAIL with `ImportError` - `resolve_media_path` does not exist. That is a collection error, not a test failure; fix it by writing the function in Step 3, then re-run and confirm the assertions themselves fail before the containment logic is right.

- [ ] **Step 3: Add the setting**

In `src/gramps_mcp/config.py`, beside the other fields:

```python
    gramps_media_import_root: str = Field(
        "/tmp",
        description=(
            "Directory that media_path values must resolve inside. The MCP "
            "container has no host mount, so files arrive by docker cp, "
            "conventionally into /tmp."
        ),
    )
```

and in the loader beside the other `os.environ.get` calls:

```python
            gramps_media_import_root=os.environ.get(
                "GRAMPS_MEDIA_IMPORT_ROOT", "/tmp"
            ),
```

Add the variable to `.env.example` with a one-line comment.

- [ ] **Step 4: Write the containment helper**

In `src/gramps_mcp/tools/media_upload.py`:

```python
def resolve_media_path(file_location: str, import_root: str) -> str:
    """
    Resolve a caller-supplied media path, refusing anything outside the root.

    Args:
        file_location (str): The path the caller asked to upload.
        import_root (str): Directory the path must resolve inside.

    Returns:
        str: The fully resolved path, safe to open.

    Raises:
        FileNotFoundError: When no regular file exists at the path.
        ValueError: When the resolved path lies outside import_root.
    """
    # Reason: realpath resolves symlinks and ".." before the comparison.
    # os.path.isfile alone followed a symlink, so a link inside the root
    # pointing at the server's own .env passed the old check - and the
    # file's bytes then became tree content readable through the media API.
    resolved = os.path.realpath(file_location)
    root = os.path.realpath(import_root)
    if os.path.commonpath([resolved, root]) != root:
        raise ValueError(
            f"'{file_location}' resolves outside the media import root "
            f"({root}). Copy the file into that directory first."
        )
    if not os.path.isfile(resolved):
        raise FileNotFoundError(f"File not found: {file_location}")
    return resolved
```

Note the order: containment is checked BEFORE existence, so a refused path does not leak whether a file exists outside the root.

- [ ] **Step 5: Use it, and bound the read**

In the upload function, replace the `os.path.isfile` check and the `open` with:

```python
    settings = get_settings()
    resolved = resolve_media_path(file_location, settings.gramps_media_import_root)

    # Reason: the whole file is read into memory before upload, so an
    # unbounded read is a denial of service on the MCP process.
    size = os.path.getsize(resolved)
    if size > MAX_MEDIA_BYTES:
        raise ValueError(
            f"'{file_location}' is {size} bytes, over the "
            f"{MAX_MEDIA_BYTES}-byte upload limit."
        )

    with open(resolved, "rb") as f:
        file_content = f.read()
    mime_type, _ = mimetypes.guess_type(resolved)
```

Define `MAX_MEDIA_BYTES = 100 * 1024 * 1024` as a module constant with a `# Reason:` naming why the bound exists. Import `get_settings` from `..config`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_media_path_containment.py -q`

Expected: all pass.

- [ ] **Step 7: Run the full offline suite**

Run: `uv run pytest -m "not integration" -q`

Expected: 339 passed (334 after Task 2, 5 added). **A pre-existing media test that now fails is a real signal**: it means an existing test or fixture uploads from outside `/tmp`. Report it with the path it uses rather than widening the root to accommodate it.

- [ ] **Step 8: Document the workflow**

The existing media workflow copies files into the container with `docker cp`. Find where that is documented (`rtk grep -rn "docker cp" docs/ README.md .claude/`) and add one sentence stating that the destination must be inside `GRAMPS_MEDIA_IMPORT_ROOT`, which defaults to `/tmp`. If it is documented only in a skill under `.claude/`, update that too.

- [ ] **Step 9: Commit**

```bash
uv run git add src/gramps_mcp tests/test_media_path_containment.py .env.example docs README.md
uv run git commit -m "fix: confine media_path to a configured import root

The tool opened any path the caller named and uploaded its bytes into the
tree, where the media API reads them back - so /app/.env, which holds
owner-role credentials, was retrievable as tree content. os.path.isfile
also followed symlinks. Paths now resolve with realpath and must land
inside GRAMPS_MEDIA_IMPORT_ROOT, and the read is bounded."
```

---

## Self-Review

**Spec coverage.** Finding B is closed by Tasks 1 and 2 - encoding at the chokepoint stops the exploit, validation at the boundary gives a useful error. Finding C is closed by Task 3, though not the way the spec proposed: the spec said to change the application's bind default, which would break the container without touching the publish that actually exposes the port. That deviation is deliberate and recorded here. Finding G is closed by Task 4.

Finding D from the spec - `replace_lists` accepted over stdio and rejected over streamable-http - is **not** in this plan. It is a coherence defect, not a safety one, and folding it in would mix a behaviour decision (which tools should accept the field) into a security change. It stays for a later plan.

**Placeholders.** None. Every code step carries the code; every run step carries the command and its expected output.

**Type consistency.** `validate_handle_shape(value: str | None) -> str | None` is defined in Task 2 and used only there. `resolve_media_path(file_location: str, import_root: str) -> str` is defined in Task 4 and used only there. `HANDLE_PATTERN` is consumed from `event_params.py` unless the circular-import check in Task 2 Step 3 moves it - which is why that step requires the implementer to state which they did.

**Two risks worth naming.**

Task 1 changes URL construction for every call in the system. The offline suite is the safety net, but any test that relied on `urljoin` collapsing a path will break - which is why Step 6 says to report such a failure rather than adjust it.

Task 4 can break the existing media workflow if files are copied somewhere other than `/tmp`. The root is configurable precisely so the user can point it at their actual staging directory, and Step 7 treats a failing pre-existing media test as a signal rather than an obstacle.
