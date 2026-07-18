"""Unit tests for configuration helpers - pure functions, no API needed."""

import pytest
from pydantic import HttpUrl

from src.gramps_mcp.config import Settings, get_api_base_url, get_settings


def make_settings(url: str) -> Settings:
    return Settings(
        gramps_api_url=HttpUrl(url),
        gramps_username="user",
        gramps_password="password",
        gramps_tree_id="tree1",
    )


def test_appends_api_suffix():
    settings = make_settings("https://gramps.example.com")
    assert get_api_base_url(settings) == "https://gramps.example.com/api"


def test_strips_trailing_slash():
    settings = make_settings("https://gramps.example.com/")
    assert get_api_base_url(settings) == "https://gramps.example.com/api"


def test_keeps_existing_api_suffix():
    settings = make_settings("https://gramps.example.com/api")
    assert get_api_base_url(settings) == "https://gramps.example.com/api"


def test_get_settings_defaults_host_and_port(monkeypatch):
    monkeypatch.setenv("GRAMPS_API_URL", "https://gramps.example.com")
    monkeypatch.setenv("GRAMPS_USERNAME", "user")
    monkeypatch.setenv("GRAMPS_PASSWORD", "password")
    monkeypatch.setenv("GRAMPS_TREE_ID", "tree1")
    monkeypatch.delenv("GRAMPS_MCP_HOST", raising=False)
    monkeypatch.delenv("GRAMPS_MCP_PORT", raising=False)

    settings = get_settings()

    assert settings.gramps_mcp_host == "0.0.0.0"
    assert settings.gramps_mcp_port == 8000


def test_get_settings_reads_explicit_host_and_port(monkeypatch):
    monkeypatch.setenv("GRAMPS_API_URL", "https://gramps.example.com")
    monkeypatch.setenv("GRAMPS_USERNAME", "user")
    monkeypatch.setenv("GRAMPS_PASSWORD", "password")
    monkeypatch.setenv("GRAMPS_TREE_ID", "tree1")
    monkeypatch.setenv("GRAMPS_MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("GRAMPS_MCP_PORT", "9000")

    settings = get_settings()

    assert settings.gramps_mcp_host == "127.0.0.1"
    assert settings.gramps_mcp_port == 9000
    assert isinstance(settings.gramps_mcp_port, int)


def test_get_settings_rejects_non_numeric_port(monkeypatch):
    monkeypatch.setenv("GRAMPS_API_URL", "https://gramps.example.com")
    monkeypatch.setenv("GRAMPS_USERNAME", "user")
    monkeypatch.setenv("GRAMPS_PASSWORD", "password")
    monkeypatch.setenv("GRAMPS_TREE_ID", "tree1")
    monkeypatch.setenv("GRAMPS_MCP_PORT", "not-a-number")

    with pytest.raises(ValueError):
        get_settings()
