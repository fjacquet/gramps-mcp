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

"""Clé phonétique française d'un patronyme — pure, stdlib only.

Sert UNIQUEMENT au rappel : elle regroupe des candidats à examiner, elle ne prouve
jamais une identité (spec §3.1). Ses limites sont assumées — elle rapproche les
graphies partageant la même ossature consonantique, pas les variations de voyelle
interne (`Lelevre` ne rejoint pas `Lelièvre`).

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/analysis/phonetics.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.
"""

from __future__ import annotations

import unicodedata


def normalize_name(s: str) -> str:
    """Lowercase, strip accents, collapse whitespace.

    Déplacée depuis `duplicates.py`, qui la réexporte : `phonetics` ne doit
    dépendre de rien, sans quoi l'import de `cle_phonetique` par `duplicates`
    formerait un cycle.
    """
    decomposed = unicodedata.normalize("NFKD", s)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(ascii_only.lower().split())


# Ordre significatif : "ch" est neutralisé en "x" AVANT que "c" ne devienne "k",
# faute de quoi Schneider deviendrait "skneider".
_REMPLACEMENTS = [
    ("ph", "f"),
    ("ch", "x"),
    ("qu", "k"),
    ("gu", "g"),
    ("c", "k"),
    ("y", "i"),
]

_TERMINAISONS_MUETTES = ("e", "s", "t", "d", "x", "z")

_LONGUEUR_MINIMALE = 2
"""On ne rabote jamais en deçà : "Est" ne doit pas se réduire à la chaîne vide."""


def cle_phonetique(nom: str) -> str:
    """Rend la clé phonétique d'un patronyme.

    Returns an empty string if unexploitable.
    """
    lettres = "".join(c for c in normalize_name(nom) if c.isalpha())
    if not lettres:
        return ""
    for avant, apres in _REMPLACEMENTS:
        lettres = lettres.replace(avant, apres)
    deduplique: list[str] = []
    for caractere in lettres:
        if not deduplique or deduplique[-1] != caractere:
            deduplique.append(caractere)
    cle = "".join(deduplique)
    while len(cle) > _LONGUEUR_MINIMALE and cle[-1] in _TERMINAISONS_MUETTES:
        cle = cle[:-1]
    return cle
