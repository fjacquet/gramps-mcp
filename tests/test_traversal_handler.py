"""
Unit tests for the traversal markdown renderer. Pure formatting, no server.
"""

from src.gramps_mcp.handlers.traversal_handler import format_traversal
from src.gramps_mcp.traversal import TraversalResult


def _profile(handle: str, gramps_id: str, name: str, **extra) -> dict:
    """
    Build a person profile shaped like the Gramps Web profile=self payload.

    Args:
        handle (str): Person handle.
        gramps_id (str): Gramps ID.
        name (str): Display name.
        **extra: Additional profile keys, for example birth= or death=.

    Returns:
        dict: A person profile.
    """
    return {"handle": handle, "gramps_id": gramps_id, "name_display": name, **extra}


def _result(**overrides) -> TraversalResult:
    """
    Build a two-generation TraversalResult with defaults callers can override.

    Args:
        **overrides: Fields to replace on the result.

    Returns:
        TraversalResult: The assembled result.
    """
    base = {
        "root": "h1",
        "nodes": {
            "h1": _profile(
                "h1",
                "I0001",
                "JACQUET, Frederic",
                birth={"date": "10 Aug 1976", "place_name": "Bourges"},
            ),
            "h2": _profile(
                "h2",
                "I0042",
                "JACQUET, Yvan",
                birth={"date": "1948", "place_name": "Lyon"},
                death={"date": "2011"},
            ),
            "h3": _profile("h3", "I0129", "MARIAUD, Odile"),
        },
        "edges": {"h1": ["h2", "h3"]},
        "truncated_by_cap": False,
        "unexplored": 0,
        "failed": {},
    }
    base.update(overrides)
    return TraversalResult(**base)


class TestFormatTraversal:
    def test_header_names_direction_generations_and_count(self):
        text = format_traversal(_result(), "ancestors")
        assert text.splitlines()[0] == (
            "# Ancestors of JACQUET, Frederic (I0001) - 2 generations, 3 people"
        )

    def test_descendants_direction_changes_only_the_header_word(self):
        text = format_traversal(_result(), "descendants")
        assert text.splitlines()[0].startswith("# Descendants of JACQUET, Frederic")

    def test_root_line_carries_id_birth_date_and_place(self):
        text = format_traversal(_result(), "ancestors")
        assert "- JACQUET, Frederic (I0001), b. 10 Aug 1976 Bourges" in text

    def test_child_lines_are_indented_two_spaces_per_generation(self):
        text = format_traversal(_result(), "ancestors")
        assert "  - JACQUET, Yvan (I0042), b. 1948 Lyon, d. 2011" in text

    def test_absent_dates_are_omitted_entirely(self):
        text = format_traversal(_result(), "ancestors")
        assert "  - MARIAUD, Odile (I0129)" in text

    def test_revisited_node_is_marked_and_not_expanded_twice(self):
        result = _result(edges={"h1": ["h2", "h3"], "h2": ["h3"]})
        text = format_traversal(result, "ancestors")
        assert text.count("MARIAUD, Odile (I0129)") == 2
        assert "[already listed above]" in text
        # Reason: the marker must sit on the deeper repeat, not the first
        # occurrence, or the reader loses the branch that was expanded.
        first, second = [line for line in text.splitlines() if "MARIAUD" in line]
        assert "[already listed above]" not in first
        assert "[already listed above]" in second

    def test_failed_node_renders_with_its_handle_and_reason(self):
        result = _result(
            edges={"h1": ["h2", "h9"]},
            failed={"h9": "HTTP 500"},
        )
        text = format_traversal(result, "ancestors")
        assert "  - (handle h9) [unavailable: HTTP 500]" in text

    def test_cap_truncation_is_announced_in_a_footer(self):
        result = _result(truncated_by_cap=True, unexplored=42)
        text = format_traversal(result, "ancestors")
        assert text.rstrip().endswith(
            "**Truncated**: visit cap of 500 reached, 42 branches unexplored. "
            "Lower max_generations or start from a closer person."
        )

    def test_no_footer_when_the_walk_completed(self):
        text = format_traversal(_result(), "ancestors")
        assert "Truncated" not in text

    def test_lone_person_with_no_relatives_reads_as_one_generation(self):
        result = _result(
            nodes={"h1": _profile("h1", "I0001", "JACQUET, Frederic")}, edges={}
        )
        text = format_traversal(result, "ancestors")
        assert "1 generations, 1 people" in text
