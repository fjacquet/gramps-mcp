# tests/test_genealogy_geo_france_ex_communes.py
from src.gramps_mcp.genealogy.domain import ParsedPlace
from src.gramps_mcp.genealogy.geo import france_ex_communes as fec

# Ligne réellement rendue par query.wikidata.org pour ?item wdt:P374 "55451",
# avec la précision (?prec) demandée via p:P576/psv:P576 — Wikidata la porte à 11
# (jour) pour cette commune : une seule déclaration P576, sans ambiguïté.
_ROW_SAINT_AGNANT = {
    "item": "http://www.wikidata.org/entity/Q25398054",
    "dissolved": "1972-12-31T00:00:00Z",
    "prec": "11",
    "succInsee": "55012",
    "coord": "Point(5.622588 48.842142)",
}


def test_parse_wkt_point_is_lon_lat():
    # WKT met la LONGITUDE en premier, comme GeoJSON. Inverser placerait
    # Saint-Agnant au large de la Somalie.
    assert fec.parse_wkt_point("Point(5.622588 48.842142)") == ("48.842142", "5.622588")


def test_parse_wkt_point_handles_negative_longitude():
    assert fec.parse_wkt_point("Point(-1.553621 47.218371)") == (
        "47.218371",
        "-1.553621",
    )


def test_parse_wkt_point_rejects_garbage():
    assert fec.parse_wkt_point("") is None
    assert fec.parse_wkt_point("MULTIPOLYGON((0 0))") is None


def test_merged_on_from_dissolved_year_boundary():
    # Amblaincourt (Meuse) : passage d'année.
    assert fec.merged_on_from_dissolved("1972-12-31") == "1973-01-01"


def test_merged_on_from_dissolved_month_boundary():
    # Auzécourt (Meuse) : passage de mois.
    assert fec.merged_on_from_dissolved("1972-06-30") == "1972-07-01"


def test_merged_on_from_dissolved_end_of_february_non_leap_year():
    # Billy-sous-les-Côtes (Meuse) : fin février, année non bissextile.
    assert fec.merged_on_from_dissolved("1973-02-28") == "1973-03-01"


def test_merged_on_from_dissolved_leap_year():
    # Cas bissextile, à ne pas rater : le lendemain du 28 février 1972 est le 29,
    # pas le 1er mars.
    assert fec.merged_on_from_dissolved("1972-02-28") == "1972-02-29"


def test_merged_on_from_dissolved_none_is_none():
    assert fec.merged_on_from_dissolved(None) is None


def test_merged_on_from_dissolved_unparsable_is_none():
    # Une année seule n'est pas une date ISO complète — pas d'exception levée.
    # NB : ce n'est PAS ainsi qu'une précision insuffisante arrive en pratique —
    # wdt:P576 rend toujours un xsd:dateTime complet ("1972-01-01T00:00:00Z"),
    # jamais la chaîne "1973" nue. Ce test documente juste que le convertisseur
    # est robuste à une entrée non-ISO ; la vraie garde contre les dates en
    # précision année vit dans `_precise_dissolved` (filtre sur `?prec`), testée
    # plus bas via `wikidata_ex_commune`.
    assert fec.merged_on_from_dissolved("1973") is None


def test_wikidata_ex_commune_single_row(monkeypatch):
    seen = {}

    def fake_rows(query):
        seen["query"] = query
        return [_ROW_SAINT_AGNANT]

    monkeypatch.setattr(fec, "sparql_rows", fake_rows)
    facts = fec.wikidata_ex_commune("55451")
    assert facts is not None
    assert facts.dissolved == "1972-12-31"  # tronqué à la date ISO
    assert facts.merged_on == "1973-01-01"  # dissolution + 1 jour
    assert facts.successor_insee == "55012"
    assert facts.lat == "48.842142" and facts.long == "5.622588"
    assert '"55451"' in seen["query"] and "wdt:P374" in seen["query"]


def test_wikidata_ex_commune_no_row_is_none(monkeypatch):
    monkeypatch.setattr(fec, "sparql_rows", lambda query: [])
    assert fec.wikidata_ex_commune("55451") is None


def test_wikidata_ex_commune_distinct_items_is_none(monkeypatch):
    # Vraie ambiguïté : deux ?item DIFFÉRENTS pour le même code INSEE. Cas réel
    # mesuré — l'INSEE 55093 est porté par Q1048039 et Q123186720.
    row_a = {
        "item": "http://www.wikidata.org/entity/Q1048039",
        "dissolved": "1972-12-31T00:00:00Z",
        "succInsee": "55012",
        "coord": "Point(5.622588 48.842142)",
    }
    row_b = {
        "item": "http://www.wikidata.org/entity/Q123186720",
        "dissolved": "1973-01-01T00:00:00Z",
        "succInsee": "55012",
        "coord": "Point(5.6 48.8)",
    }
    monkeypatch.setattr(fec, "sparql_rows", lambda query: [row_a, row_b])
    assert fec.wikidata_ex_commune("55093") is None


def test_wikidata_ex_commune_multivalued_coord_is_not_ambiguous(monkeypatch):
    # Fan-out SPARQL, pas ambiguïté : MÊME ?item, mais P625 multivaluée rend
    # deux lignes (deux revendications de coordonnées). La datation doit passer.
    row_a = dict(_ROW_SAINT_AGNANT)
    row_b = dict(_ROW_SAINT_AGNANT, coord="Point(5.6 48.8)")
    monkeypatch.setattr(fec, "sparql_rows", lambda query: [row_a, row_b])
    facts = fec.wikidata_ex_commune("55451")
    assert facts is not None
    assert facts.dissolved == "1972-12-31"
    assert facts.successor_insee == "55012"


def test_wikidata_ex_commune_missing_optionals(monkeypatch):
    # OPTIONAL non satisfaits : la variable est simplement absente de la ligne.
    monkeypatch.setattr(
        fec,
        "sparql_rows",
        lambda query: [{"item": "http://www.wikidata.org/entity/Q1"}],
    )
    facts = fec.wikidata_ex_commune("55451")
    assert facts is not None
    assert facts.dissolved is None and facts.merged_on is None
    assert facts.successor_insee is None
    assert facts.lat is None and facts.long is None


def test_wikidata_ex_commune_year_precision_is_not_dated(monkeypatch):
    # Précision 9 (année) : wdt:P576 aurait rendu "1972-01-01T00:00:00Z" comme si
    # c'était une date complète — c'est exactement la fausse précision que ?prec
    # doit démasquer. Cas réel mesuré sur Huppain (INSEE 14340).
    row = dict(_ROW_SAINT_AGNANT, dissolved="1972-01-01T00:00:00Z", prec="9")
    monkeypatch.setattr(fec, "sparql_rows", lambda query: [row])
    facts = fec.wikidata_ex_commune("55451")
    assert facts is not None
    assert facts.dissolved is None and facts.merged_on is None
    # Le reste de la ligne (successeur, GPS) n'est pas affecté par la garde de précision.
    assert facts.successor_insee == "55012"


def test_wikidata_ex_commune_day_precision_is_dated(monkeypatch):
    # Précision 11 (jour) : comportement inchangé, la datation passe normalement.
    monkeypatch.setattr(fec, "sparql_rows", lambda query: [_ROW_SAINT_AGNANT])
    facts = fec.wikidata_ex_commune("55451")
    assert facts is not None
    assert facts.dissolved == "1972-12-31"
    assert facts.merged_on == "1973-01-01"


def test_wikidata_ex_commune_missing_precision_is_not_dated(monkeypatch):
    # `?prec` absent (ex. la déclaration P576 elle-même n'existe pas, donc le bloc
    # OPTIONAL entier ne se lie pas) : traité comme une précision insuffisante.
    row = {k: v for k, v in _ROW_SAINT_AGNANT.items() if k != "prec"}
    monkeypatch.setattr(fec, "sparql_rows", lambda query: [row])
    facts = fec.wikidata_ex_commune("55451")
    assert facts is not None
    assert facts.dissolved is None and facts.merged_on is None


def test_wikidata_ex_commune_two_distinct_day_precision_dates_is_ambiguous(monkeypatch):
    # Deux déclarations P576 DISTINCTES, toutes deux en précision jour : des dates
    # de dissolution contradictoires. Pas de choix arbitraire — pas de datation.
    row_a = dict(_ROW_SAINT_AGNANT)
    row_b = dict(_ROW_SAINT_AGNANT, dissolved="1973-06-15T00:00:00Z")
    monkeypatch.setattr(fec, "sparql_rows", lambda query: [row_a, row_b])
    facts = fec.wikidata_ex_commune("55451")
    assert facts is not None
    assert facts.dissolved is None and facts.merged_on is None


def test_wikidata_ex_commune_network_failure_is_none(monkeypatch):
    import httpx

    def boom(query):
        raise httpx.ConnectError("wikidata down")

    monkeypatch.setattr(fec, "sparql_rows", boom)
    # Wikidata n'est qu'un enrichisseur : une panne réseau ne doit pas faire
    # échouer la résolution, seulement priver de la datation.
    assert fec.wikidata_ex_commune("55451") is None


def test_wikidata_ex_commune_malformed_json_is_none(monkeypatch):
    import httpx

    def boom(query):
        # httpx.DecodingError hérite de httpx.HTTPError (vérifié) : un JSON
        # malformé est donc couvert par la même clause que le réseau.
        raise httpx.DecodingError("bad")

    monkeypatch.setattr(fec, "sparql_rows", boom)
    assert fec.wikidata_ex_commune("55451") is None


def test_wikidata_ex_commune_malformed_json_from_real_transport_is_none(monkeypatch):
    # Contrairement au test ci-dessus, `sparql_rows` n'est PAS mocké : c'est le
    # vrai `httpx.get(...).json()` de sparql.py qui est exercé, sur une réponse
    # HTTP 200 dont le corps n'est pas du JSON valide. `httpx.Response.json()`
    # lève alors le `json.JSONDecodeError` de la bibliothèque standard, qui
    # N'HÉRITE PAS de `httpx.HTTPError` - contrairement à `requests`, où
    # `requests.exceptions.JSONDecodeError` hérite bien de `RequestException`.
    # Ce test échoue si la clause `except` de `wikidata_ex_commune` est un
    # jour renarrowée à `except httpx.HTTPError:` seul (vérifié : voir
    # task-16-report.md, "Fix round 1" pour la sortie réelle de l'échec).
    import httpx

    def fake_get(url, params=None, headers=None, timeout=None):
        return httpx.Response(
            200, content=b"not json", request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    assert fec.wikidata_ex_commune("55451") is None


def test_wikidata_ex_commune_programming_error_propagates(monkeypatch):
    import pytest

    def boom(query):
        raise KeyError("variable SPARQL absente du gabarit")

    monkeypatch.setattr(fec, "sparql_rows", boom)
    # Convention du dépôt (cf. places_apply.py) : un bug de programmation remonte,
    # il n'est pas déguisé en « pas de datation ».
    with pytest.raises(KeyError):
        fec.wikidata_ex_commune("55451")


# Réponse réelle de /communes_associees_deleguees?nom=…
_ASSOCIEE = {
    "nom": "Saint-Agnant-sous-les-Côtes",
    "code": "55451",
    "type": "commune-associee",
    "chefLieu": "55012",
    "centre": {"type": "Point", "coordinates": [5.6317, 48.8427]},  # [lon, lat]
    "departement": {"code": "55", "nom": "Meuse"},
    "region": {"code": "44", "nom": "Grand Est"},
}
# Réponse réelle de /communes/55012
_CHEF_LIEU = {
    "nom": "Apremont-la-Forêt",
    "code": "55012",
    "centre": {"type": "Point", "coordinates": [5.6207, 48.8467]},
    "departement": {"code": "55", "nom": "Meuse"},
    "region": {"code": "44", "nom": "Grand Est"},
}

_PARSED = ParsedPlace(
    raw=", , , Saint-Agnant-sous-les-Côtes, 55012, Meuse, Grand Est, France",
    commune="Saint-Agnant-sous-les-Côtes",
    postal="55012",
    departement="Meuse",
    region="Grand Est",
    country="France",
    shifted=True,
)


def _fake_api(associees, chef=_CHEF_LIEU):
    """Route les deux appels HTTP du résolveur sur des payloads figés."""

    def fake_get(path, params):
        if path == "/communes_associees_deleguees":
            return associees
        assert path == "/communes/55012", path
        return chef

    return fake_get


def _facts(**kw):
    defaults = {
        "dissolved": "1972-12-31",
        "merged_on": "1973-01-01",
        "successor_insee": "55012",
        "lat": "48.842142",
        "long": "5.622588",
    }
    return fec.ExCommuneFacts(**{**defaults, **kw})


def test_resolve_ex_commune_emits_two_dated_chains(monkeypatch):
    monkeypatch.setattr(fec, "_http_get", _fake_api([_ASSOCIEE]))
    monkeypatch.setattr(fec, "wikidata_ex_commune", lambda insee: _facts())
    rp = fec.resolve_fr_ex_commune(_PARSED)

    assert rp is not None
    assert rp.name == "Saint-Agnant-sous-les-Côtes"
    assert rp.place_type == "Municipality"
    assert rp.code == "55451"  # son code propre, PAS 55012
    assert rp.score == 1.0 and rp.ambiguous is False
    # GPS Wikidata (centre du bourg), pas le centroïde de l'API
    assert rp.lat == "48.842142" and rp.long == "5.622588"

    assert len(rp.chains) == 2
    historique, moderne = rp.chains[0], rp.chains[1]
    assert historique.date_qualifier == "avant 1973-01-01"
    assert [lvl.name for lvl in historique.levels] == ["France", "Grand Est", "Meuse"]
    assert moderne.date_qualifier == "après 1973-01-01"
    assert [lvl.name for lvl in moderne.levels] == [
        "France",
        "Grand Est",
        "Meuse",
        "Apremont-la-Forêt",
    ]
    assert moderne.levels[-1].code == "55012"
    assert moderne.levels[-1].place_type == "Municipality"
    assert rp.alt_names[0].value == _PARSED.raw


def test_resolve_ex_commune_successor_mismatch_degrades_to_single_chain(monkeypatch):
    # Wikidata désigne un autre successeur que le chefLieu de l'API : discordance.
    monkeypatch.setattr(fec, "_http_get", _fake_api([_ASSOCIEE]))
    monkeypatch.setattr(
        fec, "wikidata_ex_commune", lambda insee: _facts(successor_insee="55999")
    )
    rp = fec.resolve_fr_ex_commune(_PARSED)

    assert rp is not None
    assert len(rp.chains) == 1
    assert rp.chains[0].date_qualifier is None  # aucune date inventée
    assert [lvl.name for lvl in rp.chains[0].levels] == [
        "France",
        "Grand Est",
        "Meuse",
        "Apremont-la-Forêt",
    ]


def test_resolve_ex_commune_without_dissolution_date_is_undated(monkeypatch):
    monkeypatch.setattr(fec, "_http_get", _fake_api([_ASSOCIEE]))
    monkeypatch.setattr(
        fec, "wikidata_ex_commune", lambda insee: _facts(dissolved=None, merged_on=None)
    )
    rp = fec.resolve_fr_ex_commune(_PARSED)
    assert rp is not None and len(rp.chains) == 1
    assert rp.chains[0].date_qualifier is None


def test_resolve_ex_commune_dissolved_but_unparsable_merged_on_is_undated(monkeypatch):
    # Wikidata rend bien `dissolved`, mais la borne dérivée n'a pas pu être calculée
    # (ex. réponse SPARQL avec une précision insuffisante) : `merged_on` est absent,
    # et la garde de recoupement doit refuser de dater — une seule chaîne non datée,
    # pas de repli silencieux sur `dissolved`.
    monkeypatch.setattr(fec, "_http_get", _fake_api([_ASSOCIEE]))
    monkeypatch.setattr(
        fec,
        "wikidata_ex_commune",
        lambda insee: _facts(dissolved="1972-12-31", merged_on=None),
    )
    rp = fec.resolve_fr_ex_commune(_PARSED)
    assert rp is not None and len(rp.chains) == 1
    assert rp.chains[0].date_qualifier is None
    assert rp.source == "geo.api.gouv.fr/communes_associees_deleguees"


def test_resolve_ex_commune_without_wikidata_falls_back_to_api_gps(monkeypatch):
    monkeypatch.setattr(fec, "_http_get", _fake_api([_ASSOCIEE]))
    monkeypatch.setattr(fec, "wikidata_ex_commune", lambda insee: None)
    rp = fec.resolve_fr_ex_commune(_PARSED)
    assert rp is not None and len(rp.chains) == 1
    assert rp.lat == "48.8427" and rp.long == "5.6317"  # centre GeoJSON [lon, lat]


def test_resolve_ex_commune_no_match_is_none(monkeypatch):
    monkeypatch.setattr(fec, "_http_get", _fake_api([]))
    monkeypatch.setattr(fec, "wikidata_ex_commune", lambda insee: _facts())
    assert fec.resolve_fr_ex_commune(_PARSED) is None


def test_resolve_ex_commune_fuzzy_nonexact_is_none(monkeypatch):
    # La recherche par nom de l'API est floue : un quasi-homonyme ne compte pas.
    autre = {**_ASSOCIEE, "nom": "Saint-Agnant-près-Crocq", "code": "23999"}
    monkeypatch.setattr(fec, "_http_get", _fake_api([autre]))
    monkeypatch.setattr(fec, "wikidata_ex_commune", lambda insee: _facts())
    assert fec.resolve_fr_ex_commune(_PARSED) is None


def test_resolve_ex_commune_homonyms_are_ambiguous(monkeypatch):
    jumeau = {
        **_ASSOCIEE,
        "code": "88888",
        "departement": {"code": "88", "nom": "Vosges"},
    }
    monkeypatch.setattr(fec, "_http_get", _fake_api([_ASSOCIEE, jumeau]))
    monkeypatch.setattr(fec, "wikidata_ex_commune", lambda insee: _facts())
    sans_contexte = _PARSED.model_copy(update={"departement": "", "region": ""})
    rp = fec.resolve_fr_ex_commune(sans_contexte)
    assert rp is not None and rp.ambiguous is True


def test_resolve_ex_commune_department_disambiguates(monkeypatch):
    jumeau = {
        **_ASSOCIEE,
        "code": "88888",
        "departement": {"code": "88", "nom": "Vosges"},
    }
    monkeypatch.setattr(fec, "_http_get", _fake_api([jumeau, _ASSOCIEE]))
    monkeypatch.setattr(fec, "wikidata_ex_commune", lambda insee: _facts())
    rp = fec.resolve_fr_ex_commune(_PARSED)  # departement="Meuse"
    assert rp is not None and rp.ambiguous is False and rp.code == "55451"


def test_resolve_ex_commune_without_commune_is_none():
    assert (
        fec.resolve_fr_ex_commune(ParsedPlace(raw="", commune="", country="France"))
        is None
    )


# Bout en bout : une commune réellement affectée par le bug — Huppain (Calvados),
# absorbée par Port-en-Bessin-Huppain. Payloads réels de geo.api.gouv.fr, et une
# ligne SPARQL réelle mesurée sur query.wikidata.org pour ?item wdt:P374 "14340" :
# une déclaration P576 en précision ANNÉE ("1972-01-01T00:00:00Z", prec 9). Avant
# le correctif, `rows[0]` l'acceptait telle quelle et fabriquait une borne
# 1972-01-02. Ce test route `sparql_rows` (pas `wikidata_ex_commune`) pour
# exercer le vrai filtre de précision de bout en bout.
_ASSOCIEE_HUPPAIN = {
    "nom": "Huppain",
    "code": "14340",
    "type": "commune-associee",
    "chefLieu": "14515",
    "centre": {"type": "Point", "coordinates": [-0.7798, 49.3387]},  # [lon, lat]
    "departement": {"code": "14", "nom": "Calvados"},
    "region": {"code": "28", "nom": "Normandie"},
}
_CHEF_LIEU_HUPPAIN = {
    "nom": "Port-en-Bessin-Huppain",
    "code": "14515",
    "centre": {"type": "Point", "coordinates": [-0.7727, 49.3387]},
    "departement": {"code": "14", "nom": "Calvados"},
    "region": {"code": "28", "nom": "Normandie"},
}
_ROW_HUPPAIN_YEAR_PRECISION = {
    "item": "http://www.wikidata.org/entity/Q60882197",
    "dissolved": "1972-01-01T00:00:00Z",
    "prec": "9",
    "succInsee": "14515",
    "coord": "Point(-0.7723308 49.3410007)",
}
_PARSED_HUPPAIN = ParsedPlace(
    raw=", , , Huppain, 14515, Calvados, Normandie, France",
    commune="Huppain",
    postal="14515",
    departement="Calvados",
    region="Normandie",
    country="France",
    shifted=True,
)


def test_resolve_ex_commune_huppain_year_precision_degrades_to_single_undated_chain(
    monkeypatch,
):
    def fake_get(path, params):
        if path == "/communes_associees_deleguees":
            return [_ASSOCIEE_HUPPAIN]
        assert path == "/communes/14515", path
        return _CHEF_LIEU_HUPPAIN

    monkeypatch.setattr(fec, "_http_get", fake_get)
    monkeypatch.setattr(fec, "sparql_rows", lambda query: [_ROW_HUPPAIN_YEAR_PRECISION])
    rp = fec.resolve_fr_ex_commune(_PARSED_HUPPAIN)

    assert rp is not None
    assert rp.code == "14340"
    # Précision insuffisante (année) -> aucune date fabriquée : une seule chaîne,
    # rattachée au chef-lieu moderne, sans qualificatif de date.
    assert len(rp.chains) == 1
    assert rp.chains[0].date_qualifier is None
    assert [lvl.name for lvl in rp.chains[0].levels] == [
        "France",
        "Normandie",
        "Calvados",
        "Port-en-Bessin-Huppain",
    ]
    assert rp.source == "geo.api.gouv.fr/communes_associees_deleguees"
