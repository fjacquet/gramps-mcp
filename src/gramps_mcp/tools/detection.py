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

"""Read-only detection tools: duplicates, quality audit, place resolution."""

import logging

from mcp.types import TextContent

from ..client import GrampsAPIError
from ..config import get_settings
from ..genealogy.collect import collect_tree
from ..genealogy.duplicates import etager
from ..genealogy.merge_plan import plan_fusions
from ..handlers.duplicates_handler import format_duplicate_clusters
from ..models.parameters.detection_params import FindDuplicatesParams
from .search_basic import with_client

logger = logging.getLogger(__name__)


def _format_error_response(error: Exception, operation: str) -> list[TextContent]:
    """Format an error into a user-facing MCP response."""
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"
    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


@with_client
async def find_duplicates_tool(client, arguments: dict) -> list[TextContent]:
    """
    Find candidate duplicate people in the tree.

    Wraps `duplicates.etager` - the blocking path - not the module-level
    function that happens to share this tool's name, which is a quadratic
    scan meant for an already-small batch.

    Args:
        client: A GrampsWebAPIClient, injected by with_client.
        arguments (dict): Tool arguments, validated against
            FindDuplicatesParams.

    Returns:
        list[TextContent]: Proved duplicate clusters, plus pairs still
        needing human arbitration, rendered as markdown.
    """
    try:
        params = FindDuplicatesParams(**arguments)
        tree_id = get_settings().gramps_tree_id

        collected = await collect_tree(client, tree_id, limit=params.limit)
        pairs, _ignored = etager(collected.people, collected.families)
        by_handle = {p.handle: p for p in collected.people}
        clusters = plan_fusions(pairs, by_handle)

        # Reason: plan_fusions keeps only tier == "auto" pairs, so the pairs
        # needing human arbitration never reach its output. They are carried
        # separately rather than dropped - the spec forbids collapsing the
        # proved/unproved split, because a collapsed one reads as proof.
        arbitration = [p for p in pairs if p.tier == "arbitrage"]

        return [
            TextContent(
                type="text",
                text=format_duplicate_clusters(
                    clusters,
                    arbitration,
                    by_handle,
                    skipped=collected.skipped,
                    partial=collected.partial,
                    error=collected.error,
                ),
            )
        ]

    except Exception as e:
        return _format_error_response(e, "duplicate detection")
