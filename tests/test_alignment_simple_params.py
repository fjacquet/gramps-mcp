"""
Test parameter alignment with usage guide requirements.

Verifies that POST/PUT parameters in models match exactly with the requirements
specified in gramps-usage-guide.md - no more, no less, with correct required/optional status.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.destructive_params import (
    DeleteTypeParams,
    DetachReferenceParams,
    MergeTypeParams,
    UndoChangeParams,
)
from src.gramps_mcp.models.parameters.people_params import PersonData
from src.gramps_mcp.models.parameters.simple_params import (
    EntityType,
    GetEntityType,
    SimpleFindParams,
    SimpleGetParams,
    SimpleSearchParams,
)


class TestParameterAlignment:
    """Test that model parameters align with usage guide requirements."""

    def test_simple_params_exist_and_structured_correctly(self):
        """Test that all simple parameter models exist and have correct structure."""
        # Test SimpleFindParams
        assert hasattr(SimpleFindParams, "model_fields"), (
            "SimpleFindParams should be a Pydantic model"
        )
        find_fields = SimpleFindParams.model_fields
        assert "type" in find_fields, "SimpleFindParams should have 'type' field"
        assert "gql" in find_fields, "SimpleFindParams should have 'gql' field"
        assert "max_results" in find_fields, (
            "SimpleFindParams should have 'max_results' field"
        )

        # Test SimpleSearchParams
        assert hasattr(SimpleSearchParams, "model_fields"), (
            "SimpleSearchParams should be a Pydantic model"
        )
        search_fields = SimpleSearchParams.model_fields
        assert "query" in search_fields, "SimpleSearchParams should have 'query' field"
        assert "max_results" in search_fields, (
            "SimpleSearchParams should have 'max_results' field"
        )

        # Test SimpleGetParams
        assert hasattr(SimpleGetParams, "model_fields"), (
            "SimpleGetParams should be a Pydantic model"
        )
        get_fields = SimpleGetParams.model_fields
        assert "type" in get_fields, "SimpleGetParams should have 'type' field"
        assert "handle" in get_fields, "SimpleGetParams should have 'handle' field"
        assert "gramps_id" in get_fields, (
            "SimpleGetParams should have 'gramps_id' field"
        )

        # Test EntityType enum exists and has all types
        entity_types = {e.value for e in EntityType}
        expected_types = {
            "person",
            "family",
            "event",
            "place",
            "source",
            "citation",
            "media",
            "repository",
            "note",
        }
        assert entity_types == expected_types, "EntityType should have all entity types"

        # Test GetEntityType enum exists and has only person/family
        get_types = {e.value for e in GetEntityType}
        expected_get_types = {"person", "family"}
        assert get_types == expected_get_types, (
            "GetEntityType should only have person and family"
        )

    def test_person_event_reference_validation(self):
        """Test that PersonData properly validates event_ref_list structure."""
        # Test valid event reference format
        valid_data = {
            "primary_name": {
                "first_name": "Test",
                "surname_list": [{"surname": "Person"}],
            },
            "gender": 1,
            "event_ref_list": [
                {
                    "ref": "abc123def456",
                    "role": "Primary",  # Should be string, not object
                }
            ],
        }

        # This should work with proper validation
        person = PersonData(**valid_data)
        assert person.event_ref_list[0].ref == "abc123def456"
        assert person.event_ref_list[0].role == "Primary"

        # Test the incorrect format that caused Issue #9
        incorrect_data = {
            "primary_name": {
                "first_name": "Test",
                "surname_list": [{"surname": "Person"}],
            },
            "gender": 1,
            "event_ref_list": [
                {
                    "ref": "abc123def456",
                    "role": {
                        "string": "Primary"
                    },  # This incorrect format should be caught
                }
            ],
        }

        # With proper validation, this should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            PersonData(**incorrect_data)

        # The error should mention that role should be a string
        assert "role" in str(exc_info.value).lower()

    def test_delete_type_parameters_alignment(self):
        """DeleteTypeParams matches the usage guide's Destructive Operations
        section: type, handle, gramps_id, force - and nothing else."""
        fields = DeleteTypeParams.model_fields
        required_fields = {"type"}
        actual_required = {
            name for name, field in fields.items() if field.is_required()
        }
        assert actual_required == required_fields, (
            f"DeleteTypeParams required fields changed: {actual_required}"
        )
        expected_fields = {"type", "handle", "gramps_id", "force"}
        assert set(fields.keys()) == expected_fields, (
            f"DeleteTypeParams fields changed: {set(fields.keys())}"
        )

    def test_detach_reference_parameters_alignment(self):
        """DetachReferenceParams matches the usage guide: type, handle,
        gramps_id, list_name, ref_handle - and nothing else."""
        fields = DetachReferenceParams.model_fields
        required_fields = {"type", "list_name", "ref_handle"}
        actual_required = {
            name for name, field in fields.items() if field.is_required()
        }
        assert actual_required == required_fields, (
            f"DetachReferenceParams required fields changed: {actual_required}"
        )
        expected_fields = {
            "type",
            "handle",
            "gramps_id",
            "list_name",
            "ref_handle",
        }
        assert set(fields.keys()) == expected_fields, (
            f"DetachReferenceParams fields changed: {set(fields.keys())}"
        )

    def test_merge_type_parameters_alignment(self):
        """MergeTypeParams matches the usage guide, including the
        family-merge overrides (phoenix_father_handle/phoenix_mother_handle)."""
        fields = MergeTypeParams.model_fields
        required_fields = {"type"}
        actual_required = {
            name for name, field in fields.items() if field.is_required()
        }
        assert actual_required == required_fields, (
            f"MergeTypeParams required fields changed: {actual_required}"
        )
        expected_fields = {
            "type",
            "phoenix_handle",
            "phoenix_gramps_id",
            "titanic_handle",
            "titanic_gramps_id",
            "confirm",
            "phoenix_father_handle",
            "phoenix_mother_handle",
        }
        assert set(fields.keys()) == expected_fields, (
            f"MergeTypeParams fields changed: {set(fields.keys())}"
        )

    def test_undo_change_parameters_alignment(self):
        """UndoChangeParams matches the usage guide: transaction_id and the
        force escape hatch the upstream delete-undo bug requires."""
        fields = UndoChangeParams.model_fields
        required_fields = {"transaction_id"}
        actual_required = {
            name for name, field in fields.items() if field.is_required()
        }
        assert actual_required == required_fields, (
            f"UndoChangeParams required fields changed: {actual_required}"
        )
        expected_fields = {"transaction_id", "force"}
        assert set(fields.keys()) == expected_fields, (
            f"UndoChangeParams fields changed: {set(fields.keys())}"
        )
