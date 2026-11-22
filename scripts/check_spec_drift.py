#!/usr/bin/env python3
# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2026 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Compare the vendored OpenAPI spec with the one a Gramps Web server serves.

Run it before every server upgrade, to learn what the new release removed
(the `gql` parameter vanished in gramps-webapi 3.26 and nothing warned us):

    uv run python scripts/check_spec_drift.py [BASE_URL]

BASE_URL defaults to GRAMPS_API_URL, then to the local test stack. This is an
explicit command, never called by the tests: pointing it at the live tree is
the operator's choice, and it only reads the public spec.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "docs" / "reference" / "openapi.json"
DEFAULT_URL = "http://localhost:5555"
HTTP_METHODS = ("get", "post", "put", "delete", "patch")


def _params(spec: dict) -> set[str]:
    """
    List every operation parameter of a spec.

    Args:
        spec (dict): A parsed OpenAPI document.

    Returns:
        set[str]: Entries like "GET /api/people/:gql".
    """
    found = set()
    for path, item in spec.get("paths", {}).items():
        for method in HTTP_METHODS:
            for param in item.get(method, {}).get("parameters", []):
                # Reason: a $ref parameter has no name, and its target name
                # is what a reader recognises.
                name = param.get("name") or param.get("$ref", "?").rsplit("/", 1)[-1]
                found.add(f"{method.upper()} {path}:{name}")
    return found


def diff_specs(old: dict, new: dict) -> dict[str, list[str]]:
    """
    Compare two OpenAPI documents.

    Args:
        old (dict): The vendored spec.
        new (dict): The spec a server serves now.

    Returns:
        dict[str, list[str]]: Sorted entries under removed_params,
            added_params, removed_paths and added_paths.
    """
    old_paths, new_paths = set(old.get("paths", {})), set(new.get("paths", {}))
    old_params, new_params = _params(old), _params(new)
    return {
        "removed_params": sorted(old_params - new_params),
        "added_params": sorted(new_params - old_params),
        "removed_paths": sorted(old_paths - new_paths),
        "added_paths": sorted(new_paths - old_paths),
    }


def main(url: str) -> int:
    """
    Fetch a server's spec, compare it with the vendored one and print it.

    Args:
        url (str): Server base URL without the /api suffix.

    Returns:
        int: 0 when there is no drift, 1 otherwise.
    """
    # Reason: /api/openapi.json is served without a token, so no login is
    # needed (checked on 3.26.0).
    response = httpx.get(f"{url.rstrip('/')}/api/openapi.json", timeout=30)
    response.raise_for_status()
    served = response.json()
    report = diff_specs(json.loads(SPEC_PATH.read_text()), served)
    print(f"vendored {SPEC_PATH.name} vs {url} ({served['info']['version']})")
    for key, entries in report.items():
        print(f"{key}: {len(entries)}")
        for entry in entries:
            print(f"  {entry}")
    return int(any(report.values()))


if __name__ == "__main__":
    default = os.environ.get("GRAMPS_API_URL", DEFAULT_URL)
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else default))
