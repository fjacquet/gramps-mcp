"""
Integration tests for the person and family data management tools using
real Gramps Web API.

Covers create_person_tool and create_family_tool. These tests require a
working Gramps Web API instance with valid credentials. Only tests actual
API integration - Pydantic validation is tested elsewhere.
"""

import pytest

from src.gramps_mcp.tools.data_management import (
    create_citation_tool,
    create_event_tool,
    create_family_tool,
    create_note_tool,
    create_person_tool,
    create_source_tool,
)
from tests.constants import PREFIX

pytestmark = pytest.mark.integration


class TestCreatePersonTool:
    """Test create_person_tool functionality - Eighth in workflow."""

    @pytest.mark.asyncio
    async def test_create_person_success(self, event_handle, media_handle, note_handle):
        """Test successful person creation using proper structure and linking events."""
        result = await create_person_tool(
            {
                "primary_name": {
                    "first_name": "John",
                    "surname_list": [{"surname": "Smith", "primary": True}],
                },
                "gender": 1,  # Male
                "event_ref_list": [{"ref": event_handle, "role": "Primary"}],
                "media_list": [{"ref": media_handle}],
                "note_list": [note_handle],
                "urls": [
                    {
                        "type": "Web Home",
                        "path": "https://familysearch.org/person/123",
                        "description": "FamilySearch profile",
                    }
                ],
            }
        )

        print("\n--- SAVE PERSON CREATE SUCCESS RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        # Assert all required fields from usage guide are in output
        assert "John" in text, (
            f"Expected primary_name first_name (required) in output but got: {text}"
        )
        assert "Smith" in text, (
            f"Expected primary_name surname (required) in output but got: {text}"
        )
        # Gender 1 = Male should be shown as (M)
        assert "(M)" in text, f"Expected gender (M) in output but got: {text}"

        # Assert optional fields that were provided
        # Should show linked event with role - the shared event is a Marriage
        assert "Marriage" in text, f"Expected linked event in output but got: {text}"
        assert "Primary" in text, f"Expected event role in output but got: {text}"
        # Should show the linked media and note that were passed in
        assert "Attached media: O" in text, (
            f"Expected linked media reference in output but got: {text}"
        )
        assert "Attached notes: N" in text, (
            f"Expected linked note reference in output but got: {text}"
        )
        # Should show URLs
        assert "https://familysearch.org/person/123" in text, (
            f"Expected URL path in output but got: {text}"
        )
        assert "FamilySearch profile" in text, (
            f"Expected URL description in output but got: {text}"
        )

    @pytest.mark.asyncio
    async def test_update_person_with_event_reference(self):
        """Test updating an existing person with a new event reference - Issue #9."""
        import re

        # Step 1: Create a standalone test person
        person_result = await create_person_tool(
            {
                "primary_name": {
                    "first_name": "TestUpdate",
                    "surname_list": [{"surname": "PersonIssue9", "primary": True}],
                },
                "gender": 1,  # Male
            }
        )

        print("\n--- CREATE TEST PERSON ---")
        print(person_result[0].text)
        print("--- END ---\n")

        # Extract person handle
        person_handle_match = re.search(r"\[([a-f0-9]+)\]", person_result[0].text)
        if not person_handle_match:
            pytest.fail("Could not extract person handle")
        person_handle = person_handle_match.group(1)

        # Step 2: Create a simple note for our citation
        note_result = await create_note_tool(
            {"text": "Test note for Issue #9 update test", "type": "General"}
        )
        note_handle_match = re.search(r"\[([a-f0-9]+)\]", note_result[0].text)
        if not note_handle_match:
            pytest.fail("Could not extract note handle")

        # Step 3: Create a simple source
        source_result = await create_source_tool({"title": "Test Source for Issue 9"})
        source_handle_match = re.search(r"\[([a-f0-9]+)\]", source_result[0].text)
        if not source_handle_match:
            pytest.fail("Could not extract source handle")
        source_handle = source_handle_match.group(1)

        # Step 4: Create a citation
        citation_result = await create_citation_tool(
            {"source_handle": source_handle, "page": "Test Page"}
        )
        citation_handle_match = re.search(r"\[([a-f0-9]+)\]", citation_result[0].text)
        if not citation_handle_match:
            pytest.fail("Could not extract citation handle")
        citation_handle = citation_handle_match.group(1)

        # Step 5: Create first event (Birth)
        birth_event_result = await create_event_tool(
            {
                "type": "Birth",
                "citation_list": [citation_handle],
                "date": {"dateval": [1, 1, 1900, False], "quality": 0, "modifier": 0},
            }
        )

        print("\n--- CREATE BIRTH EVENT ---")
        print(birth_event_result[0].text)
        print("--- END ---\n")

        birth_event_handle_match = re.search(
            r"\[([a-f0-9]+)\]", birth_event_result[0].text
        )
        if not birth_event_handle_match:
            pytest.fail("Could not extract birth event handle")
        birth_event_handle = birth_event_handle_match.group(1)

        # Step 6: Update person with first event
        first_update_result = await create_person_tool(
            {
                "handle": person_handle,
                "primary_name": {
                    "first_name": "TestUpdate",
                    "surname_list": [{"surname": "PersonIssue9", "primary": True}],
                },
                "gender": 1,
                "event_ref_list": [{"ref": birth_event_handle, "role": "Primary"}],
            }
        )

        print("\n--- UPDATE PERSON WITH BIRTH EVENT ---")
        print(first_update_result[0].text)
        print("--- END ---\n")

        # Step 7: Create second event (Death)
        death_event_result = await create_event_tool(
            {
                "type": "Death",
                "citation_list": [citation_handle],
                "date": {"dateval": [31, 12, 1999, False], "quality": 0, "modifier": 0},
            }
        )

        print("\n--- CREATE DEATH EVENT ---")
        print(death_event_result[0].text)
        print("--- END ---\n")

        death_event_handle_match = re.search(
            r"\[([a-f0-9]+)\]", death_event_result[0].text
        )
        if not death_event_handle_match:
            pytest.fail("Could not extract death event handle")
        death_event_handle = death_event_handle_match.group(1)

        # Step 8: Now update the person with BOTH events - this is the exact scenario from issue #9
        # The person already has the birth event, and we're adding the death event
        update_result = await create_person_tool(
            {
                "handle": person_handle,
                "primary_name": {
                    "first_name": "TestUpdate",
                    "surname_list": [{"surname": "PersonIssue9", "primary": True}],
                },
                "gender": 1,
                "event_ref_list": [
                    {"ref": birth_event_handle, "role": "Primary"},
                    {"ref": death_event_handle, "role": "Primary"},
                ],
            }
        )

        print("\n--- UPDATE PERSON WITH BOTH EVENTS (Issue #9 scenario) ---")
        print(update_result[0].text)
        print("--- END ---\n")

        text = update_result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()
        assert "updated" in text.lower(), (
            f"Expected 'updated' in output but got: {text}"
        )

        # Verify both events are now linked to the person
        assert "Birth" in text, f"Expected Birth event in output but got: {text}"
        assert "Death" in text, f"Expected Death event in output but got: {text}"

    @pytest.mark.asyncio
    async def test_create_second_person_success(self, media_handle, note_handle):
        """Test creation of second person for family test."""
        result = await create_person_tool(
            {
                "primary_name": {
                    "first_name": "Mary",
                    "surname_list": [{"surname": "Johnson", "primary": True}],
                },
                "gender": 0,  # Female
                "media_list": [{"ref": media_handle}],
                "note_list": [note_handle],
                "urls": [
                    {
                        "type": "Web Home",
                        "path": "https://familysearch.org/person/456",
                        "description": "FamilySearch profile",
                    }
                ],
            }
        )

        print("\n--- SAVE SECOND PERSON CREATE SUCCESS RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        # Assert all required fields from usage guide are in output
        assert "Mary" in text, (
            f"Expected primary_name first_name (required) in output but got: {text}"
        )
        assert "Johnson" in text, (
            f"Expected primary_name surname (required) in output but got: {text}"
        )
        # Gender 0 = Female should be shown as (F)
        assert "(F)" in text, f"Expected gender (F) in output but got: {text}"

        # Assert optional fields that were provided
        # Should show the linked media and note that were passed in
        assert "Attached media: O" in text, (
            f"Expected linked media reference in output but got: {text}"
        )
        assert "Attached notes: N" in text, (
            f"Expected linked note reference in output but got: {text}"
        )
        # Should show URLs
        assert "https://familysearch.org/person/456" in text, (
            f"Expected URL path in output but got: {text}"
        )
        assert "FamilySearch profile" in text, (
            f"Expected URL description in output but got: {text}"
        )


class TestCreateFamilyTool:
    """Test create_family_tool functionality - Last in workflow."""

    @pytest.mark.asyncio
    async def test_create_family_success(
        self, person_handles, media_handle, note_handle
    ):
        """Test successful family creation using the two shared people."""
        father_handle, mother_handle = person_handles

        result = await create_family_tool(
            {
                "father_handle": father_handle,
                "mother_handle": mother_handle,
                "media_list": [{"ref": media_handle}],
                "note_list": [note_handle],
                "urls": [
                    {
                        "type": "Web Home",
                        "path": "https://familysearch.org/family/789",
                        "description": "FamilySearch family record",
                    }
                ],
            }
        )

        print("\n--- SAVE FAMILY CREATE SUCCESS RESULT ---")
        print(result[0].text)
        print("--- END ---\n")

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        # Assert required fields from usage guide are in output (at least one parent)
        # Father and mother handles are both optional, but at least one should be present
        assert f"{PREFIX} Father" in text, (
            f"Expected father reference in output but got: {text}"
        )
        assert f"{PREFIX} Mother" in text, (
            f"Expected mother reference in output but got: {text}"
        )

        # Assert optional fields that were provided
        # Should show the linked media and note that were passed in
        assert "Attached media: O" in text, (
            f"Expected linked media reference in output but got: {text}"
        )
        assert "Attached notes: N" in text, (
            f"Expected linked note reference in output but got: {text}"
        )
        # Should show URLs (new format: path - description)
        assert "https://familysearch.org/family/789" in text, (
            f"Expected URL path in output but got: {text}"
        )
        assert "FamilySearch family record" in text, (
            f"Expected URL description in output but got: {text}"
        )

    @pytest.mark.asyncio
    async def test_create_family_with_child_handles(self):
        """Regression test for issue #24: child_handles must translate to
        child_ref_list so the API actually stores the child link."""
        import re

        child_result = await create_person_tool(
            {
                "primary_name": {
                    "first_name": "ChildHandles",
                    "surname_list": [{"surname": "RegressionChild", "primary": True}],
                },
                "gender": 0,
            }
        )
        child_text = child_result[0].text
        assert "Error:" not in child_text, f"Child creation failed: {child_text}"
        child_handle_match = re.search(r"\[([a-f0-9]+)\]", child_text)
        assert child_handle_match, f"Could not extract child handle: {child_text}"
        child_handle = child_handle_match.group(1)

        family_result = await create_family_tool({"child_handles": [child_handle]})

        family_text = family_result[0].text
        assert "Error:" not in family_text, (
            f"Expected success but got error: {family_text}"
        )
        assert "ChildHandles" in family_text and "RegressionChild" in family_text, (
            f"Expected child to appear in family details but got: {family_text}"
        )
