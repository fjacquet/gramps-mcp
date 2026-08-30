"""Grappes union-find, choix du phoenix, patch du genre."""

from src.gramps_mcp.genealogy.domain import (
    EventFact,
    MergePair,
    PersonFacts,
)
from src.gramps_mcp.genealogy.merge_plan import (
    choisir_phoenix,
    plan_fusions,
    score_completude,
)


def _p(gid, sex="U", birth=None, death=None, citations=False, familles=(), parents=()):
    return PersonFacts(
        gramps_id=gid,
        handle=f"h{gid}",
        name="Jean Dupont",
        surname="Dupont",
        given="Jean",
        sex=sex,
        birth=birth,
        death=death,
        has_any_citation=citations,
        family_handles=list(familles),
        parent_family_handles=list(parents),
    )


def _naissance(annee=1850, place="Bourges"):
    return EventFact(
        type="Birth",
        sortval=annee * 366,
        year=annee,
        dateval=[3, 4, annee, False],
        place_name=place,
    )


def _auto(gid_a, gid_b):
    return MergePair(
        gramps_id_a=gid_a,
        gramps_id_b=gid_b,
        handle_a=f"h{gid_a}",
        handle_b=f"h{gid_b}",
        tier="auto",
        regle="date_complete",
    )


# --- complétude et phoenix ---------------------------------------------------


def test_score_completude_croit_avec_les_champs_renseignes():
    vide = _p("I1")
    garni = _p("I2", sex="M", birth=_naissance(), parents=["F1"], familles=["F2"])
    assert score_completude(garni) > score_completude(vide)


def test_phoenix_est_le_plus_complet():
    pauvre, riche = _p("I1"), _p("I2", sex="M", birth=_naissance())
    assert choisir_phoenix([pauvre, riche]).gramps_id == "I2"


def test_a_completude_egale_le_mieux_source_gagne():
    sans = _p("I1", sex="M", birth=_naissance())
    avec = _p("I2", sex="M", birth=_naissance(), citations=True)
    assert choisir_phoenix([sans, avec]).gramps_id == "I2"


def test_departage_stable_par_gramps_id():
    """Deux exécutions sur les mêmes données doivent choisir le même phoenix."""
    a, b = _p("I9", sex="M"), _p("I2", sex="M")
    assert choisir_phoenix([a, b]).gramps_id == "I2"
    assert choisir_phoenix([b, a]).gramps_id == "I2"


# --- grappes -----------------------------------------------------------------


def test_grappe_transitive_a_un_seul_phoenix():
    """A≈B et B≈C : fusionner A/B supprime B, l'appel B/C partirait sur un
    handle mort. Une seule grappe, un seul phoenix (spec §4.5)."""
    gens = {f"h{g}": _p(g, sex="M") for g in ("I1", "I2", "I3")}
    grappes = plan_fusions([_auto("I1", "I2"), _auto("I2", "I3")], gens)
    assert len(grappes) == 1
    assert grappes[0].phoenix_gramps_id == "I1"
    assert sorted(grappes[0].titanic_gramps_ids) == ["I2", "I3"]


def test_deux_grappes_disjointes_restent_separees():
    gens = {f"h{g}": _p(g, sex="M") for g in ("I1", "I2", "I3", "I4")}
    grappes = plan_fusions([_auto("I1", "I2"), _auto("I3", "I4")], gens)
    assert len(grappes) == 2


def test_seul_l_etage_auto_est_planifie():
    gens = {f"h{g}": _p(g) for g in ("I1", "I2")}
    arbitrage = MergePair(
        gramps_id_a="I1",
        gramps_id_b="I2",
        handle_a="hI1",
        handle_b="hI2",
        tier="arbitrage",
        regle="",
    )
    assert plan_fusions([arbitrage], gens) == []


# --- patch du genre ----------------------------------------------------------


def test_phoenix_inconnu_recupere_le_genre_du_titanic():
    """Person.merge() ignore le genre : sans patch, le M serait perdu (spec §2)."""
    gens = {"hI1": _p("I1", sex="U", birth=_naissance()), "hI2": _p("I2", sex="M")}
    grappes = plan_fusions([_auto("I1", "I2")], gens)
    assert grappes[0].phoenix_gramps_id == "I1"
    assert grappes[0].gender_patch == 1


def test_phoenix_feminin_donne_un_patch_a_zero():
    gens = {"hI1": _p("I1", sex="U", birth=_naissance()), "hI2": _p("I2", sex="F")}
    assert plan_fusions([_auto("I1", "I2")], gens)[0].gender_patch == 0


def test_phoenix_deja_genre_n_est_jamais_patche():
    gens = {"hI1": _p("I1", sex="M", birth=_naissance()), "hI2": _p("I2", sex="F")}
    grappes = plan_fusions([_auto("I1", "I2")], gens)
    assert grappes[0].phoenix_gramps_id == "I1"
    assert grappes[0].gender_patch is None


def test_aucun_genre_connu_aucun_patch():
    gens = {"hI1": _p("I1", sex="U", birth=_naissance()), "hI2": _p("I2", sex="U")}
    assert plan_fusions([_auto("I1", "I2")], gens)[0].gender_patch is None
