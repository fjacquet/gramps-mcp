"""
Unit tests for the breadth-first family-graph walk.

These patch the transport seam (GrampsWebAPIClient._make_request) over a
synthetic tree and need no server. Assertions read the returned
TraversalResult, never the patch's call arguments.
"""

from unittest.mock import patch

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.traversal import (
    TraversalResult,
    resolve_person_handle,
    walk_ancestors,
    walk_descendants,
)

# A synthetic four-generation tree.
#   h1 - child of family f1 (father h2, mother h3)
#   h2 - child of family f2 (father h4, mother h5)
#   h3 - no parents
PEOPLE = {
    "h1": {"gramps_id": "I0001", "name": "JACQUET, Frederic", "parents": ("h2", "h3")},
    "h2": {"gramps_id": "I0042", "name": "JACQUET, Yvan", "parents": ("h4", "h5")},
    "h3": {"gramps_id": "I0129", "name": "MARIAUD, Odile", "parents": None},
    "h4": {"gramps_id": "I0107", "name": "JACQUET, Joseph", "parents": None},
    "h5": {"gramps_id": "I0108", "name": "RIPPERT, Marie", "parents": None},
}


def _person_payload(handle: str, people: dict) -> dict:
    """
    Build the response GET /people/{handle} gives for an ancestor walk.

    Args:
        handle (str): Person handle being fetched.
        people (dict): The synthetic tree to read from.

    Returns:
        dict: A person payload with profile and extended.parent_families.
    """
    person = people[handle]
    parents = person["parents"]
    families = []
    if parents:
        families.append({"father_handle": parents[0], "mother_handle": parents[1]})
    return {
        "handle": handle,
        "gramps_id": person["gramps_id"],
        "profile": {
            "handle": handle,
            "gramps_id": person["gramps_id"],
            "name_display": person["name"],
        },
        "extended": {"parent_families": families},
    }


def _ancestor_transport(people: dict = PEOPLE, failures: dict | None = None):
    """
    Build a _make_request replacement serving the synthetic tree.

    Args:
        people (dict): The synthetic tree.
        failures (dict | None): handle -> exception to raise for that person.

    Returns:
        Callable: An async callable matching _make_request's signature.
    """
    failures = failures or {}

    # Reason: patch.object installs this on the class, so it is looked up
    # through the instance and receives self as its first argument. Omitting
    # self here makes the client's url= land in method= and every test
    # misbehaves in a way that looks like a traversal bug.
    async def _request(self, method=None, url=None, **kwargs):
        handle = url.rstrip("/").rsplit("/", 1)[-1]
        if handle in failures:
            raise failures[handle]
        return _person_payload(handle, people)

    return _request


class TestResolvePersonHandle:
    async def test_returns_the_handle_for_a_known_gramps_id(self):
        async def _request(self, method=None, url=None, **kwargs):
            return [{"handle": "h1", "gramps_id": "I0001"}]

        with patch.object(GrampsWebAPIClient, "_make_request", new=_request):
            handle = await resolve_person_handle(
                GrampsWebAPIClient(), "default", "I0001"
            )
        assert handle == "h1"

    async def test_returns_none_when_no_person_matches(self):
        async def _request(self, method=None, url=None, **kwargs):
            return []

        with patch.object(GrampsWebAPIClient, "_make_request", new=_request):
            handle = await resolve_person_handle(
                GrampsWebAPIClient(), "default", "I9999"
            )
        assert handle is None


class TestWalkAncestors:
    async def test_reaches_every_ancestor_within_the_generation_limit(self):
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport()
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 3)
        assert set(result.nodes) == {"h1", "h2", "h3", "h4", "h5"}
        assert result.edges["h1"] == ["h2", "h3"]
        assert result.edges["h2"] == ["h4", "h5"]
        assert result.truncated_by_cap is False

    async def test_generation_limit_stops_the_walk(self):
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport()
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 2)
        assert set(result.nodes) == {"h1", "h2", "h3"}
        assert "h4" not in result.edges.get("h2", [])

    async def test_a_person_reached_twice_is_recorded_once_and_marked(self):
        # h1's father and mother share the same parents - a cousin marriage,
        # which this tree really contains.
        people = {
            "h1": {"gramps_id": "I0001", "name": "A", "parents": ("h2", "h3")},
            "h2": {"gramps_id": "I0002", "name": "B", "parents": ("h4", "h5")},
            "h3": {"gramps_id": "I0003", "name": "C", "parents": ("h4", "h5")},
            "h4": {"gramps_id": "I0004", "name": "D", "parents": None},
            "h5": {"gramps_id": "I0005", "name": "E", "parents": None},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(people)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 5)
        assert set(result.nodes) == {"h1", "h2", "h3", "h4", "h5"}
        assert result.revisited == {"h4", "h5"}

    async def test_a_cycle_does_not_hang_the_walk(self):
        # A person who is their own grandparent cannot happen in real data,
        # but a corrupted tree can express it and must not spin forever.
        people = {
            "h1": {"gramps_id": "I0001", "name": "A", "parents": ("h2", "h2")},
            "h2": {"gramps_id": "I0002", "name": "B", "parents": ("h1", "h1")},
        }
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport(people)
        ):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 10)
        assert set(result.nodes) == {"h1", "h2"}

    async def test_visit_cap_stops_the_walk_and_reports_what_is_left(self):
        with patch.object(
            GrampsWebAPIClient, "_make_request", new=_ancestor_transport()
        ):
            result = await walk_ancestors(
                GrampsWebAPIClient(), "default", "h1", 5, visit_cap=3
            )
        assert len(result.nodes) <= 3
        assert result.truncated_by_cap is True
        assert result.unexplored > 0

    async def test_one_failing_person_does_not_lose_the_rest_of_the_level(self):
        transport = _ancestor_transport(failures={"h3": RuntimeError("HTTP 500")})
        with patch.object(GrampsWebAPIClient, "_make_request", new=transport):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 3)
        assert "HTTP 500" in result.failed["h3"]
        assert set(result.nodes) >= {"h1", "h2", "h4", "h5"}
        assert result.truncated_by_cap is False

    async def test_a_failing_root_yields_an_empty_walk_not_an_exception(self):
        transport = _ancestor_transport(failures={"h1": RuntimeError("HTTP 500")})
        with patch.object(GrampsWebAPIClient, "_make_request", new=transport):
            result = await walk_ancestors(GrampsWebAPIClient(), "default", "h1", 3)
        assert result.nodes == {}
        assert "h1" in result.failed


class TestWalkDescendants:
    async def test_follows_child_ref_list_down_the_generations(self):
        children = {"h1": ["h2", "h3"], "h2": ["h4"], "h3": [], "h4": []}
        names = {"h1": "A", "h2": "B", "h3": "C", "h4": "D"}

        async def _request(self, method=None, url=None, **kwargs):
            handle = url.rstrip("/").rsplit("/", 1)[-1]
            return {
                "handle": handle,
                "profile": {
                    "handle": handle,
                    "gramps_id": f"I{handle}",
                    "name_display": names[handle],
                },
                "extended": {
                    "families": [
                        {"child_ref_list": [{"ref": c} for c in children[handle]]}
                    ]
                },
            }

        with patch.object(GrampsWebAPIClient, "_make_request", new=_request):
            result = await walk_descendants(GrampsWebAPIClient(), "default", "h1", 3)
        assert set(result.nodes) == {"h1", "h2", "h3", "h4"}
        assert result.edges["h1"] == ["h2", "h3"]
        assert result.edges["h2"] == ["h4"]

    async def test_returns_a_traversal_result(self):
        async def _request(self, method=None, url=None, **kwargs):
            return {
                "handle": "h1",
                "profile": {"handle": "h1", "gramps_id": "I0001", "name_display": "A"},
                "extended": {"families": []},
            }

        with patch.object(GrampsWebAPIClient, "_make_request", new=_request):
            result = await walk_descendants(GrampsWebAPIClient(), "default", "h1", 3)
        assert isinstance(result, TraversalResult)
        assert result.root == "h1"
