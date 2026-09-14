"""Matching a tree person to a Wikidata entity, and refusing when unsure."""

from scripts.portrait_candidates import (
    classify,
    is_safely_dead,
    name_variants,
    year_of,
)


class TestYearOf:
    """The year inside a Gramps date string."""

    def test_a_full_date_yields_its_year(self):
        assert year_of("1820-01-15") == 1820

    def test_a_bare_year_yields_itself(self):
        assert year_of("1804") == 1804

    def test_an_empty_date_yields_nothing(self):
        assert year_of("") is None

    def test_a_qualified_date_still_yields_its_year(self):
        assert year_of("vers 1780") == 1780


class TestClassify:
    """Match, homonym, or nothing."""

    def test_both_years_agreeing_is_a_match(self):
        assert classify("1820-01-15", "1876-05-15", 1820, 1876) == "match"

    def test_one_year_disagreeing_is_not_a_match(self):
        # Reason: the first Wikidata hit for Zofia Branicka is a different
        # woman born 1790; only the dates separate her from the right one.
        assert classify("1821-09-02", "1886-08-18", 1790, 1879) == "none"

    def test_a_tree_person_with_one_known_year_never_reaches_match(self):
        assert classify("1805", "", 1807, 1845) == "none"
        assert classify("1805", "", 1805, 1845) == "homonym"

    def test_a_person_with_no_dates_cannot_be_matched(self):
        assert classify("", "", 1800, 1850) == "none"

    def test_an_entity_missing_a_year_falls_back_to_homonym(self):
        assert classify("1820-01-15", "1876-05-15", 1820, None) == "homonym"


class TestIsSafelyDead:
    """Living people are out of scope, as they are for LinkedIn."""

    def test_a_death_year_well_in_the_past_is_in_scope(self):
        assert is_safely_dead({"death": "1876-05-15"}) is True

    def test_no_death_date_is_out_of_scope(self):
        # Reason: a portrait hunt must not reach a living person, and an
        # absent death date is exactly how a living person presents.
        assert is_safely_dead({"death": ""}) is False

    def test_a_recent_death_is_out_of_scope(self):
        assert is_safely_dead({"death": "1994-03-02"}) is False


class TestNameVariants:
    """Wikidata files a noble under fewer forenames than the tree records."""

    def test_the_full_name_comes_first(self):
        assert name_variants("Stanisław Kostka Franciszek", "Zamoyski")[0] == (
            "Stanisław Kostka Franciszek Zamoyski"
        )

    def test_forenames_are_dropped_from_the_right(self):
        # Reason: "Stanisław Kostka Franciszek Zamoyski" finds nothing while
        # "Stanisław Kostka Zamoyski" finds the man himself.
        assert name_variants("Stanisław Kostka Franciszek", "Zamoyski") == [
            "Stanisław Kostka Franciszek Zamoyski",
            "Stanisław Kostka Zamoyski",
            "Stanisław Zamoyski",
        ]

    def test_a_single_forename_yields_one_variant(self):
        assert name_variants("Eliza", "Branicka") == ["Eliza Branicka"]

    def test_a_missing_forename_yields_the_surname_alone(self):
        assert name_variants("", "Bochetel") == ["Bochetel"]
