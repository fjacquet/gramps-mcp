# manage_users MCP Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `manage_users` MCP tool that lists Gramps Web users, fetches one, and creates batches of accounts with randomly generated passwords and an assigned role.

**Architecture:** One self-contained module, `src/gramps_mcp/tools/user_tools.py`, holding the Pydantic schema, the handler and the output formatting. Four entries are added to the `ApiCalls` enum; the existing `GrampsWebAPIClient` plumbing needs no change because `_build_url` ignores `tree_id` and the `users/` endpoints are not tree-scoped. The tool is registered in `TOOL_REGISTRY` in `server.py`.

**Tech Stack:** Python 3.13, pydantic v2, httpx, MCP Python SDK, pytest + pytest-asyncio, uv, ruff.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-08-11-user-management-tool-design.md`.
- Every command runs through uv: `uv run pytest`, `uv run git commit`.
- No mocks, no fixtures, no test clients. Tests hit the live Gramps Web server configured in `.env`.
- Never create a file longer than 500 lines. A pre-commit hook enforces this.
- No emojis anywhere in the code. A pre-commit hook enforces this.
- Google-style docstrings on every function.
- Every new Python file starts with the project's AGPL copyright header, copied verbatim from `src/gramps_mcp/tools/records_tools.py` lines 1-15. A pre-commit hook enforces this.
- Roles exposed by the tool: `guest` (0), `member` (1), `contributor` (2), `editor` (3). `owner` (4) and `admin` (5) must be unreachable.
- Batch limit: 50 users per `create` call.
- The `.env` account must be `owner` or `admin` for `create` to work. It currently is (`role: 4`).
- Work happens on the branch `feat/manage-users-tool`, which already exists and holds the spec commit.

---

### Task 1: Schema and API endpoints

Adds the `ApiCalls` entries and the parameter models, including the role
ceiling. No network behavior yet — this task is testable entirely offline,
which is why it stands alone.

**Files:**
- Create: `src/gramps_mcp/tools/user_tools.py`
- Modify: `src/gramps_mcp/models/api_calls.py` (append a block before the `@property` definitions at the end of the class)
- Test: `tests/test_user_tools.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `ApiCalls.GET_USERS`, `ApiCalls.GET_USER`, `ApiCalls.POST_USER`, `ApiCalls.DELETE_USER`
  - `ROLE_IDS: dict[str, int]`
  - `class NewUser(BaseModel)` with fields `name: str`, `email: str`, `full_name: str`, `role: str`
  - `class UserCreateBody(BaseModel)` with fields `email: str`, `full_name: str`, `password: str`, `role: int`
  - `class ManageUsersParams(BaseModel)` with fields `action: str`, `name: str | None`, `users: list[NewUser] | None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_user_tools.py`:

```python
"""
Integration tests for the user management tool using the real Gramps API.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools.user_tools import ManageUsersParams, NewUser


class TestUserSchema:
    """Schema-level tests. These make no network calls."""

    def test_role_ceiling_rejects_owner(self):
        with pytest.raises(ValidationError):
            NewUser(name="someone", email="a@b.fr", role="owner")

    def test_role_ceiling_rejects_admin(self):
        with pytest.raises(ValidationError):
            NewUser(name="someone", email="a@b.fr", role="admin")

    def test_editor_is_allowed(self):
        user = NewUser(name="someone", email="a@b.fr", role="editor")
        assert user.role == "editor"

    def test_role_defaults_to_member(self):
        user = NewUser(name="someone", email="a@b.fr")
        assert user.role == "member"

    def test_rejects_malformed_email(self):
        with pytest.raises(ValidationError):
            NewUser(name="someone", email="not-an-email")

    def test_rejects_malformed_username(self):
        with pytest.raises(ValidationError):
            NewUser(name="bad name with spaces", email="a@b.fr")

    def test_rejects_batch_over_fifty(self):
        users = [{"name": f"u{i}", "email": f"u{i}@b.fr"} for i in range(51)]
        with pytest.raises(ValidationError):
            ManageUsersParams(action="create", users=users)

    def test_rejects_unknown_action(self):
        with pytest.raises(ValidationError):
            ManageUsersParams(action="delete", name="someone")


class TestApiCalls:
    """The endpoints the tool relies on exist and are not tree-scoped."""

    def test_user_endpoints_defined(self):
        assert ApiCalls.GET_USERS.value == ("GET", "users/")
        assert ApiCalls.GET_USER.value == ("GET", "users/{name}/")
        assert ApiCalls.POST_USER.value == ("POST", "users/{name}/")
        assert ApiCalls.DELETE_USER.value == ("DELETE", "users/{name}/")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_user_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.gramps_mcp.tools.user_tools'`

- [ ] **Step 3: Add the API endpoints**

In `src/gramps_mcp/models/api_calls.py`, insert this block immediately after the `# TREES operations` block and before the `@property` definitions:

```python
    # USER operations (not tree-scoped - the tree comes from the JWT)
    GET_USERS = ("GET", "users/")
    GET_USER = ("GET", "users/{name}/")
    POST_USER = ("POST", "users/{name}/")
    # Reason: DELETE is defined for test cleanup only. It is deliberately not
    # reachable through any manage_users action - see the design spec.
    DELETE_USER = ("DELETE", "users/{name}/")
```

- [ ] **Step 4: Write the module with its schema**

Create `src/gramps_mcp/tools/user_tools.py`. Start with the 15-line AGPL header copied verbatim from `src/gramps_mcp/tools/records_tools.py`, then:

```python
"""
User management MCP tool for Gramps Web accounts.

Self-contained by design: schema, handler and output formatting live here
rather than being split across models/, handlers/ and tools/. The tool is
small enough that the split would cost more than it buys.
"""

import logging
import secrets
from typing import Literal

from mcp.types import TextContent
from pydantic import BaseModel, Field

from ..client import GrampsAPIError
from ..config import get_settings
from ..models.api_calls import ApiCalls
from .search_basic import with_client

logger = logging.getLogger(__name__)

# Role IDs from gramps_webapi/auth/const.py. owner (4) and admin (5) are
# deliberately absent: this tool must not be able to grant them.
ROLE_IDS = {"guest": 0, "member": 1, "contributor": 2, "editor": 3}

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{2,64}$"
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# 16 bytes, about 128 bits of entropy, URL-safe so it survives copy-paste.
PASSWORD_BYTES = 16

MAX_BATCH = 50


class NewUser(BaseModel):
    """One account to create."""

    name: str = Field(..., pattern=USERNAME_PATTERN)
    email: str = Field(..., pattern=EMAIL_PATTERN)
    full_name: str = ""
    role: Literal["guest", "member", "contributor", "editor"] = "member"


class UserCreateBody(BaseModel):
    """Request body for POST /users/{name}/."""

    email: str
    full_name: str
    password: str
    role: int


class ManageUsersParams(BaseModel):
    """Parameters for the manage_users tool."""

    action: Literal["list", "get", "create"]
    name: str | None = None
    users: list[NewUser] | None = Field(default=None, max_length=MAX_BATCH)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_user_tools.py -v`
Expected: PASS, 10 tests.

- [ ] **Step 6: Commit**

```bash
rtk git add src/gramps_mcp/models/api_calls.py src/gramps_mcp/tools/user_tools.py tests/test_user_tools.py
uv run git commit -m "feat: add user endpoints and manage_users schema"
```

---

### Task 2: The `list` and `get` actions

Read-only actions, exercised against the live server.

**Files:**
- Modify: `src/gramps_mcp/tools/user_tools.py`
- Test: `tests/test_user_tools.py`

**Interfaces:**
- Consumes: `ManageUsersParams`, `NewUser`, `ROLE_IDS`, `ApiCalls.GET_USERS`, `ApiCalls.GET_USER` from Task 1.
- Produces:
  - `async def manage_users_tool(arguments: dict) -> list[TextContent]` — note the `with_client` decorator injects `client` as the first positional argument, so callers pass only `arguments`
  - `def _format_error_response(error: Exception, operation: str) -> list[TextContent]`
  - `def _format_user_rows(users: list[dict]) -> str`
  - `def _role_name(role_id: int) -> str`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_user_tools.py`:

```python
class TestListAndGet:
    """Live-server tests for the read-only actions."""

    @pytest.mark.asyncio
    async def test_list_users(self):
        result = await manage_users_tool({"action": "list"})
        text = result[0].text
        assert "error" not in text.lower()
        # The account from .env must appear in its own instance's user list.
        assert get_settings().gramps_username in text

    @pytest.mark.asyncio
    async def test_get_user(self):
        username = get_settings().gramps_username
        result = await manage_users_tool({"action": "get", "name": username})
        text = result[0].text
        assert "error" not in text.lower()
        assert username in text

    @pytest.mark.asyncio
    async def test_get_without_name_returns_error(self):
        result = await manage_users_tool({"action": "get"})
        assert "error" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_invalid_action_returns_error(self):
        result = await manage_users_tool({"action": "destroy"})
        assert "error" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_owner_role_returns_error_not_raise(self):
        result = await manage_users_tool(
            {
                "action": "create",
                "users": [{"name": "nope", "email": "a@b.fr", "role": "owner"}],
            }
        )
        assert "error" in result[0].text.lower()
```

Add to the imports at the top of the test file:

```python
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.tools.user_tools import manage_users_tool
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_user_tools.py::TestListAndGet -v`
Expected: FAIL — `ImportError: cannot import name 'manage_users_tool'`

- [ ] **Step 3: Implement the handler with `list` and `get`**

Append to `src/gramps_mcp/tools/user_tools.py`:

```python
def _format_error_response(error: Exception, operation: str) -> list[TextContent]:
    """
    Format an exception into a user-friendly MCP response.

    Args:
        error (Exception): The exception to report.
        operation (str): Name of the operation that failed.

    Returns:
        list[TextContent]: Single-element error response.
    """
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"

    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


def _role_name(role_id: int) -> str:
    """
    Convert a Gramps Web role ID to its name.

    Args:
        role_id (int): Numeric role from the API.

    Returns:
        str: Role name, or the raw ID as a string if unknown.
    """
    # Reason: owner/admin/disabled are absent from ROLE_IDS because the tool
    # cannot grant them, but existing accounts hold them and must display.
    by_id = {value: key for key, value in ROLE_IDS.items()}
    by_id.update({4: "owner", 5: "admin", -1: "disabled", -2: "unconfirmed"})
    return by_id.get(role_id, str(role_id))


def _format_user_rows(users: list[dict]) -> str:
    """
    Format user objects as aligned text rows.

    Args:
        users (list[dict]): User objects from the API.

    Returns:
        str: One row per user: name, e-mail, full name, role.
    """
    if not users:
        return "No users found."

    rows = []
    for user in users:
        rows.append(
            f"{user.get('name', '-'):<20} "
            f"{user.get('email', '-'):<30} "
            f"{user.get('full_name', '-'):<25} "
            f"{_role_name(user.get('role', -99))}"
        )
    return "\n".join(rows)


@with_client
async def manage_users_tool(client, arguments: dict) -> list[TextContent]:
    """
    List, get, or create Gramps Web user accounts.

    Args:
        client (GrampsWebAPIClient): Injected by the with_client decorator.
        arguments (dict): Raw tool arguments, validated against
            ManageUsersParams.

    Returns:
        list[TextContent]: Formatted result, or an error message.
    """
    try:
        params = ManageUsersParams(**arguments)
        tree_id = get_settings().gramps_tree_id

        if params.action == "list":
            result = await client.make_api_call(
                api_call=ApiCalls.GET_USERS, params=None, tree_id=tree_id
            )
            formatted = _format_user_rows(result if isinstance(result, list) else [])

        elif params.action == "get":
            if not params.name:
                raise ValueError("name is required for action 'get'")
            result = await client.make_api_call(
                api_call=ApiCalls.GET_USER,
                params=None,
                tree_id=tree_id,
                name=params.name,
            )
            formatted = _format_user_rows([result] if result else [])

        else:
            raise ValueError(f"Unsupported action: {params.action}")

        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, f"manage_users({arguments.get('action')})")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_user_tools.py -v`
Expected: PASS, 15 tests. Requires the live server; a connection error here means the server is down, not that the code is wrong.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/tools/user_tools.py tests/test_user_tools.py
uv run git commit -m "feat: add list and get actions to manage_users"
```

---

### Task 3: The `create` action

The only action that writes. Generates passwords, skips accounts that already
exist, and reports per-user outcomes without aborting the batch.

**Files:**
- Modify: `src/gramps_mcp/tools/user_tools.py`
- Test: `tests/test_user_tools.py`

**Interfaces:**
- Consumes: everything from Tasks 1 and 2.
- Produces:
  - `async def _existing_usernames(client, tree_id: str) -> set[str]`
  - `async def _create_one(client, tree_id: str, user: NewUser) -> tuple[str, str]` returning `(status, detail)` where status is `"created"`, `"skipped"` or `"failed"` and detail is the password for `"created"`, a reason otherwise

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_user_tools.py`:

```python
class TestCreate:
    """Live-server tests for the writing action."""

    @pytest.mark.asyncio
    async def test_create_without_users_returns_error(self):
        result = await manage_users_tool({"action": "create"})
        assert "error" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_create_skips_existing_user(self):
        username = get_settings().gramps_username
        result = await manage_users_tool(
            {
                "action": "create",
                "users": [{"name": username, "email": "someone@example.org"}],
            }
        )
        text = result[0].text
        assert "skipped" in text.lower()
        assert "created 0" in text.lower()

    @pytest.mark.asyncio
    async def test_create_then_delete(self):
        name = f"pytest_{uuid.uuid4().hex[:8]}"
        client = GrampsWebAPIClient()
        try:
            result = await manage_users_tool(
                {
                    "action": "create",
                    "users": [
                        {
                            "name": name,
                            "email": f"{name}@example.org",
                            "full_name": "Pytest Account",
                            "role": "guest",
                        }
                    ],
                }
            )
            text = result[0].text
            assert "created 1" in text.lower()
            assert name in text

            listed = await manage_users_tool({"action": "list"})
            assert name in listed[0].text
        finally:
            # Reason: DELETE is not a tool action, so cleanup goes straight
            # through the client.
            await client.make_api_call(
                api_call=ApiCalls.DELETE_USER,
                params=None,
                tree_id=get_settings().gramps_tree_id,
                name=name,
            )
            await client.close()
```

Add to the test file imports:

```python
import uuid

from src.gramps_mcp.client import GrampsWebAPIClient
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_user_tools.py::TestCreate -v`
Expected: FAIL — `test_create_without_users_returns_error` passes by accident (the `else` branch rejects it), the other two fail because `create` is not implemented.

- [ ] **Step 3: Implement `create`**

Add these two helpers to `src/gramps_mcp/tools/user_tools.py`, above `manage_users_tool`:

```python
async def _existing_usernames(client, tree_id: str) -> set[str]:
    """
    Fetch the set of usernames already registered on the instance.

    Args:
        client (GrampsWebAPIClient): Client to use.
        tree_id (str): Family tree identifier.

    Returns:
        set[str]: Existing usernames.
    """
    # Reason: one list call up front, rather than reading a 409 back off each
    # POST. _format_http_error flattens every status into prose, so "already
    # exists" and a real server fault would otherwise be indistinguishable.
    result = await client.make_api_call(
        api_call=ApiCalls.GET_USERS, params=None, tree_id=tree_id
    )
    if not isinstance(result, list):
        return set()
    return {user.get("name", "") for user in result}


async def _create_one(client, tree_id: str, user: NewUser) -> tuple[str, str]:
    """
    Create a single account with a generated password.

    Args:
        client (GrampsWebAPIClient): Client to use.
        tree_id (str): Family tree identifier.
        user (NewUser): Account to create.

    Returns:
        tuple[str, str]: ("created", password) or ("failed", reason).
    """
    password = secrets.token_urlsafe(PASSWORD_BYTES)
    body = UserCreateBody(
        email=user.email,
        full_name=user.full_name or user.name,
        password=password,
        role=ROLE_IDS[user.role],
    )
    try:
        await client.make_api_call(
            api_call=ApiCalls.POST_USER,
            params=body,
            tree_id=tree_id,
            name=user.name,
        )
    except GrampsAPIError as e:
        message = str(e)
        if "Permission denied" in message:
            message = (
                "Permission denied - the account in .env must have the "
                "owner or admin role to create users"
            )
        return "failed", message
    return "created", password
```

Then replace the `else: raise ValueError(...)` branch of `manage_users_tool` with:

```python
        elif params.action == "create":
            if not params.users:
                raise ValueError("users is required for action 'create'")

            existing = await _existing_usernames(client, tree_id)
            rows: list[str] = []
            counts = {"created": 0, "skipped": 0, "failed": 0}

            # Reason: sequential on purpose. Parallel writes against one
            # Gramps Web worker invite rate-limiting and interleave partial
            # failures that are hard to read back.
            for user in params.users:
                if user.name in existing:
                    status, detail = "skipped", "already exists"
                else:
                    status, detail = await _create_one(client, tree_id, user)
                counts[status] += 1
                if status == "created":
                    rows.append(
                        f"{user.name:<20} {user.email:<30} "
                        f"{user.role:<12} {detail}"
                    )
                else:
                    rows.append(f"{user.name:<20} {status}: {detail}")

            header = (
                f"Created {counts['created']}, skipped {counts['skipped']}, "
                f"failed {counts['failed']}"
            )
            formatted = header + "\n\n" + "\n".join(rows)

        else:
            raise ValueError(f"Unsupported action: {params.action}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_user_tools.py -v`
Expected: PASS, 18 tests.

- [ ] **Step 5: Verify the account was really removed**

Run: `uv run pytest tests/test_user_tools.py::TestListAndGet::test_list_users -v -s`
Expected: PASS, and no `pytest_*` account appears in the printed list. If one lingers, the cleanup in `finally` did not run — fix that before continuing.

- [ ] **Step 6: Commit**

```bash
rtk git add src/gramps_mcp/tools/user_tools.py tests/test_user_tools.py
uv run git commit -m "feat: add create action to manage_users"
```

---

### Task 4: Register the tool

**Files:**
- Modify: `src/gramps_mcp/server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `manage_users_tool`, `ManageUsersParams` from Tasks 1-3.
- Produces: the `"manage_users"` key in `TOOL_REGISTRY`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_server.py`:

```python
def test_manage_users_registered():
    from src.gramps_mcp.server import TOOL_REGISTRY

    assert "manage_users" in TOOL_REGISTRY
    entry = TOOL_REGISTRY["manage_users"]
    schema = entry["schema"].model_json_schema()
    # The role ceiling must be visible in the advertised schema, so a caller
    # knows owner/admin are impossible before trying.
    assert "owner" not in str(schema["$defs"]["NewUser"]["properties"]["role"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py::test_manage_users_registered -v`
Expected: FAIL — `AssertionError: assert 'manage_users' in {...}`

- [ ] **Step 3: Register the tool**

In `src/gramps_mcp/server.py`, add the import next to the other tool imports:

```python
from .tools.user_tools import ManageUsersParams, manage_users_tool
```

And add this entry to `TOOL_REGISTRY`, immediately after the `"manage_tags"` entry:

```python
    "manage_users": {
        "description": (
            "List, get, or create Gramps Web user accounts with generated "
            "passwords (action: list/get/create - no update or delete). "
            "Requires an owner account. Roles are capped at editor. "
            "WARNING: generated passwords appear in the response - have "
            "users change them on first login"
        ),
        "schema": ManageUsersParams,
        "handler": manage_users_tool,
    },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS. Some tests in this file assert the tool count; update any hard-coded count from 22 to 23 if one fails.

- [ ] **Step 5: Commit**

```bash
rtk git add src/gramps_mcp/server.py tests/test_server.py
uv run git commit -m "feat: register manage_users in the tool registry"
```

---

### Task 5: Documentation

**Files:**
- Create: `docs/user-management.md`
- Modify: `README.md` (tool bullet list, near line 90)

**Interfaces:**
- Consumes: the finished tool.
- Produces: no code.

- [ ] **Step 1: Write `docs/user-management.md`**

Create the file with these sections, written as prose, not placeholders:

1. **Purpose** — what the tool does, and the three actions.
2. **Prerequisite** — the `.env` account needs role `owner` (4) or `admin` (5); how to check with `manage_users` action `get` on your own username.
3. **Roles** — the full eight-row table from the design spec, marking which four the tool can assign and stating that `owner`/`admin` are rejected by the schema before any network call.
4. **Usage** — a call example per action, with the `create` example showing two users and the resulting output block.
5. **Passwords** — state plainly that generated passwords are returned in the tool result, therefore enter the model's context and the on-disk session transcript, and must be treated as exposed from creation. Instruct that accounts be handed out for a first login with an immediate password change.
6. **What the tool cannot do** — no update, no delete, no password reset; those stay in the Gramps Web UI. Note that accounts created with placeholder e-mail addresses have no working password-reset path, so every forgotten password becomes a manual job for the owner.

- [ ] **Step 2: Add the README bullet**

In `README.md`, after the `manage_tags` bullet on line 90:

```markdown
- **manage_users** - List, get, or create Gramps Web accounts with generated passwords (owner rights required, see [docs/user-management.md](docs/user-management.md))
```

- [ ] **Step 3: Verify the docs match the code**

Run: `uv run pytest tests/test_user_tools.py -v`
Then re-read `docs/user-management.md` against the actual output format produced by the tests. Fix any drift between the documented output block and the real one.

- [ ] **Step 4: Commit**

```bash
rtk git add docs/user-management.md README.md
uv run git commit -m "docs: document the manage_users tool"
```

---

### Task 6: Full verification

- [ ] **Step 1: Run the whole suite**

Run: `uv run pytest -x -q`
Expected: no new failures. Pre-existing failures caused by an unreachable server are not regressions — confirm by checking that each failure is a connection error.

- [ ] **Step 2: Type check**

Run: `uv run mypy src/gramps_mcp --ignore-missing-imports`
Expected: no new errors in `user_tools.py`.

- [ ] **Step 3: Lint and format**

Run: `uv run ruff format src/gramps_mcp/tools/user_tools.py tests/test_user_tools.py && uv run ruff check src/gramps_mcp tests`
Expected: all checks pass.

- [ ] **Step 4: Confirm no test accounts survived**

Run: `uv run pytest tests/test_user_tools.py::TestListAndGet::test_list_users -v -s`
Expected: no `pytest_*` username in the output.

- [ ] **Step 5: Commit any formatting changes**

```bash
rtk git add -A
uv run git commit -m "chore: format and lint manage_users"
```

---

## Self-Review

**Spec coverage:** Every section of the design spec maps to a task — schema and endpoints (Task 1), `list`/`get` (Task 2), `create` with pre-check, sequential writes and per-user reporting (Task 3), registry wiring (Task 4), the role table and the password-exposure warning (Task 5), verification including test-account cleanup (Task 6).

**Placeholders:** None. Task 5 describes documentation section by section rather than supplying finished prose, which is deliberate — the output block must be copied from real test output, and Step 3 of that task enforces it.

**Type consistency:** `manage_users_tool(arguments)` is called with a single dict throughout, matching the `with_client` decorator's injection of `client`. `_create_one` returns `tuple[str, str]` and every call site unpacks two values. `ROLE_IDS` is keyed by name and inverted only inside `_role_name`.

**Test counts:** The expected counts in the "run the tests" steps (10, 15, 18) assume the tests are added cumulatively to one file, as written. If a count is off by a small amount, check that no test was dropped before assuming a failure.
