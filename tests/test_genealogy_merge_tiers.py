"""Étagement auto/arbitrage/rejet — et le CORPUS DE PIÈGES, filet de sécurité du système.

Chaque piège ici correspond à une confusion généalogique réelle et fréquente.
Aucun ne doit atteindre l'étage `auto` : une fusion est irréversible.
"""

from src.gramps_mcp.genealogy.domain import (
    EventFact,
    FamilyFacts,
    PersonFacts,
)
from src.gramps_mcp.genealogy.duplicates import date_complete, etager


def _naissance(jour, mois, annee):
    """Date de précision au jour : dateval = [jour, mois, année, slash]."""
    return EventFact(
        type="Birth",
        sortval=annee * 366 + mois * 31 + jour,
        year=annee,
        modifier=0,
        dateval=[jour, mois, annee, False],
    )


def _annee_seule(annee):
    """Date réduite à l'année — jour et mois à zéro."""
    return EventFact(
        type="Birth",
        sortval=annee * 366,
        year=annee,
        modifier=0,
        dateval=[0, 0, annee, False],
    )


def _naissance_environ(jour, mois, annee):
    """Date approximative (« vers ») : même sortval/jour/mois qu'une date
    exacte, mais modifier=3 — elle borne la date, elle ne la fixe pas."""
    return EventFact(
        type="Birth",
        sortval=annee * 366 + mois * 31 + jour,
        year=annee,
        modifier=3,
        dateval=[jour, mois, annee, False],
    )


def _p(gid, given, surname, birth=None, familles=(), parents=(), sex="U"):
    return PersonFacts(
        gramps_id=gid,
        handle=f"h{gid}",
        name=f"{given} {surname}",
        surname=surname,
        given=given,
        sex=sex,
        birth=birth,
        family_handles=list(familles),
        parent_family_handles=list(parents),
    )


def _famille(handle, pere=None, mere=None, enfants=()):
    return FamilyFacts(
        gramps_id=handle,
        handle=handle,
        father_handle=pere,
        mother_handle=mere,
        child_handles=list(enfants),
    )


def _tier(paires, gid_a, gid_b):
    for p in paires:
        if {p.gramps_id_a, p.gramps_id_b} == {gid_a, gid_b}:
            return p.tier, p.regle
    return None, None


# --- date_complete -----------------------------------------------------------


def test_date_complete_exige_jour_et_mois():
    assert date_complete(_naissance(3, 4, 1850)) is True
    assert date_complete(_annee_seule(1850)) is False
    assert date_complete(None) is False


def test_sortval_nul_n_est_jamais_complet():
    """Contrainte globale : sortval 0 ne compte jamais comme une concordance."""
    ev = EventFact(type="Birth", sortval=0, year=1850, dateval=[3, 4, 1850, False])
    assert date_complete(ev) is False


def test_date_textuelle_n_est_pas_complete():
    """modifier == 6 : date en texte libre, non exploitable."""
    ev = EventFact(
        type="Birth", sortval=677000, year=1850, modifier=6, dateval=[3, 4, 1850, False]
    )
    assert date_complete(ev) is False


def test_seul_le_modifier_exact_est_complet():
    """Seul modifier == 0 (date exacte) prouve l'identité. avant/après/vers/
    intervalle/span BORNENT une date sans la FIXER : deux personnes distinctes
    peuvent partager la même date approximative."""
    for modifier in (1, 2, 3, 4, 5, 6):
        ev = EventFact(
            type="Birth",
            sortval=677000,
            year=1850,
            modifier=modifier,
            dateval=[3, 4, 1850, False],
        )
        assert date_complete(ev) is False, f"modifier={modifier} ne doit pas compter"


# --- les trois règles de l'étage auto ---------------------------------------


def test_regle_date_complete_et_memes_parents():
    familles = {"F1": _famille("F1", "hPERE", "hMERE")}
    a = _p("I1", "Jean", "Dupont", _naissance(3, 4, 1850), parents=["F1"])
    b = _p("I2", "Jean", "Dupont", _naissance(3, 4, 1850), parents=["F1"])
    paires, _ = etager([a, b], familles)
    assert _tier(paires, "I1", "I2") == ("auto", "date_complete+parents")


def test_regle_date_complete_seule():
    a = _p("I1", "Jean", "Dupont", _naissance(3, 4, 1850))
    b = _p("I2", "Jean", "Dupont", _naissance(3, 4, 1850))
    paires, _ = etager([a, b], {})
    assert _tier(paires, "I1", "I2") == ("auto", "date_complete")


def test_regle_conjoint_et_enfant_commun_sans_aucune_date():
    familles = {
        "F1": _famille("F1", "hCONJ", "hI1", enfants=["hENF"]),
        "F2": _famille("F2", "hCONJ", "hI2", enfants=["hENF"]),
    }
    a = _p("I1", "Marie", "Sestre", familles=["F1"])
    b = _p("I2", "Marie", "Sestre", familles=["F2"])
    paires, _ = etager([a, b], familles)
    assert _tier(paires, "I1", "I2") == ("auto", "conjoint+enfant")


def test_conjoint_commun_sans_enfant_commun_reste_en_arbitrage():
    familles = {
        "F1": _famille("F1", "hCONJ", "hI1", enfants=["hENF1"]),
        "F2": _famille("F2", "hCONJ", "hI2", enfants=["hENF2"]),
    }
    a = _p("I1", "Marie", "Sestre", familles=["F1"])
    b = _p("I2", "Marie", "Sestre", familles=["F2"])
    paires, _ = etager([a, b], familles)
    assert _tier(paires, "I1", "I2")[0] == "arbitrage"


def test_noms_differents_ne_fusionnent_jamais_en_auto():
    familles = {"F1": _famille("F1", "hPERE", "hMERE")}
    a = _p("I1", "Jean", "Dupont", _naissance(3, 4, 1850), parents=["F1"])
    b = _p("I2", "Pierre", "Dupont", _naissance(3, 4, 1850), parents=["F1"])
    paires, _ = etager([a, b], familles)
    assert _tier(paires, "I1", "I2")[0] != "auto"


# --- LE CORPUS DE PIÈGES ----------------------------------------------------


def test_piege_freres_homonymes():
    """Un enfant meurt en bas âge, le suivant reçoit le même prénom.
    Mêmes parents, même nom, dates différentes. Très fréquent avant 1900."""
    familles = {"F1": _famille("F1", "hPERE", "hMERE", enfants=["hI1", "hI2"])}
    a = _p("I1", "Jean", "Dupont", _naissance(3, 4, 1850), parents=["F1"])
    b = _p("I2", "Jean", "Dupont", _naissance(7, 9, 1853), parents=["F1"])
    paires, _ = etager([a, b], familles)
    assert _tier(paires, "I1", "I2")[0] != "auto"


def test_piege_freres_homonymes_sans_aucune_date():
    """La règle explicitement rejetée par la spec §4.1 : mêmes parents + même
    prénom, sans date, ne fusionne JAMAIS automatiquement."""
    familles = {"F1": _famille("F1", "hPERE", "hMERE", enfants=["hI1", "hI2"])}
    a = _p("I1", "Jean", "Dupont", parents=["F1"])
    b = _p("I2", "Jean", "Dupont", parents=["F1"])
    paires, _ = etager([a, b], familles)
    assert _tier(paires, "I1", "I2")[0] != "auto"


def test_piege_jumeaux():
    """Mêmes parents, MÊME date de naissance, prénoms différents."""
    familles = {"F1": _famille("F1", "hPERE", "hMERE", enfants=["hI1", "hI2"])}
    a = _p("I1", "Jean", "Dupont", _naissance(3, 4, 1850), parents=["F1"])
    b = _p("I2", "Paul", "Dupont", _naissance(3, 4, 1850), parents=["F1"])
    paires, _ = etager([a, b], familles)
    assert _tier(paires, "I1", "I2")[0] != "auto"


def test_piege_pere_et_fils_homonymes():
    """Même nom complet, ~28 ans d'écart."""
    a = _p("I1", "Jean", "Dupont", _naissance(3, 4, 1822))
    b = _p("I2", "Jean", "Dupont", _naissance(3, 4, 1850))
    paires, _ = etager([a, b], {})
    assert _tier(paires, "I1", "I2")[0] != "auto"


def test_piege_pagan_contre_pagani():
    """Les deux plus grosses familles de l'arbre : 0.957 de similarité lexicale
    pour un seuil R10 à 0.85, et pourtant des lignées distinctes (spec §3.1)."""
    a = _p("I1", "Marie", "Pagan", _naissance(3, 4, 1850))
    b = _p("I2", "Marie", "Pagani", _naissance(3, 4, 1850))
    paires, _ = etager([a, b], {})
    assert _tier(paires, "I1", "I2")[0] != "auto"


def test_piege_pagan_contre_pagani_meme_famille():
    """Comme ci-dessus, mais forcé à la même paire de blocage (parents communs) :
    la clé phonétique seule sépare Pagan/Pagani (`pho:pagan:m` != `pho:pagani:m`),
    donc le test précédent ne traverse jamais `_regle_auto`. Celui-ci force le
    passage par une clé `par:` partagée pour vérifier que l'égalité stricte de
    nom protège même quand le blocage rapproche les deux lignées."""
    familles = {"F1": _famille("F1", "hPERE", "hMERE")}
    a = _p("I1", "Marie", "Pagan", _naissance(3, 4, 1850), parents=["F1"])
    b = _p("I2", "Marie", "Pagani", _naissance(3, 4, 1850), parents=["F1"])
    paires, _ = etager([a, b], familles)
    assert _tier(paires, "I1", "I2")[0] != "auto"


def test_piege_annee_seule_identique():
    """Même nom, même ANNÉE, rien d'autre : le faux positif de 2026-07-19."""
    a = _p("I1", "Jean", "Dupont", _annee_seule(1850))
    b = _p("I2", "Jean", "Dupont", _annee_seule(1850))
    paires, _ = etager([a, b], {})
    assert _tier(paires, "I1", "I2")[0] != "auto"


def test_piege_date_environ_avec_memes_parents_ne_fusionne_jamais():
    """« Vers » (modifier=3) borne une date, ne la fixe pas. Même nom complet,
    même sortval/jour/mois, mêmes parents : sans le garde-fou modifier==0,
    ceci passerait en `auto` par la règle date_complete+parents. Deux
    personnes distinctes peuvent porter la même date approximative — ça doit
    tomber en arbitrage, jamais en auto."""
    familles = {"F1": _famille("F1", "hPERE", "hMERE")}
    a = _p("I1", "Jean", "Dupont", _naissance_environ(3, 4, 1850), parents=["F1"])
    b = _p("I2", "Jean", "Dupont", _naissance_environ(3, 4, 1850), parents=["F1"])
    paires, _ = etager([a, b], familles)
    assert _tier(paires, "I1", "I2")[0] == "arbitrage"


def test_piege_deux_dates_inconnues_ne_concordent_pas():
    """Deux sortval à 0 ne sont pas « la même date »."""
    inconnue = EventFact(type="Birth", sortval=0, year=None, dateval=[])
    a = _p("I1", "Jean", "Dupont", inconnue)
    b = _p("I2", "Jean", "Dupont", inconnue)
    paires, _ = etager([a, b], {})
    assert _tier(paires, "I1", "I2")[0] != "auto"


def test_piege_sortval_nul_avec_dateval_complet_ne_concorde_pas():
    """Variante du piège précédent avec `dateval` rempli (jour+mois présents)
    mais `sortval == 0` : le fixture `dateval=[]` du test ci-dessus est déjà
    arrêté par la longueur de `dateval`, sans jamais solliciter le garde-fou
    `sortval == 0` de `date_complete`. Celui-ci le sollicite réellement."""
    ev = EventFact(type="Birth", sortval=0, year=1850, dateval=[3, 4, 1850, False])
    a = _p("I1", "Jean", "Dupont", ev)
    b = _p("I2", "Jean", "Dupont", ev)
    paires, _ = etager([a, b], {})
    assert _tier(paires, "I1", "I2")[0] != "auto"


def test_ressemblance_de_nom_seule_est_rejetee():
    a = _p("I1", "Jean", "Dupont", _naissance(3, 4, 1850))
    b = _p("I2", "Jean", "Dupond", _naissance(7, 9, 1851))
    paires, _ = etager([a, b], {})
    tier, _regle = _tier(paires, "I1", "I2")
    assert tier in (None, "rejet")
