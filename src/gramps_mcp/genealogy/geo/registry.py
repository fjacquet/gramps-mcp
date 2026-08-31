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

"""Country-routed resolver chain + action/confidence decision (dataset-agnostic).

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/geo/registry.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.

Trimmed of the `resolve_de` (Germany) and `resolve_us` (United States)
imports and their `_BY_COUNTRY` entries - those resolvers, and the
`de_communes.csv` (789 KB) / `us_places.csv` (1.56 MB) datasets they depend
on, are deliberately out of scope for this repo.
"""

from __future__ import annotations

from ..domain import ParsedPlace, ResolvedPlace
from .france import resolve_fr
from .france_ex_communes import resolve_fr_ex_commune
from .nominatim import resolve_world
from .suisse import resolve_ch
from .transitions import apply_transition, load_transitions

# Résolveurs autoritaires par pays. Ajouter un pays = une ligne (générique).
_BY_COUNTRY = {
    # Les communes fusionnées sont absentes de /communes : si resolve_fr rend None,
    # on tente /communes_associees_deleguees AVANT le repli Nominatim, qui perdrait
    # la hiérarchie. Le branchement est ici et non dans resolve_fr, parce que
    # france_ex_communes importe map_commune depuis france (sinon : cycle).
    # Nota : un résultat ambigu est truthy -> pas de repli, c'est voulu.
    "France": lambda p: resolve_fr(p) or resolve_fr_ex_commune(p),
    "Suisse": lambda p: resolve_ch(p),
}


def resolve_place(parsed: ParsedPlace) -> ResolvedPlace | None:
    """Route to the country resolver; fall back to worldwide; apply temporal
    transitions."""
    country_resolver = _BY_COUNTRY.get(parsed.country)
    resolved = country_resolver(parsed) if country_resolver is not None else None
    if resolved is None:
        resolved = resolve_world(parsed)
    return apply_transition(resolved, parsed, load_transitions())


def decide_action(resolved: ResolvedPlace | None, min_score: float) -> str:
    """Map a resolution to 'ecrire' | 'proposition' | 'indecidable'."""
    if resolved is None:
        return "indecidable"
    if resolved.ambiguous:
        return "proposition"  # ambiguity wins over any score, incl. 1.0
    if resolved.score >= 1.0:
        return "ecrire"
    if resolved.score >= min_score:
        return "ecrire"
    return "proposition"


def confiance_of(resolved: ResolvedPlace | None, min_score: float = 0.90) -> str:
    if resolved is None or resolved.ambiguous:
        return "basse"
    if resolved.score >= 1.0:
        return "haute"
    if resolved.score >= min_score:
        return "moyenne"
    return "basse"
