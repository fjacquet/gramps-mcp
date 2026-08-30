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

"""SPARQL transport for the Wikidata endpoint.

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/web/wikidata.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.

Ported from `requests` to `httpx` so this repo gains no new dependency; the
source's `WikidataSparqlTool` CrewAI `BaseTool` wrapper was not copied, only
the pure `sparql_rows` transport it and the geo resolvers both call. The
source's `USER_AGENT` value was not copied either - it names
crewai-custom-tools, and this request now comes from gramps-mcp. See the
`USER_AGENT` docstring below for why a fresh value was built instead.
"""

from __future__ import annotations

import httpx

from ... import __version__

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# Reason: Wikimedia's User-Agent policy exists so an operator seeing traffic
# can reach whoever sent it. The upstream module names crewai-custom-tools;
# sending that from here would point Wikidata at the wrong maintainer, so
# this names gramps-mcp and reads the version rather than hardcoding one
# that drifts.
USER_AGENT = (
    f"gramps-mcp/{__version__} "
    "(https://github.com/fjacquet/gramps-mcp; place resolution)"
)


def sparql_rows(query: str, *, timeout: float = 30.0) -> list[dict[str, str]]:
    """Run a SPARQL query and return its bindings flattened as {variable: value}.

    Args:
        query (str): The SPARQL query to run.
        timeout (float): Seconds before the request is abandoned.

    Returns:
        list[dict[str, str]]: One dict per result row.

    Raises:
        httpx.HTTPStatusError: If the endpoint returns an error status.
    """
    response = httpx.get(
        SPARQL_ENDPOINT,
        params={"query": query, "format": "json"},
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    bindings = response.json().get("results", {}).get("bindings", [])
    return [
        {var: cell.get("value") for var, cell in binding.items()}
        for binding in bindings
    ]
