"""Phase 1 — application navigation: active state, auth gating, rendering.

Covers the app-level nav component and its callback wiring, mirroring the
equipment selector test file's split: pure-function assertions (active key,
visibility, rendering) plus the wiring guard that every nav id a callback
references actually exists in the global layout.
"""
from __future__ import annotations

from dash.development.base_component import Component

import app as app_module
from callbacks import navigation as nav
from components.app_navigation import (
    HIDDEN_STYLE,
    NAV_ID,
    NAV_ITEMS,
    SHELL_ID,
    app_navigation,
    app_navigation_shell,
)
from pages import login
from pages.placeholder import PENDING_MESSAGE, placeholder_layout
from tests.dash_tree import find_by_class, find_by_id, links, text_of


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


GLOBAL_LAYOUT_IDS = collect_ids(app_module.app.layout)
LOGIN_LAYOUT_IDS = collect_ids(login.login_layout())


class TestNavItems:
    def test_five_application_destinations_in_order(self):
        assert [item[0] for item in NAV_ITEMS] == [
            "overview", "devices", "reports", "notifications", "administration",
        ]

    def test_monitoring_is_not_a_top_level_destination(self):
        """The Fleet -> Plant -> Transformer -> Device hierarchy is the
        monitoring workflow, not a nav destination."""
        assert "monitoring" not in [item[0] for item in NAV_ITEMS]

    def test_every_destination_resolves_to_a_known_route(self):
        """All new nav links must resolve — no 404 destinations."""
        for _key, _label, href in NAV_ITEMS:
            assert nav.active_nav_key(href) is not None, href


class TestActiveNavKey:
    def test_fleet_overview_is_overview(self):
        assert nav.active_nav_key("/") == "overview"
        assert nav.active_nav_key("/plants") == "overview"
        assert nav.active_nav_key("/plants/") == "overview"

    def test_monitoring_drill_down_stays_under_overview(self):
        """The drill-down is the monitoring workflow inside Overview, so
        Overview stays highlighted on plant/transformer/device routes."""
        assert nav.active_nav_key("/plants/plant-01") == "overview"
        assert nav.active_nav_key("/plants/plant-01/plant-01-t1") == "overview"
        assert nav.active_nav_key("/devices/plant-01-t1-d1") == "overview"

    def test_placeholder_destinations_map_to_their_own_item(self):
        assert nav.active_nav_key("/admin/devices") == "devices"
        assert nav.active_nav_key("/reports") == "reports"
        assert nav.active_nav_key("/notifications") == "notifications"
        assert nav.active_nav_key("/admin/users") == "administration"

    def test_unknown_route_has_no_active_item(self):
        assert nav.active_nav_key("/nope") is None
        assert nav.active_nav_key(None) == "overview"  # None == root, like routing


class TestNavVisibility:
    def test_hidden_when_auth_store_is_empty(self):
        assert nav.nav_visibility(None) == {"display": "none"}
        assert nav.nav_visibility({}) == {"display": "none"}

    def test_hidden_when_not_authenticated(self):
        assert nav.nav_visibility({"authenticated": False}) == {"display": "none"}

    def test_shown_when_authenticated(self):
        assert nav.nav_visibility({"authenticated": True}) != {"display": "none"}

    def test_default_shell_style_is_hidden(self):
        """First paint is the login page, so the shell must start hidden."""
        assert app_navigation_shell().style == {"display": "none"}

    def test_login_layout_renders_no_app_navigation(self):
        assert SHELL_ID not in LOGIN_LAYOUT_IDS
        assert NAV_ID not in LOGIN_LAYOUT_IDS


class TestNavRendering:
    def test_renders_all_destinations_in_order(self):
        rendered = app_navigation("devices")
        assert links(rendered) == [(label, href) for _k, label, href in NAV_ITEMS]

    def test_exactly_one_link_is_active_when_a_key_is_given(self):
        rendered = app_navigation("devices")
        active = find_by_class(rendered, "app-nav__link--active")
        assert len(active) == 1
        assert text_of(active[0]).strip() == "Devices"

    def test_no_link_is_active_without_a_key(self):
        rendered = app_navigation(None)
        assert find_by_class(rendered, "app-nav__link--active") == []

    def test_active_link_is_announced_to_assistive_technology(self):
        rendered = app_navigation("reports")
        current = [
            n for n in _walk(rendered)
            if getattr(n, "aria-current", None) == "page"
        ]
        assert len(current) == 1
        assert text_of(current[0]).strip() == "Reports"

    def test_inactive_links_carry_no_aria_current(self):
        rendered = app_navigation("reports")
        current = [
            n for n in _walk(rendered)
            if getattr(n, "aria-current", None) == "page"
        ]
        assert len(current) == 1, "exactly one nav item may claim the page"
        assert text_of(current[0]).strip() == "Reports"


class TestPlaceholderLayout:
    def test_renders_title_and_purpose(self):
        page = placeholder_layout("Reports", "View and generate reports.")
        rendered = text_of(page)
        assert "Reports" in rendered
        assert "View and generate reports." in rendered

    def test_renders_the_pending_scope_message(self):
        assert PENDING_MESSAGE in text_of(placeholder_layout("Reports", "purpose"))

    def test_invents_no_forms_fields_or_workflows(self):
        """No inputs, dropdowns, buttons, tables or role/report-type widgets."""
        from dash import dcc, html as html_mod

        page = placeholder_layout("Notifications", "purpose")
        banned_types = (dcc.Input, dcc.Dropdown, html_mod.Button, html_mod.Table)
        offenders = [n for n in _walk(page) if isinstance(n, banned_types)]
        assert not offenders, f"placeholder must not invent controls: {offenders}"


def _walk(node):
    if isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item)
        return
    if not isinstance(node, Component):
        return
    yield node
    yield from _walk(getattr(node, "children", None))


class TestWiring:
    def test_nav_ids_live_in_the_global_layout(self):
        """The nav callbacks fire on every route, so the shell must be global."""
        for component_id in (SHELL_ID, NAV_ID):
            assert component_id in GLOBAL_LAYOUT_IDS

    def test_app_navigation_is_visually_distinct_from_equipment_selector(self):
        """The two bars are separate components, not one merged control."""
        from components.equipment_selector import SHELL_ID as SELECTOR_SHELL_ID

        assert SHELL_ID != SELECTOR_SHELL_ID
        assert find_by_id(app_navigation_shell(), NAV_ID) is not None