"""Clé phonétique française — rappel uniquement, jamais une preuve."""

import pytest

from src.gramps_mcp.genealogy.phonetics import cle_phonetique


@pytest.mark.parametrize(
    "nom,attendu",
    [
        ("Villaudy", "vilaudi"),
        ("VILLAUDY", "vilaudi"),
        ("Villaudi", "vilaudi"),
        ("Jacquet", "jak"),
        ("JACQUET", "jak"),
        ("Jaquet", "jak"),
        ("Jacquier", "jakier"),
        ("Pagan", "pagan"),
        ("Pagani", "pagani"),
        ("Fouquet", "fouk"),
        ("Foucquet", "fouk"),
        ("Lelièvre", "lelievr"),
        ("Le Lievre", "lelievr"),
        ("Schneider", "sxneider"),
        ("Larpent", "larpen"),
        ("LARPENT", "larpen"),
        ("Clavier", "klavier"),
        ("Cuvier", "kuvier"),
        ("Besson", "beson"),
        ("Bessons", "beson"),
    ],
)
def test_cle_phonetique(nom, attendu):
    assert cle_phonetique(nom) == attendu


def test_chaine_vide_rend_vide():
    assert cle_phonetique("") == ""
    assert cle_phonetique("  ") == ""
    assert cle_phonetique("?") == ""


def test_separe_les_familles_voisines_de_l_arbre():
    """Pagan/Pagani et Jacquet/Jacquier sont des lignées distinctes (spec §3.1)."""
    assert cle_phonetique("Pagan") != cle_phonetique("Pagani")
    assert cle_phonetique("Jacquet") != cle_phonetique("Jacquier")


def test_limite_assumee_les_voyelles_internes_ne_sont_pas_reduites():
    """Documente une limite réelle : la clé ne sert qu'au rappel (spec §4.2)."""
    assert cle_phonetique("Lelevre") != cle_phonetique("Lelièvre")
