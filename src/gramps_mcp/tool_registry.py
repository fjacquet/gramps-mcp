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
Tool registry: the single source of truth for every MCP tool.

Pure data - a tool name mapped to its description, its parameter schema
and its handler. It lives apart from server.py because that file was at
497 of the 500 lines the pre-commit hook allows, and this dict grows by a
block every time a tool is added.
"""

from typing import Any

from .models.parameters.analysis_params import (
    AncestorsParams,
    DescendantsParams,
    LivingStatusParams,
    RelationshipQueryParams,
    TimelineQueryParams,
    TreeInfoParams,
)
from .models.parameters.citation_params import CitationData
from .models.parameters.destructive_params import (
    DeleteTypeParams,
    DetachReferenceParams,
    MergeTypeParams,
    UndoChangeParams,
)
from .models.parameters.detection_params import (
    AuditQualityParams,
    FindDuplicatesParams,
    GeocodePlaceParams,
)
from .models.parameters.event_params import EventSaveParams
from .models.parameters.facts_params import FactsParams
from .models.parameters.family_params import FamilySaveParams
from .models.parameters.media_params import MediaSaveParams
from .models.parameters.note_params import NoteSaveParams
from .models.parameters.people_params import PersonData
from .models.parameters.place_params import PlaceSaveParams
from .models.parameters.repository_params import RepositoryData
from .models.parameters.simple_params import (
    SimpleFindParams,
    SimpleGetParams,
    SimpleSearchParams,
)
from .models.parameters.source_params import SourceSaveParams
from .models.parameters.sourced_event_params import SourcedEventData
from .models.parameters.tag_params import ManageTagsParams
from .models.parameters.transactions_params import TransactionHistoryParams

# Import all tool functions
from .tools import (
    create_citation_tool,
    create_event_tool,
    create_family_tool,
    create_media_tool,
    create_note_tool,
    create_person_tool,
    create_place_tool,
    create_repository_tool,
    create_source_tool,
    create_sourced_event_tool,
    find_anything_tool,
    get_ancestors_tool,
    get_descendants_tool,
    get_recent_changes_tool,
    get_tree_info_tool,
)
from .tools.destructive import (
    delete_type_tool,
    detach_reference_tool,
    merge_type_tool,
    undo_change_tool,
)
from .tools.detection import (
    audit_quality_tool,
    find_duplicates_tool,
    geocode_place_tool,
)
from .tools.records_tools import get_facts_tool, manage_tags_tool
from .tools.relationship_tools import (
    check_living_tool,
    get_relationship_tool,
    get_timeline_tool,
)
from .tools.search_basic import find_type_tool
from .tools.search_details import get_type_tool
from .tools.user_tools import ManageUsersParams, manage_users_tool

# Tool registry - single source of truth for all tools
TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    # Search & Retrieval Tools
    "find_type": {
        "description": (
            "Search any entity type using GQL - read gql://documentation "
            "resource first to understand syntax"
        ),
        "schema": SimpleFindParams,
        "handler": find_type_tool,
    },
    "find_anything": {
        "description": (
            "Text search across all record types - matches literal text "
            "within records, not logical combinations"
        ),
        "schema": SimpleSearchParams,
        "handler": find_anything_tool,
    },
    "get_type": {
        "description": "Get full details for person or family by handle or gramps_id",
        "schema": SimpleGetParams,
        "handler": get_type_tool,
    },
    # Data Management Tools
    "create_person": {
        "description": (
            "Create or update person information including family links "
            "and event associations"
        ),
        "schema": PersonData,
        "handler": create_person_tool,
    },
    "create_family": {
        "description": "Create or update family unit including member relationships",
        "schema": FamilySaveParams,
        "handler": create_family_tool,
    },
    "create_event": {
        "description": (
            "Create or update life event including person/place associations"
        ),
        "schema": EventSaveParams,
        "handler": create_event_tool,
    },
    "create_place": {
        "description": "Create or update geographic location",
        "schema": PlaceSaveParams,
        "handler": create_place_tool,
    },
    "create_source": {
        "description": "Create or update source document",
        "schema": SourceSaveParams,
        "handler": create_source_tool,
    },
    "create_citation": {
        "description": "Create or update citation including object associations",
        "schema": CitationData,
        "handler": create_citation_tool,
    },
    "create_note": {
        "description": "Create or update textual note including object associations",
        "schema": NoteSaveParams,
        "handler": create_note_tool,
    },
    "create_media": {
        "description": "Create or update media files including object associations",
        "schema": MediaSaveParams,
        "handler": create_media_tool,
    },
    "create_repository": {
        "description": "Create or update repository information",
        "schema": RepositoryData,
        "handler": create_repository_tool,
    },
    "create_sourced_event": {
        "description": (
            "Composite tool: create a citation and event in one call, "
            "auto-wiring the citation to the event (and optionally "
            "uploading media to the citation) - avoids copy-paste handle "
            "mistakes. Either create a new source via source_title, or "
            "reuse an existing one via source_handle; a source_title that "
            "matches an existing source's title is refused rather than "
            "silently reused or duplicated."
        ),
        "schema": SourcedEventData,
        "handler": create_sourced_event_tool,
    },
    # Analysis Tools
    "tree_stats": {
        "description": (
            "Get information about a specific tree including statistics "
            "(counts of people, families, events, etc.)"
        ),
        "schema": TreeInfoParams,
        "handler": get_tree_info_tool,
    },
    "get_descendants": {
        "description": (
            "Find all descendants of a person - WARNING: Very token-heavy "
            "operation, minimize generations (default: 5)"
        ),
        "schema": DescendantsParams,
        "handler": get_descendants_tool,
    },
    "get_ancestors": {
        "description": (
            "Find all ancestors of a person - WARNING: Very token-heavy "
            "operation, minimize generations (default: 5)"
        ),
        "schema": AncestorsParams,
        "handler": get_ancestors_tool,
    },
    "recent_changes": {
        "description": "Get recent changes/modifications to the family tree",
        "schema": TransactionHistoryParams,
        "handler": get_recent_changes_tool,
    },
    "get_relationship": {
        "description": (
            "Calculate the relationship between two people (accepts handle "
            "or gramps_id for each)"
        ),
        "schema": RelationshipQueryParams,
        "handler": get_relationship_tool,
    },
    "check_living": {
        "description": (
            "Check whether a person is living and get estimated birth/death "
            "dates (accepts handle or gramps_id)"
        ),
        "schema": LivingStatusParams,
        "handler": check_living_tool,
    },
    "get_timeline": {
        "description": (
            "Build a chronological timeline for a person, family, or group "
            "(scope: person/family/people/families)"
        ),
        "schema": TimelineQueryParams,
        "handler": get_timeline_tool,
    },
    "manage_tags": {
        "description": (
            "List, get, or create/update tags (action: list/get/create - no delete)"
        ),
        "schema": ManageTagsParams,
        "handler": manage_tags_tool,
    },
    "manage_users": {
        "description": (
            "List, get, or create Gramps Web user accounts with generated "
            "passwords (action: list/get/create - no update or delete). "
            "Requires an owner or admin account. Roles are capped at editor. "
            "WARNING: generated passwords appear in the response - have "
            "users change them on first login"
        ),
        "schema": ManageUsersParams,
        "handler": manage_users_tool,
    },
    "get_facts": {
        "description": "Get interesting facts and statistics about the tree",
        "schema": FactsParams,
        "handler": get_facts_tool,
    },
    "find_duplicates": {
        "description": (
            "Find candidate duplicate people, grouped into clusters with the "
            "record that would survive a merge already chosen. Read-only: it "
            "reports pairs the rules proved and, separately, pairs needing "
            "human arbitration. Feed a proved pair to merge_type"
        ),
        "schema": FindDuplicatesParams,
        "handler": find_duplicates_tool,
    },
    "audit_quality": {
        "description": (
            "Run the deterministic consistency rules over the tree and report "
            "anomalies by severity. Read-only. Rules needing a date are "
            "skipped when that date is unknown, so unknown data never "
            "produces a false positive"
        ),
        "schema": AuditQualityParams,
        "handler": audit_quality_tool,
    },
    "geocode_place": {
        "description": (
            "Resolve a free-text place name against authoritative gazetteers "
            "(France, Switzerland, worldwide fallback). Read-only: it returns "
            "the administrative chain, coordinates and a score, and flags an "
            "ambiguous match instead of picking one. Pass the result to "
            "create_place to record it"
        ),
        "schema": GeocodePlaceParams,
        "handler": geocode_place_tool,
    },
    "delete_type": {
        "description": (
            "Delete one record (person, family, event, place, source, "
            "citation, repository, media, note, tag). Refuses while other "
            "records still reference it, listing them; pass force=true to "
            "delete anyway and sever those references. Deletions can be "
            "reversed with undo_change"
        ),
        "schema": DeleteTypeParams,
        "handler": delete_type_tool,
    },
    "detach_reference": {
        "description": (
            "Remove one element from a record's list (event_ref_list, "
            "child_ref_list, media_list, note_list, citation_list, tag_list). "
            "Only the named list is rewritten; every other list keeps its "
            "merge-on-update behaviour. Refuses if the element is not in the list"
        ),
        "schema": DetachReferenceParams,
        "handler": detach_reference_tool,
    },
    "merge_type": {
        "description": (
            "Merge two records of the same type. The phoenix survives, the "
            "titanic is absorbed and every reference to it is repointed. "
            "Returns a preview and changes nothing unless confirm=true. "
            "Tags cannot be merged"
        ),
        "schema": MergeTypeParams,
        "handler": merge_type_tool,
    },
    "undo_change": {
        "description": (
            "Undo one recorded transaction by id, reversing every object "
            "change it made. Use recent_changes to find the id. This is the "
            "recovery path for a delete or merge that went the wrong way. "
            "force=true is currently required to undo a deletion, because "
            "of an upstream Gramps Web bug that misreports the object as "
            "changed; see the force parameter's description for the risk"
        ),
        "schema": UndoChangeParams,
        "handler": undo_change_tool,
    },
}
