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
Destructive MCP tools: delete, merge, detach and undo.

Every tool here can remove data. The guard rails live in destructive.py as
pure functions; this module does the I/O and the formatting.
"""

import logging

from mcp.types import TextContent

from ..client import GrampsAPIError
from ..config import get_settings
from ..destructive import TYPE_ENDPOINTS, remove_from_list, should_refuse_delete
from ..handlers.destructive_handler import format_merge_preview
from ..models.api_mapping import get_param_model
from ..models.parameters.destructive_params import (
    DeleteTypeParams,
    DetachReferenceParams,
    MergeTypeParams,
)
from .search_basic import with_client

logger = logging.getLogger(__name__)


def _format_error_response(error: Exception, operation: str) -> list[TextContent]:
    """Format an error into a user-facing MCP response."""
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"
    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


async def resolve_target_handle(
    client, tree_id: str, obj_type: str, handle: str | None, gramps_id: str | None
) -> str:
    """
    Return the handle for a target named by handle or by gramps_id.

    Args:
        client (GrampsWebAPIClient): Client to issue the lookup with.
        tree_id (str): Family tree identifier.
        obj_type (str): One of the keys of TYPE_ENDPOINTS.
        handle (str | None): Handle, used directly when given.
        gramps_id (str | None): Gramps ID, resolved by a GQL search.

    Returns:
        str: The resolved handle.

    Raises:
        ValueError: If neither identifier is given, or the gramps_id matches
            no record.
    """
    if handle:
        return handle
    if not gramps_id:
        raise ValueError("Either handle or gramps_id is required")

    from ..models.api_calls import ApiCalls

    plural = {
        "person": ApiCalls.GET_PEOPLE,
        "family": ApiCalls.GET_FAMILIES,
        "event": ApiCalls.GET_EVENTS,
        "place": ApiCalls.GET_PLACES,
        "source": ApiCalls.GET_SOURCES,
        "citation": ApiCalls.GET_CITATIONS,
        "repository": ApiCalls.GET_REPOSITORIES,
        "media": ApiCalls.GET_MEDIA,
        "note": ApiCalls.GET_NOTES,
        "tag": ApiCalls.GET_TAGS,
    }[obj_type]

    results = await client.make_api_call(
        api_call=plural,
        params={"gql": f'gramps_id="{gramps_id}"', "pagesize": 1},
        tree_id=tree_id,
    )
    if not results:
        raise ValueError(f"No {obj_type} found with gramps_id {gramps_id}")
    return results[0]["handle"]


@with_client
async def delete_type_tool(client, arguments: dict) -> list[TextContent]:
    """Delete one record, refusing while other records still reference it."""
    try:
        params = DeleteTypeParams(**arguments)
        tree_id = get_settings().gramps_tree_id
        endpoints = TYPE_ENDPOINTS[params.type]

        handle = await resolve_target_handle(
            client, tree_id, params.type, params.handle, params.gramps_id
        )

        record = await client.make_api_call(
            api_call=endpoints.get,
            params={"backlinks": True},
            tree_id=tree_id,
            handle=handle,
        )
        gramps_id = record.get("gramps_id", handle)
        backlinks = record.get("backlinks") or {}

        refusal = should_refuse_delete(backlinks)
        if refusal and not params.force:
            return [
                TextContent(
                    type="text",
                    text=f"{params.type} {gramps_id}\n{refusal}",
                )
            ]

        await client.make_api_call(
            api_call=endpoints.delete, tree_id=tree_id, handle=handle
        )

        severed = ""
        if refusal:
            total = sum(len(v) for v in backlinks.values() if v)
            severed = f" {total} reference(s) were severed (force=true)."
        return [
            TextContent(
                type="text",
                text=f"Deleted {params.type} {gramps_id}.{severed}",
            )
        ]

    except Exception as e:
        return _format_error_response(e, "deletion")


@with_client
async def detach_reference_tool(client, arguments: dict) -> list[TextContent]:
    """Remove one element from a record's list, leaving every other list alone."""
    try:
        params = DetachReferenceParams(**arguments)
        tree_id = get_settings().gramps_tree_id
        endpoints = TYPE_ENDPOINTS[params.type]

        handle = await resolve_target_handle(
            client, tree_id, params.type, params.handle, params.gramps_id
        )

        record = await client.make_api_call(
            api_call=endpoints.get, tree_id=tree_id, handle=handle
        )
        gramps_id = record.get("gramps_id", handle)

        updated = remove_from_list(record, params.list_name, params.ref_handle)

        # Reason: make_api_call validates a dict params argument against the
        # endpoint's full write model, and that model has fields the API
        # requires on every write (e.g. PersonData needs primary_name and
        # gender) that a bare {list_name: value} payload would not carry.
        # Normal construction was tried against live data and genuinely
        # fails for reasons unrelated to required fields: EventSaveParams'
        # nested date sub-model forbids extra keys the raw GET record
        # carries, and its place validator rejects the handle shape GET
        # returns. model_construct builds the model instance without
        # running that validation, from whatever the write model declares
        # out of the record as read plus the edited list - every value but
        # the edited list is therefore identical to what is already stored.
        # replace_lists=[list_name] is what actually removes the element, and
        # every other list keeps the union semantics of ADR 0003, so this
        # call cannot drop unrelated data.
        write_model = get_param_model(endpoints.put)
        if write_model is None:
            # Reason: unreachable today - every TYPE_ENDPOINTS.put value is
            # registered in API_CALL_PARAMS with a real model. Guarded so a
            # future endpoint added without one fails loudly, not silently.
            raise ValueError(f"No write model registered for {params.type}")
        if params.list_name not in write_model.model_fields:
            raise ValueError(
                f"{params.list_name} cannot be edited on {params.type} records: "
                "the write model does not declare it."
            )
        payload = {k: v for k, v in updated.items() if k in write_model.model_fields}
        validated_params = write_model.model_construct(**payload)

        await client.make_api_call(
            api_call=endpoints.put,
            params=validated_params,
            tree_id=tree_id,
            handle=handle,
            replace_lists=[params.list_name],
        )

        return [
            TextContent(
                type="text",
                text=(
                    f"Detached {params.ref_handle} from {params.list_name} "
                    f"of {params.type} {gramps_id}."
                ),
            )
        ]

    except Exception as e:
        return _format_error_response(e, "detach")


@with_client
async def merge_type_tool(client, arguments: dict) -> list[TextContent]:
    """Merge two records of the same type, previewing unless confirm is set."""
    try:
        params = MergeTypeParams(**arguments)
        tree_id = get_settings().gramps_tree_id

        if params.phoenix_handle == params.titanic_handle:
            raise ValueError("phoenix_handle and titanic_handle must differ")

        endpoints = TYPE_ENDPOINTS[params.type]
        if endpoints.merge is None:
            raise ValueError(f"{params.type} records cannot be merged")

        phoenix = await client.make_api_call(
            api_call=endpoints.get, tree_id=tree_id, handle=params.phoenix_handle
        )
        titanic = await client.make_api_call(
            api_call=endpoints.get, tree_id=tree_id, handle=params.titanic_handle
        )

        if not params.confirm:
            return [
                TextContent(
                    type="text",
                    text=format_merge_preview(phoenix, titanic, params.type),
                )
            ]

        extra = {}
        if params.phoenix_father_handle:
            extra["phoenix_father_handle"] = params.phoenix_father_handle
        if params.phoenix_mother_handle:
            extra["phoenix_mother_handle"] = params.phoenix_mother_handle

        await client.make_api_call(
            api_call=endpoints.merge,
            params=extra or None,
            tree_id=tree_id,
            phoenix_handle=params.phoenix_handle,
            titanic_handle=params.titanic_handle,
        )

        return [
            TextContent(
                type="text",
                text=(
                    f"Merged {params.type} {titanic.get('gramps_id', '?')} into "
                    f"{phoenix.get('gramps_id', '?')}. The absorbed record is gone; "
                    "use undo_change to reverse this."
                ),
            )
        ]

    except Exception as e:
        return _format_error_response(e, "merge")
