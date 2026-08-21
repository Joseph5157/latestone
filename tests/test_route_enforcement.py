"""ROLE-2 — the router refuses, and the sidebar stops advertising.

Hiding a link is not authorization. These cover the part that is: a direct URL
for a route the signed-in role may not have must be refused, refused
*explicitly* rather than folded into not-found, and refused before any data is
read.

The last of those is not a performance point. A denied page that has already
run its hierarchy queries has done work on behalf of someone who was not
entitled to ask, and every one of those queries is a place a partial result can
leak into a log or an error message.
"""
from __future__ import annotations

import pytest
from dash import html

from callbacks import navigation, routing
from components.app_sidebar import SIDEBAR_SECTIONS, sidebar_nav
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN
from tests.dash_tree import find_by_class, links, text_of


def session(role: str | None, authenticated: bool = True) -> dict:
    data = {"authenticated": authenticated}
    if role is not None:
        data.update(
            {"user_id": 7, "username": "someone", "full_name": "Some One", "role": role}
        )
    return data


# ---------------------------------------------------------------------------
# The routing decision, as a pure function
# ---------------------------------------------------------------------------


class TestRouteDecision:
    """`routing.route_decision` answers what to do before anything renders."""

    def test_unauthenticated_goes_to_login_not_forbidden(self):
        """A signed-out visitor has not been refused anything — they have not
        asked yet. Showing them 'no access' would be both wrong and alarming."""
        assert routing.route_decision({"authenticated": False}, "admin_devices") == (
            routing.DECISION_LOGIN
        )
        assert routing.route_decision(None, "overview") == routing.DECISION_LOGIN

    def test_a_session_without_an_identity_is_not_authorised(self):
        """The pre-ROLE-1 payload. It satisfies the flag the older callbacks
        read, but it names nobody, so it cannot be granted a role's access."""
        assert routing.route_decision({"authenticated": True}, "admin_devices") == (
            routing.DECISION_FORBIDDEN
        )

    def test_administrator_is_allowed_through(self):
        assert routing.route_decision(session(ADMINISTRATOR), "admin_devices") == (
            routing.DECISION_ALLOW
        )

    @pytest.mark.parametrize("role", [TECHNICIAN, GENERAL])
    @pytest.mark.parametrize(
        "route", ["admin_devices", "device_register", "admin_users"]
    )
    def test_admin_management_is_refused_by_direct_url(self, role, route):
        assert routing.route_decision(session(role), route) == (
            routing.DECISION_FORBIDDEN
        )

    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN, GENERAL])
    @pytest.mark.parametrize(
        "route", ["overview", "plant", "transformer", "device", "notifications", "reports"]
    )
    def test_monitoring_notifications_and_reports_stay_open(self, role, route):
        assert routing.route_decision(session(role), route) == routing.DECISION_ALLOW

    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN, GENERAL])
    def test_an_unknown_route_is_not_a_permissions_problem(self, role):
        """A typo'd URL must read as 'no such page', never as 'you may not
        have this page' — otherwise every mistyped path implies something
        exists behind it."""
        assert routing.route_decision(session(role), "unknown") == (
            routing.DECISION_ALLOW
        )

    def test_a_tampered_role_is_refused(self):
        assert routing.route_decision(session("superuser"), "overview") == (
            routing.DECISION_FORBIDDEN
        )


# ---------------------------------------------------------------------------
# The forbidden panel
# ---------------------------------------------------------------------------


class TestForbiddenPanel:
    def test_says_what_happened(self):
        from components.status_panels import forbidden_panel

        assert "access" in text_of(forbidden_panel()).lower()

    def test_is_not_the_not_found_panel(self):
        """Explicit, per the ROLE-1 decision: an authenticated user reaching
        for something they are not entitled to must not be told it does not
        exist."""
        from components.status_panels import forbidden_panel, not_found_panel

        assert "not found" not in text_of(forbidden_panel()).lower()
        assert find_by_class(forbidden_panel(), "status-panel--forbidden")
        assert not find_by_class(not_found_panel("plant"), "status-panel--forbidden")

    def test_offers_a_way_back_to_a_page_every_role_may_open(self):
        from components.status_panels import forbidden_panel

        assert ("Back to Fleet Overview", "/plants") in links(forbidden_panel())

    def test_names_no_role_username_or_route(self):
        """The panel tells the operator they cannot go there. It does not
        publish the policy, and it does not echo anything from the URL."""
        from components.status_panels import forbidden_panel

        rendered = text_of(forbidden_panel()).lower()
        for leak in ("administrator", "technician", "general", "admin/devices"):
            assert leak not in rendered


# ---------------------------------------------------------------------------
# Sidebar filtering
# ---------------------------------------------------------------------------


def rendered_labels(role: str | None) -> list[str]:
    nav = sidebar_nav(None, role)
    return [
        text_of(item)
        for item in nav.children
        if "app-sidebar__section-label" not in (item.className or "")
    ]


def section_titles(role: str | None) -> list[str]:
    nav = sidebar_nav(None, role)
    return [
        text_of(item)
        for item in nav.children
        if "app-sidebar__section-label" in (item.className or "")
    ]


class TestSidebarFiltering:
    def test_administrator_sees_every_item(self):
        expected = [
            label
            for _title, items in SIDEBAR_SECTIONS
            for _key, label, _href, _icon in items
        ]
        assert rendered_labels(ADMINISTRATOR) == expected

    @pytest.mark.parametrize("role", [TECHNICIAN, GENERAL])
    def test_admin_management_items_are_gone(self, role):
        labels = rendered_labels(role)
        assert "Devices" not in labels
        assert "Registration" not in labels
        assert "Users" not in labels

    @pytest.mark.parametrize("role", [TECHNICIAN, GENERAL])
    def test_what_remains_is_what_they_may_open(self, role):
        assert rendered_labels(role) == ["Overview", "Notifications", "Reports"]

    @pytest.mark.parametrize("role", [TECHNICIAN, GENERAL])
    def test_an_emptied_section_takes_its_heading_with_it(self, role):
        """Every Operations item is administrator-only, so the heading would
        otherwise sit over nothing."""
        assert "Operations" not in section_titles(role)
        assert "System" in section_titles(role)

    def test_administrator_keeps_both_section_headings(self):
        assert section_titles(ADMINISTRATOR) == ["Operations", "System"]

    @pytest.mark.parametrize("role", [TECHNICIAN, GENERAL])
    def test_the_routeless_assignments_placeholder_hides_with_its_section(self, role):
        """It has no route of its own, so the policy cannot speak about it.
        It belongs to Operations and goes where Operations goes."""
        assert "Assignments" not in rendered_labels(role)

    def test_no_link_points_somewhere_the_role_may_not_go(self):
        for role in (TECHNICIAN, GENERAL):
            hrefs = [href for _label, href in links(sidebar_nav(None, role))]
            assert not any(h.startswith("/admin") for h in hrefs)

    @pytest.mark.parametrize("role", [None, "superuser"])
    def test_an_unrecognised_role_gets_an_empty_nav(self, role):
        assert rendered_labels(role) == []

    def test_active_state_still_works_for_a_visible_item(self):
        nav = sidebar_nav("overview", TECHNICIAN)
        assert find_by_class(nav, "app-sidebar__link--active")

    def test_active_state_cannot_resurrect_a_hidden_item(self):
        """A technician arriving on a denied route must not light up an item
        that is not there."""
        nav = sidebar_nav("devices", TECHNICIAN)
        assert "Devices" not in text_of(nav)


class TestNavigationCallbackHelper:
    def test_role_is_read_off_the_session(self):
        assert navigation.session_role(session(TECHNICIAN)) == TECHNICIAN

    def test_a_session_without_an_identity_has_no_role(self):
        assert navigation.session_role({"authenticated": True}) is None

    def test_an_unauthenticated_session_has_no_role(self):
        assert navigation.session_role({"authenticated": False}) is None
        assert navigation.session_role(None) is None

    def test_a_tampered_role_is_not_accepted(self):
        assert navigation.session_role(session("superuser")) is None
