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

"""Tests for the geocode_place tool and its rendering."""

from unittest.mock import patch

import httpx
import pytest

from src.gramps_mcp.genealogy.domain import DatedChain, PlaceLevel, ResolvedPlace
from src.gramps_mcp.handlers.geocode_handler import format_place_resolution
from src.gramps_mcp.tools.detection import geocode_place_tool


def _resolved(**overrides) -> ResolvedPlace:
    """A fully-populated ResolvedPlace, every required field filled.

    ResolvedPlace (genealogy/domain.py) requires name, place_type, score,
    source and query - none of them have defaults. Tests build one through
    this helper rather than guessing which fields matter for a given case.
    """
    fields = {
        "name": "Bourges",
        "place_type": "Municipality",
        "lat": "47.081",
        "long": "2.398",
        "code": "18033",
        "chains": [
            DatedChain(
                levels=[
                    PlaceLevel(name="France", place_type="Country"),
                    PlaceLevel(name="Centre-Val de Loire", place_type="Region"),
                    PlaceLevel(name="Cher", place_type="Department", code="18"),
                ]
            )
        ],
        "score": 1.0,
        "ambiguous": False,
        "source": "geo.api.gouv.fr",
        "query": "/communes/18033",
    }
    fields.update(overrides)
    return ResolvedPlace(**fields)


class TestGeocodeRendering:
    def test_no_match_and_a_provider_error_render_differently(self):
        no_match = format_place_resolution(
            None, action="indecidable", confiance="basse", query="Nowhere"
        )
        failed = format_place_resolution(
            None,
            action="indecidable",
            confiance="basse",
            query="Nowhere",
            error="geo.api.gouv.fr timed out",
        )

        assert no_match != failed
        assert "timed out" in failed
        assert "timed out" not in no_match

    def test_an_ambiguous_result_is_flagged_not_silently_picked(self):
        resolved = _resolved(name="Le Rocher", score=0.93, ambiguous=True)

        text = format_place_resolution(
            resolved, action="proposition", confiance="basse", query="Le Rocher"
        )

        assert "ambigu" in text.lower() or "ambiguous" in text.lower()

    def test_it_never_claims_to_have_written_anything(self):
        resolved = _resolved(name="Bourges", score=1.0, ambiguous=False)

        text = format_place_resolution(
            resolved, action="ecrire", confiance="haute", query="Bourges, Cher"
        )

        assert "created" not in text.lower()
        assert "create_place" in text

    def test_a_solid_resolution_still_names_create_place_as_next_step(self):
        """Same rule as above, from the caller's point of view: even the
        highest-confidence action ('ecrire') must read as a proposal, never
        as a completed write."""
        resolved = _resolved(score=1.0, ambiguous=False)

        text = format_place_resolution(
            resolved, action="ecrire", confiance="haute", query="Bourges, Cher"
        )

        assert "written" not in text.lower() or "not" in text.lower()
        assert "create_place" in text

    def test_the_administrative_chain_and_code_are_rendered(self):
        resolved = _resolved()

        text = format_place_resolution(
            resolved, action="ecrire", confiance="haute", query="Bourges, Cher"
        )

        assert "Cher" in text
        assert "18033" in text
        assert "47.081" in text and "2.398" in text

    def test_no_administrative_chain_renders_no_chain_line(self):
        """map_nominatim (genealogy/geo/nominatim.py) always returns
        `chains=[DatedChain(levels=[])]` on a worldwide fallback with no
        hierarchy - never an empty `chains` list. `_format_chain` must
        detect this by checking `chains[0].levels`, not `chains` itself
        (that guard was dead - `chains` is never empty in practice) or by
        checking whether `names` ended up empty (it never does: the place's
        own name is always appended, so a bare "Bourges" one-element
        "hierarchy" would have rendered instead of being suppressed).
        """
        resolved = _resolved(chains=[DatedChain(levels=[])])

        text = format_place_resolution(
            resolved, action="proposition", confiance="basse", query="Bourges"
        )

        assert "Administrative chain" not in text

    def test_a_provider_failure_names_the_error(self):
        text = format_place_resolution(
            None,
            action="indecidable",
            confiance="basse",
            query="Bourges",
            error="geo.api.gouv.fr timed out",
        )

        assert "geo.api.gouv.fr timed out" in text


class TestGeocodePlaceTool:
    """Proves the tool - not just the handler - by patching only the
    resolver seam (registry.resolve_place, imported into tools.detection)
    and asserting on the tool's own returned text, never on the mock's
    call arguments.
    """

    async def test_it_renders_a_resolved_place(self):
        resolved = _resolved()

        with patch(
            "src.gramps_mcp.tools.detection.resolve_place", return_value=resolved
        ):
            result = await geocode_place_tool(None, {"query": "Bourges, Cher, France"})

        text = result[0].text

        assert "Bourges" in text
        assert "create_place" in text
        assert "created" not in text.lower()

    async def test_a_gazetteer_being_unreachable_is_reported_as_such(self):
        """Pins that the tool catches httpx.HTTPError on its own dedicated
        seam (routing to format_place_resolution's `error=` branch), rather
        than falling through to the generic `except Exception` handler
        shared by every other tool. Both branches happen to keep the
        exception's own message ("timed out" would pass either way), so
        the discriminating assertion is the wording only the dedicated
        branch produces, and the absence of the generic handler's "Error:"
        prefix (_format_error_response's own wording, proven by
        test_the_generic_handler_prefixes_with_error below)."""
        with patch(
            "src.gramps_mcp.tools.detection.resolve_place",
            side_effect=httpx.ConnectTimeout("geo.api.gouv.fr timed out"),
        ):
            result = await geocode_place_tool(None, {"query": "Bourges, Cher"})

        text = result[0].text

        assert "timed out" in text
        assert "unreachable" in text.lower()
        assert not text.startswith("Error:")

    async def test_the_generic_handler_prefixes_with_error(self):
        """Establishes what the OTHER path (the shared `except Exception`
        fallback, used for e.g. a validation failure) looks like, so the
        assertions above are known to discriminate rather than coincide."""
        result = await geocode_place_tool(None, {})  # missing required `query`

        assert result[0].text.startswith("Error:")

    async def test_no_match_renders_differently_from_a_provider_failure(self):
        with patch("src.gramps_mcp.tools.detection.resolve_place", return_value=None):
            no_match_result = await geocode_place_tool(None, {"query": "Nowhere"})

        with patch(
            "src.gramps_mcp.tools.detection.resolve_place",
            side_effect=httpx.ConnectTimeout("timed out"),
        ):
            failed_result = await geocode_place_tool(None, {"query": "Nowhere"})

        assert no_match_result[0].text != failed_result[0].text
        assert "timed out" not in no_match_result[0].text
        assert "timed out" in failed_result[0].text
        assert "unreachable" in failed_result[0].text.lower()

    async def test_an_ambiguous_resolution_is_flagged_not_silently_picked(self):
        resolved = _resolved(name="Le Rocher", score=0.93, ambiguous=True)

        with patch(
            "src.gramps_mcp.tools.detection.resolve_place", return_value=resolved
        ):
            result = await geocode_place_tool(None, {"query": "Le Rocher"})

        text = result[0].text

        assert "ambigu" in text.lower() or "ambiguous" in text.lower()


class TestGeocodeLive:
    pytestmark = pytest.mark.integration

    async def test_it_resolves_a_french_commune(self):
        result = await geocode_place_tool(None, {"query": "Bourges, Cher, France"})
        text = result[0].text

        assert "Bourges" in text
        assert "18033" in text or "Cher" in text

    async def test_it_resolves_a_swiss_commune(self):
        result = await geocode_place_tool(None, {"query": "Nidau, Berne, Suisse"})
        text = result[0].text

        assert "Nidau" in text
