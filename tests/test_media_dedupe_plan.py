"""
Which media record survives a checksum group, and which are absorbed.

The choice is not cosmetic: the survivor keeps its gramps_id, and every
citation pointing at an absorbed record is repointed at it. Picking a bare
record over a described one loses the description; picking a record with
no backlinks over one with several is harmless but leaves the tree's own
identifiers churned for nothing.
"""

from scripts.dedupe_media import choose_keeper, plan_merges


def _media(gramps_id, checksum, backlinks=0, desc=""):
    """Build the subset of a media object the planner reads."""
    return {
        "gramps_id": gramps_id,
        "handle": f"h-{gramps_id}",
        "checksum": checksum,
        "desc": desc,
        "backlinks": {"citation": [f"c{i}" for i in range(backlinks)]},
    }


class TestChooseKeeper:
    """The survivor of one checksum group."""

    def test_the_most_referenced_record_survives(self):
        group = [_media("O0002", "x", backlinks=1), _media("O0001", "x", backlinks=3)]
        assert choose_keeper(group)["gramps_id"] == "O0001"

    def test_a_description_breaks_a_tie_on_backlinks(self):
        group = [
            _media("O0001", "x", backlinks=1),
            _media("O0002", "x", backlinks=1, desc="Acte de naissance"),
        ]
        assert choose_keeper(group)["gramps_id"] == "O0002"

    def test_the_oldest_identifier_breaks_a_full_tie(self):
        # Reason: gramps_id is assigned in creation order, so the lowest is
        # the original and the others are the retries that duplicated it.
        group = [_media("O0771", "x"), _media("O0765", "x"), _media("O0768", "x")]
        assert choose_keeper(group)["gramps_id"] == "O0765"


class TestPlanMerges:
    """Which merges the whole tree needs."""

    def test_a_unique_checksum_produces_no_merge(self):
        assert plan_merges([_media("O0001", "a"), _media("O0002", "b")]) == []

    def test_every_duplicate_is_merged_into_one_survivor(self):
        media = [
            _media("O0001", "a", backlinks=2),
            _media("O0002", "a"),
            _media("O0003", "a"),
            _media("O0004", "b"),
        ]
        plan = plan_merges(media)
        assert [(k["gramps_id"], t["gramps_id"]) for k, t in plan] == [
            ("O0001", "O0002"),
            ("O0001", "O0003"),
        ]

    def test_a_record_without_a_checksum_is_never_merged(self):
        # Reason: an empty checksum is not evidence of identical content -
        # it is evidence the server never computed one. Merging on it would
        # destroy unrelated records.
        media = [_media("O0001", ""), _media("O0002", ""), _media("O0003", None)]
        assert plan_merges(media) == []
