"""
Creation helpers shared by the workflow integration tests.

These come from `tests/test_complete_workflow.py`, which was split into
`tests/test_workflow_marriage.py` and `tests/test_workflow_attributes.py`.
Both halves create notes, media and places the same way, so the helpers live
here: duplicating them would be waste, and leaving them in the marriage module
would push it past the project's 500-line limit.

The bodies are unchanged from the original methods - only `self` was dropped.
"""

import re
from typing import Any

from src.gramps_mcp.tools.data_management import (
    create_media_tool,
    create_note_tool,
    create_person_tool,
    create_place_tool,
)
from src.gramps_mcp.tools.search_basic import find_person_tool, find_place_tool


async def create_test_note(text: str, note_type: str) -> str:
    """
    Create a test note for demonstration purposes.

    Args:
        text: The note content
        note_type: Type of note (General, Research, Transcript, etc.)

    Returns:
        Note handle
    """
    create_result = await create_note_tool({"text": text, "type": note_type})

    assert isinstance(create_result, list) and len(create_result) == 1
    create_text = create_result[0].text
    handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
    assert handle_match, f"No handle found in: {create_text}"
    return handle_match.group(1)


async def create_test_media(
    file_path: str, title: str, date_info: dict[str, Any]
) -> str:
    """
    Create a test media item for demonstration purposes.

    Args:
        file_path: Path to the media file
        title: Descriptive title for the media
        date_info: Date information with year, month, day, type, quality

    Returns:
        Media handle
    """
    create_result = await create_media_tool(
        {
            "media_path": file_path,
            "desc": title,
            "date": {
                "dateval": [
                    date_info["year"],
                    date_info.get("month", 1),
                    date_info.get("day", 1),
                    False,
                ],
                "quality": 0,
                "modifier": 0,
            },
        }
    )

    assert isinstance(create_result, list) and len(create_result) == 1
    create_text = create_result[0].text
    handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
    assert handle_match, f"No handle found in: {create_text}"
    return handle_match.group(1)


async def create_place_hierarchy(workflow_data: dict[str, Any]):
    """
    Create place hierarchy following usage guide requirements.

    Hierarchy: Country -> State -> City -> Church
    Each place must be enclosed by the higher-level place.
    """
    # Step 1: Create Country (top level, no enclosing place)
    country_handle = await create_or_find_place("United States", "Country", None)
    workflow_data["country_handle"] = country_handle

    # Step 2: Create State (enclosed by Country)
    state_handle = await create_or_find_place("Massachusetts", "State", country_handle)
    workflow_data["state_handle"] = state_handle

    # Step 3: Create City (enclosed by State)
    city_handle = await create_or_find_place("Boston", "City", state_handle)
    workflow_data["city_handle"] = city_handle

    # Step 4: Create Church (enclosed by City)
    church_handle = await create_or_find_place(
        "St. Mary's Catholic Church", "Church", city_handle
    )
    workflow_data["church_handle"] = church_handle


async def create_or_find_place(
    name: str, place_type: str, enclosed_by_handle: str = None
) -> str:
    """
    Create or find a place following the workflow guidelines.

    Args:
        name: Place name
        place_type: Type of place (Country, State, City, Church, etc.)
        enclosed_by_handle: Handle of the higher-level place that contains this place

    Returns:
        Place handle
    """
    # First: Use find_place to search for existing place
    find_result = await find_place_tool({"query": name, "pagesize": 5})

    assert isinstance(find_result, list) and len(find_result) == 1
    result_text = find_result[0].text

    # Check for potential matches
    existing_handle = None
    if "No places found" not in result_text:
        if name.lower() in result_text.lower():
            handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
            if handle_match:
                existing_handle = handle_match.group(1)

    if existing_handle:
        # Use existing place
        return existing_handle
    else:
        # Create new place with complete attributes
        place_data = {
            "name": {"value": name},
            "place_type": place_type,
            "urls": [
                {
                    "type": "Web Home",
                    "path": f"https://en.wikipedia.org/wiki/{name.replace(' ', '_')}",
                    "description": f"Wikipedia article about {name}",
                }
            ],
        }

        # Note: place_type is now used in the place_data dictionary

        # Add enclosed_by_handle if provided (not for top-level Country)
        if enclosed_by_handle:
            place_data["placeref_list"] = [{"ref": enclosed_by_handle}]

        create_result = await create_place_tool(place_data)

        assert isinstance(create_result, list) and len(create_result) == 1
        create_text = create_result[0].text
        handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
        assert handle_match, f"No handle found in: {create_text}"
        return handle_match.group(1)


async def create_or_find_person(
    given_name: str, surname: str, gender: int, birth_year: str, context: str
) -> str:
    """
    Create or find a person following the workflow guidelines (legacy method).

    Args:
        given_name: Person's first name
        surname: Person's last name
        gender: 0=Female, 1=Male, 2=Unknown
        birth_year: Estimated birth year for search
        context: Geographic context for search

    Returns:
        Person handle
    """
    # First: Use find_person to search for existing person
    search_query = f"{given_name} {surname} {birth_year} {context}"
    find_result = await find_person_tool({"query": search_query, "pagesize": 5})

    assert isinstance(find_result, list) and len(find_result) == 1
    result_text = find_result[0].text

    # Check for potential matches
    existing_handle = None
    if "No people found" not in result_text:
        if (
            given_name.lower() in result_text.lower()
            and surname.lower() in result_text.lower()
        ):
            handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
            if handle_match:
                # In real usage, we would ask user to confirm identity
                # For this test, we assume it's a match
                existing_handle = handle_match.group(1)

    if existing_handle:
        # Use existing person
        return existing_handle
    else:
        # Create new person
        create_result = await create_person_tool(
            {
                "primary_name": {"given_name": given_name, "surname": surname},
                "gender": gender,
            }
        )

        assert isinstance(create_result, list) and len(create_result) == 1
        create_text = create_result[0].text
        handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
        assert handle_match, f"No handle found in: {create_text}"
        return handle_match.group(1)
