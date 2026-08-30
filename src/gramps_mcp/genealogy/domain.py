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

"""Hand-written domain models for the deterministic audit (Phase 1a).

These are the normalized facts the pure rules operate on — decoupled from the
raw Gramps Web JSON, which the genecrew orchestrator maps into these shapes.

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/models/domain.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EventFact(BaseModel):
    """One dated event, reduced to what the rules need."""

    type: str  # "Birth", "Death", "Baptism", "Burial", "Marriage"...
    sortval: int = 0  # Julian day number; 0 = unknown/unsortable
    year: int | None = None
    modifier: int = 0  # 0 exact,1 before,2 after,3 about,4 range,5 span,6 text
    quality: int = 0  # 0 normal,1 estimated,2 calculated
    dateval: list = Field(default_factory=list)
    has_citation: bool = False
    place: str = ""  # hiérarchie complète, depuis profile.<birth|death>.place
    place_name: str = ""  # commune seule, depuis profile.<birth|death>.place_name


class PersonFacts(BaseModel):
    """Normalized person facts for the rules engine."""

    gramps_id: str
    handle: str
    name: str
    surname: str
    given: str
    sex: str  # "M", "F", "U"
    birth: EventFact | None = None
    death: EventFact | None = None
    events: list[EventFact] = Field(default_factory=list)
    has_any_citation: bool = False
    parent_family_handles: list[str] = Field(default_factory=list)
    family_handles: list[str] = Field(default_factory=list)


class FamilyFacts(BaseModel):
    """Normalized family facts for the family rules (R3, R4, R5)."""

    gramps_id: str
    handle: str
    father_handle: str | None = None
    mother_handle: str | None = None
    child_handles: list[str] = Field(default_factory=list)
    marriage: EventFact | None = None


class Anomaly(BaseModel):
    """One detected inconsistency, attached to a person."""

    rule: str  # "R1".."R9"
    severity: str  # "haute" | "moyenne" | "basse"
    gramps_id: str
    handle: str
    message: str  # human-readable, French
    detail: dict = Field(default_factory=dict)


class DuplicateCandidate(BaseModel):
    """A pair of persons that may be duplicates (R10)."""

    gramps_id_a: str
    gramps_id_b: str
    score: float
    reason: str


class ParsedPlace(BaseModel):
    """Result of parsing one flat GEDCOM-style place string.

    Positional, country last.
    """

    raw: str
    commune: str = ""
    insee: str | None = None  # 5-char INSEE code if embedded
    ags: str | None = None  # 8-digit Amtlicher Gemeindeschlüssel (Germany)
    postal: str | None = None
    departement: str = ""
    region: str = ""
    country: str = ""  # normalized country label/ISO
    shifted: bool = False  # positional shift detected (no reliable code)


class PlaceLevel(BaseModel):
    """One node in a place's parent chain (top→down)."""

    name: str
    place_type: str  # "Country" | "Region" | "Department" | "Municipality"…
    code: str | None = None


class DatedName(BaseModel):
    value: str
    date_qualifier: str | None = None  # None | "avant AAAA-MM-JJ" | "après AAAA-MM-JJ"


class DatedChain(BaseModel):
    """A parent chain valid over a period (top→down)."""

    levels: list[PlaceLevel]
    date_qualifier: str | None = None


class ResolvedPlace(BaseModel):
    """Normalized output every country resolver returns (the resolver contract)."""

    name: str
    place_type: str
    lat: str | None = None  # WGS84 decimal (never Swiss x/y grid)
    long: str | None = None
    code: str | None = None
    chains: list[DatedChain] = Field(default_factory=list)
    alt_names: list[DatedName] = Field(default_factory=list)
    score: float  # 1.0 authoritative ; <1.0 fuzzy
    ambiguous: bool = False  # ambiguity guard (spec §5) → forces proposition
    source: str
    query: str


MergeTier = Literal["auto", "arbitrage", "rejet"]
"""Les trois étages de la fusion (spec §4.1).

`auto` : preuve structurelle, fusion sans relecture. `arbitrage` : preuve
partielle, passe par un YAML relu. `rejet` : ressemblance de nom seule — jamais
une preuve.
"""


class MergePair(BaseModel):
    """Une paire de personnes, avec l'étage qui lui a été attribué."""

    gramps_id_a: str
    gramps_id_b: str
    handle_a: str
    handle_b: str
    tier: MergeTier
    regle: str = ""
    """Règle de l'étage auto qui a conclu : `date_complete+parents`,
    `date_complete`, `conjoint+enfant`. Vide pour les étages arbitrage et rejet."""
    blocs: list[str] = Field(default_factory=list)
    """Clés de blocage ayant produit la paire — traçabilité du rappel."""


class MergeCluster(BaseModel):
    """Une grappe de doublons réduite à un seul survivant (spec §4.5)."""

    phoenix_handle: str
    phoenix_gramps_id: str
    titanic_handles: list[str] = Field(default_factory=list)
    titanic_gramps_ids: list[str] = Field(default_factory=list)
    gender_patch: Literal[0, 1] | None = None
    """Genre à écrire sur le phoenix AVANT la fusion, ou None. `Person.merge()`
    ignore le genre : sans ce patch, un phoenix « Inconnu » perdrait sans trace le
    genre connu d'un titanic (spec §2)."""
