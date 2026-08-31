"""Tests for the audit_quality tool and its rendering."""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.gramps_mcp.genealogy.collect import CollectResult
from src.gramps_mcp.genealogy.domain import Anomaly, EventFact, FamilyFacts, PersonFacts
from src.gramps_mcp.handlers.audit_handler import format_anomalies
from src.gramps_mcp.models.parameters.detection_params import AuditQualityParams
from src.gramps_mcp.tools.detection import audit_quality_tool


class TestLimitRejectsZeroAndNegative:
    """See test_detection_duplicates.py::TestLimitRejectsZeroAndNegative -
    same defect (`limit=0` read as falsy, so "stop after zero" behaved like
    "no limit"), same fix (`ge=1`), mirrored here for AuditQualityParams.
    """

    @pytest.mark.parametrize("bad_limit", [0, -1, -5])
    def test_non_positive_limit_is_rejected(self, bad_limit):
        with pytest.raises(ValidationError):
            AuditQualityParams(limit=bad_limit)

    def test_positive_limit_is_accepted(self):
        assert AuditQualityParams(limit=1).limit == 1


class TestAuditRendering:
    def test_a_clean_tree_says_so_rather_than_rendering_nothing(self):
        text = format_anomalies([], skipped=0, partial=False, error=None)

        assert text.strip()
        assert "0" in text or "none" in text.lower()

    def test_a_partial_scan_says_so(self):
        text = format_anomalies([], skipped=0, partial=True, error="timeout")

        assert "partial" in text.lower()
        assert "timeout" in text

    def test_highest_severity_renders_first_with_real_domain_values(self):
        """Uses the actual severities the rules engine emits (rules.py), not
        the placeholder "high"/"low" strings above - this is the test that
        proves the ordering rule against production data, not just an
        arbitrary string comparison.

        Input is deliberately given low-severity-first, so a passing test
        only happens if format_anomalies actually reorders rather than
        preserving input order.
        """
        low_first = [
            Anomaly(
                rule="R9",
                severity="basse",
                gramps_id="I0009",
                handle="h9",
                message="Aucune source ni citation rattachee.",
            ),
            Anomaly(
                rule="R6",
                severity="moyenne",
                gramps_id="I0006",
                handle="h6",
                message="Evenement date hors de la vie.",
            ),
            Anomaly(
                rule="R1",
                severity="haute",
                gramps_id="I0001",
                handle="h1",
                message="Naissance posterieure au deces.",
            ),
        ]

        text = format_anomalies(low_first, skipped=0, partial=False, error=None)

        assert text.index("R1") < text.index("R6") < text.index("R9")

    def test_a_severity_group_is_capped_and_says_how_many_more(self):
        """Pins MAX_PER_SEVERITY (audit_handler.py): more anomalies than the
        cap in one severity must render only the cap's worth of bullets,
        plus a count of the rest - and must never claim a route to see them
        that does not exist (collect.py's `limit` has no offset, so
        `severity` + a smaller `limit` cannot page through a capped group;
        see the "Correction" note in the design doc).
        """
        from src.gramps_mcp.handlers.audit_handler import MAX_PER_SEVERITY

        many = [
            Anomaly(
                rule="R9",
                severity="basse",
                gramps_id=f"I{i:04d}",
                handle=f"h{i}",
                message="Aucune source ni citation rattachee.",
            )
            for i in range(MAX_PER_SEVERITY + 7)
        ]

        text = format_anomalies(many, skipped=0, partial=False, error=None)

        shown = sum(1 for i in range(len(many)) if f"I{i:04d}" in text)
        assert shown == MAX_PER_SEVERITY
        assert "7 more" in text
        assert "no way to page through them" in text.lower()
        # The old (wrong) advice must not survive: it told the caller to
        # narrow with severity + a smaller limit to "page through the rest",
        # which collect.py's limit (a prefix, no offset) cannot do.
        assert "page through the rest" not in text.lower()

    def test_scope_reports_the_filter_and_limit_actually_applied(self):
        """A truncated scan must say so, not read as a whole-tree one."""
        text = format_anomalies(
            [], skipped=0, partial=False, error=None, severity="basse", limit=100
        )

        assert "100" in text
        assert "basse" in text
        assert "clean" not in text.lower()


def _birth(year: int) -> EventFact:
    """A birth event with a sortable date, at day precision within the year."""
    return EventFact(type="Birth", sortval=year * 366, year=year)


def _death(year: int) -> EventFact:
    return EventFact(type="Death", sortval=year * 366, year=year)


class TestAuditQualityTool:
    """Proves the tool - not just the handler - wires collect_tree's output
    through the real check_person and check_family, not a mock.

    Only collect_tree is patched (to avoid a live server); check_person and
    check_family run for real over the CollectResult below.
    """

    async def test_it_runs_real_rules_and_renders_person_and_family_anomalies(self):
        # R1 - birth after death - a person-level anomaly.
        reversed_dates = PersonFacts(
            gramps_id="I0001",
            handle="h1",
            name="Jean Dupont",
            surname="Dupont",
            given="Jean",
            sex="M",
            birth=_birth(1950),
            death=_death(1900),
        )
        # R3 - mother far too young at the child's birth - a family-level
        # anomaly, attached to the child.
        mother = PersonFacts(
            gramps_id="I0002",
            handle="h2",
            name="Marie Dupont",
            surname="Dupont",
            given="Marie",
            sex="F",
            birth=_birth(1900),
        )
        child = PersonFacts(
            gramps_id="I0003",
            handle="h3",
            name="Paul Dupont",
            surname="Dupont",
            given="Paul",
            sex="M",
            birth=_birth(1905),
        )
        family = FamilyFacts(
            gramps_id="F0001",
            handle="hf1",
            mother_handle="h2",
            child_handles=["h3"],
        )

        collected = CollectResult(
            people=[reversed_dates, mother, child],
            families={"hf1": family},
            skipped=0,
            partial=False,
            error=None,
        )

        with patch(
            "src.gramps_mcp.tools.detection.collect_tree",
            new_callable=AsyncMock,
            return_value=collected,
        ):
            result = await audit_quality_tool({})

        text = result[0].text

        assert "R1" in text
        assert "I0001" in text
        assert "R3" in text
        assert "I0003" in text

    async def test_severity_filter_drops_other_severities(self):
        reversed_dates = PersonFacts(
            gramps_id="I0001",
            handle="h1",
            name="Jean Dupont",
            surname="Dupont",
            given="Jean",
            sex="M",
            birth=_birth(1950),
            death=_death(1900),
        )
        collected = CollectResult(
            people=[reversed_dates],
            families={},
            skipped=0,
            partial=False,
            error=None,
        )

        with patch(
            "src.gramps_mcp.tools.detection.collect_tree",
            new_callable=AsyncMock,
            return_value=collected,
        ):
            result = await audit_quality_tool({"severity": "basse"})

        text = result[0].text

        # R1 is severity "haute" - filtered out when only "basse" is asked
        # for. R9 (no citation) is "basse" and should remain.
        assert "R1" not in text
        assert "R9" in text
