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
from services.auth_service import AuthenticatedUser
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN
from tests.dash_tree import find_by_class, links, text_of


def session(role: str | None, authenticated: bool = True) -> dict:
    data = {"authenticated": authenticated}
    if role is not None:
        data.update(
            {"user_id": 7, "username": "someone", "full_name": "Some One", "role": role}
        )
    return data


def identity(role: str) -> AuthenticatedUser:
    """A trusted identity for `route_decision`'s tests.

    AUTH-HARDEN-1: `route_decision` takes the CURRENT TRUSTED identity
    directly — never the browser's `auth-store` payload the old `session()`
    helper above builds. There is no dict to tamper here: the object either
    exists (because `current_identity()` re-read a real, active `users` row)
    or it does not.
    """
    return AuthenticatedUser(user_id=7, username="someone", full_name="Some One", role=role)


# ---------------------------------------------------------------------------
# The routing decision, as a pure function
# ---------------------------------------------------------------------------


class TestRouteDecision:
    """`routing.route_decision` answers what to do before anything renders."""

    def test_no_trusted_identity_goes_to_login_not_forbidden(self):
        """No trusted server session — whether nobody ever signed in, or the
        session the server once trusted is gone (deleted, deactivated,
        expired) — has not been refused anything. Showing 'no access' would be
        both wrong and alarming; both cases read the same: sign in (again)."""
        assert routing.route_decision(None, "admin_devices") == routing.DECISION_LOGIN
        assert routing.route_decision(None, "overview") == routing.DECISION_LOGIN

    def test_administrator_is_allowed_through(self):
        assert routing.route_decision(identity(ADMINISTRATOR), "admin_devices") == (
            routing.DECISION_ALLOW
        )

    @pytest.mark.parametrize("role", [TECHNICIAN, GENERAL])
    @pytest.mark.parametrize(
        "route", ["admin_devices", "device_register", "admin_users", "audit_log"]
    )
    def test_admin_management_is_refused_by_direct_url(self, role, route):
        assert routing.route_decision(identity(role), route) == (
            routing.DECISION_FORBIDDEN
        )

    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN, GENERAL])
    @pytest.mark.parametrize(
        "route", ["overview", "plant", "transformer", "device", "reports"]
    )
    def test_monitoring_and_reports_stay_open(self, role, route):
        assert routing.route_decision(identity(role), route) == routing.DECISION_ALLOW

    @pytest.mark.parametrize(
        "route", ["notifications", "command_center"]
    )
    def test_general_operational_direct_urls_are_refused(self, route):
        assert routing.route_decision(identity(GENERAL), route) == (
            routing.DECISION_FORBIDDEN
        )

    @pytest.mark.parametrize(
        "route", ["notifications", "command_center"]
    )
    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN])
    def test_operational_direct_urls_remain_open_to_authorized_roles(self, role, route):
        assert routing.route_decision(identity(role), route) == routing.DECISION_ALLOW

    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN, GENERAL])
    def test_an_unknown_route_is_not_a_permissions_problem(self, role):
        """A typo'd URL must read as 'no such page', never as 'you may not
        have this page' — otherwise every mistyped path implies something
        exists behind it."""
        assert routing.route_decision(identity(role), "unknown") == (
            routing.DECISION_ALLOW
        )

    def test_an_unrecognised_role_is_refused(self):
        """`current_identity()` can never actually construct one of these —
        it fails closed to None first (see auth_service tests) — but
        `route_decision` refuses it anyway rather than assuming its own
        caller's discipline."""
        assert routing.route_decision(identity("superuser"), "overview") == (
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

        # RTL-LIST-ROUTE-01: the canonical address, never the legacy one.
        assert ("Back to Registered RTLs", "/rtls") in links(forbidden_panel())

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
    def test_administrator_sees_every_sidebar_item(self):
        expected = [label for _title, items in SIDEBAR_SECTIONS
                    for _key, label, _href, _icon in items]
        assert rendered_labels(ADMINISTRATOR) == expected

    def test_admin_management_items_are_gone_for_general(self):
        labels = rendered_labels(GENERAL)
        assert "Devices" not in labels
        assert "Registration" not in labels
        assert "Users" not in labels

    @pytest.mark.parametrize("role", [TECHNICIAN, GENERAL])
    def test_registration_and_users_stay_administrator_only(self, role):
        labels = rendered_labels(role)
        assert "Registration" not in labels
        assert "Users" not in labels

    def test_technician_navigation_is_the_factual_client_rtl_set(self):
        """ADR-032: Dashboard, Assigned RTLs, Network, Historical Events - the
        real-client routes - plus the shared Notifications and Reports. No
        synthetic Devices item and no assignment management."""
        assert rendered_labels(TECHNICIAN) == [
            "Assigned RTLs", "Network", "Historical Events", "Dashboard",
            "Notifications", "Reports",
        ]

    def test_technician_has_no_synthetic_devices_item(self):
        hrefs = dict(links(sidebar_nav(None, TECHNICIAN)))
        assert "Devices" not in hrefs and "/devices" not in hrefs.values()

    def test_general_user_navigation_has_no_operational_surfaces(self):
        assert rendered_labels(GENERAL) == ["Registered RTLs", "Network", "Historical Events", "Reports"]

    def test_an_emptied_section_takes_its_heading_with_it_for_general(self):
        """Every Operations item General may reach is none, so the heading
        would otherwise sit over nothing."""
        assert "Operations" not in section_titles(GENERAL)
        assert "System" in section_titles(GENERAL)

    def test_technician_has_no_operations_section(self):
        """Devices, Assignments and Registration are all closed to a Technician
        now, so the Operations heading goes with them."""
        assert "Operations" not in section_titles(TECHNICIAN)
        assert "System" in section_titles(TECHNICIAN)

    def test_administrator_keeps_both_section_headings(self):
        assert section_titles(ADMINISTRATOR) == ["Operations", "System"]

    def test_the_routeless_assignments_placeholder_hides_for_general(self):
        """It has no route of its own, so the policy cannot speak about it.
        It belongs to Operations and goes where Operations goes — and
        Operations goes nowhere for General."""
        assert "Assignments" not in rendered_labels(GENERAL)

    def test_assignments_stays_administrator_only_for_technician_too(self):
        """ADMIN-ASSIGN-1: Assignments is a real, Administrator-only route
        now (like admin_devices), not a routeless placeholder that travels
        with an otherwise-visible Operations section — a Technician having
        their own Devices item does not also grant them Assignments."""
        assert "Assignments" not in rendered_labels(TECHNICIAN)

    def test_no_link_points_somewhere_the_role_may_not_go(self):
        for role in (TECHNICIAN, GENERAL):
            hrefs = [href for _label, href in links(sidebar_nav(None, role))]
            assert not any(h.startswith("/admin") for h in hrefs)

    def test_general_user_has_no_operational_navigation_links(self):
        hrefs = [href for _label, href in links(sidebar_nav(None, GENERAL))]
        assert "/notifications" not in hrefs
        assert "/command-center" not in hrefs

    @pytest.mark.parametrize("role", [None, "superuser"])
    def test_an_unrecognised_role_gets_an_empty_nav(self, role):
        assert rendered_labels(role) == []

    def test_active_state_still_works_for_a_visible_item(self):
        nav = sidebar_nav("overview", TECHNICIAN)
        assert find_by_class(nav, "app-sidebar__link--active")

    def test_active_state_cannot_resurrect_a_hidden_item(self):
        """A technician arriving on a route denied to them (Administrator's
        "devices" key, distinct from their own "technician_devices") must
        not light up an item that is not there — but their OWN Devices item
        is legitimately visible and must not be mistaken for the denied
        one."""
        nav = sidebar_nav("devices", TECHNICIAN)
        assert find_by_class(nav, "app-sidebar__link--active") == []

    def test_a_retired_key_lights_nothing_up(self):
        nav = sidebar_nav("technician_devices", TECHNICIAN)
        assert find_by_class(nav, "app-sidebar__link--active") == []


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
