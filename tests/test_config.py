"""Unit tests for configuration helpers - pure functions, no API needed."""

from pydantic import HttpUrl

from src.gramps_mcp.config import Settings, get_api_base_url


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
