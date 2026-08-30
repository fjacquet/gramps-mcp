# tests/test_genealogy_geo_france.py
from src.gramps_mcp.genealogy.domain import ParsedPlace
from src.gramps_mcp.genealogy.geo.france import map_commune, resolve_fr

# forme réelle de geo.api.gouv.fr/communes/{code}?fields=nom,centre,codeDepartement,...
PAYLOAD = {
    "nom": "Bourges",
    "code": "18033",
    "centre": {"type": "Point", "coordinates": [2.3992, 47.0810]},  # [lon, lat]
    "codeDepartement": "18",
    "codeRegion": "24",
    "departement": {"code": "18", "nom": "Cher"},
    "region": {"code": "24", "nom": "Centre-Val de Loire"},
}


def test_map_commune_wgs84_lonlat_and_hierarchy():
    parsed = ParsedPlace(raw="…", commune="Bourges", insee="18033", country="France")
    rp = map_commune(PAYLOAD, parsed)
    assert rp.name == "Bourges" and rp.place_type == "Municipality"
    assert (
        rp.lat == "47.081" and rp.long == "2.3992"
    )  # centre = [lon, lat] → long=lon, lat=lat
    assert rp.score == 1.0 and rp.source == "geo.api.gouv.fr"
    assert len(rp.chains) == 1 and rp.chains[0].date_qualifier is None
    names = [lvl.name for lvl in rp.chains[0].levels]
    assert names == ["France", "Centre-Val de Loire", "Cher"]  # haut→bas
    assert (
        rp.alt_names[0].value == parsed.raw and rp.alt_names[0].date_qualifier is None
    )


def test_resolve_fr_returns_none_without_insee(monkeypatch):
    from src.gramps_mcp.genealogy.geo import france

    monkeypatch.setattr(france, "_http_get", lambda path, params: [])
    parsed = ParsedPlace(
        raw="…", commune="X", insee=None, country="France", shifted=True
    )
    assert resolve_fr(parsed) is None  # délègue au repli flou


_BOURGES = {
    "nom": "Bourges",
    "code": "18033",
    "centre": {"type": "Point", "coordinates": [2.3983, 47.078]},
    "departement": {"code": "18", "nom": "Cher"},
    "region": {"code": "24", "nom": "Centre-Val de Loire"},
}


def _sm(code, dept):
    return {
        "nom": "Sainte-Marie",
        "code": code,
        "centre": {"type": "Point", "coordinates": [0.0, 0.0]},
        "departement": {"code": "", "nom": dept},
        "region": {"code": "", "nom": ""},
    }


def test_resolve_fr_by_name_unique_is_authoritative(monkeypatch):
    from src.gramps_mcp.genealogy.domain import ParsedPlace
    from src.gramps_mcp.genealogy.geo import france

    seen = {}

    def fake_get(path, params):
        seen["path"] = path
        seen["params"] = params
        return [_BOURGES]

    monkeypatch.setattr(france, "_http_get", fake_get)
    rp = france.resolve_fr(ParsedPlace(raw="", commune="Bourges", country="France"))
    assert rp is not None
    assert rp.code == "18033" and rp.score == 1.0 and rp.ambiguous is False
    assert rp.lat == "47.078" and rp.long == "2.3983"  # GeoJSON [lon,lat] -> lat/lon
    assert [lvl.name for lvl in rp.chains[0].levels] == [
        "France",
        "Centre-Val de Loire",
        "Cher",
    ]
    assert seen["path"] == "/communes"
    assert (
        seen["params"]["nom"] == "Bourges" and seen["params"]["boost"] == "population"
    )


def test_resolve_fr_by_name_fuzzy_nonexact_returns_none(monkeypatch):
    from src.gramps_mcp.genealogy.domain import ParsedPlace
    from src.gramps_mcp.genealogy.geo import france

    # geo.api.gouv.fr's nom search is fuzzy: "Sainte-Marie" also returns this near-name,
    # which must NOT count as an exact match.
    fuzzy = {
        "nom": "Saintes-Maries-de-la-Mer",
        "code": "13096",
        "centre": {"type": "Point", "coordinates": [4.4, 43.4]},
        "departement": {"code": "13", "nom": "Bouches-du-Rhône"},
        "region": {"nom": ""},
    }
    monkeypatch.setattr(france, "_http_get", lambda path, params: [fuzzy])
    rp = france.resolve_fr(
        ParsedPlace(raw="", commune="Sainte-Marie", country="France")
    )
    assert rp is None


def test_resolve_fr_by_name_homonyms_are_proposition(monkeypatch):
    from src.gramps_mcp.genealogy.domain import ParsedPlace
    from src.gramps_mcp.genealogy.geo import france

    monkeypatch.setattr(
        france,
        "_http_get",
        lambda path, params: [
            _sm("97418", "La Réunion"),
            _sm("35294", "Ille-et-Vilaine"),
        ],
    )
    rp = france.resolve_fr(
        ParsedPlace(raw="", commune="Sainte-Marie", country="France")
    )
    assert rp is not None and rp.ambiguous is True


def test_resolve_fr_by_name_department_disambiguates(monkeypatch):
    from src.gramps_mcp.genealogy.domain import ParsedPlace
    from src.gramps_mcp.genealogy.geo import france

    monkeypatch.setattr(
        france,
        "_http_get",
        lambda path, params: [_sm("97418", "La Réunion"), _sm("25523", "Doubs")],
    )
    rp = france.resolve_fr(
        ParsedPlace(
            raw="", commune="Sainte-Marie", departement="Doubs", country="France"
        )
    )
    assert rp is not None and rp.ambiguous is False and rp.code == "25523"


def test_resolve_fr_by_name_region_only_context_does_not_collapse_homonyms(monkeypatch):
    from src.gramps_mcp.genealogy.domain import ParsedPlace
    from src.gramps_mcp.genealogy.geo import france

    # Two exact homonyms; context is region-only (departement=""), region matches NEITHER.
    # Candidate A has an empty dept code; the unguarded OR-clause would wrongly keep only A
    # and emit an authoritative (ambiguous=False) write. With the guard, exact stays 2 -> ambiguous.
    a = {
        "nom": "Sainte-Marie",
        "code": "97418",
        "centre": {"type": "Point", "coordinates": [0.0, 0.0]},
        "departement": {"code": "", "nom": "La Réunion"},
        "region": {"code": "", "nom": ""},
    }
    b = {
        "nom": "Sainte-Marie",
        "code": "25523",
        "centre": {"type": "Point", "coordinates": [0.0, 0.0]},
        "departement": {"code": "25", "nom": "Doubs"},
        "region": {"code": "", "nom": ""},
    }
    monkeypatch.setattr(france, "_http_get", lambda path, params: [a, b])
    rp = france.resolve_fr(
        ParsedPlace(raw="", commune="Sainte-Marie", region="Bretagne", country="France")
    )
    assert rp is not None and rp.ambiguous is True


def test_resolve_fr_insee_path_still_used(monkeypatch):
    from src.gramps_mcp.genealogy.domain import ParsedPlace
    from src.gramps_mcp.genealogy.geo import france

    calls = []

    def fake_get(path, params):
        calls.append(path)
        return dict(_BOURGES)

    monkeypatch.setattr(france, "_http_get", fake_get)
    rp = france.resolve_fr(
        ParsedPlace(raw="", commune="Bourges", insee="18033", country="France")
    )
    assert rp is not None and rp.code == "18033"
    assert calls == ["/communes/18033"]  # code path, not by-name
