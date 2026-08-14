"""
Verify the shared fixtures create real records and hand back real handles.

These run against the live Gramps Web API, like the tests that consume them.
"""

import pytest

pytestmark = pytest.mark.integration

HANDLE_LENGTH = 16


class TestSharedFixtures:
    """The fixtures in conftest.py must yield usable handles."""

    @pytest.mark.asyncio
    async def test_root_fixtures_yield_handles(
        self, note_handle, media_handle, place_handle
    ):
        """Fixtures with no prerequisites each create a record."""
        for handle in (note_handle, media_handle, place_handle):
            assert isinstance(handle, str)
            assert len(handle) >= HANDLE_LENGTH

    @pytest.mark.asyncio
    async def test_chained_fixtures_yield_handles(
        self, repository_handle, source_handle, citation_handle, event_handle
    ):
        """Fixtures that depend on earlier records resolve their chain."""
        for handle in (
            repository_handle,
            source_handle,
            citation_handle,
            event_handle,
        ):
            assert isinstance(handle, str)
            assert len(handle) >= HANDLE_LENGTH

    @pytest.mark.asyncio
    async def test_person_fixture_yields_two_handles(self, person_handles):
        """The family tests need two people, so the fixture creates two."""
        assert len(person_handles) == 2
        assert len(set(person_handles)) == 2

    @pytest.mark.asyncio
    async def test_family_fixture_yields_a_handle(self, family_handle):
        """The family fixture links the two people into one record."""
        assert isinstance(family_handle, str)
        assert len(family_handle) >= HANDLE_LENGTH
