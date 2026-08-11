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
