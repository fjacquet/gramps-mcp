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

import asyncio
import logging

from mcp.types import TextContent

from ..client import GrampsAPIError
from ..config import get_settings
from ..destructive import TYPE_ENDPOINTS, remove_from_list, should_refuse_delete
from ..handlers.destructive_handler import format_merge_preview
from ..models.api_calls import ApiCalls
from ..models.api_mapping import get_param_model
from ..models.parameters.destructive_params import (
    DeleteTypeParams,
    DetachReferenceParams,
    MergeTypeParams,
    UndoChangeParams,
)
from ..utils import escape_gql_literal
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
        ValueError: If neither identifier is given, the type has no
            gramps_id at all, or the gramps_id matches no record.
    """
    if handle:
        return handle
    if not gramps_id:
        raise ValueError("Either handle or gramps_id is required")

    # Reason: Gramps tags carry no gramps_id, and TagSearchParams declares no
    # gql field, so a gramps_id filter here reached the server as a bare
    # `GET tags/?pagesize=1` and resolved to whichever tag the server listed
    # first - which delete_type then deleted, reporting the id the caller
    # asked for. Refused outright rather than resolved to an arbitrary tag.
    if obj_type == "tag":
        raise ValueError(
            "Tags have no gramps_id. Identify a tag by handle instead - "
            "manage_tags(action='list') lists every tag with its handle."
        )

    plural = TYPE_ENDPOINTS[obj_type].plural

    # Reason: escape_gql_literal, not raw interpolation - a gramps_id such as
    # `X" or gramps_id!="X` would otherwise close the GQL string literal
    # early, match every record, and (with pagesize 1) resolve to an
    # arbitrary record that delete_type would then delete. Same escaping as
    # search_details._resolve_gramps_id, deliberately shared.
    escaped = escape_gql_literal(gramps_id)
    results = await client.make_api_call(
        api_call=plural,
        params={"gql": f'gramps_id="{escaped}"', "pagesize": 1},
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

        # Reason: the payload carries the edited list and nothing else.
        # make_api_call re-GETs the record and merges this into it
        # (merge_put_data), so every other field comes from the server's own
        # copy and is written back byte-identical. Round-tripping the whole
        # fetched record through the write model instead - as this did
        # originally - was lossless only by luck: merge_put_data replaces
        # non-list keys wholesale, so an event's `date`, a raw dict against a
        # declared DateValue, was replaced by whatever pydantic's
        # inferred-serialization fallback produced. That fallback is what
        # emitted PydanticSerializationUnexpectedValue; the day it narrows to
        # the declared fields, every event detach would silently truncate the
        # date. Sending one field removes the warning and the truncation
        # vector together.
        #
        # model_construct rather than normal construction because the write
        # models validate: EventSaveParams' nested date sub-model forbids
        # extra keys the raw GET record carries, and required fields such as
        # PersonData's primary_name and gender are deliberately absent from a
        # single-list payload. replace_lists=[list_name] is what actually
        # removes the element; every other list keeps the union semantics of
        # ADR 0003, so this call cannot drop unrelated data.
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
        validated_params = write_model.model_construct(
            **{params.list_name: updated[params.list_name]}
        )

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

        endpoints = TYPE_ENDPOINTS[params.type]
        if endpoints.merge is None:
            # Reason: unreachable today - MergeableType already excludes
            # "tag", the only type with merge=None in TYPE_ENDPOINTS, so
            # pydantic rejects that type before this function body runs.
            # Kept as defense in depth for a future type that gains
            # merge=None in TYPE_ENDPOINTS without also being removed from
            # MergeableType.
            raise ValueError(f"{params.type} records cannot be merged")

        phoenix_handle = await resolve_target_handle(
            client,
            tree_id,
            params.type,
            params.phoenix_handle,
            params.phoenix_gramps_id,
        )
        titanic_handle = await resolve_target_handle(
            client,
            tree_id,
            params.type,
            params.titanic_handle,
            params.titanic_gramps_id,
        )

        # Reason: checked after resolution, not before - two different
        # gramps_ids can resolve to the same handle, and that must be
        # refused just as surely as passing the same handle twice would be.
        if phoenix_handle == titanic_handle:
            raise ValueError("phoenix and titanic must resolve to different handles")

        phoenix = await client.make_api_call(
            api_call=endpoints.get, tree_id=tree_id, handle=phoenix_handle
        )
        titanic = await client.make_api_call(
            api_call=endpoints.get, tree_id=tree_id, handle=titanic_handle
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
            phoenix_handle=phoenix_handle,
            titanic_handle=titanic_handle,
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


async def _await_undo_result(client, task_id: str, timeout: float = 5.0) -> dict:
    """
    Poll a queued undo task until it reaches a terminal state, or timeout.

    Args:
        client (GrampsWebAPIClient): Client to issue the polling GET with.
        task_id (str): Celery task id returned by POST_TRANSACTION_UNDO.
        timeout (float): Maximum time to poll, in seconds.

    Returns:
        dict: The last task-status response observed. Its "state" key is
            "SUCCESS" or "FAILURE" on a terminal outcome, or whatever
            non-terminal state (e.g. "PENDING") was last seen when the
            timeout was reached.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    status: dict = {"state": "PENDING"}
    while loop.time() < deadline:
        status = await client.make_api_call(
            api_call=ApiCalls.GET_TASK_STATUS, task_id=task_id
        )
        if status.get("state") in ("SUCCESS", "FAILURE"):
            return status
        await asyncio.sleep(0.3)
    return status


@with_client
async def undo_change_tool(client, arguments: dict) -> list[TextContent]:
    """Undo one recorded transaction."""
    try:
        params = UndoChangeParams(**arguments)
        tree_id = get_settings().gramps_tree_id

        # Reason: force travels in the query string, not a JSON body - see
        # the ApiCalls.POST_TRANSACTION_UNDO carve-out in
        # GrampsWebAPIClient.make_api_call and UndoTransactionQueryParams,
        # which is the model registered for this endpoint.
        response = await client.make_api_call(
            api_call=ApiCalls.POST_TRANSACTION_UNDO,
            params={"force": params.force},
            tree_id=tree_id,
            transaction_id=params.transaction_id,
        )

        # Reason: "Undo a transaction using background processing" is the
        # endpoint's own docstring - the POST above only confirms the task
        # was queued, not that the undo succeeded. Without force, a known
        # Gramps Web bug (see UndoChangeParams.force's description) makes
        # every delete-undo fail silently in the background, so this tool
        # must poll the task to a terminal state before claiming success.
        task = response.get("task") if isinstance(response, dict) else None
        task_id = task.get("id") if task else None
        if task_id:
            status = await _await_undo_result(client, task_id)
            state = status.get("state")
            if state == "FAILURE":
                hint = (
                    ""
                    if params.force
                    else " Retry with force=true if the object genuinely has "
                    "not changed since the transaction."
                )
                raise GrampsAPIError(
                    f"transaction {params.transaction_id} was not undone: "
                    f"{status.get('info') or 'undo task failed'}.{hint}"
                )
            if state != "SUCCESS":
                return [
                    TextContent(
                        type="text",
                        text=(
                            f"Transaction {params.transaction_id} undo is "
                            "still processing in the background after 5 "
                            "seconds. Run recent_changes to confirm the "
                            "outcome."
                        ),
                    )
                ]

            return [
                TextContent(
                    type="text",
                    text=(
                        f"Transaction {params.transaction_id} undone. "
                        "Run recent_changes to confirm the tree is as "
                        "expected."
                    ),
                )
            ]

        # Reason: no task id means the polling above never ran, so nothing
        # here observed the undo reaching a terminal state. Claiming it was
        # undone would assert exactly what the comment above says the POST
        # cannot prove - and a delete-undo, the case that most needs a
        # truthful answer, is the one the upstream bug already makes fragile.
        return [
            TextContent(
                type="text",
                text=(
                    f"Transaction {params.transaction_id} undo was queued, "
                    "but the server returned no task to follow, so this tool "
                    "did not observe the outcome. Run recent_changes to "
                    "confirm whether the tree was actually reverted."
                ),
            )
        ]

    except Exception as e:
        return _format_error_response(e, "undo")
