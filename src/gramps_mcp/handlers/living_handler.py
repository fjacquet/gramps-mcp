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
Living status data handler for Gramps MCP operations.

Formats living-status and estimated-dates results for a person.
"""


def format_living_status(living: dict, dates: dict | None) -> str:
    """
    Format living-status data, optionally including estimated dates.

    Args:
        living: Dict with a "living" boolean field
        dates: Optional dict with "birth", "death", "explain", "other" fields

    Returns:
        Formatted living-status string
    """
    is_living = living.get("living")
    result = f"**Living:** {'Yes' if is_living else 'No'}\n"

    if dates:
        birth = dates.get("birth")
        death = dates.get("death")
        explain = dates.get("explain")

        if birth:
            result += f"Estimated birth: {birth}\n"
        if death:
            result += f"Estimated death: {death}\n"
        if explain:
            result += f"Explanation: {explain}\n"

    return result
