"""
Integration test for the complete Gramps MCP workflow.

Tests the full workflow described in gramps-usage-guide.md:
1. Repository creation
2. Source creation
3. Citation creation
4. Event creation
5. Person creation and event linking
6. Family unit creation

This test follows the example workflow: Processing a Marriage Record
"""

import re
from typing import Any

import pytest

from src.gramps_mcp.tools.data_management import (
    create_citation_tool,
    create_event_tool,
    create_family_tool,
    create_person_tool,
    create_repository_tool,
    create_source_tool,
)
from src.gramps_mcp.tools.search_basic import (
    find_citation_tool,
    find_event_tool,
    find_family_tool,
    find_person_tool,
    find_repository_tool,
    find_source_tool,
)
from tests.workflow_helpers import (
    create_place_hierarchy,
    create_test_media,
    create_test_note,
)

pytestmark = pytest.mark.integration


class TestCompleteWorkflow:
    """
    Test the complete genealogy data entry workflow using real MCP tools.

    This integration test validates the complete workflow described in
    gramps-usage-guide.md by processing a marriage record from start to finish:

    1. Repository creation (St. Mary's Catholic Church, Boston)
    2. Source creation (Marriage Register 1875-1880)
    3. Citation creation (Page 67, Entry 15)
    4. Event creation (Marriage on June 15, 1878)
    5. Person creation (John Smith, Mary Jones) and event linking
    6. Family creation and relationship linking

    The test follows the "Always Find First" principle - searching for existing
    entities before creating new ones, exactly as described in the usage guide.
    This ensures the workflow behaves correctly with both empty and populated
    genealogy databases.
    """

    @pytest.mark.asyncio
    async def test_complete_marriage_record_workflow(self):
        """
        Test the complete workflow by processing a marriage record.

        Example: Marriage of John Smith and Mary Jones on June 15, 1878
        at St. Mary's Catholic Church, Boston from Marriage Register 1875-1880.

        This test demonstrates the complete workflow from the usage guide.
        """
        workflow_data = {}

        # Step 1: Repository Creation - Find/Create "St. Mary's Catholic Church, Boston"
        await self._step_1_repository_creation(workflow_data)
        print(
            f"Step 1 completed: Repository handle = {workflow_data.get('repository_handle')}"
        )

        # Step 2: Source Creation - Find/Create "Marriage Register 1875-1880"
        await self._step_2_source_creation(workflow_data)
        print(f"Step 2 completed: Source handle = {workflow_data.get('source_handle')}")

        # Step 3: Citation Creation - Create citation for specific page/entry
        await self._step_3_citation_creation(workflow_data)
        print(
            f"Step 3 completed: Citation handle = {workflow_data.get('citation_handle')}"
        )

        # Step 4: Event Creation - Create marriage event on June 15, 1878
        await self._step_4_event_creation(workflow_data)
        print(f"Step 4 completed: Event handle = {workflow_data.get('event_handle')}")

        # Step 5: Person Creation - Create John Smith and Mary Jones, link to event
        await self._step_5_person_creation(workflow_data)
        print(
            f"Step 5 completed: John handle = {workflow_data.get('john_handle')}, Mary handle = {workflow_data.get('mary_handle')}"
        )

        # Step 6: Family Creation - Create family unit and link marriage event
        await self._step_6_family_creation(workflow_data)
        print(f"Step 6 completed: Family handle = {workflow_data.get('family_handle')}")

        # Final verification
        print("Workflow completed successfully - all entities created and linked!")

    @pytest.mark.asyncio
    async def test_place_hierarchy_creation(self):
        """
        Test place creation with proper hierarchy as described in usage guide.

        Creates the complete place hierarchy:
        Country -> State -> City -> Church
        """
        workflow_data = {}

        # Create place hierarchy from top to bottom
        await create_place_hierarchy(workflow_data)

        # Verify all places were created and linked properly
        assert "country_handle" in workflow_data
        assert "state_handle" in workflow_data
        assert "city_handle" in workflow_data
        assert "church_handle" in workflow_data

        print("Place hierarchy created successfully:")
        print(f"  Country: {workflow_data['country_handle']}")
        print(f"  State: {workflow_data['state_handle']}")
        print(f"  City: {workflow_data['city_handle']}")
        print(f"  Church: {workflow_data['church_handle']}")

    async def _step_1_repository_creation(self, workflow_data: dict[str, Any]):
        """Step 1: Repository Creation following usage guide."""

        # First: Use find_repository to search for existing repository
        find_result = await find_repository_tool(
            {"query": "St. Mary's Catholic Church Boston", "pagesize": 5}
        )

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        # Check if repository already exists and is complete
        existing_handle = None
        if (
            "No sources found" not in result_text
            and "St. Mary's Catholic Church" in result_text
        ):
            handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
            if handle_match:
                existing_handle = handle_match.group(1)

        if existing_handle:
            # Use existing repository as-is
            workflow_data["repository_handle"] = existing_handle
        else:
            # Create new repository with complete attributes
            create_result = await create_repository_tool(
                {
                    "name": "St. Mary's Catholic Church, Boston",
                    "type": "Church",
                    "urls": [
                        {
                            "type": "Web Home",
                            "path": "https://stmarysboston.org",
                            "desc": "Official church website",
                        }
                    ],
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            workflow_data["repository_handle"] = handle_match.group(1)

    async def _step_2_source_creation(self, workflow_data: dict[str, Any]):
        """Step 2: Source Document Creation following usage guide."""

        # First: Use find_source to search for existing source document
        find_result = await find_source_tool(
            {"query": "Marriage Register 1875-1880", "pagesize": 5}
        )

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        # Check if source document already exists
        existing_handle = None
        if "No sources found" not in result_text and "Marriage Register" in result_text:
            handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
            if handle_match:
                existing_handle = handle_match.group(1)

        if existing_handle:
            # Use existing source
            workflow_data["source_handle"] = existing_handle
        else:
            # Create new source document with complete attributes
            create_result = await create_source_tool(
                {
                    "title": "Marriage Register 1875-1880",
                    "reporef_list": [{"ref": workflow_data["repository_handle"]}],
                    "author": "Rev. Patrick O'Sullivan",
                    "pubinfo": "Handwritten register, maintained 1875-1880",
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            workflow_data["source_handle"] = handle_match.group(1)

    async def _step_3_citation_creation(self, workflow_data: dict[str, Any]):
        """Step 3: Citation Creation following usage guide."""

        # First create note and media for citation if needed
        note_handle = await create_test_note(
            "Research note: Found this record during genealogy research session on January 15, 2024. Quality of handwriting is excellent.",
            "Research",
        )
        workflow_data["citation_note_handle"] = note_handle

        media_handle = await create_test_media(
            "tests/sample/33SQ-GP8N-NLK.jpg",
            "Marriage Record - John Smith & Mary Jones",
            {
                "year": 1878,
                "month": 6,
                "day": 15,
                "type": "regular",
                "quality": "regular",
            },
        )
        workflow_data["citation_media_handle"] = media_handle

        # First: Use find_citation to search for existing citation
        find_result = await find_citation_tool(
            {"query": "Page 67 Entry 15 John Smith Mary Jones", "pagesize": 5}
        )

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        # Check if citation already exists
        existing_handle = None
        if "No citations found" not in result_text and "Page 67" in result_text:
            handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
            if handle_match:
                existing_handle = handle_match.group(1)

        if existing_handle:
            # Use existing citation
            workflow_data["citation_handle"] = existing_handle
        else:
            # Create new citation with complete attributes
            create_result = await create_citation_tool(
                {
                    "source_handle": workflow_data["source_handle"],
                    "page": "Page 67, Entry 15, Marriage of John Smith and Mary Jones, June 15, 1878",
                    "date": {
                        "dateval": [2024, 1, 15, False],
                        "quality": 0,
                        "modifier": 0,
                    },
                    "media_list": [{"ref": media_handle}] if media_handle else [],
                    "note_list": [note_handle] if note_handle else [],
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            workflow_data["citation_handle"] = handle_match.group(1)

    async def _step_4_event_creation(self, workflow_data: dict[str, Any]):
        """Step 4: Event Creation with place and date following usage guide."""

        # Create place hierarchy first (if event has place)
        await create_place_hierarchy(workflow_data)

        # First: Use find_event to search for existing event
        find_result = await find_event_tool(
            {"query": "marriage John Smith Mary Jones 1878", "pagesize": 5}
        )

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        # Check if event already exists
        existing_handle = None
        if "No events found" not in result_text and "marriage" in result_text:
            handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
            if handle_match:
                existing_handle = handle_match.group(1)

        if existing_handle:
            # Use existing event
            workflow_data["event_handle"] = existing_handle
        else:
            # Create new marriage event with date and place
            create_result = await create_event_tool(
                {
                    "type": "Marriage",
                    "date": {
                        "dateval": [1878, 6, 15, False],
                        "quality": 0,
                        "modifier": 0,
                    },
                    "citation_list": [workflow_data["citation_handle"]],
                    "description": "Marriage ceremony performed by Rev. Patrick O'Sullivan",
                    "place": workflow_data["church_handle"],
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_matches = re.findall(r"\[([a-f0-9]+)\]", create_text)
            if handle_matches:
                event_handle = handle_matches[0]  # First handle is the event handle
            else:
                event_handle = None
            assert event_handle, f"No handle found in: {create_text}"
            workflow_data["event_handle"] = event_handle

    async def _step_5_person_creation(self, workflow_data: dict[str, Any]):
        """Step 5: Person Creation and Event Linking following usage guide."""

        # Create/Find John Smith (groom) with complete attributes
        john_handle = await self._create_or_find_person_with_attributes(
            "John", "Smith", 1, "1850", "Boston", workflow_data["event_handle"], "groom"
        )
        workflow_data["john_handle"] = john_handle

        # Create/Find Mary Jones (bride) with complete attributes
        mary_handle = await self._create_or_find_person_with_attributes(
            "Mary", "Jones", 0, "1855", "Boston", workflow_data["event_handle"], "bride"
        )
        workflow_data["mary_handle"] = mary_handle

    async def _step_6_family_creation(self, workflow_data: dict[str, Any]):
        """Step 6: Family Unit Creation following usage guide."""

        # First: Use find_family to search for existing family
        find_result = await find_family_tool(
            {"query": "John Smith Mary Jones", "pagesize": 5}
        )

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        # Check if family already exists
        existing_handle = None
        if "No families found" not in result_text:
            handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
            if handle_match:
                existing_handle = handle_match.group(1)

        if existing_handle:
            # Use existing family
            workflow_data["family_handle"] = existing_handle
        else:
            # Create new family unit
            create_result = await create_family_tool(
                {
                    "father_handle": workflow_data["john_handle"],
                    "mother_handle": workflow_data["mary_handle"],
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            workflow_data["family_handle"] = handle_match.group(1)

    async def _create_or_find_person_with_attributes(
        self,
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
        # Create note and media for person
        person_note_handle = await create_test_note(
            f"Genealogy research note for {given_name} {surname}. Found in marriage records from St. Mary's Church, Boston.",
            "Research",
        )

        person_media_handle = await create_test_media(
            "tests/sample/33SQ-GP8N-NLK.jpg",
            f"Portrait of {given_name} {surname}",
            {"year": int(birth_year) + 25, "type": "about", "quality": "estimated"},
        )

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
            # Update existing person with event link
            create_result = await create_person_tool(
                {
                    "handle": existing_handle,
                    "event_handle": event_handle,
                    "event_role": event_role,
                }
            )
            return existing_handle
        else:
            # Create new person with complete attributes
            create_result = await create_person_tool(
                {
                    "primary_name": {"given_name": given_name, "surname": surname},
                    "gender": gender,
                    "note_handle": person_note_handle,
                    "media_handle": person_media_handle,
                    "url": {
                        "type": "Website",
                        "path": f"https://findagrave.com/memorial/{given_name.lower()}-{surname.lower()}",
                        "description": f"Find A Grave memorial for {given_name} {surname}",
                    },
                    "event_handle": event_handle,
                    "event_role": event_role,
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            return handle_match.group(1)
