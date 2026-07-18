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
Tag data handler for Gramps MCP operations.

Formats single-tag and tag-list results.
"""

from typing import Dict, List


def format_tag(data: Dict) -> str:
    """
    Format a single tag record.

    Args:
        data: Tag dict with handle, name, color, priority

    Returns:
        Formatted tag string
    """
    if not data:
        return "Tag not found."

    name = data.get("name", "Unnamed tag")
    handle = data.get("handle", "")
    color = data.get("color")
    priority = data.get("priority")

    result = f"**{name}** - [{handle}]\n"
    if color:
        result += f"Color: {color}\n"
    if priority is not None:
        result += f"Priority: {priority}\n"

    return result


def format_tags(data: List[Dict]) -> str:
    """
    Format a list of tag records.

    Args:
        data: List of tag dicts

    Returns:
        Formatted tags string
    """
    if not data:
        return "No tags found."

    result = f"Found {len(data)} tag(s):\n\n"
    for tag in data:
        name = tag.get("name", "Unnamed tag")
        handle = tag.get("handle", "")
        result += f"• {name} - [{handle}]\n"

    return result
