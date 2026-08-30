"""Contrats des modèles de fusion."""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.genealogy.domain import MergeCluster, MergePair


def test_paire_minimale():
    p = MergePair(
        gramps_id_a="I1",
        gramps_id_b="I2",
        handle_a="h1",
        handle_b="h2",
        tier="auto",
        regle="date_complete+parents",
    )
    assert p.tier == "auto"
    assert p.blocs == []


def test_tier_est_un_vocabulaire_ferme():
    with pytest.raises(ValidationError):
        MergePair(
            gramps_id_a="I1",
            gramps_id_b="I2",
            handle_a="h1",
            handle_b="h2",
            tier="peut-etre",
            regle="",
        )


def test_grappe_sans_patch_de_genre_par_defaut():
    g = MergeCluster(
        phoenix_handle="h1",
        phoenix_gramps_id="I1",
        titanic_handles=["h2"],
        titanic_gramps_ids=["I2"],
    )
    assert g.gender_patch is None


def test_grappe_refuse_un_genre_hors_vocabulaire():
    with pytest.raises(ValidationError):
        MergeCluster(
            phoenix_handle="h1",
            phoenix_gramps_id="I1",
            titanic_handles=["h2"],
            titanic_gramps_ids=["I2"],
            gender_patch=7,
        )
