"""Tests for the find_duplicates tool and its rendering."""

from unittest.mock import AsyncMock, patch

from src.gramps_mcp.genealogy.collect import CollectResult
from src.gramps_mcp.genealogy.domain import EventFact, MergeCluster, PersonFacts
from src.gramps_mcp.handlers.duplicates_handler import format_duplicate_clusters
from src.gramps_mcp.tools.detection import find_duplicates_tool


def _naissance(jour: int, mois: int, annee: int) -> EventFact:
    """A birth event with day-precision, per test_genealogy_merge_tiers.py."""
    return EventFact(
        type="Birth",
        sortval=annee * 366 + mois * 31 + jour,
        year=annee,
        modifier=0,
        dateval=[jour, mois, annee, False],
    )


def _person(
    gid: str, given: str, surname: str, birth: EventFact | None = None
) -> PersonFacts:
    return PersonFacts(
        gramps_id=gid,
        handle=f"h{gid}",
        name=f"{given} {surname}",
        surname=surname,
        given=given,
        sex="U",
        birth=birth,
    )


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

    def test_a_gender_patch_is_rendered_before_merging(self):
        """Pins the gender-patch line _format_cluster renders (duplicates_handler.py:69-74).

        `Person.merge()` does not carry gender across a merge (spec §2), so
        when the phoenix's own gender is unknown and a titanic's is not, the
        cluster carries the gender to write onto the phoenix first. If that
        block were deleted, this is the test that would catch it - nothing
        else in this module constructs a cluster with `gender_patch` set.
        """
        phoenix = PersonFacts(
            handle="a",
            gramps_id="I0001",
            name="Jacquet",
            surname="Jacquet",
            given="",
            sex="U",
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
            gender_patch=1,
        )

        text = format_duplicate_clusters(
            [cluster],
            [],
            {"a": phoenix, "b": titanic},
            skipped=0,
            partial=False,
            error=None,
        )

        assert "gender" in text.lower()
        assert "before merging" in text.lower()


class TestFindDuplicatesToolRouting:
    """Proves the tool - not just the handler - routes each tier correctly.

    Constructs six people through the real `etager`/`plan_fusions` pipeline
    (only `collect_tree` is patched, to avoid a live server): two land in
    `tier == "auto"` via an exact shared birth date, two in `tier ==
    "arbitrage"` via a shared full name with no date match, and two in
    `tier == "rejet"` via phonetic resemblance alone. Verified once offline
    with a standalone script before writing this test that these six produce
    exactly one auto pair, one arbitrage pair, and one rejet pair, with no
    cross-group blocking collisions.
    """

    async def test_each_tier_lands_under_the_right_heading_or_nowhere(self):
        proved_a = _person("I0001", "Jean", "Dupont", _naissance(3, 4, 1850))
        proved_b = _person("I0002", "Jean", "Dupont", _naissance(3, 4, 1850))
        arbitration_a = _person("I0003", "Paul", "Curnier", _naissance(3, 4, 1822))
        arbitration_b = _person("I0004", "Paul", "Curnier", _naissance(3, 4, 1850))
        rejet_a = _person("I0005", "Henri", "Dupont")
        rejet_b = _person("I0006", "Henri", "Dupond")

        collected = CollectResult(
            people=[
                proved_a,
                proved_b,
                arbitration_a,
                arbitration_b,
                rejet_a,
                rejet_b,
            ],
            families={},
            skipped=0,
            partial=False,
            error=None,
        )

        with patch(
            "src.gramps_mcp.tools.detection.collect_tree",
            new_callable=AsyncMock,
            return_value=collected,
        ):
            result = await find_duplicates_tool({})

        text = result[0].text

        proved_heading = text.index("Proved duplicates")
        arbitration_heading = text.index("Needs human arbitration")

        # The proved pair is named after the proved heading and before the
        # arbitration heading.
        assert proved_heading < text.index("I0001") < arbitration_heading
        assert proved_heading < text.index("I0002") < arbitration_heading

        # The arbitration pair is named after the arbitration heading.
        assert arbitration_heading < text.index("I0003")
        assert arbitration_heading < text.index("I0004")

        # The rejet pair - name resemblance alone - is never a proof and
        # must not appear anywhere in the output.
        assert "I0005" not in text
        assert "I0006" not in text
