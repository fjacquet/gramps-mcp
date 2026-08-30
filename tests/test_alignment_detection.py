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

"""
Test parameter alignment with usage guide requirements.

Verifies that the read-only detection tools' parameter models match exactly
what gramps-usage-guide.md documents - no more, no less. Pydantic's default
`extra="ignore"` lets a call succeed while exercising nothing, so an
undocumented field is one an assistant can pass without ever being told it
does nothing: `find_duplicates`' own `threshold` field was exactly this
before it was removed - accepted, validated, and never read by the tool.
When this test fails, fix the guide first and this file second - never this
file alone.
"""

from src.gramps_mcp.models.parameters.detection_params import (
    AuditQualityParams,
    FindDuplicatesParams,
    GeocodePlaceParams,
)


class TestParameterAlignment:
    """Test that detection parameter models align with usage guide requirements."""

    def test_find_duplicates_parameters_alignment(self):
        """Test FindDuplicatesParams parameters match the usage guide."""
        model = FindDuplicatesParams
        fields = model.model_fields

        # No required fields - find_duplicates() with no arguments scans
        # the whole tree.
        required_fields: set[str] = set()
        actual_required = {
            name for name, field in fields.items() if field.is_required()
        }
        extra_required = actual_required - required_fields
        assert not extra_required, (
            f"FindDuplicatesParams has extra required fields: {extra_required}"
        )

        # Documented in gramps-usage-guide.md's `### find_duplicates` section.
        implementation_fields = required_fields | {"limit"}
        actual_fields = set(fields.keys())
        extra_fields = actual_fields - implementation_fields
        assert not extra_fields, (
            f"FindDuplicatesParams has extra fields not in usage guide: {extra_fields}"
        )

    def test_audit_quality_parameters_alignment(self):
        """Test AuditQualityParams parameters match the usage guide."""
        model = AuditQualityParams
        fields = model.model_fields

        # No required fields - audit_quality() with no arguments scans the
        # whole tree.
        required_fields: set[str] = set()
        actual_required = {
            name for name, field in fields.items() if field.is_required()
        }
        extra_required = actual_required - required_fields
        assert not extra_required, (
            f"AuditQualityParams has extra required fields: {extra_required}"
        )

        # Documented in gramps-usage-guide.md's `### audit_quality` section.
        implementation_fields = required_fields | {"limit", "severity"}
        actual_fields = set(fields.keys())
        extra_fields = actual_fields - implementation_fields
        assert not extra_fields, (
            f"AuditQualityParams has extra fields not in usage guide: {extra_fields}"
        )

    def test_geocode_place_parameters_alignment(self):
        """Test GeocodePlaceParams parameters match the usage guide."""
        model = GeocodePlaceParams
        fields = model.model_fields

        # `query` is the only required field - geocode_place(query=...).
        required_fields = {"query"}
        actual_required = {
            name for name, field in fields.items() if field.is_required()
        }
        extra_required = actual_required - required_fields
        assert not extra_required, (
            f"GeocodePlaceParams has extra required fields: {extra_required}"
        )
        missing_required = required_fields - actual_required
        assert not missing_required, (
            f"GeocodePlaceParams is missing required fields: {missing_required}"
        )

        # Documented in gramps-usage-guide.md's `### geocode_place` section.
        implementation_fields = required_fields | {"min_score"}
        actual_fields = set(fields.keys())
        extra_fields = actual_fields - implementation_fields
        assert not extra_fields, (
            f"GeocodePlaceParams has extra fields not in usage guide: {extra_fields}"
        )
