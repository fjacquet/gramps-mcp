"""Tests for duplicate detection by date collision.

Name blocking cannot see the duplicates that matter most here: the 1819
Breitenbach pair was filed under two different surnames (Hadler and
Stadler) and no name rule would ever pair them. What proved it was a
death date shared to the day. Day-precise dates are near-unique across a
four-century tree, so a collision is evidence in a way a shared name in a
Berry parish never is.
"""

from src.gramps_mcp.genealogy.date_collision import find_date_collisions
from src.gramps_mcp.genealogy.domain import EventFact, FamilyFacts, PersonFacts


def _day(day: int, month: int, year: int, **kw) -> EventFact:
    return EventFact(type="Death", dateval=[day, month, year, False], **kw)


def _person(gid: str, given: str, surname: str, birth=None, death=None, parents=()):
    return PersonFacts(
        gramps_id=gid,
        handle=f"h{gid}",
        name=f"{given} {surname}",
        surname=surname,
        given=given,
        sex="U",
        birth=birth,
        death=death,
        parent_family_handles=list(parents),
    )


class TestProved:
    def test_two_dates_colliding_is_proof(self):
        """Pierre Voisot: born 15/03/1819 and died 12/12/1870 on both
        records. Two independent day-precise coincidences do not happen
        between different people.
        """
        a = _person("I0060", "Pierre", "Voisot", _day(15, 3, 1819), _day(12, 12, 1870))
        b = _person("I1814", "Pierre", "Voisot", _day(15, 3, 1819), _day(12, 12, 1870))

        found = find_date_collisions([a, b], {})

        assert [f.tier for f in found] == ["prouve"]
        assert {found[0].a, found[0].b} == {"I0060", "I1814"}
        assert len(found[0].reasons) == 2

    def test_one_date_plus_the_same_name_is_proof(self):
        """Marguerite Jacquet: one death date, but the names match too."""
        a = _person("I0957", "Marguerite", "Jacquet", death=_day(21, 7, 1825))
        b = _person("I1819", "Marguerite", "Jacquet", death=_day(21, 7, 1825))

        found = find_date_collisions([a, b], {})

        assert [f.tier for f in found] == ["prouve"]


class TestNearSurnames:
    def test_a_near_surname_is_strong_not_proof(self):
        """Hadler and Stadler differ by one letter and share a death
        date. No name rule pairs them; this one must.
        """
        a = _person("I0841", "Jean Jacques", "Stadler", death=_day(7, 8, 1819))
        b = _person("I1804", "Jean-Jacques", "Hadler", death=_day(7, 8, 1819))

        found = find_date_collisions([a, b], {})

        assert [f.tier for f in found] == ["fort"]

    def test_unrelated_surnames_are_only_worth_a_look(self):
        """Jean Dumas and Rosalie Vilpellet died on 15/05/1891, acts n°20
        and n°21 of one register. Real people, real day, no duplicate.
        """
        a = _person("I1639", "Rosalie", "Vilpellet", death=_day(15, 5, 1891))
        b = _person("I1904", "Jean", "Dumas", death=_day(15, 5, 1891))

        found = find_date_collisions([a, b], {})

        assert [f.tier for f in found] == ["a_verifier"]


class TestTwins:
    def test_siblings_sharing_a_birth_date_are_twins_not_duplicates(self):
        """Renee and Marguerite Cocu, dead the same day at five months,
        are called jumelles by their own act. Ami and Abraham Pagan are
        twins in the Nidau register. Reporting them every run trains the
        reader to skim the report.
        """
        a = _person("I1869", "Renee", "Cocu", death=_day(22, 7, 1901), parents=["fam1"])
        b = _person(
            "I1870", "Marguerite", "Cocu", death=_day(22, 7, 1901), parents=["fam1"]
        )
        family = FamilyFacts(
            gramps_id="F0001", handle="fam1", child_handles=["hI1869", "hI1870"]
        )

        found = find_date_collisions([a, b], {"fam1": family})

        assert found == []


class TestPrecision:
    def test_an_approximate_date_is_not_a_collision(self):
        """modifier=3 is "about". Two people about 1806 prove nothing."""
        a = _person("I1", "Ami", "Pagan", death=_day(23, 1, 1806, modifier=3))
        b = _person("I2", "Abram", "Pagan", death=_day(23, 1, 1806, modifier=3))

        assert find_date_collisions([a, b], {}) == []

    def test_a_year_only_date_is_not_a_collision(self):
        """Half the tree is dated to the year; those are not evidence."""
        a = _person("I1", "Jean", "Pagan", death=_day(0, 0, 1806))
        b = _person("I2", "Jean", "Pagan", death=_day(0, 0, 1806))

        assert find_date_collisions([a, b], {}) == []

    def test_a_birth_never_collides_with_a_death(self):
        """One person born the day another died is not a duplicate."""
        a = _person("I1", "Jean", "Pagan", birth=_day(2, 3, 1868))
        b = _person("I2", "Jean", "Pagan", death=_day(2, 3, 1868))

        assert find_date_collisions([a, b], {}) == []


class TestRendering:
    """Date evidence outranks name evidence, so it must be read first."""

    def _render(self, collisions):
        from src.gramps_mcp.handlers.duplicates_handler import (
            format_duplicate_clusters,
        )

        return format_duplicate_clusters(
            [],
            [],
            {},
            skipped=0,
            partial=False,
            error=None,
            collisions=collisions,
        )

    def test_collisions_are_named_and_placed_before_the_name_sections(self):
        from src.gramps_mcp.genealogy.date_collision import DateCollision

        text = self._render(
            [
                DateCollision(
                    a="I0060",
                    b="I1814",
                    tier="prouve",
                    reasons=["meme naissance 15/03/1819", "meme deces 12/12/1870"],
                )
            ]
        )

        assert "I0060" in text and "I1814" in text
        assert "meme deces 12/12/1870" in text
        assert text.index("I0060") < text.index("## Proved duplicates")

    def test_the_three_tiers_are_kept_apart(self):
        """A pair the dates prove must never render beside one they only
        hint at - that is the whole point of ranking instead of listing.
        """
        from src.gramps_mcp.genealogy.date_collision import DateCollision

        text = self._render(
            [
                DateCollision("I1", "I2", "prouve", ["meme deces 01/01/1900"]),
                DateCollision("I3", "I4", "fort", ["meme deces 02/02/1900"]),
                DateCollision("I5", "I6", "a_verifier", ["meme deces 03/03/1900"]),
            ]
        )

        assert text.index("I1") < text.index("I3") < text.index("I5")
        assert text.lower().count("date collision") == 3

    def test_no_collision_renders_no_section(self):
        assert "date collision" not in self._render([]).lower()
