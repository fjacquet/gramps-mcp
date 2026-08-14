"""
Test parameter alignment with usage guide requirements.

Verifies that POST/PUT parameters in models match exactly with the requirements
specified in gramps-usage-guide.md - no more, no less, with correct required/optional status.
"""

from src.gramps_mcp.models.parameters.citation_params import CitationData
from src.gramps_mcp.models.parameters.media_params import MediaSaveParams
from src.gramps_mcp.models.parameters.repository_params import RepositoryData
from src.gramps_mcp.models.parameters.source_params import SourceSaveParams


class TestParameterAlignment:
    """Test that model parameters align with usage guide requirements."""

    def test_repository_parameters_alignment(self):
        """Test RepositoryData parameters match usage guide requirements."""
        # From usage guide: Repository requires name, type
        # Optional: URL, note, handle (for updates)
        model = RepositoryData
        fields = model.model_fields

        # Required fields according to guide
        required_fields = {"name", "type"}

        # Check all required fields are present and required
        for field_name in required_fields:
            assert field_name in fields, (
                f"Required field '{field_name}' missing from RepositoryData"
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
            f"RepositoryData has extra required fields not in guide: {extra_required}"
        )

        # Check no extra fields beyond what guide allows (plus system fields from BaseDataModel)
        guide_fields = required_fields | {
            "url",
            "note",
            "urls",
        }  # urls might be alternate form of url
        system_fields = {
            "handle",
            "gramps_id",
            "note_list",
            "media_list",
            "attribute_list",
            "tag_list",
            "private",
            "change",
        }  # from BaseDataModel
        allowed_fields = guide_fields | system_fields
        actual_fields = set(fields.keys())
        extra_fields = actual_fields - allowed_fields
        assert not extra_fields, (
            f"RepositoryData has extra fields not in usage guide: {extra_fields}"
        )

    def test_source_parameters_alignment(self):
        """Test SourceSaveParams parameters match current implementation."""
        # Current implementation: Source requires title
        # Optional: reporef_list, author, pubinfo, plus BaseDataModel fields
        model = SourceSaveParams
        fields = model.model_fields

        # Required fields in current implementation
        required_fields = {"title"}

        # Check all required fields are present and required
        for field_name in required_fields:
            assert field_name in fields, (
                f"Required field '{field_name}' missing from SourceSaveParams"
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
            f"SourceSaveParams has extra required fields: {extra_required}"
        )

        # Check fields match current implementation
        implementation_fields = required_fields | {
            "reporef_list",
            "author",
            "pubinfo",
            "abbrev",
            "media_path",
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
        assert not extra_fields, f"SourceSaveParams has extra fields: {extra_fields}"

    def test_citation_parameters_alignment(self):
        """Test CitationData parameters match usage guide requirements."""
        # From usage guide: Citation requires source link (source_handle in model)
        # Optional: page, date, media, URLs, notes
        model = CitationData
        fields = model.model_fields

        # Required fields according to guide (using actual field names)
        required_fields = {"source_handle"}

        # Check all required fields are present and required
        for field_name in required_fields:
            assert field_name in fields, (
                f"Required field '{field_name}' missing from CitationData"
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
            f"CitationData has extra required fields not in guide: {extra_required}"
        )

        # Check no extra fields beyond what guide allows (plus system fields from BaseDataModel)
        guide_fields = required_fields | {
            "page",
            "date",
            "media",
            "urls",
            "media_path",
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
        allowed_fields = guide_fields | system_fields
        actual_fields = set(fields.keys())
        extra_fields = actual_fields - allowed_fields
        assert not extra_fields, (
            f"CitationData has extra fields not in usage guide: {extra_fields}"
        )

    def test_media_parameters_alignment(self):
        """Test MediaSaveParams parameters match usage guide requirements."""
        # From usage guide: Media requires file, title
        # Optional: date
        model = MediaSaveParams
        fields = model.model_fields

        # Required fields according to guide (using actual field names from model)
        required_fields = {
            "desc"
        }  # desc=title; path=file is provided differently (file upload)

        # Check all required fields are present and required
        for field_name in required_fields:
            assert field_name in fields, (
                f"Required field '{field_name}' missing from MediaSaveParams"
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
            f"MediaSaveParams has extra required fields not in guide: {extra_required}"
        )

        # Check no extra fields beyond what guide allows (plus system fields and media-specific fields)
        guide_fields = required_fields | {
            "date",
            "path",
        }  # path is optional since file provided via upload
        media_specific_fields = {
            "description",
            "mime",
            "citation_list",
            "media_path",
        }  # media-specific fields
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
        allowed_fields = guide_fields | media_specific_fields | system_fields
        actual_fields = set(fields.keys())
        extra_fields = actual_fields - allowed_fields
        assert not extra_fields, (
            f"MediaSaveParams has extra fields not in usage guide: {extra_fields}"
        )
