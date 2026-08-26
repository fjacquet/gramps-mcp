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


def merge_put_data(
    existing: dict, changes: dict, replace_lists: list[str] | None = None
) -> dict:
    """
    Merge requested changes into an existing record for a PUT update.

    Lists are merged with deduplication (unless replace_lists says otherwise),
    dicts merge recursively by sub-key, and everything else replaces the
    existing value. Neither input is mutated.

    Args:
        existing (Dict): The record currently stored in Gramps.
        changes (Dict): The fields the caller wants to change.
        replace_lists (List | None): Keys whose lists should be replaced
            outright rather than merged. Everything else keeps the default
            union behaviour.

    Returns:
        Dict: A new dict containing the merged record.
    """
    replace = set(replace_lists or ())
    merged = existing.copy()
    for key, value in changes.items():
        # Reason: dispatch on the value being a list, not on the key's name.
        # urls and alt_names are writable lists whose names do not end in
        # _list; keying off the suffix sent them down the replace branch and
        # destroyed entries the caller never mentioned.
        if (
            isinstance(value, list)
            and isinstance(existing.get(key), list)
            and key not in replace
        ):
            merged[key] = _merge_list(existing.get(key, []), value)
        # Reason: primary_name is required on PersonData, so it is resent on
        # every person update - including ones that have nothing to do with
        # the name. Replacing it wholesale destroyed surname_list, suffix,
        # type and the name's own citations. replace_lists is honoured here
        # too, so an explicit replacement is still available per key.
        elif (
            isinstance(value, dict)
            and isinstance(existing.get(key), dict)
            and key not in replace
        ):
            merged[key] = _merge_dict(existing[key], value)
        else:
            merged[key] = value
    return merged


def _merge_dict(existing_value: dict, new_value: dict) -> dict:
    """
    Merge a DESCRIPTIVE nested object (e.g. primary_name, a place's date).

    A descriptive object states its content rather than accumulating it, so
    a nested dict merges but a nested list replaces, one level down,
    recursively. Sub-keys the caller does not mention are always preserved.

    Args:
        existing_value (dict): The nested object currently stored in Gramps.
        new_value (dict): The sub-keys the caller wants to change.

    Returns:
        dict: A new dict containing the merged object.
    """
    merged = existing_value.copy()
    for key, value in new_value.items():
        current = existing_value.get(key)
        # Reason: a nested dict merges, but a nested LIST replaces. A list
        # inside a descriptive object is stated, not appended to - unioning
        # surname_list would make correcting a surname impossible, yielding
        # both the old and the new. Only unmentioned sub-keys are preserved.
        if isinstance(value, dict) and isinstance(current, dict):
            merged[key] = _merge_dict(current, value)
        else:
            merged[key] = value
    return merged


def _merge_ref_entry(existing_entry: dict, new_entry: dict) -> dict:
    """
    Merge a REFERENCE-list entry (e.g. one media_list/event_ref_list item).

    A reference entry mixes in CitationBase/NoteBase/AttributeBase: its
    citation_list, note_list and attribute_list accumulate just like the
    top-level lists, unlike a descriptive object's stated content. So this
    applies the TOP-LEVEL rule one level down, recursively - nested list
    merges via _merge_list, nested dict merges via _merge_dict, else
    replaces - instead of _merge_dict's replace-nested-lists rule.

    Args:
        existing_entry (dict): The reference entry currently stored.
        new_entry (dict): The sub-keys the caller wants to change.

    Returns:
        dict: A new dict containing the merged entry.
    """
    merged = existing_entry.copy()
    for key, value in new_entry.items():
        current = existing_entry.get(key)
        if isinstance(value, list) and isinstance(current, list):
            merged[key] = _merge_list(current, value)
        elif isinstance(value, dict) and isinstance(current, dict):
            merged[key] = _merge_dict(current, value)
        else:
            merged[key] = value
    return merged


def _merge_list(existing_items: list, new_items: list) -> list:
    """
    Merge two lists, deduplicating when the item type supports it.

    Dicts with a "ref" field (event_ref_list, media_list, ...) are
    deduplicated by identity (ref, role, rect); matching identity merges
    new attributes over the existing entry in place. Dicts without "ref"
    (attribute_list, ...) deduplicate by whole content, and strings by
    value. Existing order is preserved. Mixed or unknown item types are
    concatenated as-is.

    Args:
        existing_items (List): Items already stored in Gramps.
        new_items (List): Items requested in the update.

    Returns:
        List: The merged list.
    """
    if not existing_items and not new_items:
        return []

    # Reason: a ref-less dict update can arrive with no existing list to
    # merge against (e.g. the first attribute_list update on a record), but
    # the incoming list itself can still carry the same dict twice. That
    # case needs the same whole-content dedup as the non-empty path below,
    # so it is routed there instead of the plain-concatenation shortcut.
    if not existing_items:
        sample_new = new_items[0]
        if isinstance(sample_new, dict) and "ref" not in sample_new:
            return _dedupe_dicts_without_ref(existing_items, new_items)
        return existing_items + new_items

    # Reason: if there is nothing new, there is nothing to deduplicate
    if not new_items:
        return existing_items + new_items

    sample_existing = existing_items[0]
    sample_new = new_items[0]

    if (
        isinstance(sample_existing, dict)
        and "ref" in sample_existing
        and isinstance(sample_new, dict)
        and "ref" in sample_new
    ):
        # Reason: identity for reference entries is (ref, role, rect) - the
        # fields Gramps uses to express multiplicity. Other keys are attributes
        # that update in place, not separate entries. Same person, same event,
        # different role is two entries. Same photo with different private flag
        # is one entry with updated metadata.
        identity_to_index = {
            _entry_key(item): i for i, item in enumerate(existing_items)
        }
        result = list(existing_items)
        for new_item in new_items:
            identity = _entry_key(new_item)
            if identity in identity_to_index:
                # Merge new attributes over existing entry at this position
                idx = identity_to_index[identity]
                if isinstance(result[idx], dict) and isinstance(new_item, dict):
                    # Reason: a shallow spread here replaced a nested dict or
                    # list (e.g. a placeref_list "date", a media_list
                    # citation_list) wholesale - the exact destructive
                    # behaviour this module exists to kill, one level deeper.
                    # _merge_ref_entry applies the top-level, accumulative
                    # rule, not _merge_dict's descriptive-object one.
                    result[idx] = _merge_ref_entry(result[idx], new_item)
            else:
                # New identity, append as new entry
                result.append(new_item)
                identity_to_index[identity] = len(result) - 1
        return result

    if isinstance(sample_existing, str) and isinstance(sample_new, str):
        existing_set = set(existing_items)
        return existing_items + [item for item in new_items if item not in existing_set]

    if isinstance(sample_existing, dict) and isinstance(sample_new, dict):
        # Reason: attribute_list entries are {type, value} dicts with no ref,
        # so they miss the ref branch above. Without this they concatenate,
        # and N identical updates leave N copies.
        return _dedupe_dicts_without_ref(existing_items, new_items)

    # Reason: mixed/unknown item types - concatenation is the safe fallback
    return existing_items + new_items


def _freeze(value: object) -> object:
    """
    Canonicalise a JSON value into a hashable form, recursively.

    Args:
        value (object): Any JSON-shaped value - dict, list, scalar, or None.

    Returns:
        object: value itself if already hashable-shaped; a dict becomes a
        tuple of its (key, frozen value) pairs sorted by key, a list
        becomes a tuple of frozen elements.
    """
    # Reason: identity must be TOTAL over server-shaped JSON, not merely
    # hashable - a try/hash-except fallback keyed on the whole entry instead
    # changes the KIND of key on the unhashable path (attributes like
    # "private" leak into identity), reintroducing the duplicate-attachment
    # defect this module exists to kill.
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def _entry_key(item: dict | str | list) -> object:
    """
    Build an identity key for a reference-list entry.

    Args:
        item: One element of a reference list, normally a dict.

    Returns:
        object: A hashable key based on ref, role, and rect only, each
        passed through _freeze. Missing fields contribute None, and falsy
        values (the server sends "role": [] rather than omitting the key)
        are normalised to None first, so that shape and the documented
        {"ref": ...}-only shape share one identity instead of being treated
        as different entries.
    """
    # Reason: identity must distinguish structural cases (same person in
    # different roles, or same photo with different crop regions), while
    # treating metadata changes (private flag) as updates to the same entry,
    # not duplicates to discard or append.
    if isinstance(item, dict):
        ref = item.get("ref")
        role = _freeze(item.get("role") or None)
        rect = _freeze(item.get("rect") or None)
        return (_freeze(ref), role, rect)
    return (_freeze(item), None, None)


def _dedupe_dicts_without_ref(existing_items: list, new_items: list) -> list:
    """
    Append new ref-less dict items, deduplicating on whole content.

    Deduplicates each incoming item against both the existing items and
    the items already accepted from this same incoming list, so a single
    update carrying the same dict twice only stores it once.

    Args:
        existing_items (List): Items already stored in Gramps.
        new_items (List): Items requested in the update.

    Returns:
        List: existing_items followed by the deduplicated additions.
    """
    seen = list(existing_items)
    additions = []
    for item in new_items:
        if isinstance(item, dict) and item not in seen:
            additions.append(item)
            seen.append(item)
    return existing_items + additions
