# tests/test_genealogy_geo_nominatim.py
from src.gramps_mcp.genealogy.domain import ParsedPlace
from src.gramps_mcp.genealogy.geo.nominatim import map_nominatim

RESULTS = [
    {
        "display_name": "Alger, Algérie",
        "lat": "36.7538",
        "lon": "3.0588",
        "importance": 0.82,
    },
    {"display_name": "Alger (autre)", "lat": "0", "lon": "0", "importance": 0.40},
]


def test_map_nominatim_score_and_gps():
    parsed = ParsedPlace(raw="…", commune="Alger", country="Algérie")
    rp = map_nominatim(RESULTS, parsed)
    assert rp.lat == "36.7538" and rp.long == "3.0588"
    assert rp.source == "Nominatim/OSM"
    assert 0.0 < rp.score <= 1.0
    # Les deux candidats partagent le même nom-cœur "Alger" (le suffixe "(autre)" est une
    # décoration retirée par best_similarity) : score plein pour les deux -> ambiguïté réelle.
    # Avant le fix, la depression par `importance` (0.82 vs 0.40) masquait cette ambiguïté.
    assert rp.ambiguous is True
    assert rp.chains[0].levels[0].name == "Algérie"  # pays parent depuis parsed.country


def test_map_nominatim_empty_returns_none():
    assert map_nominatim([], ParsedPlace(raw="x", commune="Nowhere")) is None


def test_map_nominatim_picks_best_score_not_first():
    # results[0] a une importance élevée mais un mauvais match de nom ;
    # results[1] est le bon lieu -> l'argmax du fuzzy_score doit choisir results[1].
    parsed = ParsedPlace(raw="…", commune="Roma", country="Italie")
    results = [
        {
            "display_name": "Grande Raccordo Anulare, Italia",
            "lat": "41.9",
            "lon": "12.5",
            "importance": 0.9,
        },
        {
            "display_name": "Roma, Italia",
            "lat": "41.9028",
            "lon": "12.4964",
            "importance": 0.6,
        },
    ]
    rp = map_nominatim(results, parsed)
    assert rp.name == "Roma"  # results[1], choisi par score, pas results[0]
    assert rp.lat == "41.9028" and rp.long == "12.4964"


def test_map_nominatim_ignores_low_importance_on_exact_name():
    from src.gramps_mcp.genealogy.domain import ParsedPlace
    from src.gramps_mcp.genealogy.geo.nominatim import map_nominatim

    results = [
        {
            "display_name": "Stuttgart, Bade-Wurtemberg, Allemagne",
            "lat": "48.77",
            "lon": "9.18",
            "importance": 0.25,
        }
    ]
    rp = map_nominatim(
        results, ParsedPlace(raw="", commune="Stuttgart", country="Allemagne")
    )
    assert rp is not None
    assert rp.score == 1.0  # was ~0.25 * 1.0 before
    assert rp.lat == "48.77" and rp.long == "9.18"


def test_map_nominatim_multiscript_core_match():
    from src.gramps_mcp.genealogy.domain import ParsedPlace
    from src.gramps_mcp.genealogy.geo.nominatim import map_nominatim

    results = [
        {
            "display_name": "Annaba ⵄⴻⵍⵃⴲⵃ عنابة, Algérie",
            "lat": "36.9",
            "lon": "7.76",
            "importance": 0.3,
        }
    ]
    rp = map_nominatim(
        results, ParsedPlace(raw="", commune="Annaba", country="Algérie")
    )
    assert rp.score == 1.0
