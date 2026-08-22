"""Structural guard against fail-open scope arguments (ROLE-3 invariant 8).

The analogue of ROLE-2's test that fails when a route ships without a policy
entry. A scoped query added later cannot silently mean "show everything":
it must take its constraint as a keyword-only parameter with no default, so
every caller states what it wants.

WHEN YOU ADD A SCOPED QUERY, ADD ITS NAME HERE. That is the point of the
test — the list is the checklist.
"""
from __future__ import annotations

import inspect

import pytest

from repositories import plant_monitoring_repository as repo
from services import hierarchy_service

#: Repository functions whose results depend on which RTLs are visible.
SCOPED_REPOSITORY_FUNCTIONS = [
    "list_devices",
    "list_plants",
    "list_transformers",
]

#: Service functions that carry a DeviceScope down to them.
SCOPED_SERVICE_FUNCTIONS = [
    "list_devices",
    "list_plants",
    "list_transformers",
]


@pytest.mark.parametrize("name", SCOPED_REPOSITORY_FUNCTIONS)
def test_repository_scope_argument_is_keyword_only_and_undefaulted(name):
    parameter = inspect.signature(getattr(repo, name)).parameters["allowed_device_ids"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty, (
        f"{name} defaults allowed_device_ids — an omitted argument would "
        f"silently return the whole fleet"
    )


@pytest.mark.parametrize("name", SCOPED_SERVICE_FUNCTIONS)
def test_service_scope_argument_is_keyword_only_and_undefaulted(name):
    parameter = inspect.signature(getattr(hierarchy_service, name)).parameters["scope"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty, (
        f"{name} defaults scope — the fail-open seam closes at both "
        f"boundaries or at neither"
    )
