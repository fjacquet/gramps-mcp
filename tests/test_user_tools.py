"""
Integration tests for the user management tool using the real Gramps API.
"""

import uuid

import pytest
from pydantic import ValidationError

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools.user_tools import (
    ManageUsersParams,
    NewUser,
    _format_user_rows,
    manage_users_tool,
)


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

    def test_rejects_path_traversal_name(self):
        """
        ManageUsersParams.name is substituted unescaped into the request
        URL path. Without USERNAME_PATTERN, a value like "../metadata"
        survives urljoin's path normalization and redirects a "get" call to
        an unrelated endpoint - see the fix for that finding.
        """
        with pytest.raises(ValidationError):
            ManageUsersParams(action="get", name="../metadata")


class TestApiCalls:
    """The endpoints the tool relies on exist and are not tree-scoped."""

    def test_user_endpoints_defined(self):
        assert ApiCalls.GET_USERS.value == ("GET", "users/")
        assert ApiCalls.GET_USER.value == ("GET", "users/{name}/")
        assert ApiCalls.POST_USER.value == ("POST", "users/{name}/")
        assert ApiCalls.DELETE_USER.value == ("DELETE", "users/{name}/")


class TestFormatUserRows:
    """Test the _format_user_rows helper function with various input scenarios."""

    def test_format_with_null_values(self):
        """Test that null values in user objects are coerced to placeholder."""
        users = [
            {
                "name": None,
                "email": None,
                "full_name": None,
                "role": None,
            }
        ]
        result = _format_user_rows(users)
        assert "error" not in result.lower()
        # All fields should have been replaced with placeholder
        # Verify that null role renders as "-", not as "None"
        assert "-" in result
        assert "None" not in result

    def test_format_null_and_absent_role_consistency(self):
        """Test that null role and absent role both render as placeholder."""
        users_null_role = [
            {"name": "alice", "email": "a@b.fr", "full_name": "Alice", "role": None}
        ]
        users_absent_role = [{"name": "bob", "email": "b@b.fr", "full_name": "Bob"}]
        result_null = _format_user_rows(users_null_role)
        result_absent = _format_user_rows(users_absent_role)
        # Both should have exactly one "-" in the role column (rightmost)
        # Verify both render "-" for role, not "None" or "-99"
        assert result_null.rstrip().endswith("-")
        assert result_absent.rstrip().endswith("-")
        # Neither should contain "None" (would indicate null role bug)
        assert "None" not in result_null
        assert "None" not in result_absent

    def test_format_with_mixed_null_and_values(self):
        """Test formatting with some null and some present fields."""
        users = [
            {
                "name": "alice",
                "email": None,
                "full_name": "Alice Smith",
                "role": 1,  # member
            }
        ]
        result = _format_user_rows(users)
        assert "alice" in result
        assert "Alice Smith" in result
        assert "member" in result

    def test_format_with_absent_keys(self):
        """Test formatting with absent keys (should use defaults)."""
        users = [{"name": "bob"}]
        result = _format_user_rows(users)
        assert "bob" in result
        # Missing fields should show as placeholder
        assert "-" in result

    def test_format_empty_list(self):
        """Test formatting with empty user list."""
        result = _format_user_rows([])
        assert result == "No users found."

    def test_format_with_normal_values(self):
        """Test formatting with all normal values."""
        users = [
            {
                "name": "charlie",
                "email": "charlie@example.com",
                "full_name": "Charlie Brown",
                "role": 3,  # editor
            }
        ]
        result = _format_user_rows(users)
        assert "charlie" in result
        assert "charlie@example.com" in result
        assert "Charlie Brown" in result
        assert "editor" in result


class TestListAndGet:
    """Live-server tests for the read-only actions."""

    pytestmark = pytest.mark.integration

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


class TestCreate:
    """Live-server tests for the writing action."""

    pytestmark = pytest.mark.integration

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

    @pytest.mark.asyncio
    async def test_duplicate_name_within_batch_maps_to_skipped(self):
        """
        Two entries in one batch sharing a name reproduce the acknowledged
        create-time race for real: the pre-check's existing-username set is
        fetched once up front, so the second entry is not caught by it and
        reaches the API after the first entry has already created the
        account, drawing a real 409.

        This also proves the fix for the mid-batch-abort finding: the row
        for the user that succeeded (first entry) is still present in the
        output alongside the row for the one that did not (second entry),
        rather than the whole batch aborting and losing the first entry's
        password.
        """
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
                            "role": "guest",
                        },
                        {
                            "name": name,
                            "email": f"{name}-second@example.org",
                            "role": "guest",
                        },
                    ],
                }
            )
            text = result[0].text
            assert "created 1" in text.lower()
            assert "skipped 1" in text.lower()
            assert "already exists" in text.lower()
            assert "status 409" not in text.lower()
            # Both rows for this name are present - the row for the user
            # that succeeded was not discarded by the second entry's 409.
            assert text.count(name) >= 2
        finally:
            await client.make_api_call(
                api_call=ApiCalls.DELETE_USER,
                params=None,
                tree_id=get_settings().gramps_tree_id,
                name=name,
            )
            await client.close()
