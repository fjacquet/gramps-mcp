"""Coverage of a person's images, by the path that reaches them."""

from scripts.media_coverage import (
    has_document_nearby,
    index_media_holders,
    is_uncovered,
    needs_surfacing,
    person_coverage,
)


def _person(gramps_id: str, media: int = 0, events: list[str] | None = None) -> dict:
    return {
        "gramps_id": gramps_id,
        "handle": f"h-{gramps_id}",
        "media_list": [{"ref": f"m{i}"} for i in range(media)],
        "event_ref_list": [{"ref": e} for e in events or []],
    }


def _event(handle: str, citations: list[str] | None = None, place: str = "") -> dict:
    return {"handle": handle, "citation_list": citations or [], "place": place}


class TestIndexMediaHolders:
    """Which records hold an image."""

    def test_a_record_without_media_is_left_out(self):
        records = [{"handle": "a", "media_list": []}, {"handle": "b"}]
        assert index_media_holders(records) == set()

    def test_a_record_with_media_is_kept(self):
        records = [{"handle": "a", "media_list": [{"ref": "m1"}]}]
        assert index_media_holders(records) == {"a"}


class TestPersonCoverage:
    """The three counts, kept apart."""

    def test_media_on_the_person_counts_as_direct(self):
        row = person_coverage(_person("I0001", media=2), {}, set(), set())
        assert (row["direct"], row["via_citation"], row["via_place"]) == (2, 0, 0)

    def test_a_scan_on_an_event_citation_counts_as_indirect(self):
        events = {"e1": _event("e1", citations=["c1", "c2"])}
        row = person_coverage(_person("I0001", events=["e1"]), events, {"c1"}, set())
        assert (row["direct"], row["via_citation"]) == (0, 1)

    def test_a_postcard_on_an_event_place_counts_as_indirect(self):
        events = {"e1": _event("e1", place="p1")}
        row = person_coverage(_person("I0001", events=["e1"]), events, set(), {"p1"})
        assert row["via_place"] == 1

    def test_an_event_with_no_place_is_not_matched_by_an_empty_handle(self):
        # Reason: the API serves "" rather than None for a place-less event,
        # so an empty string must never match a place holding media.
        events = {"e1": _event("e1", place="")}
        row = person_coverage(_person("I0001", events=["e1"]), events, set(), {""})
        assert row["via_place"] == 0

    def test_a_dangling_event_reference_is_skipped(self):
        row = person_coverage(_person("I0001", events=["gone"]), {}, set(), set())
        assert (row["via_citation"], row["via_place"]) == (0, 0)


class TestClassification:
    """Acquisition backlog versus surfacing backlog."""

    def test_a_person_with_nothing_anywhere_is_uncovered(self):
        row = person_coverage(_person("I0001"), {}, set(), set())
        assert is_uncovered(row) is True
        assert needs_surfacing(row) is False

    def test_a_person_reached_only_through_an_event_needs_surfacing(self):
        events = {"e1": _event("e1", citations=["c1"])}
        row = person_coverage(_person("I0001", events=["e1"]), events, {"c1"}, set())
        assert is_uncovered(row) is False
        assert needs_surfacing(row) is True

    def test_a_person_holding_their_own_portrait_needs_neither(self):
        row = person_coverage(_person("I0001", media=1), {}, set(), set())
        assert is_uncovered(row) is False
        assert needs_surfacing(row) is False


class TestDocumentNearby:
    """A register scan is actionable; a commune photograph is not."""

    def test_a_scan_on_a_citation_is_a_document_nearby(self):
        events = {"e1": _event("e1", citations=["c1"])}
        row = person_coverage(_person("I0001", events=["e1"]), events, {"c1"}, set())
        assert has_document_nearby(row) is True

    def test_a_place_photograph_alone_is_not_a_document_nearby(self):
        # Reason: place media are commune illustrations from Wikimedia, not
        # images of the person - copying one onto a record misrepresents it.
        events = {"e1": _event("e1", place="p1")}
        row = person_coverage(_person("I0001", events=["e1"]), events, set(), {"p1"})
        assert has_document_nearby(row) is False
        assert is_uncovered(row) is False

    def test_a_person_already_holding_media_is_not_a_candidate(self):
        events = {"e1": _event("e1", citations=["c1"])}
        row = person_coverage(
            _person("I0001", media=1, events=["e1"]), events, {"c1"}, set()
        )
        assert has_document_nearby(row) is False
