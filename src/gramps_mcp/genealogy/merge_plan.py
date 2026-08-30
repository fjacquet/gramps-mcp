# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2026 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Du lot de paires au plan de fusion : grappes, phoenix, patch du genre.

Pur, stdlib only. Ne fait aucun appel réseau — l'exécution vit dans genecrew.

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/analysis/merge_plan.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.

Two lines diverge from that copy, both annotations for mypy, not behaviour
changes: `_GENRE_PAR_SEXE` is typed `dict[str, Literal[0, 1]]` instead of an
unannotated `dict`, and `_patch_genre` returns `Literal[0, 1] | None` instead
of `int | None` — `MergeCluster.gender_patch` is itself `Literal[0, 1] | None`,
and the values returned were always 0 or 1 already.
"""

from __future__ import annotations

from typing import Literal

from .domain import (
    MergeCluster,
    MergePair,
    PersonFacts,
)

_GENRE_PAR_SEXE: dict[str, Literal[0, 1]] = {"F": 0, "M": 1}
"""PersonFacts.sex vers l'entier attendu par l'API Gramps. "U" n'y figure pas :
un genre inconnu ne se patche pas."""


def score_completude(p: PersonFacts) -> int:
    """Nombre de champs renseignés parmi les sept retenus par la spec §4.4."""
    return sum(
        (
            p.sex != "U",
            p.birth is not None,
            p.death is not None,
            bool(p.birth and p.birth.sortval),
            bool(p.birth and p.birth.place_name),
            bool(p.parent_family_handles),
            bool(p.family_handles),
        )
    )


def _rang(p: PersonFacts) -> tuple[int, int, str]:
    """Clé de tri décroissante-puis-croissante : complétude, citations, id.

    Le `gramps_id` clôt le départage pour qu'une seconde exécution sur les mêmes
    données choisisse le même phoenix.
    """
    return (-score_completude(p), -int(p.has_any_citation), p.gramps_id)


def choisir_phoenix(membres: list[PersonFacts]) -> PersonFacts:
    """Rend le survivant d'une grappe (spec §4.4)."""
    return min(membres, key=_rang)


def _grappes(paires: list[MergePair]) -> list[list[str]]:
    """Union-find sur les handles : rend les composantes connexes."""
    parent: dict[str, str] = {}

    def trouver(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def unir(a: str, b: str) -> None:
        racine_a, racine_b = trouver(a), trouver(b)
        if racine_a != racine_b:
            parent[racine_b] = racine_a

    for paire in paires:
        unir(paire.handle_a, paire.handle_b)

    composantes: dict[str, list[str]] = {}
    for handle in parent:
        composantes.setdefault(trouver(handle), []).append(handle)
    return [sorted(membres) for membres in composantes.values()]


def _patch_genre(
    phoenix: PersonFacts, titanics: list[PersonFacts]
) -> Literal[0, 1] | None:
    """Genre à écrire sur le phoenix avant fusion, ou None.

    `Person.merge()` n'unit pas le genre : celui du phoenix survit, celui du
    titanic disparaît sans trace (spec §2). C'est le seul patch nécessaire.
    """
    if phoenix.sex != "U":
        return None
    for titanic in sorted(titanics, key=lambda p: p.gramps_id):
        if titanic.sex in _GENRE_PAR_SEXE:
            return _GENRE_PAR_SEXE[titanic.sex]
    return None


def plan_fusions(
    paires: list[MergePair], par_handle: dict[str, PersonFacts]
) -> list[MergeCluster]:
    """Rend une grappe par groupe de doublons de l'étage `auto`."""
    auto = [p for p in paires if p.tier == "auto"]
    grappes: list[MergeCluster] = []
    for handles in _grappes(auto):
        membres = [par_handle[h] for h in handles if h in par_handle]
        if len(membres) < 2:
            continue
        phoenix = choisir_phoenix(membres)
        titanics = [m for m in membres if m.handle != phoenix.handle]
        grappes.append(
            MergeCluster(
                phoenix_handle=phoenix.handle,
                phoenix_gramps_id=phoenix.gramps_id,
                titanic_handles=[t.handle for t in titanics],
                titanic_gramps_ids=[t.gramps_id for t in titanics],
                gender_patch=_patch_genre(phoenix, titanics),
            )
        )
    return sorted(grappes, key=lambda g: g.phoenix_gramps_id)
