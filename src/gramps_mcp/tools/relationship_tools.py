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
Relationship analysis MCP tools for genealogy operations.

This module contains tools for calculating relationships between people,
checking living status, and building timelines.
"""

import logging
import re
from typing import Dict, List, Optional

from mcp.types import TextContent
from pydantic import BaseModel

from ..client import GrampsAPIError
from ..config import get_settings
from ..handlers.living_handler import format_living_status
from ..handlers.relationship_handler import format_relationship, format_relationships
from ..handlers.timeline_handler import format_timeline
from ..models.api_calls import ApiCalls
from ..models.parameters.family_params import FamilyTimelineParams
from ..models.parameters.living_params import LivingParams
from ..models.parameters.people_params import PersonTimelineParams
from ..models.parameters.relations_params import RelationParams
from ..models.parameters.timeline_params import (
    FamiliesTimelineParams,
    PeopleTimelineParams,
)
from ..utils import resolve_family_handle, resolve_person_handle
from .search_basic import with_client

logger = logging.getLogger(__name__)

GRAMPS_ID_PATTERN = re.compile(r"^[A-Z]+[0-9]+$")


class _RelationsQueryParams(BaseModel):
    """
    Query-string-only parameters for the Gramps Web relations endpoints.

    The relations endpoints (``relations/{handle1}/{handle2}`` and
    ``.../all``) take handle1/handle2 as URL path segments and only accept
    ``depth`` as a query parameter; the API rejects unknown query fields.
    RelationParams bundles handle1/handle2 with depth for input validation,
    but handing that full model to the client would also serialize
    handle1/handle2 into the query string. This model carries just the
    query-eligible field through to the request.
    """

    depth: Optional[int] = None


class _LivingQueryParams(BaseModel):
    """
    Query-string-only parameters for the Gramps Web living endpoints.

    The living endpoints (``living/{handle}`` and ``living/{handle}/dates``)
    take handle as a URL path segment and only accept
    average_generation_gap/max_age_probably_alive/max_sibling_age_difference
    as query parameters; the API rejects unknown query fields. LivingParams
    bundles handle with those fields for input validation, but handing that
    full model to the client would also serialize handle into the query
    string. This model carries just the query-eligible fields through to
    the request.
    """

    average_generation_gap: Optional[int] = None
    max_age_probably_alive: Optional[int] = None
    max_sibling_age_difference: Optional[int] = None


class _FamilyTimelineQueryParams(BaseModel):
    """
    Query-string-only parameters for the Gramps Web family timeline endpoint.

    ``families/{handle}/timeline`` takes handle as a URL path segment and
    does not accept it as a query parameter; the live API rejects it with
    "handle: Unknown field." FamilyTimelineParams bundles handle with the
    query-eligible fields for input validation, but handing that full model
    to the client would also serialize handle into the query string. This
    model carries just the query-eligible fields through to the request.
    """

    dates: Optional[str] = None
    events: Optional[str] = None
    event_classes: Optional[str] = None
    ratings: Optional[bool] = None
    discard_empty: Optional[bool] = None
    page: Optional[int] = None
    pagesize: Optional[int] = None


class _PeopleTimelineQueryParams(BaseModel):
    """
    Query-string-only parameters for the Gramps Web people timeline endpoint.

    PeopleTimelineParams.page defaults to 0, matching the value documented
    as the API default, but the live Gramps Web server's query validator
    rejects an explicit page=0 with "page: Must be greater than or equal to
    1." even though its own spec lists 0 as the default. This model mirrors
    PeopleTimelineParams field-for-field except page is Optional and left
    out of the query entirely unless the caller explicitly asked for one,
    avoiding the 422.
    """

    anchor: Optional[str] = None
    dates: Optional[str] = None
    first: bool = True
    last: bool = True
    handles: Optional[str] = None
    events: Optional[str] = None
    event_classes: Optional[str] = None
    ratings: bool = False
    precision: int = 1
    discard_empty: bool = True
    omit_anchor: bool = True
    page: Optional[int] = None
    pagesize: int = 20


class _FamiliesTimelineQueryParams(BaseModel):
    """
    Query-string-only parameters for the Gramps Web families timeline
    endpoint.

    Same page=0-vs-live-validator mismatch as _PeopleTimelineQueryParams
    (see that class's docstring); page is Optional here and left out of
    the query unless explicitly requested.
    """

    handles: Optional[str] = None
    dates: Optional[str] = None
    events: Optional[str] = None
    event_classes: Optional[str] = None
    ratings: bool = False
    discard_empty: bool = True
    page: Optional[int] = None
    pagesize: int = 20


def _format_error_response(error: Exception, operation: str) -> List[TextContent]:
    """Format error into user-friendly MCP response."""
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {str(error)}"

    logger.error(f"Tool error in {operation}: {error_msg}")
    return [TextContent(type="text", text=f"Error: {error_msg}")]


async def _resolve_person(client, tree_id: str, value: str) -> str:
    """
    Resolve a person reference that may be a handle or a gramps_id.

    Values matching GRAMPS_ID_PATTERN (one or more uppercase letters
    followed by one or more digits, e.g. "I0044") are treated as a
    gramps_id and resolved; anything else is treated as an already-valid
    handle.

    Args:
        client: Gramps API client instance
        tree_id: Family tree identifier
        value: Handle or gramps_id string

    Returns:
        A resolved handle

    Raises:
        ValueError: If value looks like a gramps_id but no matching person
            is found
    """
    if GRAMPS_ID_PATTERN.match(value):
        handle = await resolve_person_handle(client, tree_id, value)
        if not handle:
            raise ValueError(f"No person found with gramps_id '{value}'")
        return handle
    return value


async def _resolve_family(client, tree_id: str, value: str) -> str:
    """
    Resolve a family reference that may be a handle or a gramps_id.

    Values matching GRAMPS_ID_PATTERN are treated as a gramps_id and
    resolved; anything else is treated as an already-valid handle.

    Args:
        client: Gramps API client instance
        tree_id: Family tree identifier
        value: Handle or gramps_id string

    Returns:
        A resolved handle

    Raises:
        ValueError: If value looks like a gramps_id but no matching family
            is found
    """
    if GRAMPS_ID_PATTERN.match(value):
        handle = await resolve_family_handle(client, tree_id, value)
        if not handle:
            raise ValueError(f"No family found with gramps_id '{value}'")
        return handle
    return value


@with_client
async def get_relationship_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Calculate the relationship between two people.
    """
    try:
        person1 = arguments.get("person1")
        person2 = arguments.get("person2")
        all_relationships = arguments.get("all_relationships", False)
        depth = arguments.get("depth")

        if not person1 or not person2:
            raise ValueError("person1 and person2 are required")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        handle1 = await _resolve_person(client, tree_id, person1)
        handle2 = await _resolve_person(client, tree_id, person2)

        params = RelationParams(handle1=handle1, handle2=handle2, depth=depth)

        api_call = (
            ApiCalls.GET_RELATIONS_ALL if all_relationships else ApiCalls.GET_RELATIONS
        )

        result = await client.make_api_call(
            api_call=api_call,
            params=_RelationsQueryParams(depth=params.depth),
            tree_id=tree_id,
            handle1=handle1,
            handle2=handle2,
        )

        if all_relationships:
            formatted = await format_relationships(result, client, tree_id)
        else:
            formatted = format_relationship(result)

        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, "relationship calculation")


@with_client
async def check_living_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Check whether a person is living and get estimated birth/death dates.
    """
    try:
        person = arguments.get("person")
        include_dates = arguments.get("include_dates", True)

        if not person:
            raise ValueError("person is required")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        handle = await _resolve_person(client, tree_id, person)

        params = LivingParams(
            handle=handle,
            average_generation_gap=arguments.get("average_generation_gap"),
            max_age_probably_alive=arguments.get("max_age_probably_alive"),
            max_sibling_age_difference=arguments.get("max_sibling_age_difference"),
        )

        query_params = _LivingQueryParams(
            average_generation_gap=params.average_generation_gap,
            max_age_probably_alive=params.max_age_probably_alive,
            max_sibling_age_difference=params.max_sibling_age_difference,
        )

        living_result = await client.make_api_call(
            api_call=ApiCalls.GET_LIVING,
            params=query_params,
            tree_id=tree_id,
            handle=handle,
        )

        dates_result = None
        if include_dates:
            dates_result = await client.make_api_call(
                api_call=ApiCalls.GET_LIVING_DATES,
                params=query_params,
                tree_id=tree_id,
                handle=handle,
            )

        formatted = format_living_status(living_result, dates_result)
        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, "living status check")


@with_client
async def get_timeline_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Build a chronological timeline for a person, family, or group.
    """
    try:
        scope = arguments.get("scope")
        target = arguments.get("target")

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        if scope == "person":
            if not target:
                raise ValueError("target is required when scope is 'person'")
            handle = await _resolve_person(client, tree_id, target)
            person_params = PersonTimelineParams(
                dates=arguments.get("dates"),
                first=arguments.get("first"),
                last=arguments.get("last"),
                ancestors=None,
                offspring=None,
                events=arguments.get("events"),
                event_classes=arguments.get("event_classes"),
                relatives=None,
                relative_events=None,
                relative_event_classes=None,
                ratings=None,
                precision=None,
                discard_empty=None,
                omit_anchor=None,
                page=None,
                pagesize=None,
            )
            result = await client.make_api_call(
                api_call=ApiCalls.GET_PERSON_TIMELINE,
                params=person_params,
                tree_id=tree_id,
                handle=handle,
            )

        elif scope == "family":
            if not target:
                raise ValueError("target is required when scope is 'family'")
            handle = await _resolve_family(client, tree_id, target)
            family_params = FamilyTimelineParams(
                handle=handle,
                dates=arguments.get("dates"),
                events=arguments.get("events"),
                event_classes=arguments.get("event_classes"),
                ratings=arguments.get("ratings"),
                discard_empty=arguments.get("discard_empty"),
                page=arguments.get("page"),
                pagesize=arguments.get("pagesize"),
            )
            family_query_params = _FamilyTimelineQueryParams(
                dates=family_params.dates,
                events=family_params.events,
                event_classes=family_params.event_classes,
                ratings=family_params.ratings,
                discard_empty=family_params.discard_empty,
                page=family_params.page or None,
                pagesize=family_params.pagesize,
            )
            result = await client.make_api_call(
                api_call=ApiCalls.GET_FAMILY_TIMELINE,
                params=family_query_params,
                tree_id=tree_id,
                handle=handle,
            )

        elif scope == "people":
            anchor = None
            if target:
                anchor = await _resolve_person(client, tree_id, target)
            people_params = PeopleTimelineParams(
                anchor=anchor,
                dates=arguments.get("dates"),
                first=arguments.get("first", True),
                last=arguments.get("last", True),
                handles=arguments.get("handles"),
                events=arguments.get("events"),
                event_classes=arguments.get("event_classes"),
                ratings=arguments.get("ratings", False),
                precision=arguments.get("precision", 1),
                discard_empty=arguments.get("discard_empty", True),
                page=arguments.get("page", 0),
                pagesize=arguments.get("pagesize", 20),
            )
            people_query_params = _PeopleTimelineQueryParams(
                anchor=people_params.anchor,
                dates=people_params.dates,
                first=people_params.first,
                last=people_params.last,
                handles=people_params.handles,
                events=people_params.events,
                event_classes=people_params.event_classes,
                ratings=people_params.ratings,
                precision=people_params.precision,
                discard_empty=people_params.discard_empty,
                omit_anchor=people_params.omit_anchor,
                page=arguments.get("page") or None,
                pagesize=people_params.pagesize,
            )
            result = await client.make_api_call(
                api_call=ApiCalls.GET_TIMELINES_PEOPLE,
                params=people_query_params,
                tree_id=tree_id,
            )

        elif scope == "families":
            families_params = FamiliesTimelineParams(
                handles=arguments.get("handles"),
                dates=arguments.get("dates"),
                events=arguments.get("events"),
                event_classes=arguments.get("event_classes"),
                ratings=arguments.get("ratings", False),
                discard_empty=arguments.get("discard_empty", True),
                page=arguments.get("page", 0),
                pagesize=arguments.get("pagesize", 20),
            )
            families_query_params = _FamiliesTimelineQueryParams(
                handles=families_params.handles,
                dates=families_params.dates,
                events=families_params.events,
                event_classes=families_params.event_classes,
                ratings=families_params.ratings,
                discard_empty=families_params.discard_empty,
                page=arguments.get("page") or None,
                pagesize=families_params.pagesize,
            )
            result = await client.make_api_call(
                api_call=ApiCalls.GET_TIMELINES_FAMILIES,
                params=families_query_params,
                tree_id=tree_id,
            )

        else:
            raise ValueError(f"Invalid scope: {scope}")

        formatted = format_timeline(result)
        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        return _format_error_response(e, "timeline retrieval")
