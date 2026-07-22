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
Pure merge logic for PUT (update) operations.

Gramps Web API PUT requests replace the whole object. To preserve data the
caller did not mention, the client fetches the existing record and merges the
requested changes into it before sending. This module holds that merge logic
as a pure, side-effect-free function so it can be unit-tested without a live
server.
"""


def merge_put_data(existing: dict, changes: dict) -> dict:
    """
    Merge requested changes into an existing record for a PUT update.

    Keys ending in "_list" whose value is a list and which are present in
    the existing record are merged with deduplication; every other key in
    changes replaces the existing value. Neither input is mutated.

    Args:
        existing (Dict): The record currently stored in Gramps.
        changes (Dict): The fields the caller wants to change.

    Returns:
        Dict: A new dict containing the merged record.
    """
    merged = existing.copy()
    for key, value in changes.items():
        if key.endswith("_list") and isinstance(value, list) and key in existing:
            merged[key] = _merge_list(existing.get(key, []), value)
        else:
            merged[key] = value
    return merged


def _merge_list(existing_items: list, new_items: list) -> list:
    """
    Merge two lists, deduplicating when the item type supports it.

    Lists of dicts carrying a "ref" field (event_ref_list, media_list, ...)
    are deduplicated by ref; lists of strings by value. Existing items always
    come first. Mixed or unknown item types are concatenated as-is.

    Args:
        existing_items (List): Items already stored in Gramps.
        new_items (List): Items requested in the update.

    Returns:
        List: The merged list.
    """
    # Reason: if either side is empty there is nothing to deduplicate
    if not existing_items or not new_items:
        return existing_items + new_items

    sample_existing = existing_items[0]
    sample_new = new_items[0]

    if (
        isinstance(sample_existing, dict)
        and "ref" in sample_existing
        and isinstance(sample_new, dict)
        and "ref" in sample_new
    ):
        existing_refs = {
            item.get("ref") for item in existing_items if isinstance(item, dict)
        }
        additions = [
            item
            for item in new_items
            if isinstance(item, dict) and item.get("ref") not in existing_refs
        ]
        return existing_items + additions

    if isinstance(sample_existing, str) and isinstance(sample_new, str):
        existing_set = set(existing_items)
        return existing_items + [item for item in new_items if item not in existing_set]

    # Reason: mixed/unknown item types - concatenation is the safe fallback
    return existing_items + new_items
