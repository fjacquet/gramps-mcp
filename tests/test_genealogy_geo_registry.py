import pytest

from src.gramps_mcp.genealogy.domain import ParsedPlace, ResolvedPlace
from src.gramps_mcp.genealogy.geo import registry


def _rp(score, ambiguous=False):
    return ResolvedPlace(
        name="X",
        place_type="Municipality",
        score=score,
        ambiguous=ambiguous,
        source="s",
        query="q",
    )


def test_route_france_uses_fr_resolver(monkeypatch):
    called = {}
    monkeypatch.setattr(
        registry, "resolve_fr", lambda p: called.setdefault("fr", _rp(1.0))
    )
    monkeypatch.setattr(registry, "resolve_world", lambda p: _rp(0.5))
    out = registry.resolve_place(
        ParsedPlace(raw="…", commune="Bourges", insee="18033", country="France")
    )
    assert out.score == 1.0 and "fr" in called  # FR autoritaire, pas de repli


def test_route_falls_back_to_world_when_country_resolver_returns_none(monkeypatch):
    monkeypatch.setattr(
        registry, "resolve_fr", lambda p: None
    )  # pas d'INSEE utilisable
    monkeypatch.setattr(registry, "resolve_world", lambda p: _rp(0.93))
    out = registry.resolve_place(
        ParsedPlace(raw="…", commune="X", insee=None, country="France", shifted=True)
    )
    assert out.score == 0.93  # repli mondial


def test_decide_action_thresholds():
    assert registry.decide_action(_rp(1.0), 0.90) == "ecrire"
    assert registry.decide_action(_rp(0.92), 0.90) == "ecrire"
    assert registry.decide_action(_rp(0.92, ambiguous=True), 0.90) == "proposition"
    assert registry.decide_action(_rp(0.80), 0.90) == "proposition"
    assert registry.decide_action(None, 0.90) == "indecidable"


def test_ambiguous_forces_proposition_even_at_score_1():
    rp = _rp(1.0, ambiguous=True)
    assert registry.decide_action(rp, 0.90) == "proposition"
    assert registry.confiance_of(rp) == "basse"


def test_registry_falls_through_to_ex_commune_when_resolve_fr_none(monkeypatch):
    from src.gramps_mcp.genealogy.domain import (
        DatedChain,
        ParsedPlace,
        PlaceLevel,
        ResolvedPlace,
    )
    from src.gramps_mcp.genealogy.geo import registry

    france = PlaceLevel(name="France", place_type="Country")
    sentinel = ResolvedPlace(
        name="Saint-Agnant-sous-les-Côtes",
        place_type="Municipality",
        code="55451",
        chains=[
            DatedChain(levels=[france], date_qualifier="avant 1973-01-01"),
            DatedChain(levels=[france], date_qualifier="après 1973-01-01"),
        ],
        score=1.0,
        source="ex-commune",
        query="",
    )
    monkeypatch.setattr(registry, "resolve_fr", lambda p: None)
    monkeypatch.setattr(registry, "resolve_fr_ex_commune", lambda p: sentinel)
    monkeypatch.setattr(
        registry, "resolve_world", lambda p: pytest.fail("Nominatim atteint")
    )

    got = registry.resolve_place(
        ParsedPlace(raw="", commune="Saint-Agnant-sous-les-Côtes", country="France")
    )
    assert got is not None and got.code == "55451"
    # resolve_place applique apply_transition en sortie. transitions.csv ne contient
    # aucune ligne dont modern_country == "France" (la France n'y figure que comme
    # historical_parent), donc les deux chaînes datées doivent survivre intactes.
    # Cette assertion est le garde-fou : ajouter une ligne "France" au dataset
    # écraserait silencieusement les rattachements des ex-communes.
    assert [c.date_qualifier for c in got.chains] == [
        "avant 1973-01-01",
        "après 1973-01-01",
    ]


def test_registry_live_commune_never_reaches_ex_commune_path(monkeypatch):
    from src.gramps_mcp.genealogy.domain import (
        DatedChain,
        ParsedPlace,
        PlaceLevel,
        ResolvedPlace,
    )
    from src.gramps_mcp.genealogy.geo import registry

    bourges = ResolvedPlace(
        name="Bourges",
        place_type="Municipality",
        code="18033",
        chains=[DatedChain(levels=[PlaceLevel(name="France", place_type="Country")])],
        score=1.0,
        source="geo.api.gouv.fr",
        query="",
    )
    monkeypatch.setattr(registry, "resolve_fr", lambda p: bourges)
    monkeypatch.setattr(
        registry,
        "resolve_fr_ex_commune",
        lambda p: pytest.fail("chemin ex-commune emprunté à tort"),
    )

    got = registry.resolve_place(
        ParsedPlace(raw="", commune="Bourges", country="France")
    )
    assert got is not None and got.code == "18033"


def test_registry_ambiguous_live_commune_does_not_fall_through(monkeypatch):
    # Un résultat ambigu est truthy : il ne doit PAS déclencher le repli ex-commune.
    from src.gramps_mcp.genealogy.domain import (
        DatedChain,
        ParsedPlace,
        PlaceLevel,
        ResolvedPlace,
    )
    from src.gramps_mcp.genealogy.geo import registry

    ambigu = ResolvedPlace(
        name="Sainte-Marie",
        place_type="Municipality",
        code="97418",
        chains=[DatedChain(levels=[PlaceLevel(name="France", place_type="Country")])],
        score=1.0,
        ambiguous=True,
        source="geo.api.gouv.fr",
        query="",
    )
    monkeypatch.setattr(registry, "resolve_fr", lambda p: ambigu)
    monkeypatch.setattr(
        registry,
        "resolve_fr_ex_commune",
        lambda p: pytest.fail("repli sur une résolution ambiguë"),
    )

    got = registry.resolve_place(
        ParsedPlace(raw="", commune="Sainte-Marie", country="France")
    )
    assert got is not None and got.ambiguous is True
