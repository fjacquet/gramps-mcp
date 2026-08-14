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

from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
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
    TagSearchParams,
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


def test_base_get_multiple_params_rejects_query():
    """'query' used to be silently dropped by extra='ignore', leaving a
    caller believing an unfiltered result set was filtered (issue #18). It
    must now raise and point at the two real search paths."""
    with pytest.raises(ValidationError) as exc_info:
        BaseGetMultipleParams(query="anything")
    message = str(exc_info.value)
    assert "gql" in message
    assert "find_anything" in message


def test_base_get_multiple_params_still_accepts_gql():
    """The rejection above must not be a broken model - a real gql= filter,
    the field query= should have been, still works."""
    params = BaseGetMultipleParams(gql="first_name = 'Jean'")
    assert params.gql == "first_name = 'Jean'"


def test_tag_search_params_rejects_a_filter_it_cannot_honour():
    """
    The tags endpoint supports no gql filter and tags have no gramps_id, so
    extra='ignore' used to drop both keys and return the first page of every
    tag. delete_type's gramps_id lookup then resolved to an arbitrary tag.
    """
    for bad_key in ("gql", "gramps_id", "query"):
        with pytest.raises(ValidationError):
            TagSearchParams(**{bad_key: "anything"})


def test_tag_search_params_still_accepts_its_real_fields():
    """The rejection above must not break the one live caller, manage_tags."""
    params = TagSearchParams(page=1, pagesize=10, sort=["name"])
    assert params.pagesize == 10
