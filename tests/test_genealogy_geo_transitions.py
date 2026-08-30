from src.gramps_mcp.genealogy.domain import (
    DatedChain,
    ParsedPlace,
    PlaceLevel,
    ResolvedPlace,
)
from src.gramps_mcp.genealogy.geo.transitions import (
    Transition,
    apply_transition,
)


def _base(country):
    return ResolvedPlace(
        name="Alger",
        place_type="Municipality",
        score=0.9,
        source="Nominatim/OSM",
        query="q",
        chains=[DatedChain(levels=[PlaceLevel(name=country, place_type="Country")])],
    )


def test_empty_transitions_leave_single_undated_chain():
    parsed = ParsedPlace(raw="…", commune="Alger", country="Algérie")
    out = apply_transition(_base("Algérie"), parsed, [])
    assert len(out.chains) == 1 and out.chains[0].date_qualifier is None


def test_one_transition_row_yields_two_dated_chains_and_dated_altname():
    t = Transition(
        modern_country="Algérie",
        historical_country="Algérie française",
        historical_parent="France",
        date="1962-07-05",
    )
    parsed = ParsedPlace(
        raw=", , Alger, , , Alger, , France",
        commune="Alger",
        departement="Alger",
        country="Algérie",
    )
    out = apply_transition(_base("Algérie"), parsed, [t])
    quals = sorted(c.date_qualifier for c in out.chains)
    assert quals == ["après 1962-07-05", "avant 1962-07-05"]
    hist = next(c for c in out.chains if c.date_qualifier.startswith("avant"))
    names = [lvl.name for lvl in hist.levels]
    assert names[0] == "France" and "Algérie française" in names and "Alger" in names
    assert out.alt_names[0].date_qualifier == "avant 1962-07-05"


def test_transition_not_matching_country_is_noop():
    t = Transition(
        modern_country="Algérie",
        historical_country="Algérie française",
        historical_parent="France",
        date="1962-07-05",
    )
    out = apply_transition(
        _base("Italie"), ParsedPlace(raw="…", commune="Roma", country="Italie"), [t]
    )
    assert len(out.chains) == 1 and out.chains[0].date_qualifier is None
