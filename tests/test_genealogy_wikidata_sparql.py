"""Tests for the httpx-backed SPARQL transport."""

import httpx
import pytest

from src.gramps_mcp.genealogy.geo import sparql


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_sparql_rows_flattens_bindings(monkeypatch):
    payload = {
        "head": {"vars": ["item", "dissolved"]},
        "results": {
            "bindings": [
                {
                    "item": {"value": "http://www.wikidata.org/entity/Q25398054"},
                    "dissolved": {"value": "1972-12-31T00:00:00Z"},
                },
            ]
        },
    }
    seen = {}

    def fake_get(url, params, headers, timeout):
        seen["url"] = url
        seen["query"] = params["query"]
        seen["format"] = params["format"]
        return _FakeResponse(payload)

    monkeypatch.setattr(sparql.httpx, "get", fake_get)
    query = "SELECT ?item WHERE { ?item wdt:P374 '55451' }"
    rows = sparql.sparql_rows(query)
    assert rows == [
        {
            "item": "http://www.wikidata.org/entity/Q25398054",
            "dissolved": "1972-12-31T00:00:00Z",
        }
    ]
    assert seen["url"] == sparql.SPARQL_ENDPOINT
    assert seen["format"] == "json"
    assert seen["query"] == query


def test_sparql_rows_empty_results(monkeypatch):
    monkeypatch.setattr(
        sparql.httpx,
        "get",
        lambda *a, **k: _FakeResponse({"results": {"bindings": []}}),
    )
    assert sparql.sparql_rows("SELECT ?x WHERE { ?x wdt:P374 '00000' }") == []


def test_sparql_rows_raises_on_http_error(monkeypatch):
    class _FailingResponse(_FakeResponse):
        def raise_for_status(self):
            raise httpx.HTTPStatusError("500", request=None, response=None)

    monkeypatch.setattr(sparql.httpx, "get", lambda *a, **k: _FailingResponse({}))
    with pytest.raises(httpx.HTTPStatusError):
        sparql.sparql_rows("SELECT ?x WHERE { ?x wdt:P374 '00000' }")
