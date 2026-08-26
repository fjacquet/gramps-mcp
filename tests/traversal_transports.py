"""
Shared transport builders for the family-walk test modules.

Not collected by pytest: the filename does not start with test_. These
replace GrampsWebAPIClient._make_request over a synthetic tree, which is
the one seam the project allows tests to stand in for.
"""


def _ancestor_transport(tree: dict):
    """
    Build a _make_request replacement serving an ancestor tree with relations.

    Args:
        tree (dict): handle -> {"name": str, "families": list[dict]}, where
            each family carries optional "father", "mother", "frel", "mrel".
            Omitting frel/mrel omits the child_ref_list entry entirely, which
            is what the API returns for a plain birth link.

    Returns:
        Callable: An async callable matching _make_request's signature.
    """

    # Reason: patch.object installs this on the class, so it is looked up
    # through the instance and receives self as its first argument.
    async def _request(self, method=None, url=None, **kwargs):
        handle = url.rstrip("/").rsplit("/", 1)[-1]
        person = tree[handle]
        families = []
        for family in person.get("families", []):
            entry: dict = {
                "father_handle": family.get("father"),
                "mother_handle": family.get("mother"),
            }
            if "frel" in family or "mrel" in family:
                entry["child_ref_list"] = [
                    {
                        "ref": handle,
                        "frel": family.get("frel", "Birth"),
                        "mrel": family.get("mrel", "Birth"),
                    }
                ]
            families.append(entry)
        return {
            "handle": handle,
            "gramps_id": f"I{handle}",
            "profile": {
                "handle": handle,
                "gramps_id": f"I{handle}",
                "name_display": person["name"],
            },
            "extended": {"parent_families": families},
        }

    return _request


def _descendant_transport(tree: dict):
    """
    Build a _make_request replacement serving a descendant tree with relations.

    Args:
        tree (dict): handle -> {"name": str, "families": list[dict]}, where
            each family carries optional "father", "mother", and "children"
            as a list of {"ref", "frel", "mrel"}.

    Returns:
        Callable: An async callable matching _make_request's signature.
    """

    async def _request(self, method=None, url=None, **kwargs):
        handle = url.rstrip("/").rsplit("/", 1)[-1]
        person = tree[handle]
        families = [
            {
                "father_handle": family.get("father"),
                "mother_handle": family.get("mother"),
                "child_ref_list": family.get("children", []),
            }
            for family in person.get("families", [])
        ]
        return {
            "handle": handle,
            "gramps_id": f"I{handle}",
            "profile": {
                "handle": handle,
                "gramps_id": f"I{handle}",
                "name_display": person["name"],
            },
            "extended": {"families": families},
        }

    return _request
