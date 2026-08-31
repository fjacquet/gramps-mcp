"""Tests du détecteur de doublons R10 (pur)."""

from src.gramps_mcp.genealogy.domain import EventFact, PersonFacts
from src.gramps_mcp.genealogy.duplicates import (
    find_duplicates,
    normalize_name,
)


def _p(gid, given, surname, birth_year):
    return PersonFacts(
        gramps_id=gid,
        handle=gid,
        name=f"{given} {surname}",
        surname=surname,
        given=given,
        sex="M",
        birth=EventFact(type="Birth", sortval=birth_year * 366, year=birth_year),
        has_any_citation=True,
    )


def test_normalize_strips_accents_and_case():
    assert normalize_name("Frédéric  DUPONT") == "frederic dupont"


def test_finds_near_homonyms_with_close_birth_years():
    people = [_p("I1", "Jean", "Dupont", 1850), _p("I2", "Jean", "Dupond", 1851)]
    dups = find_duplicates(people)
    assert len(dups) == 1
    assert {dups[0].gramps_id_a, dups[0].gramps_id_b} == {"I1", "I2"}
    assert dups[0].score >= 0.85


def test_ignores_when_birth_years_too_far_apart():
    people = [_p("I1", "Jean", "Dupont", 1850), _p("I2", "Jean", "Dupont", 1860)]
    assert find_duplicates(people) == []


def test_ignores_different_names():
    people = [_p("I1", "Jean", "Dupont", 1850), _p("I2", "Marie", "Lefevre", 1850)]
    assert find_duplicates(people) == []


def test_ignores_persons_without_birth_year():
    p1 = PersonFacts(
        gramps_id="I1",
        handle="I1",
        name="Jean Dupont",
        surname="Dupont",
        given="Jean",
        sex="M",
        has_any_citation=True,
    )
    p2 = PersonFacts(
        gramps_id="I2",
        handle="I2",
        name="Jean Dupont",
        surname="Dupont",
        given="Jean",
        sex="M",
        has_any_citation=True,
    )
    assert find_duplicates([p1, p2]) == []


def test_ignores_blank_name_persons():
    def _blank(gid, year):
        return PersonFacts(
            gramps_id=gid,
            handle=gid,
            name="",
            surname="",
            given="",
            sex="U",
            birth=EventFact(type="Birth", sortval=year * 366, year=year),
            has_any_citation=True,
        )

    assert find_duplicates([_blank("I1", 1850), _blank("I2", 1851)]) == []
