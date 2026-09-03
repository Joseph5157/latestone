"""Route-level scope gating (ROLE-3 Task 9 / AUTH-HARDEN-1R2): existence,
then membership -- for an UNRESTRICTED caller only.

ROLE-2 already refuses a route a ROLE may not have. It says nothing about
WHICH device this technician may see, so `/devices/<id>` renders for any
existing device today. That is the direct-URL bypass these tests close.

ROLE-3 invariant 5 (a nonexistent resource and a resource that exists but is
not yours must stay two different answers) holds for Administrator and
General, who are never membership-refused, so existence is the only question
that ever gets asked for them. AUTH-HARDEN-1R2 found that the SAME ordering,
applied to a Technician's RESTRICTED scope, was an existence oracle: an
unrestricted lookup ran before the membership check, so a Technician could
tell "valid id, not mine" (Forbidden) apart from "no such id" (Not Found) --
exactly the distinction a restricted caller must never get to make about
assets outside their scope. The fix reorders the check: for a restricted
scope, `entity_in_scope` (itself scope-FILTERED) runs FIRST, so a real
out-of-scope entity and a nonexistent one both come back Forbidden, with no
unrestricted lookup ever run to tell them apart. See
`tests/test_route_scope_db.py` for that reordering proven against a real
trusted Technician session (R2-01..R2-09).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from callbacks import routing
from services.auth_service import AuthenticatedUser
from services.device_scope import DeviceScope

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


class _CapturingApp:
    """Collects callbacks instead of registering them on a Dash runtime.

    `routing.register` declares exactly one callback, so `self.functions[0]`
    is `route_to_page`. This avoids standing up a Dash app to test a function
    that is really just (pathname, search, session) -> (layout, context).
    """

    def __init__(self):
        self.functions = []

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions.append(fn)
            return fn

        return decorator


def _identity_for(session_dict) -> AuthenticatedUser | None:
    """AUTH-HARDEN-1: `route_to_page` no longer derives identity from this
    dict — it calls `current_identity()`, which every test here patches via
    this helper instead. Reconstructing the same identity the dict used to
    describe keeps each test's intent ("as this role") while exercising the
    trusted-identity path the real callback now uses."""
    if not session_dict or not session_dict.get("authenticated"):
        return None
    return AuthenticatedUser(
        user_id=session_dict["user_id"],
        username=session_dict["username"],
        full_name=session_dict["full_name"],
        role=session_dict["role"],
    )


def routing_render(monkeypatch, pathname: str, session=TECHNICIAN_SESSION):
    monkeypatch.setattr(routing, "current_identity", lambda: _identity_for(session))
    app = _CapturingApp()
    routing.register(app)
    route_to_page = app.functions[0]
    return route_to_page(pathname, "", session)


def _device_path(device_id: str = "mine") -> SimpleNamespace:
    """A DevicePath stand-in carrying every field the device branch reads."""
    return SimpleNamespace(
        device_id=device_id,
        plant_id="plant-01",
        plant_name="Plant 01",
        transformer_id="plant-01-t1",
        transformer_code="T1",
        device_code="D1",
        device_status="active",
    )


def _patch_device_lookup(monkeypatch, device_path=None):
    monkeypatch.setattr(
        routing.hierarchy_service,
        "get_device_context",
        lambda device_id: device_path,
    )


def _patch_scope(monkeypatch, scope: DeviceScope):
    monkeypatch.setattr(routing, "current_device_scope", lambda: scope)


# --------------------------------------------------------------------------
# Device
# --------------------------------------------------------------------------


def test_in_scope_device_renders(monkeypatch):
    """The positive case. Scoping must not refuse a technician's OWN RTL."""
    _patch_scope(monkeypatch, DeviceScope(frozenset({"mine"})))
    _patch_device_lookup(monkeypatch, _device_path("mine"))

    _layout, ctx = routing_render(monkeypatch, "/devices/mine")

    assert ctx["route"] == "device"
    assert ctx["device_id"] == "mine"


def test_out_of_scope_device_is_forbidden_not_not_found(monkeypatch):
    """Invariant 5. These two outcomes must never collapse."""
    _patch_scope(monkeypatch, DeviceScope(frozenset({"mine"})))
    _patch_device_lookup(monkeypatch, _device_path("theirs"))

    _layout, ctx = routing_render(monkeypatch, "/devices/theirs")

    assert ctx == {"route": "forbidden"}


def test_nonexistent_device_is_not_found(monkeypatch):
    _patch_scope(monkeypatch, DeviceScope(None))
    _patch_device_lookup(monkeypatch, None)

    _layout, ctx = routing_render(monkeypatch, "/devices/no-such-device")

    assert ctx == {"route": "unknown"}


def test_nonexistent_device_is_forbidden_not_not_found_when_scope_is_empty(monkeypatch):
    """AUTH-HARDEN-1R2: membership is now decided BEFORE existence for a
    restricted scope.

    An EMPTY-scope technician asking for an id that does not exist gets the
    SAME generic Forbidden as a real-but-unassigned device
    (`test_out_of_scope_device_is_forbidden_not_not_found`) - not Not Found.
    `entity_in_scope`'s device branch is a pure in-memory membership test
    (`DeviceScope.allows`), so it never performs the unrestricted existence
    lookup that would let a Technician tell the two apart. The device-lookup
    stub is left returning `None` deliberately: if the fix ever regressed to
    checking existence first, this test would start failing loudly by
    invoking a lookup this scope must never reach.
    """
    _patch_scope(monkeypatch, DeviceScope(frozenset()))
    _patch_device_lookup(monkeypatch, None)

    _layout, ctx = routing_render(monkeypatch, "/devices/no-such-device")

    assert ctx == {"route": "forbidden"}


def test_forbidden_device_route_issues_no_reading_query(monkeypatch):
    """Invariant 9, made executable. The per-device reading queries take no
    scope constraint; they are safe only because a refused route never builds
    a real page-context for their callbacks to fire on."""
    calls = []
    for name in (
        "get_latest_reading",
        "get_last_reading_before",
        "get_latest_readings_for_device",
        "get_readings_in_range",
        "get_readings_for_device_in_range",
    ):
        monkeypatch.setattr(
            routing.hierarchy_service.repo,
            name,
            lambda *a, _n=name, **k: calls.append(_n),
        )
    _patch_scope(monkeypatch, DeviceScope(frozenset()))
    _patch_device_lookup(monkeypatch, _device_path("anything"))

    _layout, ctx = routing_render(monkeypatch, "/devices/anything")

    assert ctx == {"route": "forbidden"}
    assert calls == [], "a refused route reached {}".format(calls)


# --------------------------------------------------------------------------
# Plant
# --------------------------------------------------------------------------


def test_plant_holding_no_visible_device_is_forbidden(monkeypatch):
    """Invariant 5: a Technician cannot hand-type a path to an otherwise-valid
    plant containing none of their RTLs."""
    _patch_scope(monkeypatch, DeviceScope(frozenset({"mine"})))
    monkeypatch.setattr(
        routing.hierarchy_service,
        "get_plant_or_none",
        lambda plant_id: SimpleNamespace(
            plant_id="plant-07", name="Plant 07", status="active"
        ),
    )
    monkeypatch.setattr(
        routing.hierarchy_service, "list_transformers", lambda plant_id, *, scope: []
    )

    _layout, ctx = routing_render(monkeypatch, "/plants/plant-07")

    assert ctx == {"route": "forbidden"}


def test_plant_holding_a_visible_device_renders(monkeypatch):
    _patch_scope(monkeypatch, DeviceScope(frozenset({"mine"})))
    monkeypatch.setattr(
        routing.hierarchy_service,
        "get_plant_or_none",
        lambda plant_id: SimpleNamespace(
            plant_id="plant-01", name="Plant 01", status="active"
        ),
    )
    monkeypatch.setattr(
        routing.hierarchy_service,
        "list_transformers",
        lambda plant_id, *, scope: [SimpleNamespace(transformer_id="plant-01-t1")],
    )

    _layout, ctx = routing_render(monkeypatch, "/plants/plant-01")

    assert ctx["route"] == "plant"
    assert ctx["plant_id"] == "plant-01"


def test_nonexistent_plant_is_not_found(monkeypatch):
    """Unrestricted scope only (Administrator/General): `entity_in_scope`
    short-circuits True with no query, so the existence lookup below is the
    only check that ever runs and Not Found is still the correct answer.
    See `test_nonexistent_plant_is_forbidden_not_not_found_when_scope_is_empty`
    for the restricted-scope case, which now answers differently on purpose.
    """
    _patch_scope(monkeypatch, DeviceScope(None))
    monkeypatch.setattr(
        routing.hierarchy_service, "get_plant_or_none", lambda plant_id: None
    )

    _layout, ctx = routing_render(monkeypatch, "/plants/no-such-plant")

    assert ctx == {"route": "unknown"}


def test_nonexistent_plant_is_forbidden_not_not_found_when_scope_is_empty(monkeypatch):
    """AUTH-HARDEN-1R2 companion to the device-level fix above, one level up
    the hierarchy: an EMPTY-scope technician gets the same generic Forbidden
    for a plant that does not exist as for one that exists but holds none of
    their RTLs (`test_empty_scope_technician_cannot_reach_a_real_plant`).
    `get_plant_or_none` is left unpatched (its default None) deliberately:
    `entity_in_scope`'s plant branch never calls it for a restricted scope,
    so a caller that starts using it there is exactly what this guards
    against.
    """
    _patch_scope(monkeypatch, DeviceScope(frozenset()))
    monkeypatch.setattr(
        routing.hierarchy_service, "list_transformers", lambda plant_id, *, scope: []
    )

    _layout, ctx = routing_render(monkeypatch, "/plants/no-such-plant")

    assert ctx == {"route": "forbidden"}


# --------------------------------------------------------------------------
# Transformer
# --------------------------------------------------------------------------


def test_transformer_holding_no_visible_device_is_forbidden(monkeypatch):
    """Same rule one level down: a real transformer with zero visible RTLs."""
    _patch_scope(monkeypatch, DeviceScope(frozenset({"mine"})))
    monkeypatch.setattr(
        routing.hierarchy_service,
        "get_plant_or_none",
        lambda plant_id: SimpleNamespace(
            plant_id="plant-07", name="Plant 07", status="active"
        ),
    )
    monkeypatch.setattr(
        routing.hierarchy_service,
        "get_transformer_in_plant",
        lambda plant_id, transformer_id: SimpleNamespace(
            transformer_id="plant-07-t2",
            plant_id="plant-07",
            transformer_code="T2",
            status="active",
        ),
    )
    monkeypatch.setattr(
        routing.hierarchy_service, "list_devices", lambda transformer_id, *, scope: []
    )

    _layout, ctx = routing_render(monkeypatch, "/plants/plant-07/plant-07-t2")

    assert ctx == {"route": "forbidden"}


def test_transformer_holding_a_visible_device_renders(monkeypatch):
    _patch_scope(monkeypatch, DeviceScope(frozenset({"mine"})))
    monkeypatch.setattr(
        routing.hierarchy_service,
        "get_plant_or_none",
        lambda plant_id: SimpleNamespace(
            plant_id="plant-01", name="Plant 01", status="active"
        ),
    )
    monkeypatch.setattr(
        routing.hierarchy_service,
        "get_transformer_in_plant",
        lambda plant_id, transformer_id: SimpleNamespace(
            transformer_id="plant-01-t1",
            plant_id="plant-01",
            transformer_code="T1",
            status="active",
        ),
    )
    monkeypatch.setattr(
        routing.hierarchy_service,
        "list_devices",
        lambda transformer_id, *, scope: [SimpleNamespace(device_id="mine")],
    )

    _layout, ctx = routing_render(monkeypatch, "/plants/plant-01/plant-01-t1")

    assert ctx["route"] == "transformer"
    assert ctx["transformer_id"] == "plant-01-t1"


# --------------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------------


@pytest.mark.parametrize("session", [ADMINISTRATOR_SESSION, GENERAL_SESSION])
def test_unrestricted_roles_reach_any_existing_device(monkeypatch, session):
    """Administrator unchanged, and General keeps unrestricted SIGHT.

    General is read-only on actions, not blind (invariant 3). If this test
    ever fails, someone has confused read-only with restricted visibility.
    """
    _patch_scope(monkeypatch, DeviceScope(None))
    _patch_device_lookup(monkeypatch, _device_path("any-device"))

    _layout, ctx = routing_render(monkeypatch, "/devices/any-device", session=session)

    assert ctx["route"] == "device"
    assert ctx["device_id"] == "any-device"


@pytest.mark.parametrize("session", [ADMINISTRATOR_SESSION, GENERAL_SESSION])
def test_unrestricted_roles_reach_any_existing_plant(monkeypatch, session):
    _patch_scope(monkeypatch, DeviceScope(None))
    monkeypatch.setattr(
        routing.hierarchy_service,
        "get_plant_or_none",
        lambda plant_id: SimpleNamespace(
            plant_id="plant-07", name="Plant 07", status="active"
        ),
    )

    _layout, ctx = routing_render(monkeypatch, "/plants/plant-07", session=session)

    assert ctx["route"] == "plant"


def test_unrestricted_plant_route_does_not_list_transformers(monkeypatch):
    """An unrestricted scope must short-circuit BEFORE the membership probe.

    Otherwise every Administrator plant render pays for an extra listing
    query only to discard the answer.
    """
    calls = []
    _patch_scope(monkeypatch, DeviceScope(None))
    monkeypatch.setattr(
        routing.hierarchy_service,
        "get_plant_or_none",
        lambda plant_id: SimpleNamespace(
            plant_id="plant-07", name="Plant 07", status="active"
        ),
    )
    monkeypatch.setattr(
        routing.hierarchy_service,
        "list_transformers",
        lambda plant_id, *, scope: calls.append(plant_id) or [],
    )

    _layout, ctx = routing_render(monkeypatch, "/plants/plant-07", session=ADMINISTRATOR_SESSION)

    assert ctx["route"] == "plant"
    assert calls == []


# --------------------------------------------------------------------------
# Technician with EMPTY scope
# --------------------------------------------------------------------------


def test_empty_scope_technician_cannot_reach_a_real_device(monkeypatch):
    _patch_scope(monkeypatch, DeviceScope(frozenset()))
    _patch_device_lookup(monkeypatch, _device_path("plant-01-t1-d1"))

    _layout, ctx = routing_render(monkeypatch, "/devices/plant-01-t1-d1")

    assert ctx == {"route": "forbidden"}


def test_empty_scope_technician_cannot_reach_a_real_plant(monkeypatch):
    _patch_scope(monkeypatch, DeviceScope(frozenset()))
    monkeypatch.setattr(
        routing.hierarchy_service,
        "get_plant_or_none",
        lambda plant_id: SimpleNamespace(
            plant_id="plant-01", name="Plant 01", status="active"
        ),
    )
    monkeypatch.setattr(
        routing.hierarchy_service, "list_transformers", lambda plant_id, *, scope: []
    )

    _layout, ctx = routing_render(monkeypatch, "/plants/plant-01")

    assert ctx == {"route": "forbidden"}


def test_empty_scope_technician_cannot_reach_a_real_transformer(monkeypatch):
    _patch_scope(monkeypatch, DeviceScope(frozenset()))
    monkeypatch.setattr(
        routing.hierarchy_service,
        "get_plant_or_none",
        lambda plant_id: SimpleNamespace(
            plant_id="plant-01", name="Plant 01", status="active"
        ),
    )
    monkeypatch.setattr(
        routing.hierarchy_service,
        "get_transformer_in_plant",
        lambda plant_id, transformer_id: SimpleNamespace(
            transformer_id="plant-01-t1",
            plant_id="plant-01",
            transformer_code="T1",
            status="active",
        ),
    )
    monkeypatch.setattr(
        routing.hierarchy_service, "list_devices", lambda transformer_id, *, scope: []
    )

    _layout, ctx = routing_render(monkeypatch, "/plants/plant-01/plant-01-t1")

    assert ctx == {"route": "forbidden"}


# --------------------------------------------------------------------------
# entity_in_scope directly
# --------------------------------------------------------------------------


def test_entity_in_scope_defaults_to_deny_when_given_no_entity():
    """Default-deny: called with no identifier at all, it refuses."""
    assert routing.entity_in_scope(DeviceScope(frozenset({"mine"}))) is False
