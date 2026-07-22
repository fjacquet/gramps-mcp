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
Timeline data handler for Gramps MCP operations.

Formats chronological event lists from person, family, and group timeline
endpoints.
"""


def format_timeline(data: dict | list[dict]) -> str:
    """
    Format timeline event data into a chronological markdown list.

    The Gramps Web API spec for the single-person/single-family timeline
    endpoints does not clearly show list-wrapping in its schema, so this
    accepts either a single event dict or a list of them defensively.

    Args:
        data: A single timeline event dict, or a list of them

    Returns:
        Formatted timeline string
    """
    if not data:
        events = []
    elif isinstance(data, list):
        events = data
    else:
        events = [data]

    if not events:
        return "No timeline events found."

    result = f"Found {len(events)} timeline event(s):\n\n"

    for event in events:
        date = event.get("date", "Unknown date")
        label = event.get("label") or event.get("description", "Event")
        age = event.get("age")

        result += f"• **{date}** - {label}"
        if age:
            result += f" (age {age})"
        result += "\n"

        citations = event.get("citations")
        confidence = event.get("confidence")
        if citations is not None or confidence is not None:
            result += f"  Citations: {citations or 0}, Confidence: {confidence or 0}\n"

        result += "\n"

    return result
