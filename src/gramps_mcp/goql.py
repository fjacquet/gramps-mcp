# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
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
GOQL helpers for the gramps-webapi 3.26 MatchesQuery filter.
"""

import json


def build_rules(expr: str) -> str:
    """
    Wrap a GOQL expression in the `rules` parameter the API expects.

    Args:
        expr: GOQL expression, e.g. `gramps_id == "I0001"`.

    Returns:
        JSON text of a single MatchesQuery rule combined with "and".
    """
    return json.dumps(
        {"function": "and", "rules": [{"name": "MatchesQuery", "values": [expr]}]},
        ensure_ascii=False,
    )
