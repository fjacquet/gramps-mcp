"""Tests for the pure spec comparison in scripts/check_spec_drift.py."""

import copy
import json

from scripts.check_spec_drift import SPEC_PATH, diff_specs


def _spec() -> dict:
    """Return the vendored OpenAPI spec as real data."""
    return json.loads(SPEC_PATH.read_text())


def test_identical_specs_report_nothing():
    """A spec compared with itself has no drift."""
    spec = _spec()
    assert diff_specs(spec, spec) == {
        "removed_params": [],
        "added_params": [],
        "removed_paths": [],
        "added_paths": [],
    }


def test_dropped_param_and_added_path_are_reported():
    """Removing a parameter and adding a path show up under their keys."""
    old = _spec()
    new = copy.deepcopy(old)
    path = next(p for p, item in old["paths"].items() if "get" in item)
    params = new["paths"][path]["get"].get("parameters", [])
    assert params, "vendored spec has no GET parameters to drop"
    dropped = params.pop()["name"]
    new["paths"]["/api/x/"] = {"get": {"parameters": []}}

    report = diff_specs(old, new)

    assert report["removed_params"] == [f"GET {path}:{dropped}"]
    assert report["added_paths"] == ["/api/x/"]
    assert report["added_params"] == []
    assert report["removed_paths"] == []

    reverse = diff_specs(new, old)
    assert reverse["added_params"] == [f"GET {path}:{dropped}"]
    assert reverse["removed_paths"] == ["/api/x/"]
