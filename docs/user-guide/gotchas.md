# Things that will surprise you

These are the behaviours that catch people out. Read them before your first
data-entry session rather than after it - the first one in particular shapes
how carefully you should check a write before submitting it.

**Updates merge, and removal is possible through detach_reference.** A write is a read
followed by a full replacement, so the client fetches the current record and
merges your changes into it before sending. Fields you do not mention keep
their values, and any list you supply is added to what is already stored rather
than replacing it. That protects you from silently wiping data. When you do need
to remove an item from a list, use `detach_reference`; when you need to remove a
whole record, use `delete_type`. Still, check `child_handles`, `father_handle`
and `mother_handle` before submitting a family - while `detach_reference` can
remove a child, it is easier to add one by mistake than to remove it deliberately,
and the safer habit is to review the link before you commit.

The one escape hatch is `replace_lists` on `create_place`, which names list
fields to overwrite rather than add to - `replace_lists=["placeref_list"]` to
move a place to a different parent instead of giving it a second one.

**`get_type` does not error on an unknown identifier.** Ask for a
`gramps_id` that does not exist and you get a plain message saying no record
was found and suggesting `find_type`, not a failure. If the assistant reports
"no person found with I9999", that is the record being absent, not the server
being broken.

**Search results report the true total, not what you were shown.** The count in
"Found 312 people (showing 20)" comes from the server's own total-match header.
The number in the header is the size of the answer; the records below it are
one page of it. Use `page` to walk through the rest.

**Error messages carry a fragment of the server's explanation.** When Gramps
rejects a call, the message includes the server's own text - usually naming the
offending field, which is what makes the error actionable - truncated to 300
characters. The truncation is deliberate: Gramps echoes the submitted payload
on some errors, and that payload can hold genealogy data about living people.
A message ending in an ellipsis is not a bug.

**`tree_stats` fails even for an owner account.** It is registered, it takes an
`include_statistics` flag, and on the reference deployment it answers
"Permission denied for this operation" whatever role the configured account
holds. That is an environment fact about Gramps Web, not something wrong with
your setup, and no argument works around it. Use
[`get_facts`](searching.md#reading-a-record-in-depth) when you want tree-level
numbers.

## Partial updates merge, including inside nested objects

Before 2026-08-26, `merge_put_data` reasoned only about top-level keys whose
name ended in `_list`. A partial `primary_name` replaced the whole name
object, `urls` and `alt_names` were replaced outright, and a reference whose
`ref` already existed was dropped even when its role differed - so adding
someone to an event in a second role did nothing and reported success.

All of it is fixed. Dispatch is by value type rather than key name, nested
objects merge sub-key by sub-key, and a reference entry is identified by
`(ref, role, rect)`: a differing identity is appended, while a differing
attribute merges into the entry already stored.

A list nested inside an object is the one thing that still replaces rather
than merging. That is deliberate - unioning `primary_name.surname_list` would
make correcting a surname impossible, yielding both the old and the new.

If you need replace-outright behaviour for a specific top-level key, pass it
in `replace_lists`, which now covers nested objects as well as lists.
