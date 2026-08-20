"""Phase ADMIN-0 — application shell: persistent collapsible sidebar as the
primary navigation, replacing the horizontal app_navigation bar.

Covers the sidebar component, its callback wiring (visibility, active state,
collapse), and the app-shell/content-region wrapper that reserves the
sidebar's width without touching each page's own max-width CSS.
"""
from __future__ import annotations

import importlib

import pytest
from dash import html
from dash.development.base_component import Component

import app as app_module
from callbacks import navigation as nav
from components.app_shell import CONTENT_ID, app_shell
from components.app_sidebar import (
    COLLAPSE_STORE_ID,
    HIDDEN_STYLE,
    NAV_ID,
    SHELL_ID,
    SIDEBAR_ID,
    SIDEBAR_SECTIONS,
    TOGGLE_ID,
    app_sidebar,
    app_sidebar_shell,
)
from pages import login
from tests.dash_tree import find_by_class, find_by_id, links, text_of


def _walk(node):
    if isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item)
        return
    if not isinstance(node, Component):
        return
    yield node
    yield from _walk(getattr(node, "children", None))


def collect_ids(node) -> set[str]:
    """Recursively collect every component `id` in a Dash layout tree."""
    found: set[str] = set()
    for n in _walk(node):
        node_id = getattr(n, "id", None)
        if isinstance(node_id, str):
            found.add(node_id)
    return found


def collect_id_occurrences(node) -> list[str]:
    return [
        getattr(n, "id", None)
        for n in _walk(node)
        if isinstance(getattr(n, "id", None), str)
    ]


GLOBAL_LAYOUT_IDS = collect_ids(app_module.app.layout)
LOGIN_LAYOUT_IDS = collect_ids(login.login_layout())


def _all_items():
    """Flatten SIDEBAR_SECTIONS into (key, label, href, abbr) tuples."""
    items = []
    for _section_title, section_items in SIDEBAR_SECTIONS:
        items.extend(section_items)
    return items


class TestSidebarItems:
    def test_information_architecture_in_order(self):
        labels = [label for _key, label, _href, _abbr in _all_items()]
        assert labels == [
            "Overview",
            "Devices", "Assignments", "Registration",
            "Notifications", "Reports", "Users",
        ]

    def test_sections_are_grouped_operations_and_system(self):
        titles = [title for title, _items in SIDEBAR_SECTIONS]
        assert titles == [None, "Operations", "System"]

    def test_every_routable_item_resolves_to_a_known_active_key(self):
        """Every item with a real href must highlight when its own route is active."""
        for key, _label, href, _abbr in _all_items():
            if href is None:
                continue
            assert nav.active_nav_key(href) == key, href

    def test_assignments_has_no_standalone_route(self):
        """ADMIN-0 explicitly does not build an Assignments page."""
        items = {label: href for _key, label, href, _abbr in _all_items()}
        assert items["Assignments"] is None

    def test_existing_routes_are_reused_not_reinvented(self):
        items = {label: href for _key, label, href, _abbr in _all_items()}
        assert items["Overview"] == "/plants"
        assert items["Devices"] == "/admin/devices"
        assert items["Registration"] == "/admin/devices/new"
        assert items["Notifications"] == "/notifications"
        assert items["Reports"] == "/reports"
        assert items["Users"] == "/admin/users"


class TestActiveNavKey:
    def test_fleet_overview_is_overview(self):
        assert nav.active_nav_key("/") == "overview"
        assert nav.active_nav_key("/plants") == "overview"
        assert nav.active_nav_key("/plants/") == "overview"

    def test_monitoring_drill_down_stays_under_overview(self):
        assert nav.active_nav_key("/plants/plant-01") == "overview"
        assert nav.active_nav_key("/plants/plant-01/plant-01-t1") == "overview"
        assert nav.active_nav_key("/devices/plant-01-t1-d1") == "overview"

    def test_each_destination_maps_to_its_own_item(self):
        assert nav.active_nav_key("/admin/devices") == "devices"
        assert nav.active_nav_key("/admin/devices/new") == "registration"
        assert nav.active_nav_key("/reports") == "reports"
        assert nav.active_nav_key("/notifications") == "notifications"
        assert nav.active_nav_key("/admin/users") == "users"

    def test_unknown_route_has_no_active_item(self):
        assert nav.active_nav_key("/nope") is None

    def test_none_pathname_is_root(self):
        assert nav.active_nav_key(None) == "overview"


class TestSidebarVisibility:
    def test_hidden_when_auth_store_is_empty(self):
        assert nav.sidebar_visibility(None) == {"display": "none"}
        assert nav.sidebar_visibility({}) == {"display": "none"}

    def test_hidden_when_not_authenticated(self):
        assert nav.sidebar_visibility({"authenticated": False}) == {"display": "none"}

    def test_shown_when_authenticated(self):
        assert nav.sidebar_visibility({"authenticated": True}) != {"display": "none"}

    def test_default_shell_style_is_hidden(self):
        """First paint is the login page, so the shell must start hidden."""
        assert app_sidebar_shell().style == {"display": "none"}

    def test_login_layout_renders_no_sidebar(self):
        assert SHELL_ID not in LOGIN_LAYOUT_IDS
        assert SIDEBAR_ID not in LOGIN_LAYOUT_IDS


class TestSidebarRendering:
    def test_renders_all_routable_destinations_in_order(self):
        """Each link's rendered text carries its label (plus a collapsed-view
        abbreviation prefix) and its href, in information-architecture order."""
        rendered = app_sidebar("devices")
        expected = [(label, href) for _k, label, href, _a in _all_items() if href is not None]
        rendered_links = links(rendered)
        assert len(rendered_links) == len(expected)
        for (text, href), (label, expected_href) in zip(rendered_links, expected):
            assert label in text
            assert href == expected_href

    def test_exactly_one_link_is_active_when_a_key_is_given(self):
        rendered = app_sidebar("devices")
        active = find_by_class(rendered, "app-sidebar__link--active")
        assert len(active) == 1
        assert "Devices" in text_of(active[0])

    def test_no_link_is_active_without_a_key(self):
        rendered = app_sidebar(None)
        assert find_by_class(rendered, "app-sidebar__link--active") == []

    def test_active_link_is_announced_to_assistive_technology(self):
        rendered = app_sidebar("reports")
        current = [n for n in _walk(rendered) if getattr(n, "aria-current", None) == "page"]
        assert len(current) == 1
        assert "Reports" in text_of(current[0])

    def test_inactive_items_carry_no_aria_current(self):
        rendered = app_sidebar("reports")
        current = [n for n in _walk(rendered) if getattr(n, "aria-current", None) == "page"]
        assert len(current) == 1, "exactly one item may claim the page"

    def test_assignments_renders_disabled_not_as_a_dead_link(self):
        rendered = app_sidebar(None)
        assert "Assignments" in text_of(rendered)
        disabled = find_by_class(rendered, "app-sidebar__link--disabled")
        assert len(disabled) == 1
        assert getattr(disabled[0], "aria-disabled", None) == "true"
        assert "Assignments" not in [label for label, _href in links(rendered)]

    def test_section_labels_render(self):
        rendered = app_sidebar(None)
        assert "Operations" in text_of(rendered)
        assert "System" in text_of(rendered)

    def test_toggle_control_is_present(self):
        rendered = app_sidebar(None)
        assert find_by_id(rendered, TOGGLE_ID) is not None


class TestCollapseBehavior:
    def test_toggle_flips_collapsed_state_on_click(self):
        assert nav.toggle_collapsed(1, {"collapsed": False}) == {"collapsed": True}
        assert nav.toggle_collapsed(1, {"collapsed": True}) == {"collapsed": False}

    def test_toggle_is_a_noop_without_a_real_click(self):
        assert nav.toggle_collapsed(None, {"collapsed": False}) == {"collapsed": False}
        assert nav.toggle_collapsed(0, {"collapsed": True}) == {"collapsed": True}

    def test_toggle_defaults_to_expanded_with_no_prior_state(self):
        assert nav.toggle_collapsed(1, None) == {"collapsed": True}

    def test_sidebar_class_reflects_collapsed_state(self):
        assert nav.sidebar_class({"collapsed": False}) == "app-sidebar"
        assert "app-sidebar--collapsed" in nav.sidebar_class({"collapsed": True}).split()

    def test_content_class_reflects_collapsed_state(self):
        assert nav.content_class({"collapsed": False}) == "app-shell__content"
        assert "app-shell__content--sidebar-collapsed" in nav.content_class({"collapsed": True}).split()

    def test_toggle_aria_state_reflects_collapsed(self):
        assert nav.toggle_aria_expanded({"collapsed": False}) == "true"
        assert nav.toggle_aria_expanded({"collapsed": True}) == "false"
        assert nav.toggle_aria_label({"collapsed": False}) == "Collapse sidebar"
        assert nav.toggle_aria_label({"collapsed": True}) == "Expand sidebar"

    def test_default_store_data_is_expanded(self):
        shell = app_sidebar_shell()
        store = find_by_id(shell, COLLAPSE_STORE_ID)
        assert store is not None
        assert store.data == {"collapsed": False}


class TestAppShell:
    def test_shell_wraps_sidebar_and_content_region(self):
        content = html.Div(id="page-content")
        shell = app_shell(app_sidebar_shell(), content)
        assert find_by_id(shell, SHELL_ID) is not None
        assert find_by_id(shell, CONTENT_ID) is not None
        assert find_by_id(shell, "page-content") is not None

    def test_content_region_id_is_distinct_from_page_content(self):
        assert CONTENT_ID != "page-content"


class TestWiring:
    def test_sidebar_ids_live_in_the_global_layout(self):
        """The sidebar callbacks fire on every route, so the shell must be
        global, and page-content must sit inside the new content region."""
        for component_id in (
            SHELL_ID, SIDEBAR_ID, NAV_ID, TOGGLE_ID, COLLAPSE_STORE_ID,
            CONTENT_ID, "page-content",
        ):
            assert component_id in GLOBAL_LAYOUT_IDS, component_id

    def test_old_horizontal_nav_module_is_retired(self):
        """The sidebar replaces app_navigation as the primary nav — it must
        not exist as a second navigation system alongside it."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("components.app_navigation")

    def test_old_horizontal_nav_css_class_is_gone_from_global_layout(self):
        assert not find_by_class(app_module.app.layout, "app-nav-shell")

    def test_no_duplicate_ids_in_global_layout(self):
        """Dash raises at runtime on duplicate ids; assert the invariant
        directly rather than relying on the app happening to boot in CI."""
        occurrences = collect_id_occurrences(app_module.app.layout)
        duplicates = {i for i in occurrences if occurrences.count(i) > 1}
        assert not duplicates, duplicates

    def test_sidebar_is_visually_distinct_from_equipment_selector(self):
        from components.equipment_selector import SHELL_ID as SELECTOR_SHELL_ID

        assert SHELL_ID != SELECTOR_SHELL_ID
        assert find_by_id(app_sidebar_shell(), SIDEBAR_ID) is not None

    def test_equipment_selector_shell_still_mounted_globally(self):
        """Requirement 10: equipment selector behaviour is unchanged — it
        must still be a global-layout shell, untouched by the shell rework."""
        from components.equipment_selector import SHELL_ID as SELECTOR_SHELL_ID

        assert SELECTOR_SHELL_ID in GLOBAL_LAYOUT_IDS
