"""Tests par table des règles personne R1, R2, R6, R7, R8, R9 (pures, hors-ligne)."""

from src.gramps_mcp.genealogy.domain import EventFact, PersonFacts
from src.gramps_mcp.genealogy.rules import check_person


def _p(**kw):
    base = {
        "gramps_id": "I1",
        "handle": "h1",
        "name": "X",
        "surname": "X",
        "given": "x",
        "sex": "M",
        "has_any_citation": True,
    }
    base.update(kw)
    return PersonFacts(**base)


def _rules(anoms):
    return {a.rule for a in anoms}


def test_r1_birth_after_death():
    p = _p(
        birth=EventFact(type="Birth", sortval=2400000, year=1850),
        death=EventFact(type="Death", sortval=2390000, year=1820),
    )
    assert "R1" in _rules(check_person(p))


def test_r1_ok_when_order_correct():
    p = _p(
        birth=EventFact(type="Birth", sortval=2390000, year=1820),
        death=EventFact(type="Death", sortval=2400000, year=1850),
    )
    assert "R1" not in _rules(check_person(p))


def test_r2_age_over_105():
    # ~120 ans : 120 * 365.25 ≈ 43830 jours
    p = _p(
        birth=EventFact(type="Birth", sortval=2300000, year=1700),
        death=EventFact(type="Death", sortval=2343830, year=1820),
    )
    assert "R2" in _rules(check_person(p))


def test_r2_ok_normal_lifespan():
    p = _p(
        birth=EventFact(type="Birth", sortval=2300000, year=1700),
        death=EventFact(type="Death", sortval=2325000, year=1768),
    )
    assert "R2" not in _rules(check_person(p))


def test_r6_life_event_before_birth():
    p = _p(
        birth=EventFact(type="Birth", sortval=2400000, year=1850),
        death=EventFact(type="Death", sortval=2420000, year=1905),
        events=[EventFact(type="Marriage", sortval=2399000, year=1848)],
    )
    assert "R6" in _rules(check_person(p))


def test_r6_burial_after_death_is_not_flagged():
    p = _p(
        birth=EventFact(type="Birth", sortval=2400000, year=1850),
        death=EventFact(type="Death", sortval=2420000, year=1905),
        events=[EventFact(type="Burial", sortval=2420010, year=1905)],
    )
    assert "R6" not in _rules(check_person(p))


def test_r6_postmortem_event_before_birth_is_flagged():
    p = _p(
        birth=EventFact(type="Birth", sortval=2400000, year=1850),
        death=EventFact(type="Death", sortval=2420000, year=1905),
        events=[EventFact(type="Cremation", sortval=2390000, year=1820)],
    )
    assert "R6" in _rules(check_person(p))


def test_r7_baptism_before_birth():
    p = _p(
        birth=EventFact(type="Birth", sortval=2400000, year=1850),
        events=[EventFact(type="Baptism", sortval=2399990, year=1849)],
    )
    assert "R7" in _rules(check_person(p))


def test_r6_does_not_double_count_a_baptism_before_birth():
    """R6's before-birth branch used to fire for every event type,
    including Baptism - the exact fact R7 already reports more precisely
    (baptism vs. birth). Same anomaly, reported twice, inflated the
    per-severity cap and the guide's totals.
    """
    p = _p(
        birth=EventFact(type="Birth", sortval=2400000, year=1850),
        events=[EventFact(type="Baptism", sortval=2399990, year=1849)],
    )
    anomalies = check_person(p)
    rules_fired = [a.rule for a in anomalies]
    assert rules_fired.count("R6") == 0
    assert rules_fired.count("R7") == 1


def test_r1_not_flagged_when_death_is_year_only_same_year_as_exact_birth():
    """I0943 : naissance exacte le 09/01/1782, deces a l'annee seule 1782 -
    meme annee, l'ordre reel est inconnu, ne doit pas etre signale."""
    p = _p(
        birth=EventFact(
            type="Birth", sortval=2370010, year=1782, dateval=[9, 1, 1782, False]
        ),
        death=EventFact(
            type="Death", sortval=2370001, year=1782, dateval=[0, 0, 1782, False]
        ),
    )
    assert "R1" not in _rules(check_person(p))


def test_r6_event_not_flagged_before_birth_when_year_only_same_year():
    """I0763 : recensement '1833' (annee seule) contre naissance exacte du
    10/06/1833 - meme mecanisme que R1/R7."""
    p = _p(
        birth=EventFact(
            type="Birth", sortval=2390100, year=1833, dateval=[10, 6, 1833, False]
        ),
        events=[
            EventFact(
                type="Census", sortval=2390000, year=1833, dateval=[0, 0, 1833, False]
            )
        ],
    )
    assert "R6" not in _rules(check_person(p))


def test_r6_still_flags_event_clearly_before_birth_year():
    """Regression : un evenement d'une annee anterieure reste signale meme a
    precision annee seule."""
    p = _p(
        birth=EventFact(
            type="Birth", sortval=2390100, year=1833, dateval=[10, 6, 1833, False]
        ),
        events=[
            EventFact(
                type="Census", sortval=2385000, year=1830, dateval=[0, 0, 1830, False]
            )
        ],
    )
    assert "R6" in _rules(check_person(p))


def test_r6_before_modifier_date_not_flagged_after_death():
    """I2385 : profession datee 'avant le 16/04/1895' (modifier=1) pour un
    homme mort en 1852 - le modificateur ne fixe pas la date."""
    p = _p(
        death=EventFact(
            type="Death", sortval=2398000, year=1852, dateval=[1, 1, 1852, False]
        ),
        events=[
            EventFact(
                type="Occupation",
                sortval=2415000,
                year=1895,
                modifier=1,
                dateval=[16, 4, 1895, False],
            )
        ],
    )
    assert "R6" not in _rules(check_person(p))


def test_r7_burial_not_flagged_when_year_only_same_year_as_exact_death():
    """I0408 : mort le 30/04/1971 (exact), inhume '1971' (annee seule) - le
    1er janvier calcule pour l'inhumation ne prouve pas qu'elle a precede le
    deces."""
    p = _p(
        death=EventFact(
            type="Death", sortval=2500100, year=1971, dateval=[30, 4, 1971, False]
        ),
        events=[
            EventFact(
                type="Burial", sortval=2500000, year=1971, dateval=[0, 0, 1971, False]
            )
        ],
    )
    assert "R7" not in _rules(check_person(p))


def test_r7_burial_before_death():
    p = _p(
        death=EventFact(type="Death", sortval=2420000, year=1905),
        events=[EventFact(type="Burial", sortval=2419990, year=1905)],
    )
    assert "R7" in _rules(check_person(p))


def test_r8_malformed_date_unsortable():
    # date présente (year renseigné) mais sortval == 0
    p = _p(
        events=[
            EventFact(
                type="Residence", sortval=0, year=1850, dateval=[0, 0, 1850, False]
            )
        ]
    )
    # year renseigné + sortval 0 → R8
    p.events[0].dateval = [40, 13, 1850, False]  # jour 40, mois 13 hors bornes
    assert "R8" in _rules(check_person(p))


def test_r9_no_citation():
    p = _p(has_any_citation=False)
    assert "R9" in _rules(check_person(p))


def test_r9_absent_when_cited():
    p = _p(has_any_citation=True)
    assert "R9" not in _rules(check_person(p))


def test_r8_undated_event_not_flagged():
    # événement sans date : dateval [0,0,0], year 0, sortval 0 → PAS d'anomalie
    p = _p(
        events=[
            EventFact(type="Residence", sortval=0, year=0, dateval=[0, 0, 0, False])
        ]
    )
    assert "R8" not in _rules(check_person(p))


def test_r8_aberrant_modifier_or_quality_is_flagged():
    p = _p(
        events=[
            EventFact(
                type="Birth",
                sortval=2400000,
                year=1850,
                dateval=[1, 1, 1850, False],
                modifier=99,
                quality=0,
            )
        ]
    )
    assert "R8" in _rules(check_person(p))


def test_r8_real_date_but_unsortable_is_flagged():
    # vraie date (année renseignée) mais non triable (sortval 0) → R8
    p = _p(
        events=[
            EventFact(type="Death", sortval=0, year=1850, dateval=[0, 0, 1850, False])
        ]
    )
    assert "R8" in _rules(check_person(p))


def test_d1_no_vital_date_flagged():
    assert "D1" in _rules(check_person(_p()))


def test_d1_absent_when_birth_present():
    p = _p(birth=EventFact(type="Birth", sortval=2400000, year=1850))
    assert "D1" not in _rules(check_person(p))


def test_d2_free_text_date_flagged():
    p = _p(
        events=[
            EventFact(
                type="Death", sortval=0, year=0, modifier=6, dateval=[0, 0, 0, False]
            )
        ]
    )
    assert "D2" in _rules(check_person(p))


def test_d2_absent_for_normal_date():
    p = _p(events=[EventFact(type="Death", sortval=2400000, year=1850, modifier=0)])
    assert "D2" not in _rules(check_person(p))


def test_d3_unknown_gender_flagged():
    assert "D3" in _rules(check_person(_p(sex="U")))


def test_d3_absent_for_known_gender():
    assert "D3" not in _rules(check_person(_p(sex="F")))


# --- Précision et modificateur de date : pas de comparaison stricte abusive ---
#
# Mesuré le 17/09/2026 sur l'arbre entier : 35 des 38 anomalies unitaires
# étaient des faux positifs, tous nés de deux confusions - une date à l'année
# seule sort au 1er janvier, et un modificateur « avant » était lu comme une
# date exacte.


def test_r1_silent_when_death_is_year_only_in_the_birth_year():
    """Née le 9 janvier 1782, morte « en 1782 » : l'arbre a raison.

    Le sortval d'une date à l'année seule tombe au 1er janvier, donc une
    naissance datée au jour dans la même année lui est postérieure. Cas réel
    I0943, une enfant morte dans son année de naissance.
    """
    p = _p(
        birth=EventFact(
            type="Birth", sortval=2371931, year=1782, dateval=[9, 1, 1782, False]
        ),
        death=EventFact(
            type="Death", sortval=2371923, year=1782, dateval=[0, 0, 1782, False]
        ),
    )
    assert "R1" not in _rules(check_person(p))


def test_r1_still_fires_when_both_dates_are_exact_days():
    p = _p(
        birth=EventFact(
            type="Birth", sortval=2400000, year=1850, dateval=[1, 6, 1850, False]
        ),
        death=EventFact(
            type="Death", sortval=2390000, year=1820, dateval=[1, 6, 1820, False]
        ),
    )
    assert "R1" in _rules(check_person(p))


def test_r7_silent_when_burial_is_year_only_in_the_death_year():
    """Mort le 30/04/1971, inhumé « 1971 » : cas réel I0408."""
    p = _p(
        death=EventFact(
            type="Death", sortval=2441072, year=1971, dateval=[30, 4, 1971, False]
        ),
        events=[
            EventFact(
                type="Burial", sortval=2440953, year=1971, dateval=[0, 0, 1971, False]
            )
        ],
    )
    assert "R7" not in _rules(check_person(p))


def test_r7_still_fires_on_a_real_burial_before_death():
    p = _p(
        death=EventFact(
            type="Death", sortval=2441072, year=1971, dateval=[30, 4, 1971, False]
        ),
        events=[
            EventFact(
                type="Burial", sortval=2440000, year=1968, dateval=[2, 5, 1968, False]
            )
        ],
    )
    assert "R7" in _rules(check_person(p))


def test_r6_silent_when_event_is_year_only_in_the_birth_year():
    """Recensement « 1833 » pour une naissance du 10/06/1833 : cas réel I0763."""
    p = _p(
        birth=EventFact(
            type="Birth", sortval=2390710, year=1833, dateval=[10, 6, 1833, False]
        ),
        events=[
            EventFact(
                type="Census", sortval=2390550, year=1833, dateval=[0, 0, 1833, False]
            )
        ],
    )
    assert "R6" not in _rules(check_person(p))


def test_r6_silent_when_event_date_carries_a_modifier():
    """Profession datée « avant le 16/04/1895 » chez un mort de 1852 : I2385.

    Un modificateur non nul veut dire que le sortval n'est pas un point, donc
    qu'aucune comparaison stricte n'est licite.
    """
    p = _p(
        death=EventFact(
            type="Death", sortval=2397569, year=1852, dateval=[21, 3, 1852, False]
        ),
        events=[
            EventFact(
                type="Occupation",
                sortval=2413300,
                year=1895,
                dateval=[16, 4, 1895, False],
                modifier=1,
            )
        ],
    )
    assert "R6" not in _rules(check_person(p))
