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

    def test_text_only_date_with_no_dateval_is_accepted(self):
        # Reason: this is the case that motivated relaxing the field-level
        # requirement. date_handler.py returns `text` for modifier 6 before
        # ever reading `dateval`, so a text-only payload with no dateval key
        # at all is legitimate and must not be rejected.
        value = DateValue(modifier=6, text="vers la Saint-Jean 1885")

        assert value.dateval is None
        assert value.text == "vers la Saint-Jean 1885"

    def test_text_only_date_with_empty_dateval_is_accepted(self):
        value = DateValue(dateval=[], modifier=6, text="vers 1885")

        assert value.text == "vers 1885"

    def test_range_with_more_than_eight_entries_is_rejected(self):
        with pytest.raises(ValidationError):
            DateValue(
                dateval=[12, 3, 1885, False, 26, 3, 1885, False, 1, 1, 1900, False],
                modifier=4,
            )

    def test_regular_date_with_fewer_than_four_entries_is_rejected(self):
        with pytest.raises(ValidationError):
            DateValue(dateval=[12, 3], modifier=0)

    def test_regular_date_with_four_entries_is_accepted(self):
        value = DateValue(dateval=[12, 3, 1885, False], modifier=0)

        assert len(value.dateval) == 4

    def test_modifier_out_of_range_is_rejected(self):
        # Reason: modifier 45 validates against a bare int field and reaches
        # Gramps, which renders it with an empty prefix (date_handler.py's
        # lookup falls back to "") - a silently wrong date. Valid modifiers
        # are 0-8.
        with pytest.raises(ValidationError):
            DateValue(dateval=[12, 3, 1885, False], modifier=45)

    def test_negative_modifier_is_rejected(self):
        with pytest.raises(ValidationError):
            DateValue(dateval=[12, 3, 1885, False], modifier=-1)

    def test_quality_out_of_range_is_rejected(self):
        # Reason: valid qualities are 0 (regular), 1 (estimated), 2
        # (calculated). Anything else is a silently wrong date.
        with pytest.raises(ValidationError):
            DateValue(dateval=[12, 3, 1885, False], quality=3)

    def test_negative_quality_is_rejected(self):
        with pytest.raises(ValidationError):
            DateValue(dateval=[12, 3, 1885, False], quality=-1)
