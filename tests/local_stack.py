"""
Coordinates of the local Gramps Web stack the tests run against.

Single source of truth: the seed script creates the account named here
and pytest authenticates with it, so the two cannot drift. The values
live in a tracked module rather than a dotenv file because .gitignore
swallows .env-*, which would leave every contributor to recreate it by
hand.

The password is a local-only credential for a stack published on the
loopback interface and filled with a throwaway copy of the tree. It is
not a secret, and it guards nothing reachable from off the machine.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent

API_URL = "http://localhost:5555"
USERNAME = "test-owner"
PASSWORD = "test-only-not-a-secret"
EMAIL = "test-owner@example.invalid"
FULL_NAME = "Test Owner"
# Reason: _build_url ignores the tree id for every ordinary call - the
# token selects the tree (client.py:73-85) - but get_tree_info reads
# /trees/<id> and answers 404 for a wrong one, and Settings requires the
# variable to be non-empty either way. The real id is a UUID minted when
# the stack's volumes are created, so it cannot be a constant: the seed
# script writes it here, and this file is gitignored.
TREE_ID_FILE = REPO_ROOT / "tests" / ".local-tree-id"
TREE_ID_FALLBACK = "TestTree"

ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "host.docker.internal"})


def tree_id() -> str:
    """
    Return the seeded stack's tree id, or a placeholder before seeding.

    Returns:
        str: The UUID written by scripts/seed_test_tree.py, or
            TREE_ID_FALLBACK when the stack has not been seeded yet.
    """
    if TREE_ID_FILE.is_file():
        recorded = TREE_ID_FILE.read_text().strip()
        if recorded:
            return recorded
    return TREE_ID_FALLBACK


def is_local(url: str) -> bool:
    """
    Report whether a URL points at this machine.

    Args:
        url (str): The URL to classify.

    Returns:
        bool: True when the host is one of ALLOWED_HOSTS.
    """
    # Reason: urlparse().hostname returns the host alone - port stripped,
    # userinfo discarded, lowercased - so the comparison is against whole
    # hostnames rather than a substring of the URL. A substring test would
    # accept "localhost.evil.example" and "user@localhost.evil.example".
    return urlparse(url).hostname in ALLOWED_HOSTS


def assert_local(url: str) -> None:
    """
    Refuse a URL that is not the local stack.

    Args:
        url (str): The URL to check.

    Returns:
        None

    Raises:
        RuntimeError: When the host is not in ALLOWED_HOSTS.
    """
    if not is_local(url):
        raise RuntimeError(
            f"Refusing to run against '{url}': not the local test stack. "
            f"Allowed hosts: {sorted(ALLOWED_HOSTS)}. Start the stack with "
            "'docker compose -f docker-compose.test.yml up -d' and seed it "
            "with 'uv run python scripts/seed_test_tree.py'."
        )


def apply_test_environment() -> None:
    """
    Point the Gramps configuration at the local stack, or refuse.

    Returns:
        None

    Raises:
        RuntimeError: When GRAMPS_TEST_API_URL names a non-local host.
    """
    url = os.environ.get("GRAMPS_TEST_API_URL", API_URL)
    assert_local(url)
    os.environ["GRAMPS_API_URL"] = url
    os.environ["GRAMPS_USERNAME"] = USERNAME
    os.environ["GRAMPS_PASSWORD"] = PASSWORD
    os.environ["GRAMPS_TREE_ID"] = tree_id()
    # Reason: the media_path tests upload tests/sample/33SQ-GP8N-NLK.jpg,
    # a fixture inside the repository. The default import root is /tmp, so
    # without this every one of them is refused by resolve_media_path -
    # which is the containment check doing its job, not a bug. Widening
    # the root to the repository is safe here and nowhere else: it is the
    # test process reading its own fixtures, not the MCP container
    # exposing a host filesystem.
    os.environ["GRAMPS_MEDIA_IMPORT_ROOT"] = str(REPO_ROOT)
