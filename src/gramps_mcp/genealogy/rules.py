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

"""Pure deterministic genealogy consistency rules (R1–R9).

Every function is side-effect free: it takes normalized facts and returns
Anomaly objects. Date comparisons use the Gramps Julian-day `sortval`
(integer); a rule is skipped when the dates it needs are unknown (sortval 0),
so unknown data never produces a false positive.

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/analysis/rules.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.

Two lines diverge from that copy, both annotations for mypy, not behaviour
changes: `is_valid` is typed `(ev: EventFact | None) -> TypeGuard[EventFact]`
instead of an unannotated `(ev) -> bool`, so callers get real narrowing on
`person.birth`/`person.death` instead of an untyped bool; `years_between` is
typed `(a: EventFact, b: EventFact) -> float` instead of unannotated
parameters.

A third divergence, made during the final review of this branch: R6's
before-birth branch (a life event dated before the person's birth) used to
fire for any event type, including `Baptism` and `Burial` - the same two
types R7 already checks against a more specific reference date (baptism vs.
birth, burial vs. death). A baptism dated before birth was reported twice,
once by each rule. See `R7_BEFORE_TYPES` below, excluded from R6's
before-birth branch the same way `POSTMORTEM_TYPES` is already excluded
from its after-death branch.
"""

from __future__ import annotations

from typing import TypeGuard

from .domain import (
    Anomaly,
    EventFact,
    FamilyFacts,
    PersonFacts,
)

DAYS_PER_YEAR = 365.25
POSTMORTEM_TYPES = {"Burial", "Cremation", "Probate", "Will"}
R7_BEFORE_TYPES = {"Baptism", "Burial"}
"""Event types R7 already checks against a specific reference date (baptism
vs. birth, burial vs. death). Excluded from R6's generic before-birth check
below - divergence from upstream (code review, round 2): the source let R6's
"any event before birth" branch fire for these too, so a baptism dated
before birth was reported twice, once by each rule, inflating the per-
severity cap and the totals the guide quotes. Mirrors the exclusion R6
already applies to POSTMORTEM_TYPES on its own after-death branch, for the
same reason.
"""


def is_valid(ev: EventFact | None) -> TypeGuard[EventFact]:
    """True when the event exists and carries a sortable date."""
    return ev is not None and ev.sortval > 0


def years_between(a: EventFact, b: EventFact) -> float:
    """Signed years from a to b using sortval (both must be valid)."""
    return (b.sortval - a.sortval) / DAYS_PER_YEAR


def _anom(rule, severity, p: PersonFacts, message, **detail) -> Anomaly:
    return Anomaly(
        rule=rule,
        severity=severity,
        gramps_id=p.gramps_id,
        handle=p.handle,
        message=message,
        detail=detail,
    )


def check_person(person: PersonFacts) -> list[Anomaly]:
    """Run all person-scoped rules (R1, R2, R6, R7, R8, R9)."""
    out: list[Anomaly] = []
    b, d = person.birth, person.death

    # R1 — birth after death
    if is_valid(b) and is_valid(d) and b.sortval > d.sortval:
        out.append(
            _anom(
                "R1",
                "haute",
                person,
                "Naissance postérieure au décès.",
                birth_year=b.year,
                death_year=d.year,
            )
        )

    # R2 — age at death > 105
    if is_valid(b) and is_valid(d):
        age = years_between(b, d)
        if age > 105:
            out.append(
                _anom(
                    "R2",
                    "haute",
                    person,
                    f"Âge au décès de {age:.0f} ans (> 105).",
                    birth_year=b.year,
                    death_year=d.year,
                    age=round(age, 1),
                )
            )

    # R6 — life event outside the person's lifespan
    for ev in person.events:
        if ev.type in {"Birth", "Death"} or not is_valid(ev):
            continue
        if ev.type not in R7_BEFORE_TYPES and is_valid(b) and ev.sortval < b.sortval:
            out.append(
                _anom(
                    "R6",
                    "moyenne",
                    person,
                    f"Événement « {ev.type} » ({ev.year}) daté avant la naissance.",
                    event_type=ev.type,
                    event_year=ev.year,
                    birth_year=b.year,
                )
            )
        elif ev.type not in POSTMORTEM_TYPES and is_valid(d) and ev.sortval > d.sortval:
            out.append(
                _anom(
                    "R6",
                    "moyenne",
                    person,
                    f"Événement « {ev.type} » ({ev.year}) daté après le décès.",
                    event_type=ev.type,
                    event_year=ev.year,
                    death_year=d.year,
                )
            )

    # R7 — baptism before birth ; burial before death
    for ev in person.events:
        if (
            ev.type == "Baptism"
            and is_valid(ev)
            and is_valid(b)
            and ev.sortval < b.sortval
        ):
            out.append(
                _anom(
                    "R7",
                    "moyenne",
                    person,
                    "Baptême antérieur à la naissance.",
                    baptism_year=ev.year,
                    birth_year=b.year,
                )
            )
        if (
            ev.type == "Burial"
            and is_valid(ev)
            and is_valid(d)
            and ev.sortval < d.sortval
        ):
            out.append(
                _anom(
                    "R7",
                    "moyenne",
                    person,
                    "Inhumation antérieure au décès.",
                    burial_year=ev.year,
                    death_year=d.year,
                )
            )

    # R8 — malformed date
    for ev in person.events:
        has_real_date = (ev.year is not None and ev.year != 0) or (
            len(ev.dateval) >= 3
            and all(isinstance(x, int) for x in ev.dateval[:3])
            and any(ev.dateval[:3])
        )
        out_of_bounds = (
            len(ev.dateval) >= 2
            and isinstance(ev.dateval[0], int)
            and isinstance(ev.dateval[1], int)
            and (ev.dateval[0] > 31 or ev.dateval[1] > 12)
        )
        aberrant_meta = ev.modifier not in range(0, 7) or ev.quality not in range(0, 3)
        if out_of_bounds or aberrant_meta or (has_real_date and ev.sortval == 0):
            out.append(
                _anom(
                    "R8",
                    "basse",
                    person,
                    f"Date malformée ou non interprétable sur « {ev.type} ».",
                    event_type=ev.type,
                    dateval=ev.dateval,
                )
            )

    # R9 — no source at all
    if not person.has_any_citation:
        out.append(_anom("R9", "basse", person, "Aucune source ni citation rattachée."))

    # D1 — aucune date vitale (complétude)
    if not is_valid(b) and not is_valid(d):
        out.append(
            _anom("D1", "basse", person, "Aucune date de naissance ni de décès.")
        )

    # D2 — date en texte libre (modifier 6 = non triable)
    for ev in person.events:
        if ev.modifier == 6:
            out.append(
                _anom(
                    "D2",
                    "basse",
                    person,
                    f"Date en texte libre (non exploitable) sur « {ev.type} ».",
                    event_type=ev.type,
                )
            )

    # D3 — genre non renseigné
    if person.sex not in ("M", "F"):
        out.append(_anom("D3", "basse", person, "Genre non renseigné."))

    return out


DAYS_9_MONTHS = 280


def _fanom(rule, p: PersonFacts, message, **detail) -> Anomaly:
    return Anomaly(
        rule=rule,
        severity="haute",
        gramps_id=p.gramps_id,
        handle=p.handle,
        message=message,
        detail=detail,
    )


def check_family(family: FamilyFacts, persons: dict[str, PersonFacts]) -> list[Anomaly]:
    """Run family-scoped rules (R3, R4, R5). Missing handles are skipped."""
    out: list[Anomaly] = []
    father = persons.get(family.father_handle) if family.father_handle else None
    mother = persons.get(family.mother_handle) if family.mother_handle else None
    children = [persons[h] for h in family.child_handles if h in persons]

    # R3 — parent age at each child's birth
    for child in children:
        if not is_valid(child.birth):
            continue
        for parent, lo, hi, label in (
            (mother, 13, 55, "de la mère"),
            (father, 13, 80, "du père"),
        ):
            if parent and is_valid(parent.birth):
                age = years_between(parent.birth, child.birth)
                if age < lo or age > hi:
                    out.append(
                        _fanom(
                            "R3",
                            child,
                            f"Âge {label} à la naissance : {age:.0f} ans "
                            f"(hors [{lo}, {hi}]).",
                            parent_gramps_id=parent.gramps_id,
                            parent_age=round(age, 1),
                        )
                    )

    # R4 — marriage before age 13 (each dated spouse)
    if is_valid(family.marriage):
        for spouse in (mother, father):
            if spouse and is_valid(spouse.birth):
                age = years_between(spouse.birth, family.marriage)
                if age < 13:
                    out.append(
                        _fanom(
                            "R4",
                            spouse,
                            f"Mariage à {age:.0f} ans (< 13).",
                            marriage_year=family.marriage.year,
                        )
                    )

    # R5 — child born after a parent's death
    for child in children:
        if not is_valid(child.birth):
            continue
        if (
            mother
            and is_valid(mother.death)
            and child.birth.sortval > mother.death.sortval
        ):
            out.append(
                _fanom(
                    "R5",
                    child,
                    "Naissance postérieure au décès de la mère.",
                    mother_gramps_id=mother.gramps_id,
                )
            )
        if (
            father
            and is_valid(father.death)
            and child.birth.sortval > father.death.sortval + DAYS_9_MONTHS
        ):
            out.append(
                _fanom(
                    "R5",
                    child,
                    "Naissance plus de 9 mois après le décès du père.",
                    father_gramps_id=father.gramps_id,
                )
            )

    return out
