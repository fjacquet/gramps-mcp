"""Construction/validation des modèles de domaine de l'audit."""

from src.gramps_mcp.genealogy.domain import (
    Anomaly,
    DuplicateCandidate,
    EventFact,
    FamilyFacts,
    PersonFacts,
)


def test_eventfact_defaults():
    e = EventFact(type="Birth", sortval=2346578, year=1712)
    assert e.modifier == 0 and e.quality == 0 and e.has_citation is False


def test_personfacts_minimal_and_lists_default_empty():
    p = PersonFacts(
        gramps_id="I0001",
        handle="h1",
        name="Jean Test",
        surname="Test",
        given="Jean",
        sex="M",
    )
    assert p.birth is None and p.death is None
    assert p.events == [] and p.family_handles == [] and p.parent_family_handles == []
    assert p.has_any_citation is False


def test_familyfacts_and_anomaly_and_duplicate():
    f = FamilyFacts(gramps_id="F0001", handle="fh1")
    assert f.father_handle is None and f.child_handles == [] and f.marriage is None
    a = Anomaly(
        rule="R1",
        severity="haute",
        gramps_id="I0001",
        handle="h1",
        message="naissance après décès",
    )
    assert a.detail == {}
    d = DuplicateCandidate(
        gramps_id_a="I0001",
        gramps_id_b="I0002",
        score=0.91,
        reason="homonymes, naissances proches",
    )
    assert d.score == 0.91
