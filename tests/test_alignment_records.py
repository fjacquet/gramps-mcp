"""
Test parameter alignment with usage guide requirements.

Verifies that POST/PUT parameters in models match exactly with the requirements
specified in gramps-usage-guide.md - no more, no less, with correct required/optional status.
"""

from src.gramps_mcp.models.parameters.event_params import EventSaveParams
from src.gramps_mcp.models.parameters.family_params import FamilySaveParams
from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
from src.gramps_mcp.models.parameters.people_params import PersonData
from src.gramps_mcp.models.parameters.place_params import PlaceSaveParams


class TestParameterAlignment:
    """Test that model parameters align with usage guide requirements."""

    def test_event_parameters_alignment(self):
        """Test EventSaveParams parameters match current implementation."""
        # Current implementation: Event requires type, citation_list
        # Optional: handle, date, description, place, note_list
        model = EventSaveParams
        fields = model.model_fields

        # Required fields in current implementation
        required_fields = {"type", "citation_list"}

        # Check all required fields are present and required
        for field_name in required_fields:
            assert field_name in fields, (
                f"Required field '{field_name}' missing from EventSaveParams"
            )
            assert fields[field_name].is_required(), (
                f"Field '{field_name}' should be required"
            )

        # Check no extra required fields beyond current implementation
        actual_required = {
            name for name, field in fields.items() if field.is_required()
        }
        extra_required = actual_required - required_fields
        assert not extra_required, (
            f"EventSaveParams has extra required fields: {extra_required}"
        )

        # Check fields match current implementation
        implementation_fields = required_fields | {
            "handle",
            "date",
            "description",
            "place",
            "note_list",
        }
        actual_fields = set(fields.keys())
        extra_fields = actual_fields - implementation_fields
        assert not extra_fields, f"EventSaveParams has extra fields: {extra_fields}"

    def test_person_parameters_alignment(self):
        """Test PersonData parameters match current implementation."""
        # Current implementation: Person requires primary_name, gender
        # Optional: event_ref_list, family_list, parent_family_list, urls, plus BaseDataModel fields
        # Birth/Death info should NOT be direct fields (should be events)
        model = PersonData
        fields = model.model_fields

        # Required fields in current implementation
        required_fields = {"primary_name", "gender"}

        # Check all required fields are present and required
        for field_name in required_fields:
            assert field_name in fields, (
                f"Required field '{field_name}' missing from PersonData"
            )
            assert fields[field_name].is_required(), (
                f"Field '{field_name}' should be required"
            )

        # Check no extra required fields beyond current implementation
        actual_required = {
            name for name, field in fields.items() if field.is_required()
        }
        extra_required = actual_required - required_fields
        assert not extra_required, (
            f"PersonData has extra required fields: {extra_required}"
        )

        # Birth/death info should NOT be direct fields (should be events)
        birth_death_fields = {"birth_date", "birth_place", "death_date", "death_place"}
        actual_fields = set(fields.keys())
        birth_death_in_model = actual_fields & birth_death_fields
        assert not birth_death_in_model, (
            f"PersonData should not have direct birth/death fields: {birth_death_in_model}"
        )

        # Check that essential linking fields are present
        required_linking_fields = {
            "event_ref_list",
            "family_list",
            "parent_family_list",
        }
        for field_name in required_linking_fields:
            assert field_name in fields, (
                f"Required linking field '{field_name}' missing from PersonData"
            )

        # Check fields match current implementation
        implementation_fields = required_fields | {
            "event_ref_list",
            "family_list",
            "parent_family_list",
            "urls",
        }
        system_fields = {
            "handle",
            "gramps_id",
            "note_list",
            "media_list",
            "attribute_list",
            "tag_list",
            "private",
            "change",
        }
        allowed_fields = implementation_fields | system_fields
        actual_fields = set(fields.keys())
        extra_fields = actual_fields - allowed_fields
        assert not extra_fields, f"PersonData has extra fields: {extra_fields}"

    def test_family_parameters_alignment(self):
        """Test FamilySaveParams parameters match usage guide requirements."""
        # From usage guide: Family requires father_handle, mother_handle, children_handles (all optional)
        # Optional: notes, media, URLs, family events
        # Must support linking family events (marriage, divorce)
        model = FamilySaveParams
        fields = model.model_fields

        # No required fields according to guide - all family fields are optional
        # Check no fields are required (except handle for updates)
        actual_required = {
            name for name, field in fields.items() if field.is_required()
        }
        unexpected_required = actual_required - {
            "handle"
        }  # handle might be required for updates in BaseDataModel
        assert not unexpected_required, (
            f"FamilySaveParams has unexpected required fields: {unexpected_required}"
        )

        # Check that essential family linking fields are present
        # Reason: child_ref_list is the API-shaped counterpart of child_handles;
        # create_family translates the latter into the former (issue #24).
        family_linking_fields = {
            "father_handle",
            "mother_handle",
            "child_handles",
            "child_ref_list",
            "event_ref_list",
        }
        for field_name in family_linking_fields:
            assert field_name in fields, (
                f"Required family linking field '{field_name}' missing from FamilySaveParams"
            )

        # Check no extra fields beyond what guide allows (plus system fields from BaseDataModel and linking fields)
        guide_fields = {"notes", "media", "urls", "type"}
        system_fields = {
            "handle",
            "gramps_id",
            "note_list",
            "media_list",
            "attribute_list",
            "tag_list",
            "private",
            "change",
        }
        allowed_fields = guide_fields | system_fields | family_linking_fields
        actual_fields = set(fields.keys())
        extra_fields = actual_fields - allowed_fields
        assert not extra_fields, (
            f"FamilySaveParams has extra fields not in usage guide: {extra_fields}"
        )

    def test_place_parameters_alignment(self):
        """Test PlaceSaveParams parameters match current implementation."""
        # Current implementation: place_type is optional so a partial
        # update (e.g. moving a place via placeref_list) does not have to
        # resupply it. It is also optional on creation: the API accepts a
        # place with no place_type and Gramps stores "Unknown" (see
        # tests/test_place_media.py::TestPlaceCreationWithoutType).
        # Optional: handle, gramps_id, name, code, alt_loc, place_type, placeref_list, alt_names, lat, long, urls, media_list, citation_list, note_list, tag_list, private
        model = PlaceSaveParams
        fields = model.model_fields

        # Required fields in current implementation
        required_fields = set()

        # Check all required fields are present and required
        for field_name in required_fields:
            assert field_name in fields, (
                f"Required field '{field_name}' missing from PlaceSaveParams"
            )
            assert fields[field_name].is_required(), (
                f"Field '{field_name}' should be required"
            )

        # Check no extra required fields beyond current implementation
        actual_required = {
            name for name, field in fields.items() if field.is_required()
        }
        extra_required = actual_required - required_fields
        assert not extra_required, (
            f"PlaceSaveParams has extra required fields: {extra_required}"
        )

        # Check fields match current implementation
        # Reason: replace_lists names list fields to overwrite rather than
        # add to (e.g. ["placeref_list"] to move a place to a different
        # parent instead of giving it a second one). It is popped from the
        # raw arguments in data_management.py before PlaceSaveParams is
        # constructed, so it never reaches Gramps as request data - it is
        # only carried on this model to document/validate the tool's
        # advertised input schema.
        implementation_fields = required_fields | {
            "handle",
            "gramps_id",
            "name",
            "code",
            "alt_loc",
            "place_type",
            "placeref_list",
            "alt_names",
            "lat",
            "long",
            "urls",
            "media_list",
            "citation_list",
            "note_list",
            "tag_list",
            "private",
            "replace_lists",
        }
        actual_fields = set(fields.keys())
        extra_fields = actual_fields - implementation_fields
        assert not extra_fields, f"PlaceSaveParams has extra fields: {extra_fields}"

    def test_note_parameters_alignment(self):
        """Test NoteSaveParams parameters match usage guide requirements."""
        # From usage guide: Note requires text, type
        model = NoteSaveParams
        fields = model.model_fields

        # Required fields according to guide
        required_fields = {"text", "type"}

        # Check all required fields are present and required
        for field_name in required_fields:
            assert field_name in fields, (
                f"Required field '{field_name}' missing from NoteSaveParams"
            )
            assert fields[field_name].is_required(), (
                f"Field '{field_name}' should be required"
            )

        # Check no extra required fields beyond what guide specifies
        actual_required = {
            name for name, field in fields.items() if field.is_required()
        }
        extra_required = actual_required - required_fields
        assert not extra_required, (
            f"NoteSaveParams has extra required fields not in guide: {extra_required}"
        )

        # Check no extra fields beyond what guide allows (plus system fields from BaseDataModel)
        guide_fields = required_fields
        system_fields = {
            "handle",
            "gramps_id",
            "note_list",
            "media_list",
            "attribute_list",
            "tag_list",
            "private",
            "change",
        }
        allowed_fields = guide_fields | system_fields
        actual_fields = set(fields.keys())
        extra_fields = actual_fields - allowed_fields
        assert not extra_fields, (
            f"NoteSaveParams has extra fields not in usage guide: {extra_fields}"
        )
