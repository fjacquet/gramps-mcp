# crewai_custom_tools/tests/test_genealogy_places_parse.py
from src.gramps_mcp.genealogy.geo.places_parse import (
    normalize_country,
    parse_pname,
)


def test_parse_aligned_fr_with_insee():
    p = parse_pname(", , Bourges, 18033, 18000, Cher, Centre-Val de Loire, France")
    assert (p.commune, p.insee, p.postal) == ("Bourges", "18033", "18000")
    assert (p.departement, p.region, p.country) == (
        "Cher",
        "Centre-Val de Loire",
        "France",
    )
    assert p.shifted is False


def test_parse_shifted_fr_without_code_flags_shift():
    # établissement en tête, pas de code INSEE trouvé pour un lieu français
    p = parse_pname("Hôpital, , , , , , , France")
    assert p.insee is None
    assert p.shifted is True
    assert p.country == "France"


def test_parse_non_fr_no_code_not_shifted():
    p = parse_pname(", , Zürich, , , , , Suisse")
    assert p.commune == "Zürich"
    assert p.insee is None
    assert p.country == "Suisse"
    assert p.shifted is False  # hors FR : pas de code attendu → pas un décalage


def test_normalize_country_variants():
    assert normalize_country("FRANCE") == "France"
    assert normalize_country("Switzerland") == "Suisse"
    assert normalize_country("Germany>") == "Allemagne"
    assert normalize_country("Algerie") == "Algérie"
    assert normalize_country("") == ""


def test_parse_repeated_value_not_deduped_by_value():
    # commune/département homonyme (Marne) : l'exclusion doit être par INDEX, pas par valeur
    p = parse_pname(", , Marne, , , Marne, Grand Est, France")
    assert p.commune == "Marne"
    assert p.departement == "Marne" and p.region == "Grand Est"


def test_parse_country_only_string_has_empty_commune():
    p = parse_pname(", , , , , , , France")
    assert p.commune == ""  # le pays n'est jamais choisi comme commune
    assert p.country == "France" and p.shifted is True


def test_parse_lone_postal_not_taken_as_insee():
    p = parse_pname(", , Bourges, , 18000, Cher, Centre-Val de Loire, France")
    assert p.insee is None  # 18000 is a postal, not an INSEE
    assert p.postal == "18000"
    assert p.commune == "Bourges"
    assert p.shifted is True  # France + no reliable code -> fuzzy, not authoritative


def test_parse_corsica_lone_insee_still_detected():
    p = parse_pname(", , Ajaccio, 2A004, , Corse-du-Sud, Corse, France")
    assert p.insee == "2A004"  # Corsica code is unambiguously INSEE
    assert p.commune == "Ajaccio"


def test_parse_two_codes_first_is_insee():
    p = parse_pname(", , Bourges, 18033, 18000, Cher, Centre-Val de Loire, France")
    assert p.insee == "18033" and p.postal == "18000"  # unchanged behavior


def test_parse_right_truncated_flat_name_is_commune():
    from src.gramps_mcp.genealogy.geo.places_parse import parse_pname

    p = parse_pname(", , BOURGES, , , , ,")
    assert p.commune == "BOURGES"
    assert p.country == ""


def test_parse_single_token_is_commune():
    from src.gramps_mcp.genealogy.geo.places_parse import parse_pname

    p = parse_pname("Bourges")
    assert p.commune == "Bourges"
    assert p.country == ""


def test_parse_known_country_last_segment_unchanged():
    from src.gramps_mcp.genealogy.geo.places_parse import parse_pname

    p = parse_pname("Lausanne, Vaud, Suisse")
    assert p.commune == "Lausanne"
    assert p.country == "Suisse"


def test_parse_full_french_chain_unchanged():
    from src.gramps_mcp.genealogy.geo.places_parse import parse_pname

    p = parse_pname("Bourges, Cher, Centre-Val de Loire, France")
    assert p.commune == "Bourges"
    assert p.country == "France"
    assert p.departement == "Cher"


def test_parse_garbage_becomes_commune_not_country():
    # A date/URL/description in the name field must NOT be invented as a country;
    # it becomes the commune so the downstream resolver returns nothing -> indecidable.
    from src.gramps_mcp.genealogy.geo.places_parse import parse_pname

    p = parse_pname(", , 1790 ( avant), , , , ,")
    assert p.commune == "1790 ( avant)"
    assert p.country == ""


def test_parse_recognizes_ags_8_digit_and_keeps_land():
    p = parse_pname(
        ", Waldeck, 06635021, 34513, Regierungsbezirk Kassel, Hesse, Germany"
    )
    assert p.ags == "06635021"
    assert p.commune == "Waldeck"
    assert p.country == "Allemagne"
    assert p.region == "Hesse"  # Land récupéré (plus perdu par le tail)
    assert p.postal == "34513"


def test_parse_no_ags_when_no_8_digit_segment():
    p = parse_pname(", , Bourges, 18033, 18000, Cher, Centre-Val de Loire, France")
    assert p.ags is None  # non-régression: 5 chiffres reste INSEE/postal
    assert p.insee == "18033"


def test_suffixe_de_code_cantonal_sur_un_nom_sans_virgule_donne_la_suisse():
    """Forme réelle de 19 lieux de l'arbre : `Montreux (VD)`. Sans cette règle, le pays
    reste vide, resolve_ch n'est jamais appelé et la hiérarchie revient vide."""
    from src.gramps_mcp.genealogy.geo.places_parse import parse_pname

    parsed = parse_pname("Montreux (VD)")
    assert parsed.country == "Suisse"
    assert parsed.commune == "Montreux"


def test_le_suffixe_est_retire_de_la_commune_interrogee():
    from src.gramps_mcp.genealogy.geo.places_parse import parse_pname

    assert parse_pname("Genève (GE)").commune == "Genève"


def test_un_nom_a_virgules_ne_declenche_pas_la_regle_cantonale():
    """Un nom à virgules a déjà un segment pays exploitable : la règle n'a pas à s'en mêler."""
    from src.gramps_mcp.genealogy.geo.places_parse import parse_pname

    parsed = parse_pname("Springfield (BE), Illinois, United States")
    assert parsed.country == "États-Unis"


def test_un_suffixe_a_deux_lettres_hors_table_reste_non_suisse():
    from src.gramps_mcp.genealogy.geo.places_parse import parse_pname

    parsed = parse_pname("Springfield (NY)")
    assert parsed.country != "Suisse"


def test_un_nom_a_virgule_finale_tronquee_ne_declenche_pas_la_regle_cantonale():
    """Sans la garde `len(segments) == 1`, `Springfield (BE),` — artefact d'un titre tronqué —
    passerait pour suisse : le pays reste vide après le repli, et le suffixe `(BE)` suffirait
    à lui seul à déclencher la règle."""
    from src.gramps_mcp.genealogy.geo.places_parse import parse_pname

    parsed = parse_pname("Springfield (BE),")
    assert parsed.country != "Suisse"


def test_parenthese_finale_avec_virgule_est_une_annotation_retiree_avant_le_split():
    """'(Ville, Pays)' en fin de nom est un rappel de rattachement, pas un niveau de
    hiérarchie de plus. Sans garde, `raw.split(",")` coupe DANS la parenthèse :
    'Lagoa e Gávea (Rio de Janeiro, Brésil)' rendait pays='Brésil)' (parenthèse fermante
    collée) et commune='Lagoa e Gávea (Rio de Janeiro' (parenthèse ouvrante orpheline)."""
    p = parse_pname("Lagoa e Gávea (Rio de Janeiro, Brésil)")
    assert p.commune == "Lagoa e Gávea"
    assert p.country == "Brésil"


def test_parenthese_finale_sans_virgule_reste_intacte_pour_la_regle_cantonale():
    """Garde-fou inverse : une parenthèse courte SANS virgule ('(VD)', '(NY)') n'est pas une
    annotation hiérarchique — elle doit rester dans le segment pour que
    `split_canton_suffix` continue de la lire."""
    p = parse_pname("Montreux (VD)")
    assert p.commune == "Montreux"
    assert p.country == "Suisse"
