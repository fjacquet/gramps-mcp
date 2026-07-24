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
Relationship data handler for Gramps MCP operations.

Formats direct and all-possible relationship results between two people.
"""

from ..utils import get_gramps_id_from_handle


def format_relationship(data: dict) -> str:
    """
    Format a single most-direct relationship result.

    Args:
        data: Relationship dict with relationship_string,
            distance_common_origin, distance_common_other

    Returns:
        Formatted relationship string
    """
    if not data:
        return "No relationship found between these two people."

    relationship_string = data.get("relationship_string", "Unknown relationship")
    result = f"**Relationship:** {relationship_string}\n"

    distance_origin = data.get("distance_common_origin")
    distance_other = data.get("distance_common_other")

    if distance_origin is not None and distance_origin != -1:
        result += f"Generations to common ancestor: {distance_origin}\n"
    if distance_other is not None and distance_other != -1:
        result += (
            f"Generations from common ancestor to other person: {distance_other}\n"
        )

    return result


async def format_relationships(data: list[dict], client, tree_id: str) -> str:
    """
    Format all-possible-relationships results.

    Args:
        data: List of relationship dicts with relationship_string,
            common_ancestors
        client: Gramps API client instance
        tree_id: Family tree identifier

    Returns:
        Formatted relationships string
    """
    if not data:
        return "No relationships found between these two people."

    result = f"Found {len(data)} possible relationship(s):\n\n"

    for item in data:
        relationship_string = item.get("relationship_string", "Unknown relationship")
        result += f"• **{relationship_string}**\n"

        common_ancestors = item.get("common_ancestors", [])
        if common_ancestors:
            ancestor_ids = []
            for handle in common_ancestors:
                gramps_id = await get_gramps_id_from_handle(
                    client, "person", handle, tree_id
                )
                ancestor_ids.append(gramps_id)
            result += f"  Common ancestors: {', '.join(ancestor_ids)}\n"

        result += "\n"

    return result
