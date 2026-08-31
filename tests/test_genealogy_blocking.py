"""Génération des paires candidates — c'est du RAPPEL, pas de la preuve."""

from src.gramps_mcp.genealogy.domain import EventFact, PersonFacts
from src.gramps_mcp.genealogy.duplicates import (
    MAX_BLOC,
    blocking_keys,
    candidate_pairs,
)


def _p(gid, given, surname, year=None, familles=(), parents=()):
    return PersonFacts(
        gramps_id=gid,
        handle=f"h{gid}",
        name=f"{given} {surname}",
        surname=surname,
        given=given,
        sex="U",
        birth=EventFact(type="Birth", sortval=year * 366, year=year) if year else None,
        family_handles=list(familles),
        parent_family_handles=list(parents),
    )


def test_cle_nom_exact_ignore_casse_et_accents():
    a = blocking_keys(_p("I1", "Jean", "VILLAUDY"))
    b = blocking_keys(_p("I2", "Jean", "Villaudy"))
    assert a & b


def test_cle_phonetique_rapproche_les_graphies():
    a = blocking_keys(_p("I1", "Jean", "Jacquet"))
    b = blocking_keys(_p("I2", "Jean", "Jaquet"))
    assert a & b


def test_personne_sans_nom_ne_produit_aucune_cle():
    assert blocking_keys(_p("I1", "", "")) == set()


def test_annee_proche_bloque_ensemble_annee_lointaine_non():
    proches = blocking_keys(_p("I1", "Jean", "Dupont", 1850)) & blocking_keys(
        _p("I2", "Jean", "Dupont", 1852)
    )
    assert any(k.startswith("an:") for k in proches)
    lointaines = blocking_keys(_p("I1", "Jean", "Dupont", 1850)) & blocking_keys(
        _p("I2", "Jean", "Dupont", 1860)
    )
    assert not any(k.startswith("an:") for k in lointaines)


def test_famille_conjugale_commune_bloque_sans_aucune_date():
    """Le cas que R10 rate totalement aujourd'hui (spec §4.2)."""
    a = _p("I1", "Marie", "Sestre", familles=["F1"])
    b = _p("I2", "Marie", "Sestre", familles=["F1"])
    pairs, _ = candidate_pairs([a, b])
    assert ("hI1", "hI2") in pairs
    assert any(k.startswith("fam:") for k in pairs[("hI1", "hI2")])


def test_famille_conjugale_seule_suffit_prenoms_differents_sans_date():
    """fam: doit à elle seule produire la paire — nom: et pho: ne s'y déclenchent pas
    (prénoms d'initiales différentes, aucune date de naissance)."""
    a = _p("I1", "Jean", "Sestre", familles=["F1"])
    b = _p("I2", "Marie", "Sestre", familles=["F1"])
    pairs, _ = candidate_pairs([a, b])
    assert ("hI1", "hI2") in pairs
    cles = pairs[("hI1", "hI2")]
    assert not any(k.startswith("nom:") for k in cles)
    assert cles == {"fam:F1"}


def test_famille_parentale_seule_suffit_prenoms_differents_sans_date():
    """par: doit à elle seule produire la paire — nom: et pho: ne s'y déclenchent pas
    (prénoms d'initiales différentes, aucune date de naissance)."""
    a = _p("I1", "Jean", "Sestre", parents=["F2"])
    b = _p("I2", "Marie", "Sestre", parents=["F2"])
    pairs, _ = candidate_pairs([a, b])
    assert ("hI1", "hI2") in pairs
    cles = pairs[("hI1", "hI2")]
    assert not any(k.startswith("nom:") for k in cles)
    assert cles == {"par:F2"}


def test_paires_normalisees_et_sans_doublon():
    a, b = _p("I1", "Jean", "Dupont", 1850), _p("I2", "Jean", "Dupont", 1850)
    pairs, _ = candidate_pairs([a, b])
    assert list(pairs) == [("hI1", "hI2")]
    assert len(pairs[("hI1", "hI2")]) >= 2


def test_une_personne_ne_se_paire_pas_avec_elle_meme():
    pairs, _ = candidate_pairs([_p("I1", "Jean", "Dupont", 1850)])
    assert pairs == {}


def test_bloc_trop_gros_est_ignore_et_signale():
    gros = [_p(f"I{i}", "Jean", "Pagan") for i in range(MAX_BLOC + 5)]
    pairs, ignores = candidate_pairs(gros, max_bloc=MAX_BLOC)
    assert pairs == {}
    assert any(k.startswith("nom:") for k in ignores)
