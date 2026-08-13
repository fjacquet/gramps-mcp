"""
Unit tests for date parameter validation. No server involved.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.date_params import DateValue


class TestDateValue:
    """A modifier promising two dates must carry two."""

    def test_range_without_second_date_is_rejected(self):
        with pytest.raises(ValidationError):
            DateValue(dateval=[12, 3, 1885, False], modifier=4)

    def test_span_without_second_date_is_rejected(self):
        with pytest.raises(ValidationError):
            DateValue(dateval=[1, 1, 1900, False], modifier=5)

    def test_range_with_second_date_is_accepted(self):
        value = DateValue(dateval=[12, 3, 1885, False, 26, 3, 1885, False], modifier=4)

        assert len(value.dateval) == 8

    def test_plain_date_is_accepted(self):
        value = DateValue(dateval=[12, 3, 1885, False])

        assert value.modifier == 0
        assert value.quality == 0

    def test_estimated_quality_is_accepted(self):
        # Reason: CLAUDE.md recommends quality 1 with modifier 0 for an
        # approximate date, precisely to avoid the malformed range case.
        value = DateValue(dateval=[0, 0, 1885, False], quality=1, modifier=0)

        assert value.quality == 1

    def test_text_only_date_is_accepted(self):
        value = DateValue(dateval=[0, 0, 0, False], modifier=6, text="vers 1885")

        assert value.text == "vers 1885"

    def test_from_modifier_without_second_date_is_accepted(self):
        # Reason: modifier 7 (from) is an open-ended single-date modifier,
        # not a two-date modifier. Verified against Gramps' is_compound(),
        # which is True only for modifier 4 (range) and 5 (span).
        value = DateValue(dateval=[12, 3, 1885, False], modifier=7)

        assert value.modifier == 7

    def test_to_modifier_without_second_date_is_accepted(self):
        value = DateValue(dateval=[12, 3, 1885, False], modifier=8)

        assert value.modifier == 8
