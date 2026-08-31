from src.gramps_mcp.genealogy.geo.score import (
    fuzzy_score,
    is_ambiguous,
    similarity,
)


def test_similarity_accent_and_case_insensitive():
    assert similarity("Zürich", "ZURICH") > 0.99


def test_fuzzy_score_penalizes_wrong_name():
    good = fuzzy_score(0.9, "Bourges", "Bourges")
    bad = fuzzy_score(0.9, "Bourges", "Paris")
    assert good > bad
    assert 0.0 <= bad <= good <= 1.0


def test_ambiguity_margin():
    assert is_ambiguous([0.95, 0.90]) is True  # marge 0.05 < 0.10
    assert is_ambiguous([0.95, 0.70]) is False  # marge 0.25 ≥ 0.10
    assert is_ambiguous([0.95]) is False  # un seul candidat


def test_best_similarity_strips_paren_suffix():
    from src.gramps_mcp.genealogy.geo.score import best_similarity

    assert best_similarity("Lausanne", "Lausanne (VD)") == 1.0
    assert best_similarity("Bern", "Bern (BE)") == 1.0


def test_best_similarity_multiscript_token():
    from src.gramps_mcp.genealogy.geo.score import best_similarity

    assert best_similarity("Annaba", "Annaba ⵄⴻⵍⵃⴲⵃ عنابة") == 1.0


def test_best_similarity_monotone_ge_similarity():
    from src.gramps_mcp.genealogy.geo.score import best_similarity, similarity

    for a, b in [
        ("Lausanne", "Lausanne (VD)"),
        ("Aix en Provence", "Aix-en-Provence"),
        ("Paris", "Marseille"),
        ("x", "y"),
        ("", ""),
        ("", "   "),
        ("Paris", ""),
    ]:
        assert best_similarity(a, b) >= similarity(a, b)


def test_best_similarity_no_substring_inflation():
    from src.gramps_mcp.genealogy.geo.score import best_similarity

    # a shorter query must not reach 1.0 against a longer token
    assert best_similarity("Ann", "Annaba") < 1.0


def test_distance_m_est_nulle_sur_le_meme_point():
    from src.gramps_mcp.genealogy.geo.score import distance_m

    assert distance_m(46.5617, 4.9122, 46.5617, 4.9122) == 0.0


def test_distance_m_mesure_une_distance_connue():
    """Paris-Lyon ~392 km à vol d'oiseau (référence indépendante, tolérance 1 %)."""
    from src.gramps_mcp.genealogy.geo.score import distance_m

    d = distance_m(48.8566, 2.3522, 45.7640, 4.8357)
    assert 388_000 < d < 396_000, d


def test_distance_m_ne_confond_pas_latitude_et_longitude():
    """Un degré de longitude vaut moins qu'un degré de latitude dès qu'on quitte l'équateur.

    Le piège n'est pas théorique : GeoJSON, WKT Wikidata et la grille suisse ordonnent
    leurs couples différemment, et une inversion silencieuse passerait tous les tests
    symétriques.
    """
    from src.gramps_mcp.genealogy.geo.score import distance_m

    nord_sud = distance_m(46.0, 6.0, 47.0, 6.0)
    est_ouest = distance_m(46.0, 6.0, 46.0, 7.0)
    assert nord_sud > est_ouest
    assert 110_000 < nord_sud < 112_000, nord_sud
