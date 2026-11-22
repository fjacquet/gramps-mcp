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
RESOURCE_DOCS = ["gramps-usage-guide.md", "gql-documentation.md"]
# Reason: the published guides teach GOQL too; gramps-web-api.md is generated
# from the upstream API reference and is not ours to hold to this.
PUBLISHED = sorted(Path("docs/user-guide").glob("*.md")) + [
    Path("docs/reference/tools.md"),
    Path("docs/reference/api-capabilities-notes.md"),
]
DOCS = [RESOURCES / n for n in RESOURCE_DOCS] + PUBLISHED
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
EXAMPLE = re.compile(r"""find_type\(\s*type="(\w+)",\s*gql='(.*?)'""")


def collect() -> list[tuple[str, str, str, bool]]:
    """Return (doc, type, expression, needs_rows) for every runnable example."""
    found = []
    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for match in EXAMPLE.finditer(text):
            obj_type, expr = match.groups()
            if PLACEHOLDER.search(expr):  # such as <father handle>
                continue
            i = text.count("\n", 0, match.start())
            rows = i > 0 and lines[i - 1].strip() == "<!-- rows -->"
            found.append((path.name, obj_type, expr, rows))
    return found


EXAMPLES = collect()


def test_docs_carry_examples():
    """Guard against the extractor silently matching nothing."""
    assert len(EXAMPLES) >= 25
    assert set(RESOURCE_DOCS) <= {doc for doc, *_ in EXAMPLES}
    assert {"recording.md", "searching.md"} <= {doc for doc, *_ in EXAMPLES}


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
