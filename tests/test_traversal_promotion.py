"""
Unit tests for reconciling links that reach the same relative twice.

A person can be reached by both a birth link and a non-birth one - a
grandfather who adopted his own grandchild is reached as an adoptive
father and again through the birth mother. The birth link must win
whatever order the two surface in, or real ancestry is lost to the
accident of discovery order.

These patch the transport seam over a synthetic tree and need no server.
"""

from unittest.mock import patch

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.handlers.traversal_handler import format_traversal
from src.gramps_mcp.traversal import walk_ancestors
from tests.traversal_transports import _ancestor_transport


class TestPromotionAcrossLevels:
    async def test_a_birth_link_found_a_level_later_reopens_the_lineage(self):
        # A grandfather adopting his own grandchild is one of the commonest
        # real adoption patterns. He is reached first as an adoptive father
        # (level 1, not followed), then again through the birth mother
        # (level 2) as her birth father. His own ancestry is the subject's
        # real ancestry and must not be lost to the order of discovery.
        tree = {
            "h1": {
                "name": "Child",
                "families": [
                    {"father": "hG", "mother": "hM", "frel": "Adopted", "mrel": "Birth"}
                ],
            },
            "hG": {"name": "Grandfather", "families": [{"father": "hGG"}]},
            "hM": {"name": "Birth mother", "families": [{"father": "hG"}]},
            "hGG": {"name": "Great-grandfather", "families": []},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(tree)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 6)

        assert "hGG" in result.nodes
        assert [link.handle for link in result.edges["hG"]] == ["hGG"]

    async def test_promotion_does_not_spin_on_a_cycle(self):
        # Re-queueing a promoted handle must be bounded, or a corrupted
        # tree that keeps re-offering the same person spins forever.
        tree = {
            "h1": {
                "name": "A",
                "families": [
                    {"father": "h2", "mother": "h3", "frel": "Adopted", "mrel": "Birth"}
                ],
            },
            "h2": {"name": "B", "families": [{"father": "h1", "mother": "h3"}]},
            "h3": {"name": "C", "families": [{"father": "h2"}]},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(tree)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 10)

        assert set(result.nodes) == {"h1", "h2", "h3"}

    async def test_one_link_per_relative_even_when_two_families_share_a_parent(self):
        # The same man as adoptive father in the main family and birth
        # father in the second yields two raw entries for one person. They
        # must reconcile into a single link, or the renderer prints him
        # twice and contradicts itself about whether his line was followed.
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

        targets = [link.handle for link in result.edges["h1"]]
        assert targets.count("hX") == 1
        # The birth link wins the reconciliation: he really is a birth
        # father, so the lineage through him is genuine.
        merged = next(link for link in result.edges["h1"] if link.handle == "hX")
        assert merged.expand is True
        assert merged.relation is None
        assert merged.secondary_family is False

    async def test_a_terminal_relative_refused_by_the_cap_leaves_no_dangling_edge(self):
        # The cap strips refused handles out of the edges already recorded.
        # A terminal relative is fetched like any other, so it must be
        # stripped the same way rather than surviving as a phantom line.
        tree = {
            "h1": {
                "name": "A",
                "families": [
                    {"father": "hA", "mother": "hB", "frel": "Foster", "mrel": "Foster"}
                ],
            },
            "hA": {"name": "B", "families": []},
            "hB": {"name": "C", "families": []},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(tree)
        ):
            result = await walk_ancestors(
                GrampsWebAPIClient(), "default", "h1", 5, visit_cap=1
            )

        assert result.truncated_by_cap is True
        assert set(result.nodes) == {"h1"}
        assert result.edges.get("h1", []) == []
        assert "not fetched" not in format_traversal(result, "ancestors")
