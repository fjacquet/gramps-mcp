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
Breadth-first traversal of the Gramps family graph.

Pure graph logic: this module fetches people and follows family links. It
formats nothing - rendering lives in handlers/traversal_handler.py.
"""

from dataclasses import dataclass, field

VISIT_CAP = 500


@dataclass
class TraversalResult:
    """Outcome of one breadth-first walk of the family graph."""

    root: str
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: dict[str, list[str]] = field(default_factory=dict)
    truncated_by_cap: bool = False
    unexplored: int = 0
    revisited: set[str] = field(default_factory=set)
    failed: dict[str, str] = field(default_factory=dict)
