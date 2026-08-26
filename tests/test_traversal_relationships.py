"""
Unit tests for child-to-parent relationship handling in the family walk.

Gramps records a relationship type on each child's entry in a family
(frel for the father, mrel for the mother): Birth, Adopted, Stepchild,
Foster, Sponsored, None, Unknown, or a custom string. Only a birth link
continues the lineage; the others are reported but not followed.

These patch the transport seam (GrampsWebAPIClient._make_request) over a
synthetic tree and need no server. The live tree carries no non-birth
relationship at all, so there is nothing real to exercise here.
Assertions read the returned TraversalResult, never the patch's call
arguments.
"""

from unittest.mock import patch

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.traversal import Link, walk_ancestors, walk_descendants
from tests.traversal_transports import _ancestor_transport, _descendant_transport


class TestAncestorRelationships:
    async def test_adoptive_parents_are_labelled_and_their_lines_stop_there(self):
        # The adoptive parents' own ancestors are not the subject's
        # ancestors, so the walk names the adoptive parents and stops.
        tree = {
            "h1": {
                "name": "A",
                "families": [
                    {
                        "father": "hA",
                        "mother": "hB",
                        "frel": "Adopted",
                        "mrel": "Adopted",
                    }
                ],
            },
            "hA": {"name": "B", "families": [{"father": "hAA", "mother": "hAB"}]},
            "hB": {"name": "C", "families": []},
            "hAA": {"name": "D", "families": []},
            "hAB": {"name": "E", "families": []},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(tree)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 5)

        assert result.edges["h1"] == [
            Link(handle="hA", relation="Adopted", expand=False),
            Link(handle="hB", relation="Adopted", expand=False),
        ]
        # Fetched, so the renderer can name them rather than print a handle.
        assert set(result.nodes) == {"h1", "hA", "hB"}
        assert result.edges.get("hA", []) == []

    async def test_frel_and_mrel_are_read_independently_per_parent(self):
        # Gramps records one relationship per parent: a child can be the
        # birth child of the mother and the stepchild of her husband.
        tree = {
            "h1": {
                "name": "A",
                "families": [
                    {
                        "father": "hF",
                        "mother": "hM",
                        "frel": "Stepchild",
                        "mrel": "Birth",
                    }
                ],
            },
            "hF": {"name": "F", "families": [{"father": "hFF"}]},
            "hM": {"name": "M", "families": [{"father": "hMF"}]},
            "hFF": {"name": "FF", "families": []},
            "hMF": {"name": "MF", "families": []},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(tree)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 5)

        assert result.edges["h1"] == [
            Link(handle="hF", relation="Stepchild", expand=False),
            Link(handle="hM", relation=None, expand=True),
        ]
        # The birth line continues, the step line does not.
        assert "hMF" in result.nodes
        assert "hFF" not in result.nodes

    async def test_parent_family_beyond_the_first_is_marked_as_not_the_main_one(self):
        # Gramps designates the first parent family as the main one; the
        # rest are equally real but secondary, and must not read alike.
        tree = {
            "h1": {
                "name": "A",
                "families": [
                    {"father": "hF1", "mother": "hM1"},
                    {"father": "hF2", "mother": "hM2"},
                ],
            },
            "hF1": {"name": "F1", "families": []},
            "hM1": {"name": "M1", "families": []},
            "hF2": {"name": "F2", "families": []},
            "hM2": {"name": "M2", "families": []},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(tree)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 3)

        assert result.edges["h1"] == [
            Link(handle="hF1", relation=None, expand=True, secondary_family=False),
            Link(handle="hM1", relation=None, expand=True, secondary_family=False),
            Link(handle="hF2", relation=None, expand=True, secondary_family=True),
            Link(handle="hM2", relation=None, expand=True, secondary_family=True),
        ]

    async def test_a_parent_reached_as_both_adopted_and_birth_is_still_followed(self):
        # The same man is the subject's adoptive father in the main family
        # and his birth father in the second. The birth link wins: refusing
        # to follow it would drop a real biological lineage.
        tree = {
            "h1": {
                "name": "A",
                "families": [
                    {
                        "father": "hX",
                        "mother": "hY",
                        "frel": "Adopted",
                        "mrel": "Adopted",
                    },
                    {"father": "hX", "mother": "hZ", "frel": "Birth", "mrel": "Birth"},
                ],
            },
            "hX": {"name": "X", "families": [{"father": "hXF"}]},
            "hY": {"name": "Y", "families": []},
            "hZ": {"name": "Z", "families": []},
            "hXF": {"name": "XF", "families": []},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(tree)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 5)

        assert "hXF" in result.nodes
        assert result.edges["hX"] == [Link(handle="hXF", relation=None, expand=True)]

    async def test_unknown_and_none_relationships_are_reported_but_not_followed(self):
        # "birth or the lack of a qualifier" is what continues a lineage.
        # Unknown is a qualifier, and None asserts there is no relationship.
        tree = {
            "h1": {
                "name": "A",
                "families": [
                    {"father": "hF", "mother": "hM", "frel": "Unknown", "mrel": "None"}
                ],
            },
            "hF": {"name": "F", "families": [{"father": "hFF"}]},
            "hM": {"name": "M", "families": [{"father": "hMF"}]},
            "hFF": {"name": "FF", "families": []},
            "hMF": {"name": "MF", "families": []},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(tree)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 5)

        assert result.edges["h1"] == [
            Link(handle="hF", relation="Unknown", expand=False),
            Link(handle="hM", relation="None", expand=False),
        ]
        assert set(result.nodes) == {"h1", "hF", "hM"}

    async def test_a_custom_relationship_string_is_carried_through_verbatim(self):
        # Gramps allows a custom child reference type. Nothing may silently
        # promote an unrecognised string to a birth link.
        tree = {
            "h1": {
                "name": "A",
                "families": [
                    {
                        "father": "hF",
                        "mother": "hM",
                        "frel": "Mere porteuse",
                        "mrel": "Mere porteuse",
                    }
                ],
            },
            "hF": {"name": "F", "families": []},
            "hM": {"name": "M", "families": []},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(tree)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 3)

        assert [link.relation for link in result.edges["h1"]] == [
            "Mere porteuse",
            "Mere porteuse",
        ]
        assert all(link.expand is False for link in result.edges["h1"])

    async def test_a_family_without_a_child_ref_list_is_treated_as_a_birth_link(self):
        # The export omits frel/mrel when both are Birth, and a payload can
        # arrive without the entry at all. Absence means birth, not unknown.
        tree = {
            "h1": {"name": "A", "families": [{"father": "hF", "mother": "hM"}]},
            "hF": {"name": "F", "families": []},
            "hM": {"name": "M", "families": []},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(tree)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 3)

        assert result.edges["h1"] == [
            Link(handle="hF", relation=None, expand=True),
            Link(handle="hM", relation=None, expand=True),
        ]

    async def test_an_unexpanded_parent_is_still_fetched_so_it_can_be_named(self):
        # Stopping the lineage must not cost the foster parent's identity:
        # the renderer needs a profile, or the line degrades to a bare
        # handle and reads as a fetch failure. Fetched, named, not walked
        # through - the grandfather beyond is out of reach.
        tree = {
            "h1": {
                "name": "A",
                "families": [
                    {"father": "hA", "mother": "hB", "frel": "Foster", "mrel": "Foster"}
                ],
            },
            "hA": {"name": "Foster father", "families": [{"father": "hAA"}]},
            "hB": {"name": "Foster mother", "families": []},
            "hAA": {"name": "His own father", "families": []},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(tree)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 5)

        assert result.nodes["hA"]["name_display"] == "Foster father"
        assert "hAA" not in result.nodes
        assert result.truncated_by_cap is False


class TestDescendantRelationships:
    async def test_the_relationship_is_read_from_the_subjects_own_parent_role(self):
        # The subject is the mother here, so mrel is the relationship that
        # describes her link to the child - frel describes her husband's.
        tree = {
            "h1": {
                "name": "A",
                "families": [
                    {
                        "father": "hSpouse",
                        "mother": "h1",
                        "children": [
                            {"ref": "hc1", "frel": "Birth", "mrel": "Stepchild"},
                            {"ref": "hc2", "frel": "Birth", "mrel": "Birth"},
                        ],
                    }
                ],
            },
            "hc1": {
                "name": "C1",
                "families": [
                    {"father": "hc1", "children": [{"ref": "hg1", "frel": "Birth"}]}
                ],
            },
            "hc2": {
                "name": "C2",
                "families": [
                    {"father": "hc2", "children": [{"ref": "hg2", "frel": "Birth"}]}
                ],
            },
            "hg1": {"name": "G1", "families": []},
            "hg2": {"name": "G2", "families": []},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_descendant_transport(tree)
        ):
            result = await walk_descendants(GrampsWebAPIClient(), "default", "h1", 5)

        assert result.edges["h1"] == [
            Link(handle="hc1", relation="Stepchild", expand=False),
            Link(handle="hc2", relation=None, expand=True),
        ]
        # The stepchild's own children are not the subject's descendants.
        assert "hg1" not in result.nodes
        assert "hg2" in result.nodes

    async def test_the_fathers_relationship_is_used_when_the_subject_is_the_father(
        self,
    ):
        tree = {
            "h1": {
                "name": "A",
                "families": [
                    {
                        "father": "h1",
                        "mother": "hSpouse",
                        "children": [
                            {"ref": "hc1", "frel": "Adopted", "mrel": "Birth"}
                        ],
                    }
                ],
            },
            "hc1": {"name": "C1", "families": []},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_descendant_transport(tree)
        ):
            result = await walk_descendants(GrampsWebAPIClient(), "default", "h1", 5)

        assert result.edges["h1"] == [
            Link(handle="hc1", relation="Adopted", expand=False)
        ]
