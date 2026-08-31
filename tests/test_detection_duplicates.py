"""Tests for the find_duplicates tool and its rendering."""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.gramps_mcp.genealogy.collect import CollectResult
from src.gramps_mcp.genealogy.domain import (
    EventFact,
    FamilyFacts,
    MergeCluster,
    PersonFacts,
)
from src.gramps_mcp.handlers.duplicates_handler import format_duplicate_clusters
from src.gramps_mcp.models.parameters.detection_params import FindDuplicatesParams
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

    def test_ignored_blocking_keys_are_reported(self):
        """Pins the ignored-key count added alongside the arbitrage fix:
        etager()'s second return value (blocking keys dropped for covering
        more than MAX_BLOC people) must be visible, or a narrowed scan
        reads as a full one.
        """
        text = format_duplicate_clusters(
            [], [], {}, skipped=0, partial=False, error=None, ignored=2
        )

        assert "2" in text
        assert "blocking key" in text.lower()

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


class TestLimitRejectsZeroAndNegative:
    """`raw_people[:limit] if limit else raw_people` (genealogy/collect.py)
    tested truthiness, so limit=0 ("stop after zero people") was
    indistinguishable from limit=None ("no limit") and scanned the whole
    tree; a negative limit silently drops items from the end via Python
    slicing. `ge=1` on the parameter model rejects both before they reach
    collect_tree.
    """

    @pytest.mark.parametrize("bad_limit", [0, -1, -5])
    def test_non_positive_limit_is_rejected(self, bad_limit):
        with pytest.raises(ValidationError):
            FindDuplicatesParams(limit=bad_limit)

    def test_positive_limit_is_accepted(self):
        assert FindDuplicatesParams(limit=1).limit == 1


class TestRelativesAreNotArbitrationCandidates:
    """A married couple and their children only ever share a family, never a
    name-derived blocking key (`nom:`, `pho:`, `an:` - see
    `genealogy.duplicates.blocking_keys`). Sharing a family alone
    (`fam:`/`par:`) is not evidence of a duplicate - every spouse and every
    sibling in the tree would otherwise be reported as a "candidate".

    Verified by execution before the fix: with the arbitrage filter absent,
    this family of five (one couple, three children) produced exactly four
    arbitration pairs - the couple, plus all three sibling pairs - none of
    them a duplicate.
    """

    async def test_no_spouse_or_sibling_pair_is_reported(self):
        father = _person("I0001", "Jean", "Sestre")
        mother = _person("I0002", "Marie", "Villaudy")
        child_a = _person("I0003", "Paul", "Sestre")
        child_b = _person("I0004", "Louise", "Sestre")
        child_c = _person("I0005", "Marc", "Sestre")

        father.family_handles = ["hF1"]
        mother.family_handles = ["hF1"]
        for child in (child_a, child_b, child_c):
            child.parent_family_handles = ["hF1"]

        family = FamilyFacts(
            gramps_id="F0001",
            handle="hF1",
            father_handle="hI0001",
            mother_handle="hI0002",
            child_handles=["hI0003", "hI0004", "hI0005"],
        )

        collected = CollectResult(
            people=[father, mother, child_a, child_b, child_c],
            families={"hF1": family},
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

        assert "Needs human arbitration" not in text
        for gramps_id in ("I0001", "I0002", "I0003", "I0004", "I0005"):
            assert gramps_id not in text


class TestSiblingsAreNotArbitrationCandidates:
    """Siblings sharing a surname and born close together also share an
    `an:` blocking key (surname + birth-year +/-2 window -
    `genealogy.duplicates.blocking_keys`) even with no shared `nom:`/`pho:`
    key at all - `an:` carries no given-name test whatsoever. The previous
    class (`TestRelativesAreNotArbitrationCandidates`) could not catch this:
    its children have no birth dates, so no `an:` key is ever emitted -
    `EventFact.year` defaults to `None` and blocking_keys only builds an an:
    key when `p.birth.year` is truthy.

    These two siblings are given real birth dates one and two years apart
    (with `year` set), sharing different given-name initials (Paul/Louise,
    so no `pho:` collision) and no full-name match (so no `nom:` collision
    either) - the only key they share is `an:sestre:1850`. Proof this test
    is load-bearing: against the pre-fix filter
    (`any(b.startswith(("nom:", "pho:", "an:")) ...)`)  it fails, asserting
    "Needs human arbitration" is present and I0003/I0004 are named; against
    the fixed filter (`nom:`/`pho:` only) it passes.
    """

    async def test_siblings_born_close_together_are_not_reported(self):
        child_a = _person("I0003", "Paul", "Sestre", _naissance(3, 4, 1850))
        child_b = _person("I0004", "Louise", "Sestre", _naissance(6, 9, 1852))

        child_a.parent_family_handles = ["hF1"]
        child_b.parent_family_handles = ["hF1"]

        family = FamilyFacts(
            gramps_id="F0001",
            handle="hF1",
            father_handle="hI0001",
            mother_handle="hI0002",
            child_handles=["hI0003", "hI0004"],
        )

        collected = CollectResult(
            people=[child_a, child_b],
            families={"hF1": family},
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

        assert "Needs human arbitration" not in text
        assert "I0003" not in text
        assert "I0004" not in text
