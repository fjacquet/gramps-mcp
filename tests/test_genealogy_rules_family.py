"""Tests des règles famille R3, R4, R5 (pures)."""

from src.gramps_mcp.genealogy.domain import (
    EventFact,
    FamilyFacts,
    PersonFacts,
)
from src.gramps_mcp.genealogy.rules import check_family


def _person(
    hid, sex, birth_sort=None, birth_year=None, death_sort=None, death_year=None
):
    b = (
        EventFact(type="Birth", sortval=birth_sort, year=birth_year)
        if birth_sort
        else None
    )
    d = (
        EventFact(type="Death", sortval=death_sort, year=death_year)
        if death_sort
        else None
    )
    return PersonFacts(
        gramps_id=hid,
        handle=hid,
        name=hid,
        surname=hid,
        given=hid,
        sex=sex,
        birth=b,
        death=d,
        has_any_citation=True,
    )


def _rules(anoms):
    return {a.rule for a in anoms}


def test_r3_mother_too_old():
    mother = _person("M", "F", birth_sort=2300000, birth_year=1700)
    # enfant né ~60 ans après la naissance de la mère : 60*365.25≈21915
    child = _person("C", "M", birth_sort=2321915, birth_year=1760)
    fam = FamilyFacts(
        gramps_id="F1", handle="F1", mother_handle="M", child_handles=["C"]
    )
    anoms = check_family(fam, {"M": mother, "C": child})
    assert "R3" in _rules(anoms)
    assert any(a.gramps_id == "C" for a in anoms if a.rule == "R3")


def test_r3_father_too_old():
    father = _person("P", "M", birth_sort=2300000, birth_year=1700)
    child = _person("C", "M", birth_sort=2330000, birth_year=1782)  # ~82 ans
    fam = FamilyFacts(
        gramps_id="F1", handle="F1", father_handle="P", child_handles=["C"]
    )
    assert "R3" in _rules(check_family(fam, {"P": father, "C": child}))


def test_r3_ok_normal_ages():
    mother = _person("M", "F", birth_sort=2300000, birth_year=1700)
    child = _person("C", "M", birth_sort=2309131, birth_year=1725)  # ~25 ans
    fam = FamilyFacts(
        gramps_id="F1", handle="F1", mother_handle="M", child_handles=["C"]
    )
    assert "R3" not in _rules(check_family(fam, {"M": mother, "C": child}))


def test_r4_marriage_before_13():
    wife = _person("W", "F", birth_sort=2300000, birth_year=1700)
    fam = FamilyFacts(
        gramps_id="F1",
        handle="F1",
        mother_handle="W",
        marriage=EventFact(type="Marriage", sortval=2303652, year=1710),
    )  # ~10 ans
    assert "R4" in _rules(check_family(fam, {"W": wife}))


def test_r5_child_after_mother_death():
    mother = _person(
        "M",
        "F",
        birth_sort=2300000,
        birth_year=1700,
        death_sort=2320000,
        death_year=1755,
    )
    child = _person("C", "M", birth_sort=2320500, birth_year=1756)  # après décès mère
    fam = FamilyFacts(
        gramps_id="F1", handle="F1", mother_handle="M", child_handles=["C"]
    )
    assert "R5" in _rules(check_family(fam, {"M": mother, "C": child}))


def test_r5_child_within_9_months_of_father_death_is_ok():
    father = _person(
        "P",
        "M",
        birth_sort=2300000,
        birth_year=1700,
        death_sort=2320000,
        death_year=1755,
    )
    child = _person("C", "M", birth_sort=2320100, birth_year=1755)  # 100 j après, < 280
    fam = FamilyFacts(
        gramps_id="F1", handle="F1", father_handle="P", child_handles=["C"]
    )
    assert "R5" not in _rules(check_family(fam, {"P": father, "C": child}))
