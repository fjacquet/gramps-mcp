"""
Integration tests for detailed search tools using real Gramps API.

Tests get_person_details and get_family_details tools that provide comprehensive structured data.
"""

import re

import pytest
from dotenv import load_dotenv
from mcp.types import TextContent

from src.gramps_mcp.tools.data_management import create_note_tool, create_person_tool
from src.gramps_mcp.tools.search_basic import find_type_tool
from src.gramps_mcp.tools.search_details import get_person_tool, get_type_tool

# Load environment variables
load_dotenv()


def _extract_handle(text: str) -> str:
    match = re.search(r"\[([a-f0-9]+)\]", text)
    assert match, f"Could not extract handle from: {text}"
    return match.group(1)


def extract_gramps_id_from_search(search_text: str):
    """Extract gramps_id from search result text."""
    # Format: Name (gender) - gramps_id - [handle]
    id_match = re.search(r"\([FM]\) - ([^-]+) - \[", search_text)

    if id_match:
        return id_match.group(1).strip()
    return None


@pytest.mark.asyncio
async def test_get_person_tool():
    """Test get_type_tool provides comprehensive person data with timeline."""

    # Use specific person I0001 - first find the handle
    search_result = await find_type_tool({"type": "person", "gql": 'gramps_id="I0001"'})

    # Extract handle from search results
    search_text = search_result[0].text
    if "Found" in search_text and "Found 0" not in search_text:
        lines = search_text.split("\n")
        for line in lines:
            if "[" in line and "]" in line and "I0001" in line:
                # Extract handle from brackets
                start = line.rfind("[")
                end = line.rfind("]")
                handle = line[start + 1 : end]

                # Get comprehensive details report for person I0001
                result = await get_type_tool(
                    {
                        "type": "person",
                        "handle": handle,
                    }
                )

                assert len(result) == 1
                assert isinstance(result[0], TextContent)

                text = result[0].text
                # Print complete output without truncation
                for line in text.split("\n"):
                    print(line)

                # Should be substantial structured data content
                assert isinstance(text, str)
                assert len(text.strip()) > 50  # Should have basic content

                # Should contain structured person header: Name (Gender) - ID - [handle]
                assert f" - I0001 - [{handle}]" in text
                assert "(" in text and ")" in text  # Should have gender in parentheses

                # Should contain at least one of these life events
                has_life_events = "Born:" in text or "Died:" in text
                assert has_life_events, (
                    "Should have at least Born: or Died: information"
                )

                # Should contain family relationships
                assert "RELATIONS:" in text, "Should have relations section"
                assert "Parents:" in text, "Should have parents section"

                # Should contain timeline section with structured data
                assert "TIMELINE:" in text, "Should have timeline section"

                # Timeline events should include participant information in new format
                timeline_section = text.split("TIMELINE:")[1]
                # Should have events in format: date (place) - eventID : eventType, participantName participantID, role
                assert ":" in timeline_section and " I" in timeline_section, (
                    "Timeline events should include participant info in new format"
                )

                # Should have attached media or notes properly formatted
                assert "Attached media:" in text, "Should have attached media"
                assert "Attached notes:" in text, "Should have attached notes"
                break
        else:
            pytest.skip("Person I0001 not found in search results")
    else:
        pytest.skip("Person I0001 not found in tree")


@pytest.mark.asyncio
async def test_get_person_by_gramps_id():
    """Test get_type_tool with gramps_id parameter (no handle)."""

    # Test getting person details using gramps_id directly
    result = await get_type_tool({"type": "person", "gramps_id": "I0001"})

    assert len(result) == 1
    assert isinstance(result[0], TextContent)

    text = result[0].text
    print(f"Result: {text}")

    # Should contain person details with I0001 in it
    assert "I0001" in text
    assert len(text.strip()) > 50  # Should have substantial content


@pytest.mark.asyncio
async def test_get_family_tool():
    """Test get_type_tool provides comprehensive family data with timeline."""

    # Use specific family F0001 - first find the handle
    search_result = await find_type_tool({"type": "family", "gql": 'gramps_id="F0001"'})

    # Extract handle from search results
    search_text = search_result[0].text
    if "Found" in search_text and "Found 0" not in search_text:
        lines = search_text.split("\n")
        for line in lines:
            if "[" in line and "]" in line and "F0001" in line:
                # Extract handle from brackets
                start = line.rfind("[")
                end = line.rfind("]")
                handle = line[start + 1 : end]

                # Get comprehensive family group report for F0001
                result = await get_type_tool(
                    {
                        "type": "family",
                        "handle": handle,
                    }
                )

                assert len(result) == 1
                assert isinstance(result[0], TextContent)

                text = result[0].text
                # Print complete output without truncation
                for line in text.split("\n"):
                    print(line)

                # Should be substantial structured data content
                assert isinstance(text, str)
                assert len(text.strip()) > 50  # Should have basic content

                # Should contain structured family header with ID and handle
                assert f"F0001 - [{handle}]" in text

                # Should contain parent information or children
                has_family_members = (
                    "Father:" in text or "Mother:" in text or "CHILDREN:" in text
                )
                assert has_family_members, (
                    "Should have at least one family member listed"
                )

                # Should have father properly formatted
                assert "Father:" in text, "Should have father information"
                father_line = text.split("Father:")[1].split("\n")[0]
                assert " (" in father_line and ") - " in father_line, (
                    "Father should be in Name (Gender) - ID format"
                )

                # Should have mother properly formatted
                assert "Mother:" in text, "Should have mother information"
                mother_line = text.split("Mother:")[1].split("\n")[0]
                assert " (" in mother_line and ") - " in mother_line, (
                    "Mother should be in Name (Gender) - ID format"
                )

                # Should contain marriage information
                assert "Married:" in text, "Should have marriage information"
                marriage_section = (
                    text.split("Married:")[1].split("TIMELINE:")[0].strip()
                )
                assert marriage_section, "Marriage should have date or place"

                # Should have children properly listed
                assert "Children:" in text or "CHILDREN:" in text, (
                    "Should have children information"
                )
                children_section = (
                    text.split("Children:")[1]
                    if "Children:" in text
                    else text.split("CHILDREN:")[1]
                )
                assert " (" in children_section and ") - " in children_section, (
                    "Children should be in Name (Gender) - ID format"
                )

                # Should contain timeline section
                assert "TIMELINE:" in text, "Should have timeline section"

                # Timeline events should include participant information in new format
                timeline_section = text.split("TIMELINE:")[1]
                # Should have events in format: date (place) - eventID : eventType, participantName participantID, role
                assert ":" in timeline_section and " I" in timeline_section, (
                    "Timeline events should include participant info in new format"
                )

                # Should have attached media or notes properly formatted
                assert "Attached media:" in text, "Should have attached media"
                assert "Attached notes:" in text, "Should have attached notes"
                break
        else:
            pytest.skip("Family F0001 not found in search results")
    else:
        pytest.skip("Family F0001 not found in tree")


class TestGetPersonToolWithNote:
    """Regression test for upstream issue #29/#30."""

    @pytest.mark.asyncio
    async def test_get_person_with_attached_note_does_not_crash(self):
        """A person with an attached note must format without error."""
        note_result = await create_note_tool(
            {
                "text": "Detail handler regression note for issue 29/30.",
                "type": "Research",
            }
        )
        note_text = note_result[0].text
        assert "Error:" not in note_text, f"Note creation failed: {note_text}"
        note_handle = _extract_handle(note_text)

        person_result = await create_person_tool(
            {
                "primary_name": {
                    "first_name": "NoteRegression",
                    "surname_list": [{"surname": "TestPerson", "primary": True}],
                },
                "gender": 1,
                "note_list": [note_handle],
            }
        )
        person_text = person_result[0].text
        assert "Error:" not in person_text, f"Person creation failed: {person_text}"
        person_handle = _extract_handle(person_text)

        detail_result = await get_person_tool({"person_handle": person_handle})
        detail_text = detail_result[0].text

        assert "Error:" not in detail_text, (
            f"get_person_tool crashed on attached note: {detail_text}"
        )
        assert "Detail handler regression note for issue 29/30." in detail_text, (
            f"Expected real note text in output but got: {detail_text}"
        )
