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
Facts data handler for Gramps MCP operations.

Formats "interesting facts" statistics about the tree.
"""

from typing import Dict, List

from ..utils import get_gramps_id_from_handle


async def format_facts(data: List[Dict], client, tree_id: str) -> str:
    """
    Format a list of RecordFact entries.

    Args:
        data: List of fact dicts with description, key, objects
        client: Gramps API client instance
        tree_id: Family tree identifier

    Returns:
        Formatted facts string
    """
    if not data:
        return "No facts found."

    result = f"Found {len(data)} fact(s):\n\n"

    for fact in data:
        description = fact.get("description", "Unknown fact")
        result += f"• **{description}**\n"

        objects = fact.get("objects", [])
        for obj in objects:
            # Reason: the live API returns the object's type under the
            # "object" key (e.g. "Person"), not "class" as originally
            # assumed - confirmed against a real GET_FACTS response.
            handle = obj.get("handle") if isinstance(obj, dict) else None
            obj_class = obj.get("object") if isinstance(obj, dict) else None
            if handle and obj_class:
                gramps_id = await get_gramps_id_from_handle(
                    client, obj_class, handle, tree_id
                )
                result += f"  - {obj_class}: {gramps_id}\n"

        result += "\n"

    return result
