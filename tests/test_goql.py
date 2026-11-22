"""Offline tests for the GOQL rules builder."""

import json

from src.gramps_mcp.goql import build_rules


def test_build_rules_shape():
    """The rules JSON holds one MatchesQuery rule under "and"."""
    rules = json.loads(build_rules('gramps_id == "I0001"'))
    assert rules["function"] == "and"
    assert rules["rules"][0]["name"] == "MatchesQuery"
    assert rules["rules"][0]["values"] == ['gramps_id == "I0001"']


def test_build_rules_keeps_unicode():
    """Non-ASCII characters survive the round trip."""
    out = build_rules('surname == "Müller"')
    assert json.loads(out)["rules"][0]["values"][0] == 'surname == "Müller"'
