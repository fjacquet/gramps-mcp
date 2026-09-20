"""
The shared httpx client's read timeout must cover a slow `profile=all` page.

`collect.py` pages people 500 at a time with `profile=all&extend=
event_ref_list` for `audit_quality`/`find_duplicates`. Measured 2026-09-17:
that shape approaches or exceeds 30s per page under load, so the old 30s
budget tripped mid-scan with "Request timeout" - and `audit_quality` then
rendered that partial scan as "the tree is clean" (see
test_detection_audit.py). No network call is made here: constructing the
client is pure local config, so this stays an offline unit test.
"""

import pytest

from src.gramps_mcp.auth import REQUEST_TIMEOUT_SECONDS, AuthManager


@pytest.fixture(autouse=True)
def isolated_auth_manager():
    AuthManager.reset_instance()
    yield
    AuthManager.reset_instance()


def test_shared_client_read_timeout_covers_a_slow_profile_all_page():
    manager = AuthManager()
    client = manager.client

    assert client.timeout.read == REQUEST_TIMEOUT_SECONDS
    assert client.timeout.read >= 60.0


def test_shared_client_connect_timeout_stays_short():
    """The connect budget is unrelated to the slow-page fix - a dead server
    should still fail fast rather than wait out the read timeout."""
    manager = AuthManager()
    client = manager.client

    assert client.timeout.connect == 10.0
