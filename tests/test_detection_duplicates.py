"""Tests for the find_duplicates tool and its rendering."""

from src.gramps_mcp.genealogy.domain import MergeCluster, PersonFacts
from src.gramps_mcp.handlers.duplicates_handler import format_duplicate_clusters


class TestDuplicateRendering:
    def test_it_names_the_surviving_record(self):
        phoenix = PersonFacts(
            handle="a",
            gramps_id="I0001",
            name="Jean Jacquet",
            surname="Jacquet",
            given="Jean",
            sex="M",
        )
        titanic = PersonFacts(
            handle="b",
            gramps_id="I0002",
            name="Jean Jacquet",
            surname="Jacquet",
            given="Jean",
            sex="M",
        )
        cluster = MergeCluster(
            phoenix_handle="a",
            phoenix_gramps_id="I0001",
            titanic_handles=["b"],
            titanic_gramps_ids=["I0002"],
        )

        text = format_duplicate_clusters(
            [cluster],
            [],
            {"a": phoenix, "b": titanic},
            skipped=0,
            partial=False,
            error=None,
        )

        assert "I0001" in text
        assert "I0002" in text
        assert "survives" in text.lower()

    def test_an_arbitration_pair_is_not_presented_as_proved(self):
        from src.gramps_mcp.genealogy.domain import MergePair

        pair = MergePair(
            gramps_id_a="I0003",
            gramps_id_b="I0004",
            handle_a="c",
            handle_b="d",
            tier="arbitrage",
            regle="",
            blocs=["pho:JCQ"],
        )

        text = format_duplicate_clusters(
            [], [pair], {}, skipped=0, partial=False, error=None
        )

        assert "I0003" in text
        assert "arbitration" in text.lower() or "review" in text.lower()

    def test_a_partial_scan_says_so(self):
        text = format_duplicate_clusters(
            [], [], {}, skipped=0, partial=True, error="connection reset"
        )

        assert "partial" in text.lower()
        assert "connection reset" in text

    def test_skipped_records_are_reported(self):
        text = format_duplicate_clusters(
            [], [], {}, skipped=3, partial=False, error=None
        )

        assert "3" in text
