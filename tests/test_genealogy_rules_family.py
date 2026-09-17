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


# --- Précision et modificateur de date, côté famille ---
#
# Un âge calculé depuis une date « avant 1400 » ou « vers 1880 » n'est pas un
# âge. Mesuré le 17/09/2026 : les pères d'âge négatif de la branche Cœur
# venaient tous de là.


def _facts(gid, sex, birth=None, death=None):
    return PersonFacts(
        gramps_id=gid,
        handle=gid,
        name=gid,
        surname=gid,
        given=gid,
        sex=sex,
        birth=birth,
        death=death,
        has_any_citation=True,
    )


def test_r3_silent_when_the_parent_birth_carries_a_modifier():
    """Pierre Cœur est né « avant 1400 », pas en 1400 : cas réel I1720."""
    father = _facts(
        "F",
        "M",
        birth=EventFact(
            type="Birth",
            sortval=2232400,
            year=1400,
            dateval=[0, 0, 1400, False],
            modifier=1,
        ),
    )
    child = _facts(
        "C",
        "M",
        birth=EventFact(
            type="Birth", sortval=2230575, year=1395, dateval=[0, 0, 1395, False]
        ),
    )
    fam = FamilyFacts(
        gramps_id="FAM",
        handle="FAM",
        father_handle="F",
        child_handles=["C"],
    )
    persons = {"F": father, "C": child}
    assert "R3" not in _rules(check_family(fam, persons))


def test_r3_still_fires_on_a_twelve_year_old_father():
    """Père né en 1767, enfant né le 28/01/1779 : cas réel I1220, vrai défaut."""
    father = _facts(
        "F",
        "M",
        birth=EventFact(
            type="Birth", sortval=2366120, year=1767, dateval=[0, 0, 1767, False]
        ),
    )
    child = _facts(
        "C",
        "M",
        birth=EventFact(
            type="Birth", sortval=2370508, year=1779, dateval=[28, 1, 1779, False]
        ),
    )
    fam = FamilyFacts(
        gramps_id="FAM",
        handle="FAM",
        father_handle="F",
        child_handles=["C"],
    )
    persons = {"F": father, "C": child}
    assert "R3" in _rules(check_family(fam, persons))


def test_r5_silent_when_the_mother_death_is_year_only_in_the_birth_year():
    mother = _facts(
        "M",
        "F",
        death=EventFact(
            type="Death", sortval=2371923, year=1782, dateval=[0, 0, 1782, False]
        ),
    )
    child = _facts(
        "C",
        "M",
        birth=EventFact(
            type="Birth", sortval=2372100, year=1782, dateval=[5, 7, 1782, False]
        ),
    )
    fam = FamilyFacts(
        gramps_id="FAM",
        handle="FAM",
        mother_handle="M",
        child_handles=["C"],
    )
    persons = {"M": mother, "C": child}
    assert "R5" not in _rules(check_family(fam, persons))


def test_r5_still_fires_when_the_father_died_eleven_months_earlier():
    """Jeanne VILLAUDY née le 02/10/1848, père mort le 11/11/1847 : I0113."""
    father = _facts(
        "F",
        "M",
        death=EventFact(
            type="Death", sortval=2395723, year=1847, dateval=[11, 11, 1847, False]
        ),
    )
    child = _facts(
        "C",
        "F",
        birth=EventFact(
            type="Birth", sortval=2396048, year=1848, dateval=[2, 10, 1848, False]
        ),
    )
    fam = FamilyFacts(
        gramps_id="FAM",
        handle="FAM",
        father_handle="F",
        child_handles=["C"],
    )
    persons = {"F": father, "C": child}
    assert "R5" in _rules(check_family(fam, persons))
