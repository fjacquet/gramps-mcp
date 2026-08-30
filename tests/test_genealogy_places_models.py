# crewai_custom_tools/tests/test_genealogy_places_models.py
from src.gramps_mcp.genealogy.domain import (
    DatedChain,
    DatedName,
    PlaceLevel,
    ResolvedPlace,
)


def test_resolved_place_defaults_single_chain_roundtrip():
    rp = ResolvedPlace(
        name="Bourges",
        place_type="Municipality",
        lat="47.081",
        long="2.399",
        code="18033",
        chains=[
            DatedChain(
                levels=[
                    PlaceLevel(name="France", place_type="Country"),
                    PlaceLevel(name="Centre-Val de Loire", place_type="Region"),
                    PlaceLevel(name="Cher", place_type="Department", code="18"),
                ]
            )
        ],
        alt_names=[DatedName(value=", , Bourges, 18033, 18000, Cher, ...")],
        score=1.0,
        source="geo.api.gouv.fr",
        query="/communes/18033",
    )
    assert rp.chains[0].date_qualifier is None  # P1-P4 : chaîne unique non datée
    assert rp.ambiguous is False  # garde-fou d'ambiguïté, défaut
    assert ResolvedPlace(**rp.model_dump()) == rp  # round-trip
