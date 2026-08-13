"""
Unit tests for Gramps date rendering. These are pure functions - no server.
"""

from src.gramps_mcp.handlers.date_handler import format_date


class TestRangeAndSpan:
    """Modifiers carrying two dates must render both."""

    def test_range_renders_both_endpoints(self):
        date_obj = {
            "dateval": [12, 3, 1885, False, 26, 3, 1885, False],
            "modifier": 4,
            "quality": 0,
        }

        result = format_date(date_obj)

        assert "12 March 1885" in result
        assert "26 March 1885" in result

    def test_span_renders_both_endpoints(self):
        date_obj = {
            "dateval": [1, 1, 1900, False, 31, 12, 1910, False],
            "modifier": 5,
            "quality": 0,
        }

        result = format_date(date_obj)

        assert "1900" in result
        assert "1910" in result

    def test_single_date_is_unchanged(self):
        date_obj = {"dateval": [12, 3, 1885, False], "modifier": 0, "quality": 0}

        assert format_date(date_obj) == "12 March 1885"

    def test_from_modifier_is_open_ended_single_date(self):
        """Modifier 7 (from) is not compound: it has a four-element dateval
        with no stop date, and renders as a single date with the "from "
        prefix."""
        date_obj = {"dateval": [12, 3, 1885, False], "modifier": 7, "quality": 0}

        assert format_date(date_obj) == "from 12 March 1885"


class TestFreeText:
    """Modifier 6 keeps its content in the text field."""

    def test_free_text_date_is_returned(self):
        date_obj = {
            "dateval": [0, 0, 0, False],
            "modifier": 6,
            "quality": 0,
            "text": "vers la Saint-Jean 1885",
        }

        assert format_date(date_obj) == "vers la Saint-Jean 1885"

    def test_free_text_without_content_is_unknown(self):
        date_obj = {
            "dateval": [0, 0, 0, False],
            "modifier": 6,
            "quality": 0,
            "text": "",
        }

        assert format_date(date_obj) == "date unknown"


class TestExistingBehaviour:
    """The preformatted string and the empty cases keep winning."""

    def test_preformatted_string_wins(self):
        date_obj = {"string": "1885-03-12", "dateval": [12, 3, 1885, False]}

        assert format_date(date_obj) == "1885-03-12"

    def test_empty_object_is_unknown(self):
        assert format_date({}) == "date unknown"
