"""Birth and death must survive a person whose ref indexes are unset.

`birth_ref_index` and `death_ref_index` are stored on the Gramps Person
object and filled in by the Gramps desktop and web UIs. A person created
through the REST API never gets them: the record comes back with both at
-1 even when its `event_ref_list` holds exactly one Primary Death and
`extended.events` renders it.

Trusting the index alone therefore blinded every date rule to every
person this server itself created - on the live tree, hundreds of them,
including both halves of duplicate pairs the tools exist to find.
"""

from src.gramps_mcp.genealogy.facts import person_from_json


def _raw(**over) -> dict:
    base = {
        "handle": "h1",
        "gramps_id": "I1904",
        "gender": 1,
        "primary_name": {"first_name": "Jean", "surname_list": [{"surname": "Dumas"}]},
        "birth_ref_index": -1,
        "death_ref_index": -1,
        "event_ref_list": [{"ref": "e1", "role": "Primary"}],
        "extended": {"events": [{"type": "Death", "date": {"dateval": [15, 5, 1891]}}]},
        "profile": {},
    }
    base.update(over)
    return base


class TestRefIndexFallback:
    def test_a_death_is_found_when_the_index_is_unset(self):
        person = person_from_json(_raw())

        assert person.death is not None
        assert person.death.dateval == [15, 5, 1891]

    def test_a_birth_is_found_when_the_index_is_unset(self):
        person = person_from_json(
            _raw(
                extended={
                    "events": [{"type": "Birth", "date": {"dateval": [2, 5, 1834]}}]
                }
            )
        )

        assert person.birth is not None
        assert person.birth.dateval == [2, 5, 1834]

    def test_a_non_primary_role_is_not_the_person_s_own_event(self):
        """A witness at someone else's death has that event in their list.
        Taking it as their own death would kill them decades early.
        """
        person = person_from_json(
            _raw(event_ref_list=[{"ref": "e1", "role": "Witness"}])
        )

        assert person.death is None

    def test_an_explicit_index_still_wins(self):
        """Where Gramps did set the index, it names the preferred event -
        the fallback must not override that choice.
        """
        person = person_from_json(
            _raw(
                death_ref_index=1,
                event_ref_list=[
                    {"ref": "e1", "role": "Primary"},
                    {"ref": "e2", "role": "Primary"},
                ],
                extended={
                    "events": [
                        {"type": "Death", "date": {"dateval": [1, 1, 1800]}},
                        {"type": "Death", "date": {"dateval": [15, 5, 1891]}},
                    ]
                },
            )
        )

        assert person.death is not None
        assert person.death.dateval == [15, 5, 1891]

    def test_other_event_types_are_never_mistaken_for_a_death(self):
        person = person_from_json(
            _raw(
                extended={
                    "events": [
                        {"type": "Occupation", "date": {"dateval": [0, 0, 1860]}}
                    ]
                }
            )
        )

        assert person.death is None
        assert person.birth is None
