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

"""Deterministic duplicate detection (R10) — pure, stdlib only.

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/analysis/duplicates.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.

Three lines diverge from that copy, each an annotation for mypy, not a
behaviour change: `candidate_pairs` unpacks the sorted handle pair into two
names before using it as a dict key, instead of an unannotated
`tuple(sorted(...))`; `_regle_auto`'s `dates_identiques` adds explicit
`a.birth is not None`/`b.birth is not None` conjuncts ahead of the
`date_complete` calls that already guarantee it by short-circuit; and
`etager` declares `tier: MergeTier` before assigning it, instead of letting
it infer as plain `str`.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from itertools import combinations

from .domain import (
    DuplicateCandidate,
    EventFact,
    FamilyFacts,
    MergePair,
    MergeTier,
    PersonFacts,
)
from .phonetics import (
    cle_phonetique,
    normalize_name,
)

__all__ = [
    "MAX_BLOC",
    "blocking_keys",
    "candidate_pairs",
    "date_complete",
    "etager",
    "find_duplicates",
    "normalize_name",
]

BIRTH_YEAR_WINDOW = 2


def _key(p: PersonFacts) -> str:
    return normalize_name(f"{p.given} {p.surname}")


def find_duplicates(
    people: list[PersonFacts], threshold: float = 0.85
) -> list[DuplicateCandidate]:
    """Return candidate duplicate pairs within `people` (O(n²) over the batch)."""
    out: list[DuplicateCandidate] = []
    keyed = [(p, _key(p), p.birth.year if p.birth else None) for p in people]
    for i in range(len(keyed)):
        pa, ka, ya = keyed[i]
        if ya is None or not ka:
            continue
        for j in range(i + 1, len(keyed)):
            pb, kb, yb = keyed[j]
            if yb is None or not kb or abs(ya - yb) > BIRTH_YEAR_WINDOW:
                continue
            score = SequenceMatcher(None, ka, kb).ratio()
            if score >= threshold:
                out.append(
                    DuplicateCandidate(
                        gramps_id_a=pa.gramps_id,
                        gramps_id_b=pb.gramps_id,
                        score=round(score, 3),
                        reason=f"Homonymes ({ka!r} ≈ {kb!r}), naissances {ya}/{yb}.",
                    )
                )
    return out


MAX_BLOC = 60
"""Au-delà, un bloc est ignoré : `Pagan` (151 personnes) produirait 11 325 paires
à lui seul. Le rappel perdu est couvert par les quatre autres clés (spec §4.2)."""

_FENETRE_ANNEE = 2
"""Chaque personne enregistre ses années ±2, si bien que deux personnes distantes
d'au plus 2 ans partagent forcément une clé."""


def blocking_keys(p: PersonFacts) -> set[str]:
    """Rend les clés de blocage d'une personne — du RAPPEL, jamais une preuve."""
    cles: set[str] = set()
    nom = normalize_name(f"{p.given} {p.surname}")
    patronyme = normalize_name(p.surname)
    if nom:
        cles.add(f"nom:{nom}")
    initiale = normalize_name(p.given)[:1]
    phonetique = cle_phonetique(p.surname)
    if phonetique and initiale:
        cles.add(f"pho:{phonetique}:{initiale}")
    if patronyme and p.birth and p.birth.year:
        for delta in range(-_FENETRE_ANNEE, _FENETRE_ANNEE + 1):
            cles.add(f"an:{patronyme}:{p.birth.year + delta}")
    for handle in p.family_handles:
        cles.add(f"fam:{handle}")
    for handle in p.parent_family_handles:
        cles.add(f"par:{handle}")
    return cles


def candidate_pairs(
    people: list[PersonFacts], max_bloc: int = MAX_BLOC
) -> tuple[dict[tuple[str, str], set[str]], list[str]]:
    """Rend les paires candidates et les clés écartées pour cause de bloc trop
    gros.
    """
    blocs: dict[str, list[PersonFacts]] = {}
    for personne in people:
        for cle in blocking_keys(personne):
            blocs.setdefault(cle, []).append(personne)
    paires: dict[tuple[str, str], set[str]] = {}
    ignores: list[str] = []
    for cle, membres in blocs.items():
        if len(membres) < 2:
            continue
        if len(membres) > max_bloc:
            ignores.append(cle)
            continue
        for a, b in combinations(membres, 2):
            handle_a, handle_b = sorted((a.handle, b.handle))
            paires.setdefault((handle_a, handle_b), set()).add(cle)
    return paires, ignores


REGLE_DATE_PARENTS = "date_complete+parents"
REGLE_DATE = "date_complete"
REGLE_CONJOINT_ENFANT = "conjoint+enfant"

_MODIFIER_EXACT = 0
"""Seul modificateur Gramps qui FIXE une date au lieu de la borner."""


def date_complete(ev: EventFact | None) -> bool:
    """Vrai si l'événement porte une date EXACTE de précision au JOUR.

    Seul `modifier == 0` (date exacte) prouve une identité : c'est le seul cas
    où la date est fixée plutôt que bornée. Tous les autres modificateurs
    Gramps — avant (1), après (2), environ (3), intervalle (4), span (5),
    texte libre (6) — bornent ou approximent une date sans la fixer : deux
    personnes distinctes peuvent tout à fait partager la même date « vers » ou
    la même borne « avant »/« après ». Les accepter créerait un faux positif
    de fusion automatique et irréversible (§4.1 — cf. l'incident du
    2026-07-19 sur l'année seule, dont ceci est une variante).

    Un `sortval` à 0 (inconnu ou non triable) ne compte jamais non plus.
    """
    if ev is None or ev.sortval == 0 or ev.modifier != _MODIFIER_EXACT:
        return False
    if len(ev.dateval) < 3:
        return False
    jour, mois = ev.dateval[0], ev.dateval[1]
    return bool(jour) and bool(mois)


def _memes_parents(
    a: PersonFacts, b: PersonFacts, familles: dict[str, FamilyFacts]
) -> bool:
    """Vrai si les deux personnes ont un père ET une mère identiques et connus."""

    def parents(p: PersonFacts) -> tuple[str | None, str | None]:
        for handle in p.parent_family_handles:
            famille = familles.get(handle)
            if famille and famille.father_handle and famille.mother_handle:
                return famille.father_handle, famille.mother_handle
        return None, None

    pere_a, mere_a = parents(a)
    if pere_a is None or mere_a is None:
        return False
    return (pere_a, mere_a) == parents(b)


def _conjoints_et_enfants(
    p: PersonFacts, familles: dict[str, FamilyFacts]
) -> tuple[set[str], set[str]]:
    conjoints: set[str] = set()
    enfants: set[str] = set()
    for handle in p.family_handles:
        famille = familles.get(handle)
        if famille is None:
            continue
        for candidat in (famille.father_handle, famille.mother_handle):
            if candidat and candidat != p.handle:
                conjoints.add(candidat)
        enfants.update(famille.child_handles)
    return conjoints, enfants


def _meme_conjoint_et_enfant(
    a: PersonFacts, b: PersonFacts, familles: dict[str, FamilyFacts]
) -> bool:
    conjoints_a, enfants_a = _conjoints_et_enfants(a, familles)
    conjoints_b, enfants_b = _conjoints_et_enfants(b, familles)
    return bool(conjoints_a & conjoints_b) and bool(enfants_a & enfants_b)


def _regle_auto(
    a: PersonFacts, b: PersonFacts, familles: dict[str, FamilyFacts]
) -> str:
    """Rend la règle de l'étage auto qui conclut, ou la chaîne vide.

    Prérequis commun aux trois règles : le nom normalisé complet doit être
    identique et non vide. La similarité n'entre JAMAIS en jeu (spec §3.1).
    """
    nom = normalize_name(f"{a.given} {a.surname}")
    if not nom or nom != normalize_name(f"{b.given} {b.surname}"):
        return ""
    dates_identiques = (
        a.birth is not None
        and b.birth is not None
        and date_complete(a.birth)
        and date_complete(b.birth)
        and a.birth.sortval == b.birth.sortval
    )
    if dates_identiques and _memes_parents(a, b, familles):
        return REGLE_DATE_PARENTS
    if dates_identiques:
        return REGLE_DATE
    if _meme_conjoint_et_enfant(a, b, familles):
        return REGLE_CONJOINT_ENFANT
    return ""


def etager(
    people: list[PersonFacts],
    familles: dict[str, FamilyFacts],
    max_bloc: int = MAX_BLOC,
) -> tuple[list[MergePair], list[str]]:
    """Classe chaque paire candidate en auto / arbitrage / rejet (spec §4.1)."""
    par_handle = {p.handle: p for p in people}
    paires_candidates, ignores = candidate_pairs(people, max_bloc=max_bloc)
    resultat: list[MergePair] = []
    for (handle_a, handle_b), blocs in sorted(paires_candidates.items()):
        a, b = par_handle[handle_a], par_handle[handle_b]
        regle = _regle_auto(a, b, familles)
        tier: MergeTier
        if regle:
            tier = "auto"
        elif blocs == {cle for cle in blocs if cle.startswith("pho:")}:
            # Rapprochées par la seule ressemblance de nom : jamais une preuve.
            tier = "rejet"
        else:
            tier = "arbitrage"
        resultat.append(
            MergePair(
                gramps_id_a=a.gramps_id,
                gramps_id_b=b.gramps_id,
                handle_a=handle_a,
                handle_b=handle_b,
                tier=tier,
                regle=regle,
                blocs=sorted(blocs),
            )
        )
    return resultat, ignores
