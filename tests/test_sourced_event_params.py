"""
Unit tests for SourcedEventData.event_place validation. No server involved.

These assert the refusal happens on model construction, before
create_sourced_event_tool makes any network call - so an invalid place name
must never create a source, upload media, or create a citation.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.sourced_event_params import SourcedEventData


class TestSourcedEventPlaceValidation:
    """event_place takes a handle, never a name, checked before any save."""

    def test_place_name_is_rejected(self):
        with pytest.raises(ValidationError):
            SourcedEventData(
                source_title="Acte de naissance",
                event_type="Birth",
                event_place="Lyon",
            )

    def test_rejection_message_carries_guidance(self):
        """The raised error must tell the caller what to do, not just fail."""
        with pytest.raises(ValidationError) as exc_info:
            SourcedEventData(
                source_title="Acte de naissance",
                event_type="Birth",
                event_place="Lyon",
            )

        message = str(exc_info.value)
        assert "handle" in message
        assert "name" in message
        assert "find_type" in message
        assert "Lyon" in message

    def test_handle_is_accepted(self):
        params = SourcedEventData(
            source_title="Acte de naissance",
            event_type="Birth",
            event_place="103c4094f2414e2400974f979824",
        )

        assert params.event_place == "103c4094f2414e2400974f979824"

    def test_event_place_may_be_omitted(self):
        params = SourcedEventData(source_title="Acte de naissance", event_type="Birth")

        assert params.event_place is None
