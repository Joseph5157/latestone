"""Route-level behaviour of the RETIRED synthetic monitoring routes.

LEGACY-SYNTHETIC-UX-CLEANUP-01. This file used to prove the AUTH-HARDEN-1R2
device-scope gating on the synthetic `/plants/<id>`, `/plants/<id>/<tf>` and
`/devices/<id>` routes: existence-then-membership for an unrestricted caller,
membership-first for a restricted (Technician) one, so a Technician could never
use the route as an existence oracle for a synthetic device outside their scope.

Those routes are now RETIRED. Each resolves to `legacy_retired` (routes.py) and
the router answers it with the static legacy/not-found panel — it resolves no
identifier, performs no `hierarchy_service` lookup and reads no scope at all. The
old existence-oracle question therefore cannot arise: there is nothing to gate,
for any role, because nothing is looked up. That is a strictly stronger property
than the one this file used to assert, and it is what these tests now pin.

(The real client-RTL routes keep their own scope gate — `services.rtl_scope`,
ADR-032 — proven in `tests/test_rtl_scope.py` and `tests/test_rtl_detail_route.py`,
not here. `tests/test_route_scope_db.py` covered the retired DeviceScope path
against a real Technician session and is retired with it.)
"""
from __future__ import annotations

import pytest

from callbacks import routing
from services.auth_service import AuthenticatedUser

TECHNICIAN_SESSION = {
    "authenticated": True,
    "user_id": 42,
    "username": "tech",
    "full_name": "Tech",
    "role": "technician",
}

ADMINISTRATOR_SESSION = {
    "authenticated": True,
    "user_id": 1,
    "username": "admin",
    "full_name": "Admin",
    "role": "administrator",
}

GENERAL_SESSION = {
    "authenticated": True,
    "user_id": 7,
    "username": "general",
    "full_name": "General",
    "role": "general",
}

ALL_SESSIONS = [TECHNICIAN_SESSION, ADMINISTRATOR_SESSION, GENERAL_SESSION]

#: Every retired synthetic monitoring/device/admin-device address. Each must
#: resolve to the legacy panel for every role, reading nothing on the way.
RETIRED_PATHS = [
    "/plants/plant-01",
    "/plants/plant-01/plant-01-t1",
    "/devices/plant-01-t1-d1",
    "/devices",
    "/admin/devices",
    "/admin/devices/new",
    "/admin/assignments",
]


class _CapturingApp:
    """Collects callbacks instead of registering them on a Dash runtime.

    `routing.register` declares exactly one callback, so `self.functions[0]`
    is `route_to_page`.
    """

    def __init__(self):
        self.functions = []

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions.append(fn)
            return fn

        return decorator


def _identity_for(session_dict) -> AuthenticatedUser | None:
    if not session_dict or not session_dict.get("authenticated"):
        return None
    return AuthenticatedUser(
        user_id=session_dict["user_id"],
        username=session_dict["username"],
        full_name=session_dict["full_name"],
        role=session_dict["role"],
    )


def routing_render(monkeypatch, pathname: str, session=TECHNICIAN_SESSION, search: str = ""):
    monkeypatch.setattr(routing, "current_identity", lambda: _identity_for(session))
    app = _CapturingApp()
    routing.register(app)
    route_to_page = app.functions[0]
    return route_to_page(pathname, search, session)


@pytest.mark.parametrize("pathname", RETIRED_PATHS)
@pytest.mark.parametrize("session", ALL_SESSIONS)
def test_a_retired_route_renders_the_legacy_panel_for_every_role(monkeypatch, pathname, session):
    _layout, ctx = routing_render(monkeypatch, pathname, session=session)
    assert ctx == {"route": "legacy_retired"}


@pytest.mark.parametrize("pathname", RETIRED_PATHS)
def test_a_retired_route_reads_no_scope_and_no_source(monkeypatch, pathname):
    """The whole point of the retirement: no identifier is resolved and no
    scope or source is read. The router no longer imports `current_device_scope`
    or `hierarchy_service` at all — if a retired-route branch ever tried to, it
    would raise here rather than silently reintroduce a synthetic lookup."""
    assert not hasattr(routing, "current_device_scope")
    assert not hasattr(routing, "hierarchy_service")
    # A guard that would fire the moment any client-RTL scope read crept onto a
    # retired route: make it explode if called, then prove it never is.
    called = []
    monkeypatch.setattr(routing, "current_rtl_scope", lambda: called.append(1))
    _layout, ctx = routing_render(monkeypatch, pathname, session=TECHNICIAN_SESSION)
    assert ctx == {"route": "legacy_retired"}
    assert called == []


def test_the_device_scope_module_is_no_longer_a_routing_dependency():
    """DeviceScope gated the synthetic device routes; with them retired, the
    router reasons only about the client-RTL scope (`services.rtl_scope`)."""
    import inspect

    src = inspect.getsource(routing)
    assert "current_device_scope" not in src
    assert "entity_in_scope" not in src
    assert "build_device_context" not in src
