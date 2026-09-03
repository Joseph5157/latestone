"""ROLE-4B — the Technician's authorized actions, reachable from the device page.

The gap this closes is reachability, not authority. `ACTION_POLICY` has granted
a technician `program_rtl`, `toggle_message_forwarding` and `deactivate_rtl` on
an assigned device since ROLE-3, and `require_action` has enforced it. But the
only surface rendering those three was `device_manage_drawer()`, mounted once,
in `pages/device_admin.py` — the `/admin/devices` page, which `ROUTE_POLICY`
gives to `_ADMIN_ONLY`. A technician held the permission and had nowhere to
exercise it.

**The fix is reachability only.** No role gains an action here, `/admin/devices`
stays administrator-only, and `manage_assignment` stays off the technician's
surface entirely — assignment is what *grants* technician authority, so a
technician who could manage it could grant it to themselves
(`services/authorization.py`, ACTION_POLICY's second set).

Visibility is not authority. Every test that asserts a control is absent has a
sibling asserting the guard still refuses the call, because a hidden button is
a courtesy and `require_action` is the rule.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from components.device_manage_drawer import (
    DEACTIVATE_CONFIRM_BTN,
    MANAGE_DRAWER_ID,
    MSG_FWD_CONFIRM_BTN,
    PROGRAM_RTL_CONFIRM_BTN,
)
from pages import device_dashboard
from services import action_guard
from services.authorization import (
    DEACTIVATE_RTL,
    MANAGE_ASSIGNMENT,
    PROGRAM_RTL,
    TOGGLE_MESSAGE_FORWARDING,
    AuthorizationError,
)
from services.auth_service import AuthenticatedUser
from tests.dash_tree import find_by_id, text_of, walk

ASSIGNED = "plant-01-t1-d1"
OUT_OF_SCOPE = "plant-09-t1-d1"

OPERATIONAL_ACTIONS = (PROGRAM_RTL, TOGGLE_MESSAGE_FORWARDING, DEACTIVATE_RTL)


def user(role: str, user_id: int = 1) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id, username=f"demo.{role}", full_name=f"Demo {role}", role=role
    )


ADMIN = user("administrator", 1)
TECH = user("technician", 2)
GENERAL = user("general", 3)


@dataclass(frozen=True)
class _Scope:
    """Device scope double — a technician assigned exactly one device."""

    allowed: frozenset

    @property
    def is_unrestricted(self) -> bool:
        return False

    def allows(self, device_id: str) -> bool:
        return device_id in self.allowed


@pytest.fixture
def scoped(monkeypatch):
    """`demo.tech01` holds ASSIGNED and nothing else."""

    def _scope_for(u):
        if u.role == "technician":
            return _Scope(frozenset({ASSIGNED}))
        return _Scope(frozenset())

    monkeypatch.setattr(action_guard, "scope_for", _scope_for)


def device_page():
    """The device page as the router builds it (`callbacks/routing.py`)."""
    return device_dashboard.layout(
        plant_name="Plant 01",
        transformer_code="T1",
        device_code="aa12",
        plant_id="plant-01",
        transformer_id="plant-01-t1",
        device_status="active",
    )


class TestTheAuthorityAlreadyExists:
    """Not the gap. Recorded so a later change cannot quietly move it."""

    def test_technician_may_act_on_an_assigned_device(self, scoped):
        for action in OPERATIONAL_ACTIONS:
            action_guard.require_action(TECH, action, device_id=ASSIGNED)

    def test_technician_may_not_act_on_an_unassigned_device(self, scoped):
        for action in OPERATIONAL_ACTIONS:
            with pytest.raises(AuthorizationError):
                action_guard.require_action(TECH, action, device_id=OUT_OF_SCOPE)

    def test_technician_may_never_manage_assignment(self, scoped):
        """Assignment is what grants technician authority. A technician who
        could manage it could grant it to themselves."""
        for device_id in (ASSIGNED, OUT_OF_SCOPE):
            with pytest.raises(AuthorizationError):
                action_guard.require_action(
                    TECH, MANAGE_ASSIGNMENT, device_id=device_id
                )


class TestTheGapIsReachability:
    """The regression proper: the device page must carry the surface."""

    def test_the_device_page_mounts_the_operational_drawer(self):
        """It was mounted only on `/admin/devices`, which a technician cannot
        open — so the permission had no rendered path."""
        assert find_by_id(device_page(), MANAGE_DRAWER_ID) is not None, (
            "device_manage_drawer() is not mounted on the device page; a "
            "technician still has no way to reach program_rtl, "
            "toggle_message_forwarding or deactivate_rtl"
        )

    def test_the_device_page_offers_an_operations_container(self):
        assert find_by_id(device_page(), device_dashboard.OPERATIONS_ID) is not None

    @pytest.mark.parametrize(
        "button_id",
        [PROGRAM_RTL_CONFIRM_BTN, MSG_FWD_CONFIRM_BTN, DEACTIVATE_CONFIRM_BTN],
    )
    def test_each_operational_confirm_control_is_present(self, button_id):
        assert find_by_id(device_page(), button_id) is not None

    def test_the_device_page_does_not_mount_assignment_controls(self):
        """`assign_device_drawer()` belongs to `/admin/devices` only."""
        from components.assign_device_drawer import ASSIGN_DRAWER_ID

        assert find_by_id(device_page(), ASSIGN_DRAWER_ID) is None

    def test_no_assignment_wording_reaches_the_device_page(self):
        rendered = text_of(device_page()).lower()
        for phrase in ("assign technician", "reassign", "unassign"):
            assert phrase not in rendered


class TestWhatEachPersonaIsOffered:
    """`may_action` is the renderer's question — the same policy the guard
    enforces, asked without raising, so a component never carries its own
    permission table."""

    def test_administrator_is_offered_every_operational_action_anywhere(self, scoped):
        for action in OPERATIONAL_ACTIONS:
            assert action_guard.may_action(ADMIN, action, device_id=OUT_OF_SCOPE)

    def test_technician_is_offered_them_only_on_an_assigned_device(self, scoped):
        for action in OPERATIONAL_ACTIONS:
            assert action_guard.may_action(TECH, action, device_id=ASSIGNED)
            assert not action_guard.may_action(TECH, action, device_id=OUT_OF_SCOPE)

    def test_general_is_offered_none_of_them(self, scoped):
        for action in OPERATIONAL_ACTIONS:
            assert not action_guard.may_action(GENERAL, action, device_id=ASSIGNED)

    def test_nobody_is_offered_assignment_through_this_surface(self, scoped):
        assert not action_guard.may_action(TECH, MANAGE_ASSIGNMENT, device_id=ASSIGNED)
        assert not action_guard.may_action(
            GENERAL, MANAGE_ASSIGNMENT, device_id=ASSIGNED
        )

    def test_no_identity_is_offered_anything(self, scoped):
        for action in OPERATIONAL_ACTIONS:
            assert not action_guard.may_action(None, action, device_id=ASSIGNED)

    def test_may_action_and_require_action_never_disagree(self, scoped):
        """One decision, two presentations. If these could drift, the UI would
        offer a control the guard refuses — or hide one it would allow."""
        for who in (ADMIN, TECH, GENERAL, None):
            for action in OPERATIONAL_ACTIONS + (MANAGE_ASSIGNMENT,):
                for device_id in (ASSIGNED, OUT_OF_SCOPE):
                    offered = action_guard.may_action(
                        who, action, device_id=device_id
                    )
                    try:
                        action_guard.require_action(who, action, device_id=device_id)
                        enforced = True
                    except AuthorizationError:
                        enforced = False
                    assert offered is enforced, (
                        f"{who and who.role} / {action} / {device_id}: "
                        f"offered={offered} enforced={enforced}"
                    )


class TestTheRenderedOperationsPanel:
    """What the callback puts in the container, per persona."""

    def render(self, who, device_id=ASSIGNED):
        from callbacks.device_manage import device_operations_children

        return device_operations_children(who, device_id)

    def test_technician_gets_the_surface_on_an_assigned_device(self, scoped):
        rendered = text_of(self.render(TECH))
        assert "Operational controls" in rendered

    def test_technician_gets_nothing_on_an_unassigned_device(self, scoped):
        assert self.render(TECH, OUT_OF_SCOPE) is None

    def test_general_gets_nothing(self, scoped):
        assert self.render(GENERAL) is None

    def test_no_session_gets_nothing(self, scoped):
        assert self.render(None) is None

    def test_administrator_gets_the_surface(self, scoped):
        assert self.render(ADMIN) is not None

    def test_the_panel_never_offers_assignment(self, scoped):
        rendered = text_of(self.render(TECH)).lower()
        for phrase in ("assign", "reassign", "unassign"):
            assert phrase not in rendered

    def test_the_panel_names_the_selected_rtl(self, scoped):
        """UI_SPEC: the operator must be able to see which RTL they are about
        to act on before they act on it."""
        assert ASSIGNED in text_of(self.render(TECH))

    def test_the_destructive_action_is_marked_as_such(self, scoped):
        classes = [
            getattr(node, "className", "") or ""
            for node in walk(self.render(TECH))
        ]
        assert any("danger" in c for c in classes), (
            "Deactivate RTL must stay visually distinct from routine actions"
        )


class _CapturingApp:
    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


def _handlers():
    from callbacks import device_manage

    app = _CapturingApp()
    device_manage.register(app)
    return app.functions


DEVICE_CONTEXT = {
    "route": "device",
    "device_id": ASSIGNED,
    "device_code": "aa12",
    "transformer_code": "T1",
    "plant_name": "Plant 01",
}


def _session(who):
    from services.auth_service import to_session

    return to_session(who) if who else {"authenticated": False}


class TestTheDevicePageCallbacks:
    def test_the_section_renders_for_a_technician_on_an_assigned_rtl(self, scoped):
        render = _handlers()["render_device_operations"]
        assert render(DEVICE_CONTEXT, _session(TECH)) is not None

    def test_the_section_is_empty_for_general(self, scoped):
        render = _handlers()["render_device_operations"]
        assert render(DEVICE_CONTEXT, _session(GENERAL)) is None

    def test_the_section_is_empty_when_signed_out(self, scoped):
        render = _handlers()["render_device_operations"]
        assert render(DEVICE_CONTEXT, {"authenticated": False}) is None

    def test_the_section_is_empty_off_a_device_route(self, scoped):
        """`/admin/devices` keeps its own entry point; this one must not also
        fire there and give the drawer two openers on one page."""
        render = _handlers()["render_device_operations"]
        assert render({"route": "admin_devices"}, _session(ADMIN)) is None
        assert render({}, _session(ADMIN)) is None
        assert render(None, _session(ADMIN)) is None

    def test_the_section_is_empty_for_a_technician_off_scope(self, scoped):
        render = _handlers()["render_device_operations"]
        context = dict(DEVICE_CONTEXT, device_id=OUT_OF_SCOPE)
        assert render(context, _session(TECH)) is None


class TestTheDevicePageOpener:
    def opened(self, result) -> bool:
        from dash import no_update

        return result[0] is not no_update and result[0] == {"display": "block"}

    def test_a_click_opens_the_drawer_on_the_routed_device(self):
        opener = _handlers()["open_manage_drawer_from_device"]
        result = opener(1, DEVICE_CONTEXT)
        assert self.opened(result)
        assert result[1] == ASSIGNED, "the drawer must act on the routed RTL"
        assert result[2] == "menu", "it must start at the action menu"

    def test_no_click_does_nothing(self):
        opener = _handlers()["open_manage_drawer_from_device"]
        assert not self.opened(opener(0, DEVICE_CONTEXT))
        assert not self.opened(opener(None, DEVICE_CONTEXT))

    def test_it_declines_off_a_device_route(self):
        opener = _handlers()["open_manage_drawer_from_device"]
        assert not self.opened(opener(1, {"route": "admin_devices"}))
        assert not self.opened(opener(1, {}))
        assert not self.opened(opener(1, None))

    def test_it_declines_with_no_device_in_context(self):
        opener = _handlers()["open_manage_drawer_from_device"]
        assert not self.opened(opener(1, {"route": "device", "device_id": ""}))

    def test_its_decline_is_sized_like_the_admin_opener(self):
        """Both write the same twelve outputs. A short decline tuple is a Dash
        output-count error the first time a decline actually happens."""
        from callbacks.device_manage import _MANAGE_DRAWER_OUTPUTS

        opener = _handlers()["open_manage_drawer_from_device"]
        assert len(opener(1, None)) == _MANAGE_DRAWER_OUTPUTS
        assert len(opener(1, DEVICE_CONTEXT)) == _MANAGE_DRAWER_OUTPUTS


class TestDashSafety:
    """The drawer uses fixed ids, so two mounted copies would collide."""

    def test_the_two_pages_are_never_mounted_together(self):
        """The router returns ONE page per route, which is what makes mounting
        the same fixed-id drawer on both safe."""
        import inspect

        from callbacks import routing

        source = inspect.getsource(routing.register)
        assert source.count("device_admin.layout()") == 1
        assert source.count("device_dashboard.layout(") == 1
        # Each is behind its own route name, so one request renders one of them.
        assert 'route.name == "device"' in source
        assert 'route.name == "admin_devices"' in source

    def test_the_admin_opener_still_owns_the_table_path(self):
        """ROLE-4B added an opener; it must not have replaced the existing one."""
        handlers = _handlers()
        assert "open_manage_drawer" in handlers
        assert "open_manage_drawer_from_device" in handlers

    def test_the_admin_page_does_not_gain_the_device_operations_container(self):
        """Two containers with one id on one page would be a collision."""
        from pages import device_admin

        assert find_by_id(device_admin.layout(), device_dashboard.OPERATIONS_ID) is None

    def test_the_device_page_mounts_exactly_one_manage_drawer(self):
        ids = [getattr(n, "id", None) for n in walk(device_page())]
        assert ids.count(MANAGE_DRAWER_ID) == 1
