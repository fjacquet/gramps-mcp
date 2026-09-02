"""
The guard that keeps pytest off the live tree.

`tests/conftest.py` points the Gramps configuration at the local stack
before any test module is imported. These tests cover the host allowlist
that decides what "local" means, and the refusal that fires when an
override names anything else. A green local run proves nothing about the
guard - only the refusal does.
"""

import os

import pytest

from tests import local_stack


class TestHostAllowlist:
    """Which URLs count as the local test stack."""

    def test_the_configured_stack_url_is_local(self):
        assert local_stack.is_local(local_stack.API_URL)

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:5555",
            "http://127.0.0.1:5555",
            "http://host.docker.internal:5555",
        ],
    )
    def test_every_allowed_host_passes(self, url):
        assert local_stack.is_local(url)

    def test_a_remote_host_is_refused(self):
        assert not local_stack.is_local("https://gramps.example.com")

    def test_a_host_merely_starting_with_an_allowed_name_is_refused(self):
        # Reason: resolve_media_path was already defeated once in this repo
        # by a shared string prefix. The allowlist compares whole hostnames.
        assert not local_stack.is_local("https://localhost.evil.example")

    def test_userinfo_cannot_smuggle_an_allowed_host(self):
        assert not local_stack.is_local("https://localhost@gramps.example.com")

    def test_assert_local_names_the_url_it_refused(self):
        with pytest.raises(RuntimeError) as exc:
            local_stack.assert_local("https://gramps.example.com")
        assert "gramps.example.com" in str(exc.value)


class TestEnvironmentApplication:
    """What the configuration reads once the guard has run."""

    def test_the_live_settings_are_replaced_by_the_stack_settings(self, monkeypatch):
        monkeypatch.setenv("GRAMPS_API_URL", "https://gramps.example.com")
        monkeypatch.setenv("GRAMPS_USERNAME", "live")
        local_stack.apply_test_environment()
        assert os.environ["GRAMPS_API_URL"] == local_stack.API_URL
        assert os.environ["GRAMPS_USERNAME"] == local_stack.USERNAME

    def test_settings_read_the_stack_after_application(self, monkeypatch):
        monkeypatch.setenv("GRAMPS_API_URL", "https://gramps.example.com")
        local_stack.apply_test_environment()
        from src.gramps_mcp.config import get_settings

        assert str(get_settings().gramps_api_url).startswith(local_stack.API_URL)

    def test_an_override_pointing_off_the_machine_is_refused(self, monkeypatch):
        monkeypatch.setenv("GRAMPS_TEST_API_URL", "https://gramps.example.com")
        with pytest.raises(RuntimeError):
            local_stack.apply_test_environment()
