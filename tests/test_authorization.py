"""ROLE-2 — route and navigation authorization.

The policy table is the source of truth and the sidebar is derived from it.
That is what most of this file is about: a hidden item and a denied route
cannot disagree, because there is only one statement of who may go where.
Both directions are asserted — nothing visible that is denied, nothing
allowed that is invisible — since two independently-maintained tables would
each pass their own tests while contradicting each other.

WHAT THIS IS NOT. Route denial happens in the router. The data callbacks
still answer whoever asks, and the role still travels in a client-settable
browser store (S-4/S-5 in docs/CODE_AUDIT.md). ROLE-2 shapes what the UI
offers; it does not withhold data from anyone bypassing the UI.
"""
from __future__ import annotations

import pytest

from callbacks.navigation import NAV_KEY_BY_ROUTE
from components.app_sidebar import SIDEBAR_SECTIONS
from routes import parse_pathname
from services.authorization import (
    ACTION_POLICY,
    ADMINISTRATOR,
    AuthorizationError,
    CAPABILITY_POLICY,
    DEACTIVATE_RTL,
    EXPORT_DATA,
    GENERAL,
    MANAGE_ASSIGNMENT,
    MANAGE_TEMPERATURE_THRESHOLD,
    MANAGE_VIBRATION_CONTRACT,
    PROGRAM_RTL,
    REGISTER_DEVICE,
    ROUTE_POLICY,
    TECHNICIAN,
    TOGGLE_MESSAGE_FORWARDING,
    VIEW_ADMINISTRATION_OVERVIEW,
    VIEW_AUDIT_LOG,
    may_access_route,
    may_perform_action,
    may_perform_capability,
    visible_nav_keys,
)
from services.prototype_users import CONFIRMED_ROLES

#: Every route an authenticated user can ask for, with the path that produces
#: it. `unknown` is deliberately absent — it is not an application route.
ROUTE_PATHS = {
    "overview": "/rtls",
    "plant": "/plants/plant-01",
    "transformer": "/plants/plant-01/plant-01-t1",
    "device": "/devices/plant-01-t1-d1",
    "rtl_detail": "/rtls/29006",
    "rtl_network": "/rtls/network",
    "historical_events": "/events",
    "notifications": "/notifications",
    "reports": "/reports",
    "admin_devices": "/admin/devices",
    "technician_devices": "/devices",
    "admin_assignments": "/admin/assignments",
    "device_register": "/admin/devices/new",
    "admin_users": "/admin/users",
    "audit_log": "/admin/audit-log",
    "admin_settings": "/admin/settings",
    "command_center": "/command-center",
}

#: Functional Specification §5.9 retains the monitoring hierarchy and report
#: export for General Users, while reserving operational surfaces for the
#: Administrator and Technician roles.
ADMIN_ONLY = ("admin_devices", "admin_assignments", "device_register", "admin_users", "audit_log", "admin_settings")
GENERAL_READ_ROUTES = ("overview", "plant", "transformer", "device", "reports")
OPERATIONAL_ROUTES = (
    "notifications", "command_center",
)
#: ADR-016: a Technician's own assigned-devices surface. Deliberately NOT in
#: ADMIN_ONLY (the Administrator cannot reach it — it names no fleet-wide
#: administration Administrator already has via admin_devices) and NOT in
#: OPERATIONAL_ROUTES (Administrator does not share this one).
TECHNICIAN_ONLY_ROUTES = ("technician_devices",)
#: RTL-UID-DETAIL-01: raw client RTL facts. A shape no earlier route had —
#: Administrator AND General User, but NOT Technician. It is not in
#: GENERAL_READ_ROUTES (those are reachable by every role) and not in
#: ADMIN_ONLY. The Technician exclusion is not a privilege judgement: there is
#: no approved client-RTL-UID-to-assignment map, so there is no way to scope
#: the page to them truthfully.
CLIENT_RTL_ROUTES = ("rtl_detail", "rtl_network", "historical_events")  # network: LATEST-NETWORK-CONTEXT-01; events: HISTORICAL-EVENTS-01


class TestRoleConstants:
    def test_role_names_match_the_confirmed_vocabulary(self):
        """The policy must key on the same strings `users.role` holds, or it
        silently denies everyone."""
        assert {ADMINISTRATOR, TECHNICIAN, GENERAL} == set(CONFIRMED_ROLES)


class TestTheMatrix:
    @pytest.mark.parametrize("route", GENERAL_READ_ROUTES)
    def test_every_role_reaches_monitoring_and_reports(self, route):
        for role in CONFIRMED_ROLES:
            assert may_access_route(role, route) is True

    @pytest.mark.parametrize("route", OPERATIONAL_ROUTES)
    def test_general_user_cannot_reach_operational_surfaces(self, route):
        assert may_access_route(ADMINISTRATOR, route) is True
        assert may_access_route(TECHNICIAN, route) is True
        assert may_access_route(GENERAL, route) is False

    @pytest.mark.parametrize("route", CLIENT_RTL_ROUTES)
    def test_only_unrestricted_scopes_reach_client_rtl_facts(self, route):
        """RTL-UID-DETAIL-01. The Fleet page shows the client RTL directory
        to unrestricted scopes only; the detail route must refuse the same
        role, or typing a UID becomes the way around that restriction."""
        assert may_access_route(ADMINISTRATOR, route) is True
        assert may_access_route(GENERAL, route) is True
        assert may_access_route(TECHNICIAN, route) is False

    @pytest.mark.parametrize("route", ADMIN_ONLY)
    def test_only_the_administrator_reaches_admin_management(self, route):
        assert may_access_route(ADMINISTRATOR, route) is True
        assert may_access_route(TECHNICIAN, route) is False
        assert may_access_route(GENERAL, route) is False

    @pytest.mark.parametrize("route", TECHNICIAN_ONLY_ROUTES)
    def test_only_the_technician_reaches_their_own_devices(self, route):
        """ADR-016: the Administrator has admin_devices for this already —
        technician_devices names no capability the Administrator lacks, so
        it is correctly denied to them too, not just to General."""
        assert may_access_route(ADMINISTRATOR, route) is False
        assert may_access_route(TECHNICIAN, route) is True
        assert may_access_route(GENERAL, route) is False

    def test_general_user_has_only_the_functional_specification_route_set(self):
        """The General User set is exactly the §5.9 read-only route set."""
        technician = {r for r in ROUTE_POLICY if may_access_route(TECHNICIAN, r)}
        general = {r for r in ROUTE_POLICY if may_access_route(GENERAL, r)}
        assert general == set(GENERAL_READ_ROUTES) | set(CLIENT_RTL_ROUTES)
        assert technician - general == set(OPERATIONAL_ROUTES) | set(TECHNICIAN_ONLY_ROUTES)
        # The other direction, which the line above cannot see: the General
        # User reaches the client RTL routes and the Technician does not.
        assert general - technician == set(CLIENT_RTL_ROUTES)

    def test_administrator_reaches_every_policied_route_except_technicians_own(self):
        """The one deliberate exception: technician_devices names no
        capability the Administrator lacks (they already have admin_devices),
        so ADR-016 denies them this specific route rather than widening it."""
        non_admin_routes = set(ROUTE_POLICY) - set(TECHNICIAN_ONLY_ROUTES)
        assert all(may_access_route(ADMINISTRATOR, r) for r in non_admin_routes)
        assert not any(may_access_route(ADMINISTRATOR, r) for r in TECHNICIAN_ONLY_ROUTES)

    def test_the_policy_covers_every_application_route(self):
        """A route the router can produce but the policy never mentions would
        be denied to everyone — including the administrator — the moment it
        shipped. This is the test that fails when someone adds a route."""
        assert set(ROUTE_POLICY) == set(ROUTE_PATHS)

    @pytest.mark.parametrize("route,path", sorted(ROUTE_PATHS.items()))
    def test_each_path_parses_to_the_route_the_policy_names(self, route, path):
        """Guards the join: the policy keys on `Route.name`, so a renamed
        route would default-deny rather than error."""
        assert parse_pathname(path).name == route


class TestDefaultDeny:
    @pytest.mark.parametrize("role", CONFIRMED_ROLES)
    def test_an_unlisted_route_is_denied_to_everyone(self, role):
        """A route added later is unreachable until someone lists it
        deliberately. Denied is the safe direction to fail."""
        assert may_access_route(role, "some_future_admin_page") is False

    def test_the_unknown_route_is_not_authorised_here(self):
        """`unknown` stays outside the policy so a typo'd URL keeps rendering
        not-found. The router, not this table, is what keeps those apart."""
        assert "unknown" not in ROUTE_POLICY

    @pytest.mark.parametrize("role", [None, "", "superuser", "Administrator", 7, {}])
    def test_an_unrecognised_role_reaches_nothing(self, role):
        """Including the near-misses: a role is compared exactly, never
        case-folded, so `Administrator` is not the administrator."""
        assert all(may_access_route(role, r) is False for r in ROUTE_POLICY)

    def test_denial_is_the_answer_for_a_missing_role_even_on_open_routes(self):
        assert may_access_route(None, "overview") is False


class TestNavigationIsDerivedFromThePolicy:
    def _sidebar_keys(self) -> set[str]:
        return {
            key
            for _title, items in SIDEBAR_SECTIONS
            for key, _label, _href, _icon in items
            if key is not None
        }

    @pytest.mark.parametrize("role", CONFIRMED_ROLES)
    def test_nothing_visible_leads_somewhere_denied(self, role):
        """The failure this prevents: an item you can see and cannot open."""
        for key in visible_nav_keys(role):
            routes = [r for r, k in NAV_KEY_BY_ROUTE.items() if k == key]
            assert any(may_access_route(role, r) for r in routes)

    @pytest.mark.parametrize("role", CONFIRMED_ROLES)
    def test_nothing_reachable_is_hidden(self, role):
        """The opposite failure: a page you may open with no way to get
        there."""
        visible = visible_nav_keys(role)
        for route, key in NAV_KEY_BY_ROUTE.items():
            if may_access_route(role, route):
                assert key in visible

    def test_administrator_keeps_the_current_navigation(self):
        """One deliberate exception: "technician_devices" is in the sidebar
        tuple (Technician sees it) but not in the Administrator's set — see
        test_only_the_technician_reaches_their_own_devices."""
        assert visible_nav_keys(ADMINISTRATOR) == self._sidebar_keys() - {"technician_devices"}

    def test_technician_keeps_operational_navigation(self):
        assert visible_nav_keys(TECHNICIAN) == {
            "overview", "notifications", "reports", "command_center",
            "technician_devices",
        }

    def test_general_user_sees_only_read_only_navigation(self):
        assert visible_nav_keys(GENERAL) == {"overview", "network", "events", "reports"}

    @pytest.mark.parametrize("role", [None, "superuser"])
    def test_an_unrecognised_role_sees_no_navigation(self, role):
        assert visible_nav_keys(role) == frozenset()

    def test_every_sidebar_key_is_reachable_by_someone(self):
        """A navigation item nobody may open is dead chrome."""
        reachable = set()
        for role in CONFIRMED_ROLES:
            reachable |= visible_nav_keys(role)
        assert reachable == self._sidebar_keys()


class TestTheAssignDeepLinkNeedsNoRuleOfItsOwn:
    """ADMIN-3's `?assign=` handoff lives under `/admin/devices`."""

    def test_denying_device_management_denies_the_handoff(self):
        from routes import device_assign_href

        href = device_assign_href("plant-01-t1-d1")
        route = parse_pathname(href.split("?", 1)[0]).name
        assert route == "admin_devices"
        assert may_access_route(TECHNICIAN, route) is False
        assert may_access_route(GENERAL, route) is False

    def test_the_query_string_cannot_change_the_answer(self):
        """Authorization keys on the route, so no `?assign=` value can widen
        it."""
        assert (
            parse_pathname("/admin/devices").name
            == parse_pathname("/admin/devices").name
        )
        assert may_access_route(TECHNICIAN, "admin_devices") is False


# ==========================================================================
# ROLE-3 Task 10 — capability and action policy
#
# This section absorbs services/prototype_access.py, which is deleted here.
# That module answered "can this role do X?" with its own set of functions
# and its own idea of the roles, alongside this table. Two modules answering
# one question is the failure mode ROLE-3 exists to remove: each passes its
# own tests while disagreeing with the other.
#
# ONE MIGRATION IS DELIBERATELY REFUSED. `prototype_access.can_view_device`
# returned True for all three roles. That is now false — a technician sees
# assigned RTLs only — and device visibility is not this module's question
# at all. It belongs to DeviceScope.allows(). Nothing here replaces it, and
# TestVisibilityIsNotAnActionPolicy makes sure nothing quietly reintroduces
# it.
# ==========================================================================

#: The three actions BR003/BR004/BR005/BR012 make assigned-only for a
#: technician. Parametrized rather than repeated: they are one rule, and
#: writing them out three times invites the three copies to drift.
ASSIGNED_ONLY_ACTIONS = [PROGRAM_RTL, TOGGLE_MESSAGE_FORWARDING, DEACTIVATE_RTL]

EVERY_CONFIRMED_ROLE = (ADMINISTRATOR, TECHNICIAN, GENERAL)


class TestTheActionMatrix:
    """The conceptual matrix from the ROLE-3 plan, asserted cell by cell."""

    @pytest.mark.parametrize("action", ASSIGNED_ONLY_ACTIONS)
    def test_administrator_may_act_on_any_device(self, action):
        assert may_perform_action(ADMINISTRATOR, action, is_assigned=False) is True
        assert may_perform_action(ADMINISTRATOR, action, is_assigned=True) is True

    @pytest.mark.parametrize("action", ASSIGNED_ONLY_ACTIONS)
    def test_technician_may_act_only_on_assigned_devices(self, action):
        assert may_perform_action(TECHNICIAN, action, is_assigned=True) is True
        assert may_perform_action(TECHNICIAN, action, is_assigned=False) is False

    @pytest.mark.parametrize("action", ASSIGNED_ONLY_ACTIONS)
    def test_general_may_never_act(self, action):
        """Invariant 3: unrestricted read scope is not administrator.

        General sees the whole fleet and may change none of it. If this ever
        passes for General, someone has read 'unrestricted visibility' as
        'unrestricted authority'.
        """
        assert may_perform_action(GENERAL, action, is_assigned=True) is False
        assert may_perform_action(GENERAL, action, is_assigned=False) is False

    def test_manage_assignment_is_administrator_only(self):
        """Assignment is the thing that GRANTS technician authority, so a
        technician who could manage it could grant it to themselves."""
        assert may_perform_action(ADMINISTRATOR, MANAGE_ASSIGNMENT, is_assigned=True) is True
        assert may_perform_action(TECHNICIAN, MANAGE_ASSIGNMENT, is_assigned=True) is False
        assert may_perform_action(GENERAL, MANAGE_ASSIGNMENT, is_assigned=True) is False

    def test_export_is_no_longer_an_action(self):
        """ADR-013 moved EXPORT_DATA to CAPABILITY_POLICY.

        The original assertion here — every role may export on any device —
        survives as `test_export_is_open_to_every_confirmed_role` in the
        capability matrix below. What is asserted instead is that the action
        table no longer claims it, so the two tables cannot both answer for
        export and disagree.
        """
        assert EXPORT_DATA not in ACTION_POLICY
        for role in EVERY_CONFIRMED_ROLE:
            assert may_perform_action(role, EXPORT_DATA, is_assigned=True) is False


class TestActionDefaultDeny:
    """Nothing is permitted because the table forgot to mention it."""

    def test_unknown_action_is_denied(self):
        assert may_perform_action(ADMINISTRATOR, "launch_missiles", is_assigned=True) is False

    # EXPORT_DATA left this list with ADR-013: it is no longer an action, so
    # asserting it here would test the unknown-ACTION default-deny above
    # under a misleading name. The unknown-role case for export moved to
    # `TestCapabilityPolicy.test_unknown_role_may_not_perform_a_capability`.
    @pytest.mark.parametrize("action", ASSIGNED_ONLY_ACTIONS + [MANAGE_ASSIGNMENT])
    def test_unknown_role_may_not_act(self, action):
        """Migrated from prototype_access's unknown-role cases, and widened:
        the old module only checked this for three of its six functions."""
        assert may_perform_action("unknown", action, is_assigned=True) is False

    @pytest.mark.parametrize("role", [None, 42, True, ["administrator"], ""])
    def test_non_string_role_may_not_act(self, role):
        """A malformed session degrades to no access, never to a default one
        — the same posture `may_access_route` already takes."""
        assert may_perform_action(role, PROGRAM_RTL, is_assigned=True) is False

    def test_roles_are_compared_exactly(self):
        assert may_perform_action("Administrator", PROGRAM_RTL, is_assigned=True) is False
        assert may_perform_action("ADMINISTRATOR", PROGRAM_RTL, is_assigned=True) is False

    def test_is_assigned_has_no_default(self):
        """Invariant 8 at the action boundary.

        prototype_access defaulted `is_assigned_to_user=False`, which was the
        safe direction but still a default. Here the argument is keyword-only
        and required, so a caller that forgets it fails loudly instead of
        silently deciding a technician is unassigned — or, if the default had
        ever been flipped, silently deciding they were.
        """
        with pytest.raises(TypeError):
            may_perform_action(TECHNICIAN, PROGRAM_RTL)


class TestCapabilityPolicy:
    """Page content, keyed on role alone: no device, so no assignment term."""

    def test_administration_overview_capability_is_administrator_only(self):
        assert may_perform_capability(ADMINISTRATOR, VIEW_ADMINISTRATION_OVERVIEW) is True
        assert may_perform_capability(TECHNICIAN, VIEW_ADMINISTRATION_OVERVIEW) is False
        assert may_perform_capability(GENERAL, VIEW_ADMINISTRATION_OVERVIEW) is False

    def test_temperature_threshold_capability_is_administrator_only(self):
        """THRESH-CONFIG-1 (C-01): same device-less, admin-only shape as
        MANAGE_AUTO_DISABLE_OVERRIDE."""
        assert may_perform_capability(ADMINISTRATOR, MANAGE_TEMPERATURE_THRESHOLD) is True
        assert may_perform_capability(TECHNICIAN, MANAGE_TEMPERATURE_THRESHOLD) is False
        assert may_perform_capability(GENERAL, MANAGE_TEMPERATURE_THRESHOLD) is False

    def test_vibration_contract_capability_is_administrator_only(self):
        """VIB-CONFIG-1 (C-02): same device-less, admin-only shape as
        MANAGE_TEMPERATURE_THRESHOLD."""
        assert may_perform_capability(ADMINISTRATOR, MANAGE_VIBRATION_CONTRACT) is True
        assert may_perform_capability(TECHNICIAN, MANAGE_VIBRATION_CONTRACT) is False
        assert may_perform_capability(GENERAL, MANAGE_VIBRATION_CONTRACT) is False

    def test_export_is_open_to_every_confirmed_role(self):
        """Migrated intact from the action matrix by ADR-013.

        The claim is unchanged — every confirmed role may export — only the
        table answering it moved. Asserted against the same
        `EVERY_CONFIRMED_ROLE` set as before, so a silent narrowing or
        widening during the migration would have failed here.
        """
        for role in EVERY_CONFIRMED_ROLE:
            assert may_perform_capability(role, EXPORT_DATA) is True

    def test_unknown_capability_is_denied(self):
        assert may_perform_capability(ADMINISTRATOR, "read_minds") is False

    @pytest.mark.parametrize(
        "capability", [VIEW_ADMINISTRATION_OVERVIEW, EXPORT_DATA]
    )
    def test_unknown_role_may_not_perform_a_capability(self, capability):
        """EXPORT_DATA is parametrized here by ADR-013, taking over the
        unknown-role case it used to carry in the action matrix. Export is
        open to every CONFIRMED role, which is not the same as open."""
        assert may_perform_capability("unknown", capability) is False

    @pytest.mark.parametrize("role", [None, 42, True, ""])
    def test_non_string_role_may_not_perform_a_capability(self, role):
        assert may_perform_capability(role, VIEW_ADMINISTRATION_OVERVIEW) is False

    def test_the_capability_is_not_derived_from_the_admin_route(self):
        """Task 12 must not use `/admin/devices` access as a proxy.

        They agree today, which is exactly why this is worth pinning: the
        Administration BLOCK on /plants and the admin_devices ROUTE are two
        different questions, and deriving one from the other would silently
        couple them the next time either moves.
        """
        assert VIEW_ADMINISTRATION_OVERVIEW not in ROUTE_POLICY
        assert "admin_devices" not in CAPABILITY_POLICY


class TestVisibilityIsNotAnActionPolicy:
    """Invariant 1: one question, one answer, and this module is not it.

    `prototype_access.can_view_device(role)` returned True for every role.
    Keeping it would have meant a technician who cannot see a device by
    scope could still be told they may view it by policy.
    """

    def test_no_action_or_capability_answers_device_visibility(self):
        import services.authorization as authorization

        exported = set(dir(authorization)) | set(ACTION_POLICY) | set(CAPABILITY_POLICY)
        offenders = [
            name
            for name in exported
            if "view_device" in name or "can_view" in name
        ]
        assert offenders == [], (
            "device visibility belongs to DeviceScope.allows(), not to the "
            f"action/capability policy; found {offenders}"
        )

    def test_device_scope_is_the_visibility_authority(self):
        """The positive half: the answer lives somewhere, and it is here."""
        from services.device_scope import DeviceScope

        scope = DeviceScope(frozenset({"mine"}))
        assert scope.allows("mine") is True
        assert scope.allows("theirs") is False


class TestPrototypeAccessIsGone:
    def test_the_module_cannot_be_imported(self):
        """It held can_view_device() == True for every role — a second, now
        false, answer to a question DeviceScope owns (invariant 1)."""
        import importlib.util

        assert importlib.util.find_spec("services.prototype_access") is None

    def test_nothing_imports_it(self):
        """A stale `.pyc` or an editor-restored file would let the import
        test above pass while a real caller still reached the old policy."""
        import pathlib
        import re

        # Real import statements only. A substring search would flag this
        # file's own assertions and report itself as the offender.
        importer = re.compile(r"^\s*(?:from|import)\s+\S*prototype_access")

        root = pathlib.Path(__file__).resolve().parent.parent
        offenders = []
        for path in root.rglob("*.py"):
            if ".claude" in path.parts or "worktrees" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                if importer.match(line):
                    offenders.append(f"{path.name}: {line.strip()}")
        assert offenders == [], offenders


class TestTheThreeTablesStaySeparate:
    """Routes, capabilities and actions are three dimensions, not one.

    Deriving any from another is how a route change silently becomes an
    action change. Navigation IS derived from routes — that is the same
    question asked twice — and nothing else is.
    """

    def test_the_policies_share_no_keys(self):
        assert set(ROUTE_POLICY) & set(ACTION_POLICY) == set()
        assert set(ROUTE_POLICY) & set(CAPABILITY_POLICY) == set()
        assert set(ACTION_POLICY) & set(CAPABILITY_POLICY) == set()

    def test_every_action_names_its_two_role_sets(self):
        for action, entry in ACTION_POLICY.items():
            any_device, assigned_only = entry
            assert isinstance(any_device, frozenset), action
            assert isinstance(assigned_only, frozenset), action
            assert any_device <= set(EVERY_CONFIRMED_ROLE), action
            assert assigned_only <= set(EVERY_CONFIRMED_ROLE), action

    def test_general_appears_in_no_assigned_only_set(self):
        """General has no assignments, so listing it there would be a rule
        that reads as permissive but can never fire — or worse, one that
        fires the day General gains an assignment row."""
        for action, (_any_device, assigned_only) in ACTION_POLICY.items():
            assert GENERAL not in assigned_only, action


class TestAuthorizationError:
    def test_it_is_distinct_from_a_bad_identifier(self):
        """ROLE-1 froze this: refused and nonexistent are different answers.

        A caller catching ValueError for a malformed id must not accidentally
        swallow a refusal, so AuthorizationError deliberately does not
        inherit from it.
        """
        assert issubclass(AuthorizationError, Exception)
        assert not issubclass(AuthorizationError, ValueError)


class TestRegisterDeviceCapability:
    """Registration is a DEVICE-LESS permission.

    At the moment of the check no device exists — the device is what is being
    created — so this cannot live in ACTION_POLICY, which is keyed on a
    device_id and resolves an assignment against it. It belongs to
    CAPABILITY_POLICY, whose defining property is that no device is involved
    and there is therefore no assignment condition to apply.
    """

    def test_registration_is_administrator_only(self):
        assert may_perform_capability(ADMINISTRATOR, REGISTER_DEVICE) is True
        assert may_perform_capability(TECHNICIAN, REGISTER_DEVICE) is False
        assert may_perform_capability(GENERAL, REGISTER_DEVICE) is False

    @pytest.mark.parametrize("role", [None, 0, [], object()])
    def test_non_string_role_is_refused(self, role):
        assert may_perform_capability(role, REGISTER_DEVICE) is False

    def test_registration_is_not_a_device_action(self):
        """No device exists yet, so there is nothing for ACTION_POLICY to scope."""
        assert REGISTER_DEVICE not in ACTION_POLICY

    def test_capability_and_route_agree(self):
        """The page and the write behind it are gated to the same roles.

        Not derived from one another — asserted equal, so a change to either
        that forgets the other fails here rather than shipping a page an
        administrator can open and no one can submit (or worse, the reverse).
        """
        assert CAPABILITY_POLICY[REGISTER_DEVICE] == ROUTE_POLICY["device_register"]
