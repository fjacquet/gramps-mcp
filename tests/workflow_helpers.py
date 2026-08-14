"""
Creation helpers shared by the workflow integration tests.

These come from `tests/test_complete_workflow.py`, which was split into
`tests/test_workflow_marriage.py` and `tests/test_workflow_attributes.py`.
Both halves create notes, media and places the same way, so the helpers live
here: duplicating them would be waste, and leaving them in the marriage module
would push it past the project's 500-line limit.

The bodies come from the original methods; `self` was dropped and the
handle-extraction block they all repeated now lives in `extract_handle`.
"""

import re
from typing import Any

from src.gramps_mcp.tools.data_management import (
    create_media_tool,
    create_note_tool,
    create_person_tool,
    create_place_tool,
)
from src.gramps_mcp.tools.search_basic import (
    find_anything_tool,
    find_person_tool,
    find_place_tool,
)
from tests.constants import PREFIX


def _handle_on_line(text: str, marker: str) -> str:
    """Find the [handle] on the line containing marker - avoids picking up
    an unrelated handle (e.g. a repository or media ref) from elsewhere in
    a concatenated multi-entity response."""
    for line in text.splitlines():
        if marker in line:
            match = re.search(r"\[([a-f0-9]+)\]", line)
            if match:
                return match.group(1)
    raise AssertionError(f"No handle found on a line containing {marker!r} in: {text}")


def extract_handle(create_result: Any) -> str:
    """
    Pull the handle out of a creation tool's formatted response.

    Args:
        create_result (Any): The list the creation tool returned.

    Returns:
        str: The handle found between square brackets in the response text.
    """
    assert isinstance(create_result, list) and len(create_result) == 1
    create_text = create_result[0].text
    handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
    assert handle_match, f"No handle found in: {create_text}"
    return handle_match.group(1)


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

    return extract_handle(create_result)


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

    return extract_handle(create_result)


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

        # Add enclosed_by_handle if provided (not for top-level Country)
        if enclosed_by_handle:
            place_data["placeref_list"] = [{"ref": enclosed_by_handle}]

        create_result = await create_place_tool(place_data)

        return extract_handle(create_result)


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

        return extract_handle(create_result)


async def create_or_find_person_with_attributes(
    given_name: str,
    surname: str,
    gender: int,
    birth_year: str,
    context: str,
    event_handle: str,
    event_role: str,
) -> str:
    """
    Create or find a person with complete attributes following the workflow guidelines.

    The person's first name carries `PREFIX` (`tests/constants.py`), the same
    marker `tests/conftest.py` uses. Two things depend on that: it keeps this
    test's people out of `find_anything_tool`'s way of unrelated same-named
    records left by other tests (there are unprefixed "John Smith" people in
    the live tree from a different workflow test), and it is what makes a
    leftover from a killed run findable by a prefix scan - see #16.

    `find_person_tool` is not used here even though it looks like the
    natural search step: it is not MCP-exposed (only `find_type` and
    `find_anything` are, per `TOOL_REGISTRY` in `server.py`), and in the one
    real caller that does reach it (`find_type_tool`) it is always given
    `gql`, never `query`. Its `query` parameter is a latent trap - accepted
    and silently ignored, because `BaseGetMultipleParams` never declares a
    `query` field - not a live defect, since nothing in production ever
    calls it that way. `find_anything_tool` is the tool that actually
    supports free-text `query` (see #18 for the full writeup).

    Args:
        given_name: Person's first name
        surname: Person's last name
        gender: 0=Female, 1=Male, 2=Unknown
        birth_year: Estimated birth year for search
        context: Geographic context for search
        event_handle: Handle of event to link to person
        event_role: Role of person in the event (groom, bride, witness, etc.)

    Returns:
        Person handle
    """
    prefixed_first_name = f"{PREFIX} {given_name}"
    full_name = f"{prefixed_first_name} {surname}"

    # Create note and media for person
    person_note_handle = await create_test_note(
        f"Genealogy research note for {full_name}. Found in marriage records from St. Mary's Church, Boston.",
        "Research",
    )

    person_media_handle = await create_test_media(
        "tests/sample/33SQ-GP8N-NLK.jpg",
        f"Portrait of {full_name}",
        {"year": int(birth_year) + 25, "type": "about", "quality": "estimated"},
    )

    # First: Use find_anything to search for an existing, prefixed person.
    # find_anything mixes person, family, note, media and citation records
    # in one result set, so pick a handle only off a line that actually
    # looks like a person entry - "Name (M) - I0123 - [handle]" at the start
    # of a line, produced by format_person. A family line ("Father: Name
    # (M) - I0123 | Mother: ... - F0456 - [handle]") or a note/media title
    # that happens to mention the name would otherwise hand back the wrong
    # kind of handle.
    find_result = await find_anything_tool({"query": full_name})

    assert isinstance(find_result, list) and len(find_result) == 1
    result_text = find_result[0].text

    person_line_pattern = re.compile(
        rf"^{re.escape(full_name)} \([MFU]\) - I\d+ - \[([a-f0-9]+)\]",
        re.MULTILINE,
    )
    existing_handle = None
    if "No records found" not in result_text:
        person_match = person_line_pattern.search(result_text)
        if person_match:
            # In real usage, we would ask user to confirm identity
            # For this test, we assume it's a match
            existing_handle = person_match.group(1)

    if existing_handle:
        # Update existing person with event link
        update_result = await create_person_tool(
            {
                "handle": existing_handle,
                # primary_name and gender are required on PersonData, so a
                # partial update must resupply them. The old call passed
                # only handle plus two undeclared keys, which left the
                # model missing both required fields - it raised, the tool
                # swallowed it into an "Error:" string, and nothing
                # asserted on the result.
                "primary_name": {
                    "first_name": prefixed_first_name,
                    "surname_list": [{"surname": surname}],
                },
                "gender": gender,
                "event_ref_list": [{"ref": event_handle, "role": event_role}],
            }
        )
        update_text = update_result[0].text
        assert "Error:" not in update_text, (
            f"create_person_tool update failed: {update_text}"
        )
        assert "Events:" in update_text, (
            f"Marriage event was not linked on update: {update_text}"
        )
        return existing_handle
    else:
        # Create new person with complete attributes
        create_result = await create_person_tool(
            {
                "primary_name": {
                    "first_name": prefixed_first_name,
                    "surname_list": [{"surname": surname}],
                },
                "gender": gender,
                "note_list": [person_note_handle],
                "media_list": [{"ref": person_media_handle}],
                "urls": [
                    {
                        "type": "Website",
                        "path": (
                            "https://findagrave.com/memorial/"
                            f"{given_name.lower()}-{surname.lower()}"
                        ),
                        "description": f"Find A Grave memorial for {full_name}",
                    }
                ],
                "event_ref_list": [{"ref": event_handle, "role": event_role}],
            }
        )

        create_text = create_result[0].text
        assert "Error:" not in create_text, f"create_person_tool failed: {create_text}"
        # The five keys this test used to pass were silently dropped by
        # Pydantic, so it went green while linking nothing. Assert the
        # links, not just the handle.
        assert full_name in create_text, (
            f"Person was created without a name: {create_text}"
        )
        assert "Attached notes:" in create_text, (
            f"Research note was not linked: {create_text}"
        )
        assert "Attached media:" in create_text, (
            f"Portrait was not linked: {create_text}"
        )
        assert "Events:" in create_text, f"Marriage event was not linked: {create_text}"
        return extract_handle(create_result)
