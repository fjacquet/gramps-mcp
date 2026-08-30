"""Tests par table des règles personne R1, R2, R6, R7, R8, R9 (pures, hors-ligne)."""

from src.gramps_mcp.genealogy.domain import EventFact, PersonFacts
from src.gramps_mcp.genealogy.rules import check_person


def _p(**kw):
    base = {
        "gramps_id": "I1",
        "handle": "h1",
        "name": "X",
        "surname": "X",
        "given": "x",
        "sex": "M",
        "has_any_citation": True,
    }
    base.update(kw)
    return PersonFacts(**base)


def _rules(anoms):
    return {a.rule for a in anoms}


def test_r1_birth_after_death():
    p = _p(
        birth=EventFact(type="Birth", sortval=2400000, year=1850),
        death=EventFact(type="Death", sortval=2390000, year=1820),
    )
    assert "R1" in _rules(check_person(p))


def test_r1_ok_when_order_correct():
    p = _p(
        birth=EventFact(type="Birth", sortval=2390000, year=1820),
        death=EventFact(type="Death", sortval=2400000, year=1850),
    )
    assert "R1" not in _rules(check_person(p))


def test_r2_age_over_105():
    # ~120 ans : 120 * 365.25 ≈ 43830 jours
    p = _p(
        birth=EventFact(type="Birth", sortval=2300000, year=1700),
        death=EventFact(type="Death", sortval=2343830, year=1820),
    )
    assert "R2" in _rules(check_person(p))


def test_r2_ok_normal_lifespan():
    p = _p(
        birth=EventFact(type="Birth", sortval=2300000, year=1700),
        death=EventFact(type="Death", sortval=2325000, year=1768),
    )
    assert "R2" not in _rules(check_person(p))


def test_r6_life_event_before_birth():
    p = _p(
        birth=EventFact(type="Birth", sortval=2400000, year=1850),
        death=EventFact(type="Death", sortval=2420000, year=1905),
        events=[EventFact(type="Marriage", sortval=2399000, year=1848)],
    )
    assert "R6" in _rules(check_person(p))


def test_r6_burial_after_death_is_not_flagged():
    p = _p(
        birth=EventFact(type="Birth", sortval=2400000, year=1850),
        death=EventFact(type="Death", sortval=2420000, year=1905),
        events=[EventFact(type="Burial", sortval=2420010, year=1905)],
    )
    assert "R6" not in _rules(check_person(p))


def test_r6_postmortem_event_before_birth_is_flagged():
    p = _p(
        birth=EventFact(type="Birth", sortval=2400000, year=1850),
        death=EventFact(type="Death", sortval=2420000, year=1905),
        events=[EventFact(type="Cremation", sortval=2390000, year=1820)],
    )
    assert "R6" in _rules(check_person(p))


def test_r7_baptism_before_birth():
    p = _p(
        birth=EventFact(type="Birth", sortval=2400000, year=1850),
        events=[EventFact(type="Baptism", sortval=2399990, year=1849)],
    )
    assert "R7" in _rules(check_person(p))


def test_r7_burial_before_death():
    p = _p(
        death=EventFact(type="Death", sortval=2420000, year=1905),
        events=[EventFact(type="Burial", sortval=2419990, year=1905)],
    )
    assert "R7" in _rules(check_person(p))


def test_r8_malformed_date_unsortable():
    # date présente (year renseigné) mais sortval == 0
    p = _p(
        events=[
            EventFact(
                type="Residence", sortval=0, year=1850, dateval=[0, 0, 1850, False]
            )
        ]
    )
    # year renseigné + sortval 0 → R8
    p.events[0].dateval = [40, 13, 1850, False]  # jour 40, mois 13 hors bornes
    assert "R8" in _rules(check_person(p))


def test_r9_no_citation():
    p = _p(has_any_citation=False)
    assert "R9" in _rules(check_person(p))


def test_r9_absent_when_cited():
    p = _p(has_any_citation=True)
    assert "R9" not in _rules(check_person(p))


def test_r8_undated_event_not_flagged():
    # événement sans date : dateval [0,0,0], year 0, sortval 0 → PAS d'anomalie
    p = _p(
        events=[
            EventFact(type="Residence", sortval=0, year=0, dateval=[0, 0, 0, False])
        ]
    )
    assert "R8" not in _rules(check_person(p))


def test_r8_aberrant_modifier_or_quality_is_flagged():
    p = _p(
        events=[
            EventFact(
                type="Birth",
                sortval=2400000,
                year=1850,
                dateval=[1, 1, 1850, False],
                modifier=99,
                quality=0,
            )
        ]
    )
    assert "R8" in _rules(check_person(p))


def test_r8_real_date_but_unsortable_is_flagged():
    # vraie date (année renseignée) mais non triable (sortval 0) → R8
    p = _p(
        events=[
            EventFact(type="Death", sortval=0, year=1850, dateval=[0, 0, 1850, False])
        ]
    )
    assert "R8" in _rules(check_person(p))


def test_d1_no_vital_date_flagged():
    assert "D1" in _rules(check_person(_p()))


def test_d1_absent_when_birth_present():
    p = _p(birth=EventFact(type="Birth", sortval=2400000, year=1850))
    assert "D1" not in _rules(check_person(p))


def test_d2_free_text_date_flagged():
    p = _p(
        events=[
            EventFact(
                type="Death", sortval=0, year=0, modifier=6, dateval=[0, 0, 0, False]
            )
        ]
    )
    assert "D2" in _rules(check_person(p))


def test_d2_absent_for_normal_date():
    p = _p(events=[EventFact(type="Death", sortval=2400000, year=1850, modifier=0)])
    assert "D2" not in _rules(check_person(p))


def test_d3_unknown_gender_flagged():
    assert "D3" in _rules(check_person(_p(sex="U")))


def test_d3_absent_for_known_gender():
    assert "D3" not in _rules(check_person(_p(sex="F")))
