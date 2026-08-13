# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Data management MCP tools for genealogy operations.

This module contains 9 CRUD tools for creating and updating people, families,
events, places, sources, citations, notes, media, and repository records.
"""

import logging

from mcp.types import TextContent

from ..client import GrampsAPIError, GrampsWebAPIClient
from ..config import get_settings
from ..handlers.citation_handler import format_citation
from ..handlers.event_handler import format_event
from ..handlers.family_handler import format_family
from ..handlers.media_handler import format_media
from ..handlers.note_handler import format_note
from ..handlers.person_handler import format_person
from ..handlers.place_handler import format_place
from ..handlers.repository_handler import format_repository
from ..handlers.source_handler import format_source
from ..models.api_calls import ApiCalls
from ..models.parameters.citation_params import CitationData
from ..models.parameters.event_params import EventSaveParams
from ..models.parameters.family_params import FamilySaveParams
from ..models.parameters.media_params import MediaSaveParams
from ..models.parameters.note_params import NoteSaveParams
from ..models.parameters.people_params import PersonData
from ..models.parameters.place_params import PlaceSaveParams
from ..models.parameters.repository_params import RepositoryData
from ..models.parameters.source_params import SourceSaveParams
from .media_upload import upload_media_from_path

logger = logging.getLogger(__name__)


def _format_error_response(error: Exception, operation: str) -> list[TextContent]:
    """Format error into user-friendly MCP response."""
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"

    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


def _extract_entity_data(result, entity_type: str | None = None):
    """Extract entity data from API response, handling different formats."""
    if not result:
        return None

    # Handle family creation special case - find Family entry in response list
    if entity_type == "family" and isinstance(result, list) and len(result) > 1:
        family_entry = None
        for entry in result:
            if entry.get("new", {}).get("_class") == "Family":
                family_entry = entry["new"]
                break
        return family_entry if family_entry else result[0].get("new", result[0])

    # Standard case - API may return list or single object
    return (
        result[0]["new"]
        if result and isinstance(result, list) and result[0].get("new")
        else result
    )


async def _handle_crud_operation(
    params,
    entity_type: str,
    post_api_call,
    put_api_call,
    param_class,
    pre_save_hook=None,
) -> list[TextContent]:
    """Common helper for create/update operations.

    Args:
        pre_save_hook: optional async callable
            (client, tree_id, validated_params) -> validated_params, run
            after validation and before the create/update dispatch. Used to
            perform side effects (like an inline media upload) that need to
            mutate validated_params before it's sent to the Gramps API.
    """
    try:
        # Reason: replace_lists is an instruction for make_api_call (which
        # list fields to overwrite rather than merge), not entity data. Pop
        # it before building the params model so it never reaches the
        # Gramps API request body via model_dump.
        replace_lists = params.pop("replace_lists", None)

        # Validate parameters
        validated_params = param_class(**params)

        # Get tree_id from settings
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Create client and make unified API call
        client = GrampsWebAPIClient()
        if pre_save_hook is not None:
            validated_params = await pre_save_hook(client, tree_id, validated_params)

        # Choose API call based on whether handle is provided (update vs create)
        if hasattr(validated_params, "handle") and validated_params.handle:
            # Update existing entity
            result = await client.make_api_call(
                api_call=put_api_call,
                params=validated_params,
                tree_id=tree_id,
                handle=validated_params.handle,
                replace_lists=replace_lists,
            )
            operation = "updated"
        else:
            # Create new entity
            result = await client.make_api_call(
                api_call=post_api_call, params=validated_params, tree_id=tree_id
            )
            operation = "created"

        # Extract entity data from API response
        entity_data = _extract_entity_data(result, entity_type)
        formatted_response = await _format_save_response(
            client, entity_data, entity_type, operation, tree_id
        )
        return [TextContent(type="text", text=formatted_response)]

    except Exception as e:
        return _format_error_response(e, f"{entity_type} save")


async def _format_save_response(
    client: GrampsWebAPIClient,
    entity_data: dict,
    entity_type: str,
    operation: str,
    tree_id: str,
) -> str:
    """Format successful save operation response using appropriate format handler."""
    handle = entity_data.get("handle", "N/A")
    gramps_id = entity_data.get("gramps_id", "N/A")

    try:
        # Use the appropriate format handler to get consistent formatting
        if entity_type == "person":
            formatted_details = await format_person(client, tree_id, handle)
        elif entity_type == "family":
            formatted_details = await format_family(client, tree_id, handle)
        elif entity_type == "event":
            formatted_details = await format_event(client, tree_id, handle)
        elif entity_type == "place":
            formatted_details = await format_place(client, tree_id, handle)
        elif entity_type == "source":
            formatted_details = await format_source(client, tree_id, handle)
        elif entity_type == "citation":
            formatted_details = await format_citation(client, tree_id, handle)
        elif entity_type == "media":
            formatted_details = await format_media(client, tree_id, handle)
        elif entity_type == "note":
            formatted_details = await format_note(client, tree_id, handle)
        elif entity_type == "repository":
            formatted_details = await format_repository(client, tree_id, handle)
        else:
            # Fallback for unknown types
            formatted_details = (
                f"• **{entity_type.title()} {gramps_id}** (Handle: `{handle}`)\n\n"
            )

        # Add success prefix to the formatted details
        result = f"Successfully {operation} {entity_type}:\n\n{formatted_details}"
        return result

    except Exception as e:
        logger.warning(f"Error formatting {entity_type} details: {e}")
        # Fallback to basic formatting if handler fails
        display_name = f"{entity_type.title()} {gramps_id}"
        result = f"Successfully {operation} {entity_type}: **{display_name}**\n\n"
        result += f"**ID:** {gramps_id}\n"
        result += f"**Handle:** `{handle}`\n"
        return result


# ============================================================================
# Data Management Tools (8 tools)
# ============================================================================


async def create_person_tool(arguments: dict) -> list[TextContent]:
    """
    Create or update person information including family links and event associations.
    """
    return await _handle_crud_operation(
        arguments, "person", ApiCalls.POST_PEOPLE, ApiCalls.PUT_PERSON, PersonData
    )


async def create_family_tool(arguments: dict) -> list[TextContent]:
    """
    Create or update family unit including member relationships.
    """
    try:
        # Validate parameters
        params = FamilySaveParams(**arguments)

        # Reason: the real Gramps Web API has no child_handles field - it
        # expects child_ref_list entries. Translate here so the caller can
        # keep using the simpler child_handles shape.
        if params.child_handles:
            params.child_ref_list = [{"ref": h} for h in params.child_handles]
            params.child_handles = None

        # Get tree_id from settings
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Create client and make unified API call
        client = GrampsWebAPIClient()
        # Choose API call based on whether handle is provided (update vs create)
        if params.handle:
            # Update existing family
            result = await client.make_api_call(
                api_call=ApiCalls.PUT_FAMILY,
                params=params,
                tree_id=tree_id,
                handle=params.handle,
            )
            operation = "updated"
        else:
            # Create new family
            result = await client.make_api_call(
                api_call=ApiCalls.POST_FAMILIES, params=params, tree_id=tree_id
            )
            operation = "created"

        # Extract entity data from API response (handles family special case)
        entity_data = _extract_entity_data(result, "family")
        formatted_response = await _format_save_response(
            client, entity_data, "family", operation, tree_id
        )
        return [TextContent(type="text", text=formatted_response)]

    except Exception as e:
        return _format_error_response(e, "family save")


async def create_event_tool(arguments: dict) -> list[TextContent]:
    """
    Create or update life event including person/place associations.
    """
    return await _handle_crud_operation(
        arguments, "event", ApiCalls.POST_EVENTS, ApiCalls.PUT_EVENT, EventSaveParams
    )


async def create_place_tool(arguments: dict) -> list[TextContent]:
    """
    Create or update geographic location.
    """
    return await _handle_crud_operation(
        arguments, "place", ApiCalls.POST_PLACES, ApiCalls.PUT_PLACE, PlaceSaveParams
    )


async def _attach_media_path_hook(client, tree_id, validated_params):
    """Upload validated_params.media_path (if set) and append its ref to
    media_list, then clear media_path so it never reaches the Gramps API."""
    if getattr(validated_params, "media_path", None):
        media_object = await upload_media_from_path(
            client, validated_params.media_path, tree_id
        )
        media_list = list(validated_params.media_list or [])
        media_list.append({"ref": media_object["handle"]})
        validated_params.media_list = media_list
        validated_params.media_path = None
    return validated_params


async def create_source_tool(arguments: dict) -> list[TextContent]:
    """
    Create or update source document.
    """
    return await _handle_crud_operation(
        arguments,
        "source",
        ApiCalls.POST_SOURCES,
        ApiCalls.PUT_SOURCE,
        SourceSaveParams,
        pre_save_hook=_attach_media_path_hook,
    )


async def create_citation_tool(arguments: dict) -> list[TextContent]:
    """
    Create or update citation including object associations.
    """
    return await _handle_crud_operation(
        arguments,
        "citation",
        ApiCalls.POST_CITATIONS,
        ApiCalls.PUT_CITATION,
        CitationData,
        pre_save_hook=_attach_media_path_hook,
    )


async def create_note_tool(arguments: dict) -> list[TextContent]:
    """
    Create or update textual note including object associations.
    """
    return await _handle_crud_operation(
        arguments, "note", ApiCalls.POST_NOTES, ApiCalls.PUT_NOTE, NoteSaveParams
    )


async def create_media_tool(arguments: dict) -> list[TextContent]:
    """
    Create or update media files including object associations.
    """
    try:
        params = MediaSaveParams(**arguments) if arguments else None
        file_location = params.media_path if params else None
        if params:
            params.media_path = None

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        # If a handle is provided, we are updating an existing media object
        if params and params.handle:
            result = await client.make_api_call(
                api_call=ApiCalls.PUT_MEDIA_ITEM,
                params=params,
                tree_id=tree_id,
                handle=params.handle,
            )
            operation = "updated"
            entity_data = _extract_entity_data(result)
        else:
            # If no handle, we are creating a new media object,
            # which requires a file
            if not file_location:
                raise ValueError("media_path is required to create new media.")

            # 1. Upload the file to create the initial media object
            initial_media_object = await upload_media_from_path(
                client, file_location, tree_id
            )
            media_handle = initial_media_object["handle"]

            # 2. Merge initial object with metadata and update via PUT
            final_media_data = initial_media_object.copy()
            if params:
                final_media_data.update(params.model_dump(exclude_none=True))

            result = await client.make_api_call(
                api_call=ApiCalls.PUT_MEDIA_ITEM,
                params=final_media_data,
                tree_id=tree_id,
                handle=media_handle,
            )
            operation = "created"
            entity_data = _extract_entity_data(result)

        formatted_response = await _format_save_response(
            client, entity_data, "media", operation, tree_id
        )
        return [TextContent(type="text", text=formatted_response)]

    except Exception as e:
        return _format_error_response(e, "media save")


async def create_repository_tool(arguments: dict) -> list[TextContent]:
    """
    Create or update repository information.
    """
    try:
        # Let Pydantic model handle parameter validation

        # Assert required parameters
        if not arguments.get("name"):
            return [
                TextContent(
                    type="text",
                    text="Error: 'name' parameter is required for repository",
                )
            ]
        if not arguments.get("type"):
            return [
                TextContent(
                    type="text",
                    text="Error: 'type' parameter is required for repository",
                )
            ]

        # Validate parameters
        params = RepositoryData(**arguments)

        # Get tree_id from settings
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        # Create client and make unified API call
        client = GrampsWebAPIClient()
        # Choose API call based on whether handle is provided (update vs create)
        if params.handle:
            # Update existing repository
            result = await client.make_api_call(
                api_call=ApiCalls.PUT_REPOSITORY,
                params=params,
                tree_id=tree_id,
                handle=params.handle,
            )
            operation = "updated"
        else:
            # Create new repository
            result = await client.make_api_call(
                api_call=ApiCalls.POST_REPOSITORIES, params=params, tree_id=tree_id
            )
            operation = "created"

        # Extract entity data from API response
        entity_data = _extract_entity_data(result)
        formatted_response = await _format_save_response(
            client, entity_data, "repository", operation, tree_id
        )
        return [TextContent(type="text", text=formatted_response)]

    except Exception as e:
        return _format_error_response(e, "repository save")
