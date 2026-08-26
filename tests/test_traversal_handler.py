"""
Unit tests for the traversal markdown renderer. Pure formatting, no server.
"""

from src.gramps_mcp.handlers.traversal_handler import format_traversal
from src.gramps_mcp.traversal import Link, TraversalResult


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
        "edges": {"h1": [Link("h2"), Link("h3")]},
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
        result = _result(edges={"h1": [Link("h2"), Link("h3")], "h2": [Link("h3")]})
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
            edges={"h1": [Link("h2"), Link("h9")]},
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

    def test_a_non_birth_link_is_named_and_declared_unfollowed(self):
        # Both halves matter: the relationship, so the line is not read as
        # a birth link, and the fact the lineage stops, so the silence
        # beyond is not read as "no ancestors known".
        result = _result(edges={"h1": [Link("h2", relation="Adopted", expand=False)]})
        text = format_traversal(result, "ancestors")
        assert (
            "  - JACQUET, Yvan (I0042), b. 1948 Lyon, d. 2011 "
            "[Adopted, line not followed]" in text
        )

    def test_a_custom_relationship_is_printed_verbatim(self):
        result = _result(
            edges={"h1": [Link("h2", relation="Mere porteuse", expand=False)]}
        )
        text = format_traversal(result, "ancestors")
        assert "[Mere porteuse, line not followed]" in text

    def test_a_parent_from_a_secondary_family_is_marked_as_such(self):
        result = _result(edges={"h1": [Link("h3", secondary_family=True)]})
        text = format_traversal(result, "ancestors")
        assert "  - MARIAUD, Odile (I0129) [other parents family]" in text

    def test_both_markers_appear_together_on_one_line(self):
        result = _result(
            edges={
                "h1": [
                    Link("h3", relation="Foster", expand=False, secondary_family=True)
                ]
            }
        )
        text = format_traversal(result, "ancestors")
        assert (
            "  - MARIAUD, Odile (I0129) "
            "[Foster, line not followed; other parents family]" in text
        )

    def test_a_footer_explains_the_policy_when_a_line_was_not_followed(self):
        result = _result(edges={"h1": [Link("h2", relation="Adopted", expand=False)]})
        text = format_traversal(result, "ancestors")
        assert (
            "**Non-birth links**: a relationship other than birth (Adopted, "
            "Stepchild, Foster, Sponsored, None, Unknown, or a custom type) "
            "is reported but its line is not followed." in text
        )

    def test_no_policy_footer_when_no_line_was_actually_stopped(self):
        # Reason: the footer states the not-following policy. When every
        # non-birth line was reopened by a birth link elsewhere, the policy
        # never bit, and printing it would contradict the tree above it.
        # The bare "[Adopted]" marker needs no footer: it names a
        # relationship rather than claiming anything about the walk.
        result = _result(
            edges={
                "h1": [Link("h2", relation="Adopted", expand=False)],
                "h2": [Link("h3")],
            }
        )
        text = format_traversal(result, "ancestors")
        assert "Non-birth links" not in text

    def test_no_policy_footer_when_every_link_is_a_birth_link(self):
        text = format_traversal(_result(), "ancestors")
        assert "Non-birth links" not in text

    def test_an_unfollowed_person_is_still_named_not_reduced_to_a_handle(self):
        # Reason: the walk fetches an unexpanded relative precisely so this
        # line can carry a name. Printing "[unavailable: not fetched]" here
        # would trade one silent lie for another.
        result = _result(edges={"h1": [Link("h2", relation="Adopted", expand=False)]})
        text = format_traversal(result, "ancestors")
        assert "not fetched" not in text
        assert "JACQUET, Yvan" in text

    def test_a_followed_link_never_claims_its_line_was_not_followed(self):
        # Reason: the marker must describe what the walk actually did, not
        # what the relationship alone suggested. Printing "line not
        # followed" directly above the followed line tells the reader the
        # opposite of the truth and misattributes the branch.
        result = _result(
            edges={
                "h1": [Link("h2", relation="Adopted", expand=True)],
                "h2": [Link("h3")],
            }
        )
        text = format_traversal(result, "ancestors")
        assert "  - JACQUET, Yvan (I0042), b. 1948 Lyon, d. 2011 [Adopted]" in text
        assert "line not followed" not in text
        assert "    - MARIAUD, Odile (I0129)" in text

    def test_a_line_reopened_by_another_path_is_not_called_unfollowed(self):
        # Reason: the link itself is a non-birth link and says expand=False,
        # but the walk reached this person's relatives through a birth link
        # elsewhere and rendered them here. Whether the line was followed is
        # a fact about the finished walk, not about the link that named it.
        result = _result(
            edges={
                "h1": [Link("h2", relation="Adopted", expand=False)],
                "h2": [Link("h3")],
            }
        )
        text = format_traversal(result, "ancestors")
        assert "  - JACQUET, Yvan (I0042), b. 1948 Lyon, d. 2011 [Adopted]" in text
        assert "line not followed" not in text
        assert "    - MARIAUD, Odile (I0129)" in text

    def test_a_repeated_person_keeps_the_markers_of_the_path_that_reached_them(self):
        # Reason: a person can be the birth child of one parent and the
        # adopted child of another. Dropping the marker on the repeat
        # renders the adoption as an unqualified link - the exact
        # misattribution this whole change exists to prevent.
        # h3 is reached first as a plain birth link, then again through h2
        # as an adopted one. The repeat is the marked position.
        result = _result(
            edges={
                "h1": [Link("h3"), Link("h2")],
                "h2": [Link("h3", relation="Adopted", expand=False)],
            }
        )
        text = format_traversal(result, "ancestors")
        first, second = [line for line in text.splitlines() if "MARIAUD" in line]
        assert first.strip() == "- MARIAUD, Odile (I0129)"
        assert "[Adopted, line not followed]" in second
        assert "[already listed above]" in second

    def test_the_secondary_family_marker_is_explained_when_it_appears_alone(self):
        # Reason: the usage guide documents the marker, but it is a
        # separate resource a client may never have loaded. An unexplained
        # bracket in the output is a question the reader cannot answer.
        result = _result(edges={"h1": [Link("h3", secondary_family=True)]})
        text = format_traversal(result, "ancestors")
        assert (
            "**Other parents families**: Gramps designates the first parent "
            "family as the main one; a parent from any other is marked." in text
        )
        assert "Non-birth links" not in text

    def test_lone_person_with_no_relatives_reads_as_one_generation(self):
        result = _result(
            nodes={"h1": _profile("h1", "I0001", "JACQUET, Frederic")}, edges={}
        )
        text = format_traversal(result, "ancestors")
        assert "1 generations, 1 people" in text
