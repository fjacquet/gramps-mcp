"""
Shared fixtures creating real records in the Gramps Web tree.

Nothing here fakes the API. Each fixture performs a real create against the
configured server, yields the handle, and deletes the record afterwards. They
exist so that no test depends on another test having run first.

Scope is "module": one set of records per test module, reused by its tests.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.parameters.citation_params import CitationData
from src.gramps_mcp.models.parameters.event_params import EventSaveParams
from src.gramps_mcp.models.parameters.family_params import FamilySaveParams
from src.gramps_mcp.models.parameters.media_params import MediaSaveParams
from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
from src.gramps_mcp.models.parameters.people_params import PersonData
from src.gramps_mcp.models.parameters.place_params import PlaceSaveParams
from src.gramps_mcp.models.parameters.repository_params import RepositoryData
from src.gramps_mcp.models.parameters.source_params import SourceSaveParams
from src.gramps_mcp.tools.data_management import _extract_entity_data

# Reason: every record these fixtures create is named with this prefix so a
# run killed mid-test leaves objects that are obvious in the tree and easy to
# find and remove by hand.
PREFIX = "Pytest Lot5"


async def create_entity(client, tree_id, api_call, params_model, entity_type) -> str:
    """
    Create one entity and return its handle.

    Args:
        client (GrampsWebAPIClient): Client to issue the call with.
        tree_id (str): Family tree identifier.
        api_call (ApiCalls): The POST call for this entity type.
        params_model (BaseModel): Validated parameters for the new entity.
        entity_type (str): Entity name as _extract_entity_data expects it.

    Returns:
        str: The handle of the created entity.
    """
    result = await client.make_api_call(
        api_call=api_call, params=params_model, tree_id=tree_id
    )
    # Reason: the handle is read out of the structured response, never scraped
    # from formatted prose - a rendering change must not break setup.
    return _extract_entity_data(result, entity_type)["handle"]


async def delete_entity(client, tree_id, api_call, handle) -> None:
    """
    Delete one entity, ignoring a failure so teardown never masks a test result.

    Args:
        client (GrampsWebAPIClient): Client to issue the call with.
        tree_id (str): Family tree identifier.
        api_call (ApiCalls): The DELETE call for this entity type.
        handle (str): Handle of the record to remove.

    Returns:
        None
    """
    try:
        await client.make_api_call(api_call=api_call, tree_id=tree_id, handle=handle)
    except Exception:
        # Reason: a teardown failure must not turn a passing test red. The
        # PREFIX above is what makes the leftover findable if this happens.
        pass


@pytest_asyncio.fixture(scope="module")
async def gramps_client() -> AsyncIterator[GrampsWebAPIClient]:
    """Yield a client for the configured tree."""
    yield GrampsWebAPIClient()


@pytest.fixture(scope="module")
def tree_id() -> str:
    """Return the configured family tree identifier."""
    return get_settings().gramps_tree_id


@pytest_asyncio.fixture(scope="module")
async def note_handle(gramps_client, tree_id) -> AsyncIterator[str]:
    """Create a note with no prerequisites."""
    handle = await create_entity(
        gramps_client,
        tree_id,
        ApiCalls.POST_NOTES,
        NoteSaveParams(text=f"{PREFIX} note", type="Transcript"),
        "note",
    )
    yield handle
    await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_NOTE, handle)


@pytest_asyncio.fixture(scope="module")
async def media_handle(gramps_client, tree_id) -> AsyncIterator[str]:
    """
    Create a media object with no prerequisites.

    Reason: POST_MEDIA takes no JSON body (see api_mapping.py - it is a
    multipart file upload), so this fixture cannot go through create_entity.
    The file is uploaded first, then the description is set with a PUT.
    """
    upload_result = await gramps_client.upload_media_file(
        file_content=f"{PREFIX} media".encode(),
        mime_type="text/plain",
        tree_id=tree_id,
    )
    handle = upload_result[0]["new"]["handle"]
    await gramps_client.make_api_call(
        api_call=ApiCalls.PUT_MEDIA_ITEM,
        params=MediaSaveParams(desc=f"{PREFIX} media"),
        tree_id=tree_id,
        handle=handle,
    )
    yield handle
    await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_MEDIA_ITEM, handle)


@pytest_asyncio.fixture(scope="module")
async def repository_handle(gramps_client, tree_id, note_handle) -> AsyncIterator[str]:
    """Create a repository holding the shared note."""
    handle = await create_entity(
        gramps_client,
        tree_id,
        ApiCalls.POST_REPOSITORIES,
        RepositoryData(
            name=f"{PREFIX} repository", type="Archive", note_list=[note_handle]
        ),
        "repository",
    )
    yield handle
    await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_REPOSITORY, handle)


@pytest_asyncio.fixture(scope="module")
async def source_handle(
    gramps_client, tree_id, repository_handle
) -> AsyncIterator[str]:
    """Create a source held by the shared repository."""
    handle = await create_entity(
        gramps_client,
        tree_id,
        ApiCalls.POST_SOURCES,
        SourceSaveParams(
            title=f"{PREFIX} source", reporef_list=[{"ref": repository_handle}]
        ),
        "source",
    )
    yield handle
    await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_SOURCE, handle)


@pytest_asyncio.fixture(scope="module")
async def citation_handle(gramps_client, tree_id, source_handle) -> AsyncIterator[str]:
    """Create a citation pointing at the shared source."""
    handle = await create_entity(
        gramps_client,
        tree_id,
        ApiCalls.POST_CITATIONS,
        CitationData(source_handle=source_handle, page=f"{PREFIX} page 1"),
        "citation",
    )
    yield handle
    await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_CITATION, handle)


@pytest_asyncio.fixture(scope="module")
async def place_handle(gramps_client, tree_id) -> AsyncIterator[str]:
    """Create a place with no prerequisites."""
    handle = await create_entity(
        gramps_client,
        tree_id,
        ApiCalls.POST_PLACES,
        # Reason: PlaceSaveParams.name is a PlaceName object, not a string.
        PlaceSaveParams(name={"value": f"{PREFIX} place"}, place_type="City"),
        "place",
    )
    yield handle
    await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_PLACE, handle)


@pytest_asyncio.fixture(scope="module")
async def event_handle(
    gramps_client, tree_id, citation_handle, place_handle
) -> AsyncIterator[str]:
    """Create a sourced event at the shared place."""
    handle = await create_entity(
        gramps_client,
        tree_id,
        ApiCalls.POST_EVENTS,
        EventSaveParams(
            type="Marriage",
            description=f"{PREFIX} event",
            place=place_handle,
            citation_list=[citation_handle],
        ),
        "event",
    )
    yield handle
    await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_EVENT, handle)


@pytest_asyncio.fixture(scope="module")
async def person_handles(gramps_client, tree_id) -> AsyncIterator[list[str]]:
    """Create the two people the family fixture needs, father first."""
    handles = []
    for surname, gender in (("Father", 1), ("Mother", 0)):
        handles.append(
            await create_entity(
                gramps_client,
                tree_id,
                ApiCalls.POST_PEOPLE,
                PersonData(
                    primary_name={
                        "first_name": PREFIX,
                        "surname_list": [{"surname": surname}],
                    },
                    gender=gender,
                ),
                "person",
            )
        )
    yield handles
    for handle in handles:
        await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_PERSON, handle)


@pytest_asyncio.fixture(scope="module")
async def family_handle(gramps_client, tree_id, person_handles) -> AsyncIterator[str]:
    """Create a family joining the two shared people."""
    father, mother = person_handles
    handle = await create_entity(
        gramps_client,
        tree_id,
        ApiCalls.POST_FAMILIES,
        FamilySaveParams(father_handle=father, mother_handle=mother),
        "family",
    )
    yield handle
    await delete_entity(gramps_client, tree_id, ApiCalls.DELETE_FAMILY, handle)
