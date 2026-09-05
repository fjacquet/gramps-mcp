# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2026 cabout.me
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

"""Fetch the tree and convert every record to facts."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from ..client import GrampsWebAPIClient
from ..models.api_calls import ApiCalls
from .domain import FamilyFacts, PersonFacts
from .facts import _LIST_PARAMS, family_from_json, person_from_json

logger = logging.getLogger(__name__)


@dataclass
class CollectResult:
    """One pass over the tree, with what it could not read stated explicitly."""

    people: list[PersonFacts] = field(default_factory=list)
    families: dict[str, FamilyFacts] = field(default_factory=dict)
    skipped: int = 0
    partial: bool = False
    error: str | None = None


# Reason: 500 rows is what a live probe returned in seconds where the
# unbounded read never came back. The rows are heavy - `_LIST_PARAMS` asks
# for `profile=all` and extends `event_ref_list`, so one person carries
# every event it references - which is why the page has to be this small
# and why the whole tree cannot be asked for at once.
_PAGE_SIZE = 500


async def _fetch_every_page(
    client: GrampsWebAPIClient,
    api_call: ApiCalls,
    tree_id: str,
    base_params: dict[str, str | int],
) -> list[dict]:
    """Read a list endpoint page by page until it runs out of rows.

    Asking for a whole tree in one request is what made `find_duplicates`
    time out and then report "None found" over a scan that had read
    nothing: 2141 people with `profile=all` exceed the client timeout,
    while the same rows fetched 500 at a time return in seconds.

    Args:
        client (GrampsWebAPIClient): Client to issue the reads with.
        api_call (ApiCalls): List endpoint to page through.
        tree_id (str): Family tree identifier.
        base_params (dict[str, str | int]): Query parameters common to
            every page; `page` and `pagesize` are added per request.

    Returns:
        list[dict]: Every row the endpoint returned, in order.

    Raises:
        Exception: Whatever the client raises. Callers gather this with
            `return_exceptions=True` so a failure on one endpoint leaves
            the other's rows intact and only marks the scan partial.
    """
    rows: list[dict] = []
    page = 1
    while True:
        params = dict(base_params)
        params["page"] = page
        params["pagesize"] = _PAGE_SIZE
        batch = await client.make_api_call(
            api_call=api_call, params=params, tree_id=tree_id
        )
        rows.extend(batch)
        # Reason: a short page means the end of the collection. Stopping
        # only on an empty page would cost one extra round trip per scan,
        # and stopping on a full one would silently truncate a tree whose
        # size is an exact multiple of the page.
        if len(batch) < _PAGE_SIZE:
            return rows
        page += 1


async def collect_tree(
    client: GrampsWebAPIClient, tree_id: str, limit: int | None = None
) -> CollectResult:
    """Fetch every person and family, converted to facts.

    People and families are independent reads on the same
    `httpx.AsyncClient`, so both requests are issued concurrently via
    `asyncio.gather` rather than one after the other.

    Args:
        client (GrampsWebAPIClient): Client to issue the reads with.
        tree_id (str): Family tree identifier.
        limit (int | None): Stop after this many people. Cheap when set:
            `_LIST_PARAMS` already sorts by `gramps_id`, and the underlying
            API only honours `pagesize` when `page` is also given (see
            `tools/analysis.py`'s `_normalize_page_and_sort` docstring for
            the same rule elsewhere), so passing both bounds the request
            itself to `limit` rows instead of downloading and parsing
            everyone first - a live probe measured a 95x smaller transfer
            (10 rows / 158 KB vs. 1736 rows / 15 MB) for `limit=10` against
            the full tree. The client-side slice below is kept anyway as a
            belt-and-braces guard: if the API ever ignores `pagesize`/`page`
            again, the report is still bounded to `limit` people rather than
            silently growing back to the whole tree. `limit` bounds people
            only - families are always fetched whole, since there is no
            per-family bound to apply. `limit=None` (the default) keeps
            everyone; any other value must be >= 1, enforced by the
            parameter models (`FindDuplicatesParams`/`AuditQualityParams`)
            that construct it - `0` and negative values are rejected before
            they reach here, so this function does not need to
            special-case them itself, but `is not None` (rather than
            truthiness) is still used below in case a caller ever passes
            `limit=0` directly.

    Returns:
        CollectResult: The facts, plus how many records were unreadable and
            whether the pass completed.
    """
    out = CollectResult()

    people_params: dict[str, str | int] = dict(_LIST_PARAMS)
    if limit is not None:
        people_params["pagesize"] = limit
        people_params["page"] = 1

    # Reason: a partial scan that renders like a complete one is the failure
    # that matters here - "no duplicates found" over half a tree reads as a
    # clean bill of health. Every early exit leaves partial=True/error set.
    # return_exceptions=True so a failure on one read does not discard facts
    # already fetched on the other - the same "keep what was read" behaviour
    # the previous sequential version had for free.
    # Reason: `limit` already bounds the request to one short page, so it
    # keeps the single cheap read described above; only the unbounded scan
    # needs paging.
    people_read = (
        client.make_api_call(
            api_call=ApiCalls.GET_PEOPLE, params=people_params, tree_id=tree_id
        )
        if limit is not None
        else _fetch_every_page(client, ApiCalls.GET_PEOPLE, tree_id, people_params)
    )
    results: tuple[Any, Any] = await asyncio.gather(
        people_read,
        _fetch_every_page(client, ApiCalls.GET_FAMILIES, tree_id, dict(_LIST_PARAMS)),
        return_exceptions=True,
    )
    raw_people_result, raw_families_result = results

    if isinstance(raw_people_result, BaseException):
        out.partial = True
        out.error = str(raw_people_result)
    else:
        raw_people = raw_people_result
        for raw in raw_people[:limit] if limit is not None else raw_people:
            try:
                person = person_from_json(raw)
                # Reason: person_from_json defaults every field via dict.get,
                # so it never raises on a malformed record - it silently
                # returns an empty-shell PersonFacts instead. A record
                # missing either identifier is not a real person entry;
                # count it as unreadable rather than let it through. This
                # must mirror the family check below: the next task keys a
                # dict on `.handle` (`by_handle = {p.handle: p for p in
                # collected.people}`), and two people with handle="" would
                # collapse into one entry there, naming the wrong person in
                # a merge proposal.
                if not person.gramps_id or not person.handle:
                    raise ValueError("record has no gramps_id/handle")
                out.people.append(person)
            except Exception:
                out.skipped += 1
                logger.debug("unreadable person record: %s", raw.get("handle"))

    if isinstance(raw_families_result, BaseException):
        out.partial = True
        if out.error is None:
            out.error = str(raw_families_result)
    else:
        raw_families = raw_families_result
        for raw in raw_families:
            try:
                family = family_from_json(raw)
                if not family.gramps_id or not family.handle:
                    raise ValueError("record has no gramps_id/handle")
                out.families[family.handle] = family
            except Exception:
                out.skipped += 1
                logger.debug("unreadable family record: %s", raw.get("handle"))

    return out
