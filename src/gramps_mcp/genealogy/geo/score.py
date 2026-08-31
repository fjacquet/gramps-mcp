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

"""Pure scoring for place resolution (dataset-agnostic).

Copied from fjacquet/crewai-custom-tools v0.31.1 (19d78f7),
src/crewai_custom_tools/tools/genealogy/geo/score.py.
Divergence from that copy is expected and accepted; see
docs/superpowers/specs/2026-08-30-detection-tools-design.md.
"""

from __future__ import annotations

import math
import re
import unicodedata
from difflib import SequenceMatcher

AMBIGUITY_MARGIN = 0.10
_EARTH_RADIUS_M = 6_371_000.0


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance orthodromique en mètres entre deux points WGS84 (haversine).

    Sert à VÉRIFIER qu'un candidat trouvé par son nom se trouve bien au bon
    endroit — la position est ce qui distingue Paris de Paris, Texas. L'ordre
    des arguments est lat/lon, jamais lon/lat : GeoJSON et le WKT Wikidata
    ordonnent l'inverse.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _norm(s: str) -> str:
    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    return s.strip().upper()


def similarity(a: str, b: str) -> float:
    """Accent/case-insensitive string similarity in [0,1]."""
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def fuzzy_score(provider_conf: float, asked: str, returned: str) -> float:
    """Combine provider confidence with name similarity.

    Penalizes "right score, wrong place".
    """
    return max(0.0, min(1.0, provider_conf)) * similarity(asked, returned)


def is_ambiguous(candidates: list[float], margin: float = AMBIGUITY_MARGIN) -> bool:
    """True when the top two candidate scores are within `margin`.

    Undecidable -> proposition.
    """
    if len(candidates) < 2:
        return False
    top2 = sorted(candidates, reverse=True)[:2]
    return (top2[0] - top2[1]) < margin


_PAREN = re.compile(r"\s*\([^)]*\)")  # " (VD)", " (68)"


def _forms(returned: str) -> set[str]:
    """Formes-cœur candidates d'un libellé décoré : le tout, le tout sans
    suffixe parenthésé, et chaque jeton (espaces) de chacun — pour matcher
    un nom-cœur dans un libellé multi-mots ou multi-scripts."""
    stripped = _PAREN.sub("", returned).strip()
    forms = {returned.strip(), stripped}
    for base in (returned, stripped):
        forms.update(tok for tok in base.split() if tok)
    return {f for f in forms if f}


def best_similarity(asked: str, returned: str) -> float:
    """Meilleure similarité entre `asked` et une forme-cœur de `returned`.
    Monotone : toujours >= similarity(asked, returned) — les exacts restent
    1.0, les décorations ('(VD)', alias multi-scripts) ne dépriment plus le
    score."""
    return max(
        similarity(asked, returned),
        max((similarity(asked, f) for f in _forms(returned)), default=0.0),
    )
