"""The guard that stops a family merge from silently destroying a parent.

Measured on a live tree on 2026-08-31: merging two families whose fathers
differ does not choose between the two men. It merges them into one person
and the other returns 404 afterwards. Nothing in the Gramps Web API's own
schema says so - it describes phoenix_father_handle as "the person to keep
as father", which reads as a choice between two survivors.
"""

from src.gramps_mcp.destructive import ParentConflict, parent_merge_conflicts
from src.gramps_mcp.handlers.destructive_handler import format_parent_merge_refusal


class TestParentMergeConflicts:
    def test_two_different_fathers_conflict(self):
        conflicts = parent_merge_conflicts(
            {"father_handle": "pa"}, {"father_handle": "pb"}, None, None
        )

        assert conflicts == [ParentConflict("father", "pa", "pb")]

    def test_the_same_father_is_not_a_conflict(self):
        assert (
            parent_merge_conflicts(
                {"father_handle": "pa"}, {"father_handle": "pa"}, None, None
            )
            == []
        )

    def test_one_side_without_a_father_is_not_a_conflict(self):
        """Only both-present-and-different was measured to destroy a person.

        With one side empty there is no second man to absorb, so the merge
        cannot destroy one. The guard deliberately stays out of this case
        rather than refusing on an unmeasured suspicion.
        """
        assert parent_merge_conflicts({"father_handle": "pa"}, {}, None, None) == []
        assert (
            parent_merge_conflicts(
                {"father_handle": ""}, {"father_handle": "pb"}, None, None
            )
            == []
        )

    def test_naming_the_survivor_clears_the_conflict(self):
        assert (
            parent_merge_conflicts(
                {"father_handle": "pa"}, {"father_handle": "pb"}, "pa", None
            )
            == []
        )

    def test_mothers_are_guarded_too(self):
        conflicts = parent_merge_conflicts(
            {"father_handle": "pa", "mother_handle": "ma"},
            {"father_handle": "pb", "mother_handle": "mb"},
            None,
            None,
        )

        assert conflicts == [
            ParentConflict("father", "pa", "pb"),
            ParentConflict("mother", "ma", "mb"),
        ]

    def test_acknowledging_one_role_leaves_the_other(self):
        conflicts = parent_merge_conflicts(
            {"father_handle": "pa", "mother_handle": "ma"},
            {"father_handle": "pb", "mother_handle": "mb"},
            "pa",
            None,
        )

        assert conflicts == [ParentConflict("mother", "ma", "mb")]


class TestRefusalMessage:
    def test_it_names_both_people_and_the_destruction(self):
        text = format_parent_merge_refusal(
            [ParentConflict("father", "pa", "pb")],
            {"pa": "Jean Jacquet (I0001)", "pb": "Jean Jaquet (I0002)"},
        )

        assert "Jean Jacquet (I0001)" in text
        assert "Jean Jaquet (I0002)" in text
        assert "ceases to exist" in text
        assert "phoenix_father_handle" in text

    def test_a_mother_conflict_names_the_mother_parameter(self):
        text = format_parent_merge_refusal(
            [ParentConflict("mother", "ma", "mb")],
            {"ma": "Marie A (I0003)", "mb": "Marie B (I0004)"},
        )

        assert "phoenix_mother_handle" in text
        assert "phoenix_father_handle" not in text
