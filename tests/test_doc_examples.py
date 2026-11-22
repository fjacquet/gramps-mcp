"""
Doc-as-test: every GOQL example served to MCP clients runs on the real server.

The usage guide and the `gql://documentation` resource teach GOQL. An example
that the server rejects, or that is marked `<!-- rows -->` and returns nothing,
fails here, so the docs cannot drift from the server they describe.
"""

import re
from pathlib import Path

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.models.api_calls import ApiCalls

RESOURCES = Path("src/gramps_mcp/resources")
DOCS = ["gramps-usage-guide.md", "gql-documentation.md"]
ENDPOINT = {
    "person": ApiCalls.GET_PEOPLE,
    "family": ApiCalls.GET_FAMILIES,
    "event": ApiCalls.GET_EVENTS,
    "place": ApiCalls.GET_PLACES,
    "source": ApiCalls.GET_SOURCES,
    "citation": ApiCalls.GET_CITATIONS,
    "media": ApiCalls.GET_MEDIA,
    "repository": ApiCalls.GET_REPOSITORIES,
    "note": ApiCalls.GET_NOTES,
}
PLACEHOLDER = re.compile(r"<[a-z]+ [a-z]+>")
EXAMPLE = re.compile(r"""find_type\(type="(\w+)", gql='(.*?)'\)""")


def collect() -> list[tuple[str, str, str, bool]]:
    """Return (doc, type, expression, needs_rows) for every runnable example."""
    found = []
    for name in DOCS:
        lines = (RESOURCES / name).read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            for obj_type, expr in EXAMPLE.findall(line):
                if PLACEHOLDER.search(expr):  # such as <father handle>
                    continue
                rows = i > 0 and lines[i - 1].strip() == "<!-- rows -->"
                found.append((name, obj_type, expr, rows))
    return found


EXAMPLES = collect()


def test_docs_carry_examples():
    """Guard against the extractor silently matching nothing."""
    assert len(EXAMPLES) >= 25
    assert {doc for doc, *_ in EXAMPLES} == set(DOCS)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "doc,obj_type,expr,rows", EXAMPLES, ids=[f"{d}:{e}" for d, _, e, _ in EXAMPLES]
)
async def test_example_runs(doc, obj_type, expr, rows):
    """Each example is valid GOQL; those marked rows return a record."""
    client = GrampsWebAPIClient()
    try:
        result = await client.make_api_call(
            ENDPOINT[obj_type], {"gql": expr, "pagesize": 1}
        )
    finally:
        await client.close()
    if rows:
        assert result, f"{doc}: {obj_type} example returned no rows: {expr}"
