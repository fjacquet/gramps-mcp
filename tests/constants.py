"""Shared constants for the test suite.

Plain module, not a conftest - it is safe to import from any test module or
fixture file without relying on pytest's conftest-as-module behavior.
"""

# Reason: every record these fixtures create is named with this prefix so a
# run killed mid-test leaves objects that are obvious in the tree and easy to
# find and remove by hand.
PREFIX = "Pytest Lot5"
