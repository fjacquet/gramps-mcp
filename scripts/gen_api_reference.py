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
Generate the Gramps Web API coverage reference from the vendored OpenAPI spec.

Reads docs/reference/openapi.json, cross-references every operation against the
ApiCalls enum this server actually calls, and writes
docs/reference/gramps-web-api.md.

Run it after replacing the spec with a newer release:

    uv run python scripts/gen_api_reference.py

The point is not to republish upstream's documentation - it is to answer one
question that no upstream document can: which parts of the API this server
reaches, and which it leaves on the table.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Reason: the package is imported as `src.gramps_mcp.*` and the project is run
# from the repo root rather than installed, so a script invoked by path needs
# the root on sys.path before the import below resolves.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SPEC_PATH = REPO_ROOT / "docs" / "reference" / "openapi.json"
OUT_PATH = REPO_ROOT / "docs" / "reference" / "gramps-web-api.md"

HTTP_METHODS = ("get", "post", "put", "delete", "patch")

# Reason: one call in this server does not go through ApiCalls. AuthManager
# posts to "/token/" directly (src/gramps_mcp/auth.py:128) because it runs
# before the authenticated client exists. Reading the enum alone would report
# that operation as unused, which is the opposite of true - it is the one call
# every other call depends on. Verified as the only such bypass: no other
# module issues a bare client.get/post/put/delete.
EXTRA_CALLS: dict[tuple[str, str], list[str]] = {
    ("POST", "token"): ["AuthManager auth.py:128 (not via ApiCalls)"],
}


def normalise(path: str) -> str:
    """
    Reduce a path to a form comparable across the spec and the ApiCalls enum.

    The spec writes full paths with named placeholders (`/api/people/{handle}`);
    ApiCalls writes them relative to the REST base with its own placeholder
    names (`people/{handle}`). Stripping the prefix and blanking placeholder
    names makes the two comparable.

    Args:
        path (str): A path from either source.

    Returns:
        str: The comparable form, for example `people/{}`.
    """
    path = re.sub(r"^/?api/", "", path)
    path = re.sub(r"\{[^}]+\}", "{}", path)
    return path.strip("/")


def load_our_calls() -> dict[tuple[str, str], list[str]]:
    """
    Map every (method, normalised path) this server calls to its enum members.

    Imported rather than parsed: several ApiCalls entries wrap onto a second
    line, and a line-oriented regex silently misses them - which is how an
    earlier version of this audit reported MERGE_REPOSITORY as unused when it
    was there all along.

    Returns:
        dict[tuple[str, str], list[str]]: Operation to enum member names.
    """
    from src.gramps_mcp.models.api_calls import ApiCalls

    calls: dict[tuple[str, str], list[str]] = defaultdict(list)
    for member in ApiCalls:
        method, path = member.value[0], member.value[1]
        calls[(method.upper(), normalise(path))].append(member.name)
    for key, names in EXTRA_CALLS.items():
        calls[key].extend(names)
    return calls


def main() -> None:
    """Write the coverage reference, or exit non-zero if the spec is missing."""
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    ours = load_our_calls()

    by_tag: dict[str, list[dict]] = defaultdict(list)
    total = 0
    used = 0
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            total += 1
            key = (method.upper(), normalise(path))
            members = ours.get(key, [])
            if members:
                used += 1
            tags = operation.get("tags") or ["Untagged"]
            by_tag[tags[0]].append(
                {
                    "method": method.upper(),
                    "path": path,
                    "summary": (operation.get("summary") or "").strip(),
                    "members": members,
                }
            )

    info = spec.get("info", {})
    lines = [
        "# Gramps Web API coverage",
        "",
        f"Generated from `openapi.json`, **{info.get('title', 'Gramps Web API')} "
        f"{info.get('version', '?')}**, by `scripts/gen_api_reference.py`.",
        "Do not edit this page by hand - regenerate it.",
        "",
        f"This server calls **{used} of the {total} operations** the API exposes.",
        "A row with an `ApiCalls` member is reachable from an MCP tool; a row",
        "without one is a capability this server does not use today.",
        "",
        "Paths are shown as the spec writes them. The REST base is",
        "`${GRAMPS_API_URL%/}/api` - `GRAMPS_API_URL` itself carries no `/api`",
        "suffix, and calling it without one returns the web app's HTML page with",
        "HTTP 200 rather than an error.",
        "",
    ]

    for tag in sorted(by_tag):
        operations = sorted(by_tag[tag], key=lambda o: (o["path"], o["method"]))
        tag_used = sum(1 for o in operations if o["members"])
        lines += [
            f"## {tag}",
            "",
            f"{tag_used} of {len(operations)} used.",
            "",
            "| Method | Path | ApiCalls | Summary |",
            "|---|---|---|---|",
        ]
        for op in operations:
            members = ", ".join(f"`{m}`" for m in op["members"]) or "-"
            summary = op["summary"].replace("|", "\\|")
            lines.append(f"| {op['method']} | `{op['path']}` | {members} | {summary} |")
        lines.append("")

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)}: {used}/{total} operations used")


if __name__ == "__main__":
    main()
