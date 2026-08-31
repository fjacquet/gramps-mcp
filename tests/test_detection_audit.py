"""Tests for the audit_quality tool and its rendering."""

from unittest.mock import AsyncMock, patch

from src.gramps_mcp.genealogy.collect import CollectResult
from src.gramps_mcp.genealogy.domain import Anomaly, EventFact, FamilyFacts, PersonFacts
from src.gramps_mcp.handlers.audit_handler import format_anomalies
from src.gramps_mcp.tools.detection import audit_quality_tool


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
