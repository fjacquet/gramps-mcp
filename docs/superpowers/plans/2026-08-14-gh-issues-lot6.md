# Lot 6 - Closing issues #12, #13, #16, #17 - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close four open GitHub issues: stop a test from silently growing
the live genealogy tree, make the parameter models refuse unknown keys
instead of dropping them, let `create_sourced_event` reuse an existing
source, and settle two false promises (three unsatisfiable media assertions
and a usage-guide field that no model declares).

**Architecture:** A new `StrictModel` base class in `base_params.py` carries
`extra="forbid"`, and every write-path parameter model inherits it. No
fields are added to any model except `abbrev` on `SourceSaveParams`, which
issue #17 requires. `create_sourced_event` gains an optional `source_handle`
and refuses to create a source whose title already exists, rather than
guessing which of two identically-titled documents the caller meant.

**Tech Stack:** Python 3.12+, Pydantic v2, httpx, MCP Python SDK, pytest +
pytest-asyncio, uv, ruff, pre-commit.

**Spec:** `docs/superpowers/specs/2026-08-14-gh-issues-lot6-design.md`

## Global Constraints

- **Every command runs through uv.** `uv run pytest`, `uv run git commit`
  (so pre-commit hooks find a Python), `uv run mypy src/gramps_mcp
  --ignore-missing-imports`. A bare `git commit` fails this repo's
  `check-no-emojis` hook with "Executable `python` not found".
- **Live tests need an env override when run from the macOS host:**
  `GRAMPS_API_URL=http://localhost:80 uv run pytest ...`. The `.env` value
  points at `host.docker.internal`, which only resolves inside the
  container. **Do not edit `.env` and do not commit the override.**
- **Offline selection:** `uv run pytest -m "not integration"` is green and
  must stay green.
- **No file may exceed 500 lines**, tests included -
  `.pre-commit-config.yaml`'s `check-file-length` hook covers the whole tree.
- **No emojis anywhere in the repo.** Enforced by a pre-commit hook.
- **Google-style docstrings on every function.** Type hints throughout.
- **Never use `git stash`.** Compare against main with `git show main:<path>`.
- **TDD:** write the failing test, watch it fail, then implement.
- **`tree_stats` returning "Permission denied for this operation" is an
  environment fact, not a regression.**
- Branch for this work: `fix/quality-lot6-issues` (cut from
  `docs/spec-lot6-issues`, which carries the spec).

## Deviation from the spec, stated up front

The spec asks for four commits, with the `extra="forbid"` change and the
`abbrev` addition **in the same commit**, so no released version describes a
parameter the server rejects. This plan uses **five commits**: Task 2
(hardening) and Task 3 (`abbrev`) are separate commits that ship in the same
branch and the same pull request. The spec's requirement is met - there is no
released window between them - and each commit stays reviewable on its own.
If you would rather honour the spec literally, skip Task 2's commit step and
let Task 3's commit cover both.

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `src/gramps_mcp/models/parameters/base_params.py` | modify | Gains `StrictModel`; `BaseDataModel` inherits it |
| `src/gramps_mcp/models/parameters/{place,family,event,note,media,tag,sourced_event,date}_params.py` | modify | Swap base class to `StrictModel` |
| `src/gramps_mcp/models/parameters/people_params.py` | modify | `EventReference` inherits `StrictModel` |
| `src/gramps_mcp/models/parameters/source_params.py` | modify | Gains `abbrev` |
| `src/gramps_mcp/models/parameters/sourced_event_params.py` | modify | Gains `source_handle` + exclusivity validator |
| `src/gramps_mcp/utils.py` | modify | Gains `resolve_source_handles_by_title` |
| `src/gramps_mcp/tools/sourced_event.py` | modify | Source reuse; gramps_id in the media line |
| `tests/test_strict_params.py` | create | Offline: unknown keys are refused |
| `tests/test_workflow_marriage.py` | modify | #16 |
| `tests/test_create_sourcing.py` | modify | #13, #12, #17 |
| `tests/test_alignment_sourcing.py` | modify | `abbrev` in the inventory |

---

### Task 1: Fix the marriage workflow test (#16)

The test passes five keys `PersonData` does not declare
(`event_handle`, `event_role`, `note_handle`, `media_handle`, `url`) and a
name shape (`given_name`/`surname`) no formatter reads. All are dropped. It
has run 18 times and left 36 nameless people in the live tree.

**Files:**
- Modify: `tests/test_workflow_marriage.py:440-471`
- Test: the same file (this task's deliverable *is* a test)

**Interfaces:**
- Consumes: `create_person_tool(arguments: dict) -> list[TextContent]` from
  `src.gramps_mcp.tools.data_management`; `extract_handle(create_result)`
  from `tests.workflow_helpers`.
- Produces: nothing other tasks consume.

**Reference - the exact shapes involved.** `PersonData`
(`people_params.py:44-64`) declares `primary_name`, `gender`,
`event_ref_list`, `family_list`, `parent_family_list`, `urls`, plus
`BaseDataModel`'s `handle`, `gramps_id`, `note_list`, `media_list`,
`attribute_list`, `tag_list`, `private`, `change`. The name shape that
formatters read, from `tests/conftest.py:210-232`:

```python
primary_name={"first_name": "Pytest Lot5", "surname_list": [{"surname": "Father"}]}
```

`primary_name` and `gender` are both **required** (`...`). This matters for
the update branch - see step 3.

- [ ] **Step 1: Add the failing assertions to the create branch**

In `tests/test_workflow_marriage.py`, replace the block at lines 468-471:

```python
            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            return handle_match.group(1)
```

with:

```python
            create_text = create_result[0].text
            assert "Error:" not in create_text, (
                f"create_person_tool failed: {create_text}"
            )
            # The five keys this test used to pass were silently dropped by
            # Pydantic, so it went green while linking nothing. Assert the
            # links, not just the handle.
            assert f"{given_name} {surname}" in create_text, (
                f"Person was created without a name: {create_text}"
            )
            assert "Attached notes:" in create_text, (
                f"Research note was not linked: {create_text}"
            )
            assert "Attached media:" in create_text, (
                f"Portrait was not linked: {create_text}"
            )
            assert "Events:" in create_text, (
                f"Marriage event was not linked: {create_text}"
            )
            return extract_handle(create_result)
```

Add `extract_handle` to the existing `tests.workflow_helpers` import at
lines 37-41:

```python
from tests.workflow_helpers import (
    create_place_hierarchy,
    create_test_media,
    create_test_note,
    extract_handle,
)
```

Note: assert on `"Events:"` rather than on the role string. `person_handler.py:137-144`
renders `f"{event_type}, {role} ({event_gramps_id})"` from whatever the API
returns for `role`, which may be a normalised or wrapped value rather than
the literal `"groom"`. The section header is the stable signal.

- [ ] **Step 2: Run it and watch it fail**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest \
  tests/test_workflow_marriage.py::TestCompleteWorkflow::test_complete_marriage_record_workflow -xvs
```

Expected: FAIL on `Person was created without a name` - the created person
has no name at all, so `"John Smith"` is absent from the output.

- [ ] **Step 3: Fix both call sites**

Replace the create call (lines 452-466) with:

```python
            create_result = await create_person_tool(
                {
                    "primary_name": {
                        "first_name": given_name,
                        "surname_list": [{"surname": surname}],
                    },
                    "gender": gender,
                    "note_list": [person_note_handle],
                    "media_list": [{"ref": person_media_handle}],
                    "urls": [
                        {
                            "type": "Website",
                            "path": (
                                "https://findagrave.com/memorial/"
                                f"{given_name.lower()}-{surname.lower()}"
                            ),
                            "description": (
                                f"Find A Grave memorial for {given_name} {surname}"
                            ),
                        }
                    ],
                    "event_ref_list": [{"ref": event_handle, "role": event_role}],
                }
            )
```

Replace the update call (lines 442-448) with:

```python
            update_result = await create_person_tool(
                {
                    "handle": existing_handle,
                    # primary_name and gender are required on PersonData, so a
                    # partial update must resupply them. The old call passed
                    # only handle plus two undeclared keys, which left the
                    # model missing both required fields - it raised, the tool
                    # swallowed it into an "Error:" string, and nothing
                    # asserted on the result.
                    "primary_name": {
                        "first_name": given_name,
                        "surname_list": [{"surname": surname}],
                    },
                    "gender": gender,
                    "event_ref_list": [{"ref": event_handle, "role": event_role}],
                }
            )
            update_text = update_result[0].text
            assert "Error:" not in update_text, (
                f"create_person_tool update failed: {update_text}"
            )
            assert "Events:" in update_text, (
                f"Marriage event was not linked on update: {update_text}"
            )
            return existing_handle
```

- [ ] **Step 4: Run the test twice in a row**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest \
  tests/test_workflow_marriage.py -xvs
GRAMPS_API_URL=http://localhost:80 uv run pytest \
  tests/test_workflow_marriage.py -xvs
```

Expected: PASS both times. The second run must take the **update** branch,
not the create branch - that is the proof the leak is closed. Confirm with:

```bash
uv run python -c "
import asyncio
from src.gramps_mcp.tools.search_basic import find_person_tool
print(asyncio.run(find_person_tool({'query': 'John Smith 1850 Boston', 'pagesize': 5}))[0].text)
"
```

Expected: John Smith appears with a name. If the count of nameless people
grew, the create branch ran again and step 3 is incomplete.

- [ ] **Step 5: Check the file length**

```bash
wc -l tests/test_workflow_marriage.py
```

If over 500, move `_create_or_find_person_with_attributes` into
`tests/workflow_helpers.py` next to the existing `create_or_find_person`,
import it in the test module, and call it as a plain function rather than a
method.

- [ ] **Step 6: Commit**

```bash
uv run git add tests/test_workflow_marriage.py tests/workflow_helpers.py
uv run git commit -m "fix: link the people the marriage workflow test claims to link

The test passed event_handle, event_role, note_handle, media_handle and url
to create_person_tool. PersonData declares none of them, so Pydantic's
default extra=\"ignore\" dropped all five before the request was built. It
passed the name as primary_name={given_name, surname}, a shape no formatter
reads, so the people it created had no name at all.

Nameless people cannot be matched by find_person_tool, so the find-or-create
branch always created, and every run of the suite added two people, a family,
a note and a media object to the live tree. Eighteen runs did so.

Closes #16"
```

---

### Task 2: Refuse unknown keys on the write models (root cause)

**Files:**
- Create: `tests/test_strict_params.py`
- Modify: `src/gramps_mcp/models/parameters/base_params.py:149-169`
- Modify: `place_params.py:47`, `family_params.py:32`, `event_params.py:59`,
  `note_params.py:60`, `media_params.py:54`, `tag_params.py:43,55`,
  `sourced_event_params.py:32`, `date_params.py:35`, `people_params.py:37`
  (all under `src/gramps_mcp/models/parameters/`)

**Interfaces:**
- Produces: `StrictModel` in
  `src.gramps_mcp.models.parameters.base_params` - a `BaseModel` subclass
  with `model_config = {"extra": "forbid", "populate_by_name": True}` and no
  fields. Tasks 3 and 4 rely on the models below already refusing unknown
  keys.

- [ ] **Step 1: Write the failing offline test**

Create `tests/test_strict_params.py`:

```python
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
Offline tests: write-path parameter models refuse unknown keys.

Pydantic's default extra="ignore" dropped undeclared keys silently, so a
caller could pass a misspelled or invented field, get a success response, and
have the data never reach Gramps. These tests need no server: they exercise
model validation only.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.date_params import DateValue
from src.gramps_mcp.models.parameters.event_params import EventSaveParams
from src.gramps_mcp.models.parameters.family_params import FamilySaveParams
from src.gramps_mcp.models.parameters.media_params import MediaSaveParams
from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
from src.gramps_mcp.models.parameters.people_params import (
    EventReference,
    PersonData,
)
from src.gramps_mcp.models.parameters.place_params import PlaceSaveParams
from src.gramps_mcp.models.parameters.source_params import SourceSaveParams
from src.gramps_mcp.models.parameters.sourced_event_params import (
    SourcedEventData,
)
from src.gramps_mcp.models.parameters.tag_params import (
    ManageTagsParams,
    TagSaveParams,
)

HANDLE = "103f77fe86ec4c13f3fac1a420ec"

# (model, minimal valid kwargs) - the unknown key is added per test.
STRICT_MODELS = [
    (
        PersonData,
        {
            "primary_name": {
                "first_name": "Test",
                "surname_list": [{"surname": "Person"}],
            },
            "gender": 1,
        },
    ),
    (SourceSaveParams, {"title": "A Source"}),
    (EventSaveParams, {"type": "Birth", "citation_list": [HANDLE]}),
    (PlaceSaveParams, {"name": {"value": "Lyon"}}),
    (FamilySaveParams, {"father_handle": HANDLE}),
    (NoteSaveParams, {"text": "hello", "type": "General"}),
    (MediaSaveParams, {"desc": "a photo", "media_path": "tests/sample/x.jpg"}),
    (TagSaveParams, {"name": "Lot6"}),
    (ManageTagsParams, {"action": "list"}),
    (
        SourcedEventData,
        {"source_title": "A Register", "event_type": "Death"},
    ),
    (DateValue, {"dateval": [1, 1, 1900, False]}),
    (EventReference, {"ref": HANDLE, "role": "Primary"}),
]


@pytest.mark.parametrize(
    "model,valid_kwargs", STRICT_MODELS, ids=lambda v: getattr(v, "__name__", "")
)
def test_write_model_accepts_its_declared_fields(model, valid_kwargs):
    """The minimal valid payload must still build, so the test below is
    proving strictness rather than a broken fixture."""
    assert model(**valid_kwargs) is not None


@pytest.mark.parametrize(
    "model,valid_kwargs", STRICT_MODELS, ids=lambda v: getattr(v, "__name__", "")
)
def test_write_model_refuses_unknown_key(model, valid_kwargs):
    """An undeclared key must raise, not be dropped."""
    with pytest.raises(ValidationError) as exc_info:
        model(**valid_kwargs, definitely_not_a_field="x")
    assert "definitely_not_a_field" in str(exc_info.value)


def test_person_data_refuses_the_keys_issue_16_used():
    """The five keys the marriage workflow test passed for months."""
    for bad_key in (
        "event_handle",
        "event_role",
        "note_handle",
        "media_handle",
        "url",
    ):
        with pytest.raises(ValidationError):
            PersonData(
                primary_name={
                    "first_name": "Test",
                    "surname_list": [{"surname": "Person"}],
                },
                gender=1,
                **{bad_key: "x"},
            )
```

- [ ] **Step 2: Run it and watch it fail**

```bash
uv run pytest tests/test_strict_params.py -v
```

Expected: the `accepts_its_declared_fields` tests PASS, every
`refuses_unknown_key` test FAILS with `DID NOT RAISE
<class 'pydantic_core.ValidationError'>`.

- [ ] **Step 3: Add `StrictModel` and rebase `BaseDataModel` on it**

In `src/gramps_mcp/models/parameters/base_params.py`, insert before
`class BaseDataModel` (currently line 149):

```python
class StrictModel(BaseModel):
    """
    Base for write-path models: refuse unknown keys instead of dropping them.

    Pydantic's default is extra="ignore", which silently discards any key a
    model does not declare. On a write that means an incomplete record
    reaches Gramps while the call reports success - the failure mode behind
    issues #16 and #17. Read-path models keep the permissive default: a
    dropped key there only widens a result set.
    """

    model_config = {"extra": "forbid", "populate_by_name": True}
```

Then change line 149 and delete the now-redundant config at line 169:

```python
class BaseDataModel(StrictModel):
    """Base class for data models used in POST/PUT operations."""
```

and remove `    model_config = {"populate_by_name": True}` from the end of
`BaseDataModel` - it is inherited from `StrictModel`.

- [ ] **Step 4: Swap the base class in each write model**

Exact edits, file by file. Import changes matter: ruff fails on an unused
`BaseModel` import.

`place_params.py` - line 30 becomes
`from pydantic import Field, field_validator`, line 32 becomes
`from .base_params import BaseGetMultipleParams, BaseGetSingleParams, StrictModel`,
line 47 becomes `class PlaceSaveParams(StrictModel):`.
(`BaseModel` had no other user in this file.)

`family_params.py` - line 29 becomes
`from pydantic import BaseModel, Field` (unchanged; `FamilyTimelineParams`
still uses it), add `from .base_params import StrictModel`, line 32 becomes
`class FamilySaveParams(StrictModel):`.

`event_params.py` - keep the `BaseModel` import (`EventSpanParams` uses it),
line 33 becomes
`from .base_params import BaseGetMultipleParams, StrictModel`, line 59
becomes `class EventSaveParams(StrictModel):`.

`note_params.py` - line 29 becomes `from pydantic import Field`, line 31
becomes
`from .base_params import BaseGetMultipleParams, BaseGetSingleParams, StrictModel`,
line 60 becomes `class NoteSaveParams(StrictModel):`. Leave the
`model_dump` override at lines 70-83 untouched.

`media_params.py` - keep the `BaseModel` import (`MediaFileParams` uses it),
line 32 becomes `from .base_params import BaseGetMultipleParams, StrictModel`,
line 54 becomes `class MediaSaveParams(StrictModel):`. **Leave
`MediaFileParams` on `BaseModel`** - it is the one nested model on a read
path (`GET_MEDIA_FILE`).

`tag_params.py` - keep the `BaseModel` import (`TagSearchParams` uses it),
add `from .base_params import StrictModel`, line 43 becomes
`class TagSaveParams(StrictModel):` and line 55 becomes
`class ManageTagsParams(StrictModel):`.

`sourced_event_params.py` - line 26 becomes
`from pydantic import Field, field_validator`, add
`from .base_params import StrictModel`, line 32 becomes
`class SourcedEventData(StrictModel):`.

`date_params.py` - line 21 becomes
`from pydantic import Field, model_validator`, add
`from .base_params import StrictModel`, line 35 becomes
`class DateValue(StrictModel):`.

`people_params.py` - keep the `BaseModel` import
(`PersonTimelineParams`, `PersonDnaMatchesParams` use it), line 34 becomes
`from .base_params import BaseDataModel, StrictModel`, line 37 becomes
`class EventReference(StrictModel):`. `PersonData` already inherits
`BaseDataModel` and needs no change.

- [ ] **Step 5: Run the offline suite**

```bash
uv run pytest tests/test_strict_params.py -v
uv run pytest -m "not integration"
uv run mypy src/gramps_mcp --ignore-missing-imports
```

Expected: `tests/test_strict_params.py` fully PASS; the whole offline
selection PASS; mypy clean.

- [ ] **Step 6: Inventory the fallout across the live suite**

This is the step the spec flagged as being of unknown size. Undeclared keys
that used to be dropped now raise.

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest -m integration 2>&1 \
  | tee /tmp/lot6-integration.txt
grep -c "Extra inputs are not permitted" /tmp/lot6-integration.txt
grep -B5 "Extra inputs are not permitted" /tmp/lot6-integration.txt
```

Redirect to a file rather than piping - a pipe loses lines here.

`tests/test_workflow_attributes.py::test_source_attributes` is already known
to pass five keys `SourceSaveParams` does not declare, `abbreviation` among
them. Fix each failure by correcting the key to the declared name, using
`src/gramps_mcp/models/parameters/` as the reference for what each model
accepts. `abbreviation` is a special case: leave that call failing and let
**Task 3** resolve it, since the field name in the guide is `abbrev`.

**If more than roughly ten call sites fail, stop and report before fixing
them all** - that is a materially larger change than this plan scoped, and
the user asked to be told rather than have the commit grow silently.

- [ ] **Step 7: Commit**

```bash
uv run git add src/gramps_mcp/models/parameters/ tests/test_strict_params.py
uv run git commit -m "feat: refuse unknown keys on the write-path models

The parameter models carried Pydantic's default extra=\"ignore\", so any key
a model did not declare was dropped before the request was built. The call
succeeded and nothing reported it, which is how a test could claim to link
five things while linking none (#16) and how the shipped usage guide could
offer a field no model accepts (#17).

StrictModel carries extra=\"forbid\" and every write-path model now inherits
it, directly or through BaseDataModel. No fields are added to any model.
Read-path models keep the permissive default: a dropped key there only
widens a result set, it does not write an incomplete record.

The published MCP schemas gain additionalProperties: false, so clients see
the constraint rather than only the server enforcing it."
```

---

### Task 3: `abbrev` on sources (#17)

`gramps-usage-guide.md:186` tells the assistant it may pass `abbrev` when
creating a source. `SourceSaveParams` does not declare it. After Task 2 that
key is refused rather than dropped, so the guide must become true or the
mention must go. Decide by test.

**Files:**
- Modify: `tests/test_create_sourcing.py` (add one test)
- Modify: `src/gramps_mcp/models/parameters/source_params.py:112-133`
- Modify: `tests/test_alignment_sourcing.py:96-101`
- Modify (fallback branch only):
  `src/gramps_mcp/resources/gramps-usage-guide.md:186`

**Interfaces:**
- Consumes: `StrictModel` behaviour from Task 2.
- Produces: `SourceSaveParams.abbrev: str | None` (branch A only).

- [ ] **Step 1: Write the deciding test**

Add to `tests/test_create_sourcing.py`, inside `class TestCreateSourceTool`:

```python
    @pytest.mark.asyncio
    async def test_create_source_with_abbrev(
        self, gramps_client, tree_id, repository_handle
    ):
        """abbrev survives a round trip through POST /sources.

        The shipped usage guide (gramps-usage-guide.md:186) offers abbrev on
        source creation. This test decides whether the guide is true: if the
        value comes back, the field belongs on SourceSaveParams; if it does
        not, the guide is wrong and the mention has to go.
        """
        result = await create_source_tool(
            {
                "title": f"{PREFIX} Abbrev Round Trip",
                "reporef_list": [{"ref": repository_handle}],
                "abbrev": "ARR",
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"

        source_handle = _handle_on_line(text, "Abbrev Round Trip")
        source_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_SOURCE,
            tree_id=tree_id,
            handle=source_handle,
        )
        assert source_data.get("abbrev") == "ARR", (
            "POST /sources did not store abbrev; got "
            f"{source_data.get('abbrev')!r}"
        )
```

Add the `ApiCalls` import at the top of the file if it is not already there
(the file currently imports it locally inside one test at line 320 - hoist it
to the module imports):

```python
from src.gramps_mcp.models.api_calls import ApiCalls
```

- [ ] **Step 2: Run it and watch it fail**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest \
  "tests/test_create_sourcing.py::TestCreateSourceTool::test_create_source_with_abbrev" -xvs
```

Expected: FAIL with a `ValidationError` naming `abbrev` as an extra input -
Task 2 made the model strict, so the key is refused before any request goes
out.

- [ ] **Step 3: Add the field**

In `src/gramps_mcp/models/parameters/source_params.py`, after `pubinfo`
(line 124):

```python
    abbrev: str | None = Field(
        None,
        description=(
            "Short abbreviation for the source, for example 'AD18 BB 1820'. "
            "Offered by the usage guide and stored on the Gramps Source "
            "object."
        ),
    )
```

- [ ] **Step 4: Run the test again**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest \
  "tests/test_create_sourcing.py::TestCreateSourceTool::test_create_source_with_abbrev" -xvs
```

**Branch A - PASS.** The guide was right. Continue to step 5.

**Branch B - FAIL on the round-trip assertion** (`abbrev` comes back `None`
or absent, meaning `POST /sources` ignores it). Then:
1. Revert step 3 - remove the field again.
2. In `src/gramps_mcp/resources/gramps-usage-guide.md:186`, change
   `optional author/pubinfo/abbrev/media/note handles` to
   `optional author/pubinfo/media/note handles`.
3. Replace the test with one asserting that `abbrev` is refused:
   `with pytest.raises(ValidationError): SourceSaveParams(title="x", abbrev="y")`,
   and move it into `tests/test_strict_params.py` where it runs offline.
4. Skip step 5, then commit with the message variant at the end of step 6.

- [ ] **Step 5: Update the alignment inventory (branch A only)**

In `tests/test_alignment_sourcing.py`, the `implementation_fields` set at
lines 96-101 becomes:

```python
        implementation_fields = required_fields | {
            "reporef_list",
            "author",
            "pubinfo",
            "abbrev",
            "media_path",
        }
```

Without this, `test_source_parameters_alignment` fails at line 116 with
`SourceSaveParams has extra fields: {'abbrev'}`.

- [ ] **Step 6: Run the alignment tests and commit**

```bash
uv run pytest tests/test_alignment_sourcing.py -v
uv run pytest -m "not integration"
```

Expected: PASS.

Branch A commit:

```bash
uv run git add src/gramps_mcp/models/parameters/source_params.py \
  tests/test_create_sourcing.py tests/test_alignment_sourcing.py
uv run git commit -m "feat: accept abbrev when creating a source

The shipped usage guide offers abbrev on source creation but
SourceSaveParams never declared it. Before this branch the key was dropped
in silence; after the strict-validation commit it would have been refused,
so the guide had to become true or the mention had to go.

A round-trip test settles it: POST /sources stores the value, so the field
belongs on the model. The guide needed no edit - it already named the field
exactly as Gramps does.

Closes #17"
```

Branch B commit:

```bash
uv run git add src/gramps_mcp/resources/gramps-usage-guide.md \
  tests/test_strict_params.py
uv run git commit -m "docs: drop the abbrev mention the API does not honour

A round-trip test shows POST /sources does not store abbrev, so the usage
guide was promising a parameter that could never take effect. The guide is
served to MCP clients as gramps://usage-guide, so the false promise was the
server telling the assistant to do something that silently did nothing.

Closes #17"
```

---

### Task 4: Source reuse in `create_sourced_event` (#12)

One document carrying three facts currently yields three identical sources,
because `create_sourced_event` always creates one. Nothing in the MCP surface
can merge or delete a source, so each duplicate is a manual cleanup.

**Files:**
- Modify: `src/gramps_mcp/utils.py` (append a helper)
- Modify: `src/gramps_mcp/models/parameters/sourced_event_params.py:32-68`
- Modify: `src/gramps_mcp/tools/sourced_event.py:49-120`
- Modify: `tests/test_create_sourcing.py` (add two tests)

**Interfaces:**
- Consumes: `StrictModel` from Task 2.
- Produces:
  `resolve_source_handles_by_title(client, tree_id: str, title: str) -> list[str]`
  in `src.gramps_mcp.utils`;
  `SourcedEventData.source_handle: str | None`.

- [ ] **Step 1: Write the two failing tests**

Add to `tests/test_create_sourcing.py`, inside
`class TestCreateSourcedEventTool`:

```python
    @pytest.mark.asyncio
    async def test_reuses_an_existing_source_by_handle(
        self, gramps_client, tree_id
    ):
        """A second fact from the same document shares one source."""
        first = await create_sourced_event_tool(
            {
                "source_title": f"{PREFIX} Reuse Register",
                "citation_page": "Page 1, birth",
                "event_type": "Birth",
            }
        )
        first_text = first[0].text
        assert "Error:" not in first_text, first_text
        source_handle = _handle_on_line(first_text, "Reuse Register")

        second = await create_sourced_event_tool(
            {
                "source_handle": source_handle,
                "citation_page": "Page 1, death",
                "event_type": "Death",
            }
        )
        second_text = second[0].text
        assert "Error:" not in second_text, second_text
        assert source_handle in second_text, (
            f"Second call did not attach to the existing source: {second_text}"
        )

        citation_handle = _handle_on_line(second_text, "Page 1, death")
        citation_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_CITATION,
            tree_id=tree_id,
            handle=citation_handle,
        )
        assert citation_data.get("source_handle") == source_handle

    @pytest.mark.asyncio
    async def test_refuses_a_duplicate_source_title(self):
        """Creating a second source with an existing title is refused, not
        guessed: two documents can legitimately share a title."""
        title = f"{PREFIX} Collision Register"
        first = await create_sourced_event_tool(
            {
                "source_title": title,
                "citation_page": "Page 1",
                "event_type": "Birth",
            }
        )
        assert "Error:" not in first[0].text, first[0].text

        second = await create_sourced_event_tool(
            {
                "source_title": title,
                "citation_page": "Page 2",
                "event_type": "Death",
            }
        )
        second_text = second[0].text
        assert "Error:" in second_text, (
            f"Expected a refusal on the duplicate title but got: {second_text}"
        )
        assert "source_handle" in second_text, (
            f"The refusal must name the way forward: {second_text}"
        )

    @pytest.mark.asyncio
    async def test_refuses_both_source_title_and_source_handle(self):
        """The two are mutually exclusive."""
        result = await create_sourced_event_tool(
            {
                "source_title": f"{PREFIX} Both Register",
                "source_handle": "103f77fe86ec4c13f3fac1a420ec",
                "event_type": "Birth",
            }
        )
        assert "Error:" in result[0].text
```

- [ ] **Step 2: Run them and watch them fail**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest \
  "tests/test_create_sourcing.py::TestCreateSourcedEventTool" -xvs -k "reuse or refuses"
```

Expected: FAIL - `source_handle` is refused as an extra input (Task 2 made
`SourcedEventData` strict), and the duplicate-title call succeeds instead of
refusing.

- [ ] **Step 3: Add the lookup helper**

Append to `src/gramps_mcp/utils.py`:

```python
async def resolve_source_handles_by_title(
    client, tree_id: str, title: str
) -> list[str]:
    """
    Find the handles of every source carrying exactly this title.

    Args:
        client: GrampsWebAPIClient instance
        tree_id: Family tree identifier
        title: The exact source title to match

    Returns:
        Handles of matching sources, empty when none match
    """
    # Reason: unlike the gramps_id resolve_person_handle interpolates - whose
    # callers gate it against an anchored ^[A-Z]+[0-9]+$ pattern first - a
    # source title is free text supplied by the caller. Real titles in this
    # tree contain quotes, dashes and parentheses. An unescaped quote would
    # close the GQL string literal and inject filter syntax.
    escaped = title.replace("\\", "\\\\").replace('"', '\\"')
    results = await client.make_api_call(
        api_call=ApiCalls.GET_SOURCES,
        params={"gql": f'title="{escaped}"', "pagesize": 10},
        tree_id=tree_id,
    )
    if not results or not isinstance(results, list):
        return []
    return [item["handle"] for item in results if item.get("handle")]
```

`ApiCalls` is already imported in `utils.py` (used by
`resolve_person_handle`). Verify before adding an import.

- [ ] **Step 4: Add the field and the exclusivity validator**

In `sourced_event_params.py`, replace the `source_title` declaration
(line 36) with:

```python
    source_title: str | None = Field(
        None,
        description=(
            "Title of a new source to create. Mutually exclusive with "
            "source_handle: supply exactly one."
        ),
        min_length=1,
    )
    source_handle: str | None = Field(
        None,
        description=(
            "Handle of an existing source to attach the new citation to. "
            "Mutually exclusive with source_title: supply exactly one. Use "
            "this to record several facts from one document without "
            "creating a duplicate source for each."
        ),
    )
```

Change the import at line 26 to
`from pydantic import Field, field_validator, model_validator` and add, after
the existing `validate_event_place_is_handle` validator:

```python
    @model_validator(mode="after")
    def check_exactly_one_source(self) -> "SourcedEventData":
        """
        Require exactly one of source_title or source_handle.

        Returns:
            SourcedEventData: The validated model.

        Raises:
            ValueError: If both are given or neither is.
        """
        if bool(self.source_title) == bool(self.source_handle):
            raise ValueError(
                "supply exactly one of source_title or source_handle: "
                "source_title creates a new source, source_handle attaches "
                "the citation to an existing one."
            )
        return self
```

- [ ] **Step 5: Wire it into the tool**

In `src/gramps_mcp/tools/sourced_event.py`, replace the source step (lines
57-67, from `# 1. Source` through `source_handle = source_data["handle"]`)
with:

```python
        # 1. Source - reuse an existing one, or create after a collision check
        if params.source_handle:
            source_handle = params.source_handle
        else:
            existing = await resolve_source_handles_by_title(
                client, tree_id, params.source_title
            )
            if existing:
                # Reason: refuse rather than reuse. Source titles repeat
                # heavily in genealogy ("Etat civil, Paris"), so silently
                # attaching to a same-titled source would be invisible and
                # wrong - worse than the visible duplicate this guards
                # against. Only the caller knows if it is the same document.
                raise GrampsAPIError(
                    f"A source titled {params.source_title!r} already exists "
                    f"({', '.join(existing)}). Call again with "
                    "source_handle set to one of those to attach this "
                    "citation to it, or use a distinct title if this is a "
                    "different document."
                )
            source_kwargs: dict[str, Any] = {
                "title": params.source_title,
                "author": params.source_author,
                "pubinfo": params.source_pubinfo,
            }
            source_params = SourceSaveParams(**source_kwargs)
            source_result = await client.make_api_call(
                api_call=ApiCalls.POST_SOURCES,
                params=source_params,
                tree_id=tree_id,
            )
            source_data = _extract_entity_data(source_result)
            source_handle = source_data["handle"]
```

Add the imports at the top of the file:

```python
from ..client import GrampsAPIError, GrampsWebAPIClient
from ..utils import resolve_source_handles_by_title
```

(the existing line is `from ..client import GrampsWebAPIClient`.)

The response block at lines 111-118 needs no change: `format_source(client,
tree_id, source_handle)` works for a reused source exactly as for a new one.

- [ ] **Step 6: Run the tests**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest \
  "tests/test_create_sourcing.py::TestCreateSourcedEventTool" -xvs
uv run pytest -m "not integration"
uv run mypy src/gramps_mcp --ignore-missing-imports
```

Expected: PASS. Note the pre-existing
`test_create_sourced_event_with_media_path` still fails on `"image/jpeg"` -
Task 5 fixes it.

- [ ] **Step 7: Commit**

```bash
uv run git add src/gramps_mcp/utils.py \
  src/gramps_mcp/models/parameters/sourced_event_params.py \
  src/gramps_mcp/tools/sourced_event.py tests/test_create_sourcing.py
uv run git commit -m "feat: let create_sourced_event reuse an existing source

The tool always created a source, so recording a birth, a death and a
marriage from one document produced three identical sources. Neither the MCP
tools nor the API surface exposed here can merge or delete one, so each
duplicate was a manual cleanup in the Gramps Web UI.

source_handle attaches the new citation to an existing source and is
mutually exclusive with source_title. When source_title is given and a
source already carries that title, the call is refused with the colliding
handles named, rather than reused: titles repeat heavily in genealogy, and
attaching a citation to the wrong source is invisible and wrong where a
duplicate is merely visible and redundant.

The title is escaped before it reaches the GQL filter. Unlike the gramps_id
resolve_person_handle interpolates, a source title is free text and real
ones already contain quotes.

Closes #12"
```

---

### Task 5: Media assertions and the raw handle (#13)

Three tests assert a MIME type that the source and citation formatters
structurally cannot emit; they have failed on `main` for weeks. Separately,
one line prints a raw handle where every comparable site prints a gramps_id.

**Files:**
- Modify: `src/gramps_mcp/tools/sourced_event.py:120`
- Modify: `tests/test_create_sourcing.py:159`, `:242`, `:248`, `:340`

**Interfaces:**
- Consumes: nothing from earlier tasks beyond a working tree.

**Reference.** `format_source` (`source_handler.py:95-116`) and
`format_citation` (`citation_handler.py:96-117`) fetch each attached media
object and emit `Attached media: {gramps_id}` - never a MIME type.
`format_media` (`media_handler.py:69`) is the only place a MIME type is
emitted. Two tests in this same file already assert the correct shape and
pass: `"Attached media: O"` at lines 135 and 208.

- [ ] **Step 1: Fix the raw handle**

In `src/gramps_mcp/tools/sourced_event.py`, line 120:

```python
            response += f"\nAttached media: {media_info.get('handle', 'N/A')}\n"
```

becomes:

```python
            # Reason: every other site emits a gramps_id here
            # (source_handler.py:116, citation_handler.py:117,
            # person_handler.py:171, family_handler.py:206). media_info is
            # the raw new-media object from the upload, which carries both.
            response += f"\nAttached media: {media_info.get('gramps_id', 'N/A')}\n"
```

- [ ] **Step 2: Rewrite the three assertions**

`tests/test_create_sourcing.py:159-161`, in
`test_create_source_with_media_path` - change the signature to take
`gramps_client` and `tree_id`:

```python
    async def test_create_source_with_media_path(
        self, gramps_client, tree_id, repository_handle
    ):
```

and replace the `"image/jpeg"` assertion with:

```python
        # The formatters emit "Attached media: <gramps_id>", never a MIME
        # type - format_media is the only place a MIME type appears. Assert
        # the exact gramps_id so a raw handle cannot satisfy this by chance.
        source_handle = _handle_on_line(text, "Inline Media Source Test")
        source_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_SOURCE, tree_id=tree_id, handle=source_handle
        )
        media_refs = source_data.get("media_list") or []
        assert media_refs, f"No media attached to the source: {text}"
        media_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_MEDIA_ITEM,
            tree_id=tree_id,
            handle=media_refs[-1]["ref"],
        )
        assert f"Attached media: {media_data['gramps_id']}" in text, (
            f"Expected the uploaded media's gramps_id in: {text}"
        )
```

`tests/test_create_sourcing.py:242-251`, in
`test_create_citation_with_media_path` - replace **both** the `"image/jpeg"`
assertion and the `text.count("image/") >= 2` assertion. Change the signature
to `(self, gramps_client, tree_id, source_handle, media_handle)` and use:

```python
        citation_handle = _handle_on_line(text, "Page 12, inline media test")
        citation_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_CITATION, tree_id=tree_id, handle=citation_handle
        )
        media_refs = citation_data.get("media_list") or []
        assert len(media_refs) == 2, (
            "Expected both the pre-existing and the inline-uploaded media "
            f"but citation media_list was: {media_refs}"
        )
        for media_ref in media_refs:
            media_data = await gramps_client.make_api_call(
                api_call=ApiCalls.GET_MEDIA_ITEM,
                tree_id=tree_id,
                handle=media_ref["ref"],
            )
            assert media_data["gramps_id"] in text, (
                f"Media {media_data['gramps_id']} missing from output: {text}"
            )
```

`tests/test_create_sourcing.py:340-342`, in
`test_create_sourced_event_with_media_path` - the test already fetches the
citation at lines 344-350. Move the `"image/jpeg"` assertion to after that
fetch and replace it with:

```python
        media_refs = citation_data.get("media_list") or []
        assert media_refs, (
            f"Expected media attached to citation {citation_handle} but "
            f"media_list was: {media_refs}"
        )
        media_data = await gramps_client.make_api_call(
            api_call=ApiCalls.GET_MEDIA_ITEM,
            tree_id=tree_id,
            handle=media_refs[-1]["ref"],
        )
        # Guards the raw-handle regression: this line used to print
        # media_info["handle"] rather than its gramps_id.
        assert f"Attached media: {media_data['gramps_id']}" in text, (
            f"Expected the uploaded media's gramps_id in: {text}"
        )
```

and delete the now-redundant `assert citation_data.get("media_list")` at
lines 352-355.

- [ ] **Step 3: Run the three tests**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest \
  tests/test_create_sourcing.py -xvs -k "media_path"
```

Expected: all three PASS. They have failed on `main` for weeks, so this is
the first green run.

- [ ] **Step 4: Run the whole suite**

```bash
uv run pytest -m "not integration"
GRAMPS_API_URL=http://localhost:80 uv run pytest 2>&1 | tail -30
```

Expected: the offline selection fully green; the integration run green apart
from any `tree_stats` permission error, which is an environment fact.

- [ ] **Step 5: Commit**

```bash
uv run git add src/gramps_mcp/tools/sourced_event.py tests/test_create_sourcing.py
uv run git commit -m "fix: assert the media gramps_id the formatters actually emit

Three tests asserted \"image/jpeg\" appears in the output of format_source
and format_citation. Those formatters emit \"Attached media: <gramps_id>\";
format_media is the only place in the project that emits a MIME type, so the
assertion was unsatisfiable and had failed deterministically for weeks. Two
tests in the same file already assert the correct shape and pass.

The assertions now check the exact gramps_id of the uploaded media, which
also guards the second defect fixed here: create_sourced_event printed
media_info[\"handle\"] where every comparable site prints a gramps_id.

Closes #13"
```

---

### Task 9: The citation step leaks the same way (#16, third site)

Found by the final-review fix wave, which fixed the person step and then
measured the citation step still growing: note and media counts went
35 -> 36 -> 37 across two reruns of `tests/test_workflow_marriage.py`.

`_step_3_citation_creation` in `tests/test_workflow_marriage.py` has the
identical defect the fix wave just removed from the person step: it creates a
note and a media object **unconditionally**, before checking whether the
citation already exists. When the citation is found, those two records are
attached to nothing and stay in the user's live genealogy tree.

This is the same leak issue #16 describes, at a third site. Shipping
`Closes #16` while this one still bleeds two records per run would repeat the
mistake this lot was filed to correct - the first acceptance check counted only
people, missed notes and media, and let the person-step leak through.

**Files:**
- Modify: `tests/test_workflow_marriage.py` (`_step_3_citation_creation`)

- [ ] **Step 1: Measure the leak before touching it**

Count the citation-step notes and media in the live tree, run the whole test
file twice, and count again. Record both numbers. Use the same counting method
the fix wave used for the person step (see
`.superpowers/sdd/2026-08-14-gh-issues-lot6/final-fix-report.md`).

Expected: the count grows by two per run.

- [ ] **Step 2: Move the creation onto the path that links it**

Apply the same shape the fix wave applied to
`create_or_find_person_with_attributes` in `tests/workflow_helpers.py`: the
`create_test_note` and `create_test_media` calls move inside the branch that
creates the citation and attaches them. The found-existing path must create
nothing.

Read that helper first and mirror it, so the two steps stay consistent for the
next reader.

- [ ] **Step 3: Prove it with counts, not with a green test**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_workflow_marriage.py -xvs
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_workflow_marriage.py -xvs
```

Count the citation-step notes and media again after each run. They must be flat
between the second and third run. A passing test is not the deliverable; the
flat count is.

- [ ] **Step 4: Sweep the rest of the file**

`_step_1_repository_creation`, `_step_2_source_creation` and
`_step_4_event_creation` follow the same find-or-create shape. Check each for
the same pattern - anything created before the existence check that only the
create path attaches. Fix any you find, and state in your report which steps
you checked and what you found, so the sweep is on the record.

- [ ] **Step 5: Commit**

```bash
uv run git add tests/test_workflow_marriage.py
uv run git commit -m "fix: stop the citation step leaking notes and media

The person step was fixed earlier in this branch; the citation step had the
same defect. It created a note and a media object before checking whether the
citation already existed, so on every rerun those two records were attached to
nothing and stayed in the live tree. Measured at 35 -> 36 -> 37 across two
reruns.

Refs #16"
```

---

### Task 7: `get_descendants` / `get_ancestors` return nothing (#19)

Added to the lot after the final review, on the user's decision. Filed as
[#19](https://github.com/fjacquet/gramps-mcp/issues/19).

Both tools return an empty response for every person. Verified live:
`get_descendants(gramps_id="I0904")` and `get_descendants(gramps_id="I0254")`
both produce no output at all.

**The mechanism.** The tools ask Gramps for an HTML report
(`analysis.py:198`, `report_options = {"pid": ..., "off": "html"}`), then read
it back through a code path built for errors:

1. The body is HTML. `_parse_response` (`client.py:186-196`) tries
   `response.json()`, fails, logs `Failed to parse JSON response`, and returns
   `{"error": "Invalid JSON response", "raw_content": <text>}`.
2. `raw_content` is truncated to `MAX_ERROR_DETAIL`, which is **300**
   (`client.py:43`, applied at `:191-192`).
3. `analysis.py:258-262` reads that `raw_content` as the report body.
4. 300 characters of an HTML document is the `<head>` - a favicon link and a
   stylesheet. `html_to_markdown` yields an empty string.
5. The tool returns empty text and reports success.

**The cap is not the bug and must not be raised.** It exists for a documented
privacy reason (`client.py:180-184`): Gramps can echo a submitted payload back
in an error body, and that payload may carry data about living people. The
defect is upstream - a legitimate non-JSON success response is being routed
through the error channel.

**Files:**
- Modify: `src/gramps_mcp/client.py` (`make_api_call`)
- Modify: `src/gramps_mcp/tools/analysis.py` (both report downloads)
- Test: `tests/test_analysis.py`

- [ ] **Step 1: Watch the existing tests fail**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_analysis.py -xvs \
  -k "descendants_real_api or ancestors_real_api"
```

Expected: FAIL, with the payload visible as HTML head markup.

- [ ] **Step 2: Give non-JSON responses their own channel**

`make_api_call` already carries a `with_headers: bool = False` flag
(`client.py:303`); follow that precedent. Add `as_text: bool = False`. When
true, return `response.text` whole and do not call `_parse_response` at all -
no JSON attempt, no error dict, no truncation. HTTP error handling is
unchanged: a non-2xx response must still raise `GrampsAPIError` exactly as it
does today. Document the flag in the docstring, and add a `# Reason:` comment
explaining that a report download is a file fetch, not a JSON call, so it must
not travel through the error-truncation path.

- [ ] **Step 3: Use it in both report downloads**

In `src/gramps_mcp/tools/analysis.py`, the two `GET_REPORT_PROCESSED` calls
(around lines 252 and 345) pass `as_text=True`, and the block that reads
`report_response["raw_content"]` is replaced by using the returned string
directly. Remove the now-dead `isinstance(..., dict) and "raw_content" in ...`
branch.

- [ ] **Step 4: Verify against the live server**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest tests/test_analysis.py -xvs \
  -k "descendants_real_api or ancestors_real_api"
uv run pytest -m "not integration"
uv run mypy src/gramps_mcp --ignore-missing-imports
```

Expected: the two tests PASS, offline suite unchanged, mypy clean. The live
suite's failure count must drop by two.

- [ ] **Step 5: Commit**

```bash
uv run git add src/gramps_mcp/client.py src/gramps_mcp/tools/analysis.py
uv run git commit -m "fix: stop routing HTML reports through the error channel

get_descendants and get_ancestors returned nothing for every person. They ask
Gramps for an HTML report, but the response reached them through
_parse_response's JSON-failure path, which truncates raw_content to
MAX_ERROR_DETAIL (300 bytes). Three hundred characters of an HTML document is
the <head>, so html_to_markdown produced an empty string and the tools
reported success with no content.

make_api_call gains as_text for responses that are not JSON by design. The
300-byte cap is untouched: it bounds error bodies, which can echo a submitted
payload carrying data about living people.

Closes #19"
```

---

### Task 8: `test_find_anything` depends on data it does not create (#20)

Added to the lot after the final review, on the user's decision. Filed as
[#20](https://github.com/fjacquet/gramps-mcp/issues/20).

`tests/test_search_find_anything.py:32` searches for the literal `"pietrala"`
and asserts a match. The test never creates that record; it relies on a person
who happens to exist in whichever live tree the suite points at. It currently
fails with `No records found matching 'pietrala'`.

The assertion cannot tell "search is broken" from "that surname is not in this
tree", so it does not test what its name claims.

**Files:**
- Modify: `tests/test_search_find_anything.py`

- [ ] **Step 1: Rewrite the test to create what it searches for**

Create a person carrying `PREFIX` from `tests/constants.py` plus a per-run
unique suffix (`uuid.uuid4().hex[:8]`), following the pattern already used in
`tests/test_create_sourced_event.py` and the `person_handles` fixture in
`tests/conftest.py`. Search for that unique string. Keep the `max_results`
half of the test - it becomes meaningful once the number of matching records
is known rather than incidental.

Use `create_person_tool` with the name shape the formatters actually read:

```python
primary_name={"first_name": f"{PREFIX} {unique}", "surname_list": [{"surname": "Findable"}]}
```

- [ ] **Step 2: Run it twice**

```bash
GRAMPS_API_URL=http://localhost:80 uv run pytest \
  tests/test_search_find_anything.py -xvs
GRAMPS_API_URL=http://localhost:80 uv run pytest \
  tests/test_search_find_anything.py -xvs
```

Expected: PASS both times. The unique suffix makes the second run independent
of the first.

- [ ] **Step 3: Commit**

```bash
uv run git add tests/test_search_find_anything.py
uv run git commit -m "test: make find_anything search for a record it creates

The test searched for a hardcoded surname it never created, so it passed only
while that person happened to exist in the live tree it was pointed at, and
could not distinguish a broken search from absent data.

Closes #20"
```

---

### Task 6: Open the pull request

- [ ] **Step 1: Verify the branch state**

```bash
uv run pytest -m "not integration"
GRAMPS_API_URL=http://localhost:80 uv run pytest 2>&1 | tail -30
rtk git log --oneline main..HEAD
```

Expected: five or six commits, one per defect plus the spec.

- [ ] **Step 2: Push and open the PR**

```bash
rtk git push -u origin fix/quality-lot6-issues
gh pr create --repo fjacquet/gramps-mcp \
  --title "Close issues #12, #13, #16, #17" \
  --body "$(cat <<'BODY'
Closes #12
Closes #13
Closes #16
Closes #17

Three of the four shared one root cause: the parameter models carried
Pydantic's default `extra="ignore"`, so any undeclared key was dropped
before the request was built and nothing reported it.

Design: `docs/superpowers/specs/2026-08-14-gh-issues-lot6-design.md`

## Behaviour changes visible to MCP clients

- Write-model schemas gain `additionalProperties: false`. A client sending
  stray keys now gets an error instead of a silent drop.
- `create_sourced_event`: `source_title` is optional, `source_handle` is new,
  and a duplicate title is refused rather than duplicated.
- `create_source` accepts `abbrev`.

## Not included

The 36 nameless people, 18 families, 36 notes and 36 media objects that 18
runs of the marriage workflow test left in the live tree. The leak is closed;
the existing records are cleaned by hand.

Merge with `--merge`, not `--squash` - the per-defect commits should survive.
BODY
)"
```

**Note:** `--repo fjacquet/gramps-mcp` is required. Without it this fork's
`gh pr create` fails with a misleading token error.

---

## Self-review

**Spec coverage.** Section 1 (root, `StrictModel` on twelve models, read
models untouched, `MediaFileParams` left permissive) - Task 2. Section 2
(#16, both call sites, name shape, assertions, file length) - Task 1.
Section 3 (#12, `source_handle`, collision refusal, escaped GQL) - Task 4.
Section 4 (#13, raw handle plus four assertions) - Task 5. Section 5 (#17,
test-first with both branches) - Task 3. Section 6 (offline plus integration
split) - the test steps throughout. Section 7 risks: the fallout inventory is
Task 2 step 6 with an explicit stop-and-report threshold; the alignment
inventory is Task 3 step 5; the file-length check is Task 1 step 5; the
`abbrev` uncertainty is Task 3's two branches.

**Placeholders.** None. Every code step carries the code; both outcomes of
the one genuine unknown (`abbrev`) have written-out instructions.

**Type consistency.** `resolve_source_handles_by_title(client, tree_id,
title) -> list[str]` is defined in Task 4 step 3 and called in step 5 with
that signature. `StrictModel` is defined in Task 2 step 3 and referenced by
that name in step 4 and in Tasks 3 and 4. `extract_handle(create_result)`
matches `tests/workflow_helpers.py:26-40`. `_handle_on_line(text, marker)`
matches `tests/test_create_sourcing.py:26-35`. `ApiCalls` members used
(`GET_SOURCE`, `GET_SOURCES`, `POST_SOURCES`, `GET_CITATION`,
`GET_MEDIA_ITEM`) all exist in `api_calls.py:59-87`.
