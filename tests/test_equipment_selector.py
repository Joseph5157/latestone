"""Tests for the cross-plant equipment selector and callback<->layout wiring.

Two things are covered here, and the second matters more than the first.

The feature tests exercise the cascade and the navigation guard. The *wiring*
tests assert that every id a callback references actually exists in some
layout. That is the guard the codebase was missing: `hierarchy_selector()` had
four callbacks driving three dropdowns that no layout ever rendered, so every
navigation raised a nonexistent-Output `ReferenceError` in the browser while
the Python suite stayed green (docs/CODE_AUDIT.md finding 2).
"""
from __future__ import annotations

import pytest
from dash import no_update
from dash.development.base_component import Component

import app as app_module
from callbacks import equipment_selector as sel
from pages import device_dashboard, login, plant_detail, plants_overview, transformer_detail


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def collect_ids(node) -> set[str]:
    """Recursively collect every component `id` in a Dash layout tree."""
    found: set[str] = set()

    def walk(n):
        if isinstance(n, (list, tuple)):
            for item in n:
                walk(item)
            return
        if not isinstance(n, Component):
            return
        node_id = getattr(n, "id", None)
        if isinstance(node_id, str):
            found.add(node_id)
        walk(getattr(n, "children", None))

    walk(node)
    return found


def parse_output_ids(output_spec: str) -> set[str]:
    """Pull component ids out of a Dash callback `output` string.

    Single output is "my-id.prop"; multi-output is "..a.prop...b.prop..".
    """
    spec = output_spec.strip(".")
    return {chunk.rsplit(".", 1)[0] for chunk in spec.split("...") if chunk}


def callback_reference_ids(dash_app) -> set[str]:
    """Every component id referenced by any registered callback."""
    referenced: set[str] = set()
    for entry in dash_app._callback_list:
        referenced |= parse_output_ids(entry["output"])
        for dep in list(entry["inputs"]) + list(entry["state"]):
            if isinstance(dep.get("id"), str):
                referenced.add(dep["id"])
    return referenced


GLOBAL_LAYOUT_IDS = collect_ids(app_module.app.layout)

PAGE_LAYOUT_IDS = (
    collect_ids(login.login_layout())
    | collect_ids(plants_overview.layout())
    | collect_ids(plant_detail.layout("Plant"))
    | collect_ids(transformer_detail.layout("Plant", "T1", "p1"))
    | collect_ids(device_dashboard.layout("Plant", "T1", "D1"))
)

MOUNTABLE_IDS = GLOBAL_LAYOUT_IDS | PAGE_LAYOUT_IDS


# --------------------------------------------------------------------------
# Wiring integrity — the guard the previous rounds lacked
# --------------------------------------------------------------------------

class TestCallbackLayoutWiring:
    def test_every_callback_id_exists_in_some_layout(self):
        """No callback may reference a component no layout ever renders."""
        orphans = callback_reference_ids(app_module.app) - MOUNTABLE_IDS
        assert not orphans, (
            "Callbacks reference ids that exist in no layout: "
            f"{sorted(orphans)}. Every navigation would raise a Dash "
            "ReferenceError for these."
        )

    def test_selector_ids_live_in_the_global_layout(self):
        """The selector's callbacks fire on every route, so it must be global.

        If these ids only existed inside a page layout, the callbacks would
        throw on every route that does not render that page.
        """
        for component_id in (
            sel.SHELL_ID,
            sel.PLANT_ID,
            sel.TRANSFORMER_ID,
            sel.DEVICE_ID,
        ):
            assert component_id in GLOBAL_LAYOUT_IDS

    def test_selector_is_present_on_the_login_route_too(self):
        """Mounted-but-hidden, not unmounted — that is what keeps callbacks safe."""
        assert sel.SHELL_ID in GLOBAL_LAYOUT_IDS
        assert sel.SHELL_ID not in collect_ids(login.login_layout())


# --------------------------------------------------------------------------
# Visibility
# --------------------------------------------------------------------------

class TestSelectorVisibility:
    def test_hidden_when_auth_store_is_empty(self):
        assert sel.selector_visibility(None) == {"display": "none"}
        assert sel.selector_visibility({}) == {"display": "none"}

    def test_hidden_when_not_authenticated(self):
        assert sel.selector_visibility({"authenticated": False}) == {"display": "none"}

    def test_shown_when_authenticated(self):
        assert sel.selector_visibility({"authenticated": True}) != {"display": "none"}

    def test_default_shell_style_is_hidden(self):
        """First paint is the login page, so the shell must start hidden."""
        from components.equipment_selector import equipment_selector_shell

        assert equipment_selector_shell().style == {"display": "none"}


# --------------------------------------------------------------------------
# Plant options are gated on authentication
# --------------------------------------------------------------------------

class TestPlantOptionsAuthGate:
    def test_no_query_runs_before_authentication(self, monkeypatch):
        """An unauthenticated visitor must not trigger a hierarchy query."""
        def explode(*_args, **_kwargs):
            raise AssertionError("hierarchy_service was queried before login")

        monkeypatch.setattr(sel.hierarchy_service, "list_plants", explode)
        assert sel.plant_options({"authenticated": False}) == []
        assert sel.plant_options(None) == []

    def test_plants_are_listed_once_authenticated(self, monkeypatch):
        monkeypatch.setattr(
            sel.hierarchy_service,
            "list_plants",
            lambda: [_plant("p1", "Alpha"), _plant("p2", "Beta")],
        )
        assert sel.plant_options({"authenticated": True}) == [
            {"label": "Alpha", "value": "p1"},
            {"label": "Beta", "value": "p2"},
        ]


# --------------------------------------------------------------------------
# Cascade
# --------------------------------------------------------------------------

class TestCascade:
    def test_transformers_disabled_until_a_plant_is_chosen(self):
        options, disabled, value = sel.transformer_options(None)
        assert (options, disabled, value) == ([], True, None)

    def test_transformers_listed_for_a_plant(self, monkeypatch):
        monkeypatch.setattr(
            sel.hierarchy_service,
            "list_transformers",
            lambda plant_id: [_transformer("p1-t1", "T1")],
        )
        options, disabled, value = sel.transformer_options("p1")
        assert options == [{"label": "T1", "value": "p1-t1"}]
        assert disabled is False
        assert value is None, "changing plant must clear the stale transformer"

    def test_devices_disabled_until_a_transformer_is_chosen(self):
        options, disabled, value = sel.device_options(None)
        assert (options, disabled, value) == ([], True, None)

    def test_devices_listed_for_a_transformer(self, monkeypatch):
        monkeypatch.setattr(
            sel.hierarchy_service,
            "list_devices",
            lambda transformer_id: [_device("p1-t1-d1", "D1")],
        )
        options, disabled, value = sel.device_options("p1-t1")
        assert options == [{"label": "D1", "value": "p1-t1-d1"}]
        assert disabled is False
        assert value is None, "changing transformer must clear the stale device"

    def test_clearing_the_plant_collapses_the_whole_cascade(self, monkeypatch):
        """plant -> None must not leave a selectable device behind."""
        _, _, transformer_value = sel.transformer_options(None)
        _, device_disabled, device_value = sel.device_options(transformer_value)
        assert device_disabled is True
        assert device_value is None


# --------------------------------------------------------------------------
# Navigation, including the feedback-loop guard
# --------------------------------------------------------------------------

class TestDeviceNavigation:
    def test_no_navigation_without_a_device(self):
        assert sel.device_navigation_target(None, {}) is no_update

    def test_navigates_to_the_selected_device(self):
        assert sel.device_navigation_target("p1-t1-d1", {}) == "/devices/p1-t1-d1"

    def test_jumps_across_plants(self):
        """Phase 16 Step 3: reach a device under a different plant directly."""
        context = {"route": "device", "device_id": "p1-t1-d1"}
        assert sel.device_navigation_target("p9-t2-d4", context) == "/devices/p9-t2-d4"

    def test_does_not_renavigate_to_the_current_device(self):
        """Guards the cascade against a navigate -> re-render -> navigate loop."""
        context = {"route": "device", "device_id": "p1-t1-d1"}
        assert sel.device_navigation_target("p1-t1-d1", context) is no_update


# --------------------------------------------------------------------------
# Minimal record stand-ins (avoids importing repository dataclasses)
# --------------------------------------------------------------------------

class _Rec:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _plant(plant_id, name):
    return _Rec(plant_id=plant_id, name=name)


def _transformer(transformer_id, code):
    return _Rec(transformer_id=transformer_id, transformer_code=code)


def _device(device_id, code):
    return _Rec(device_id=device_id, device_code=code)
