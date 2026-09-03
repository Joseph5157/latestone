"""Route scope gating against a real database (ROLE-3 Task 9 / AUTH-HARDEN-1).

WHY THIS FILE EXISTS SEPARATELY FROM tests/test_route_scope.py.

Those tests patch `routing.current_device_scope` (and, for the identity
itself, `routing.current_identity`) so they can state each gating outcome
without a database. That makes them precise about the RULE and completely
blind to the WIRING: if the router resolved scope from the wrong function -
or, pre-AUTH-HARDEN-1, from the raw `auth-store` role instead of a validated
identity - every one of them would still pass.

These tests patch NOTHING in the identity/scope path. A real technician row
and a real assignment row go into the database, a REAL Flask session is
established via `auth_service.start_trusted_session` (the same call
`callbacks.auth.handle_login` makes on a real login), and `route_to_page` is
invoked exactly as the app would invoke it: `current_identity()`,
`current_device_scope()`, the assignment lookup and `DeviceScope` resolution
all run for real, inside a real Flask request context. This is the test that
fails if the router is wired to the wrong resolver, and the one place in this
suite that proves a forged `auth-store` payload cannot change the outcome -
every render below passes an auth_data payload that is either None or
actively WRONG about the signed-in role, and the trusted Flask session is what
actually decides.

Runs against a disposable schema - never the developer's real
plant_monitoring.* tables. See tests/conftest.py::isolated_schema.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

import app as app_module
from callbacks import routing
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import auth_service
from services.prototype_users import clear_all_users, upsert_user

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

PLANT_ID = "rs-p01"
TRANSFORMER_ID = "rs-p01-t1"
OTHER_TRANSFORMER_ID = "rs-p01-t2"
ASSIGNED_DEVICE = "rs-mine"
OTHER_DEVICE = "rs-theirs"

#: A second, wholly unrelated plant -- AUTH-HARDEN-1R2's R2-01/R2-04 need a
#: plant-level and transformer-level "valid but unrelated" entity that is not
#: merely a sibling inside the technician's own plant.
UNRELATED_PLANT_ID = "rs-p02"
UNRELATED_TRANSFORMER_ID = "rs-p02-t1"
UNRELATED_DEVICE_ID = "rs-p02-d1"


class _CapturingApp:
    """Collects `routing.register`'s one callback instead of wiring a runtime."""

    def __init__(self):
        self.functions = []

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions.append(fn)
            return fn

        return decorator


def routing_render(pathname: str, user_id: int, *, forged_role: str | None = None):
    """Render `pathname` as the REAL trusted user `user_id`.

    Establishes a genuine Flask session via `start_trusted_session` - the same
    call the real login callback makes - inside a real request context, then
    invokes the real `route_to_page`. `forged_role`, when given, is passed as
    `auth_data`'s role: a browser-supplied claim the callback must ignore,
    proving the trusted session decides rather than this payload.
    """
    auth_data = (
        {
            "authenticated": True,
            "user_id": user_id,
            "username": "irrelevant",
            "full_name": "Irrelevant",
            "role": forged_role,
        }
        if forged_role is not None
        else None
    )
    with app_module.app.server.test_request_context():
        auth_service.start_trusted_session(user_id)
        app = _CapturingApp()
        routing.register(app)
        route_to_page = app.functions[0]
        return route_to_page(pathname, "", auth_data)


def _seed_tree() -> None:
    """Two transformers under one plant; one device beneath each. Plus a
    wholly separate second plant/transformer/device the technician has no
    relationship to at all.

    The second transformer under PLANT_ID matters: it is the mixed-visibility
    shape that a single-transformer fixture cannot express, and it is what
    proves a technician assigned inside a plant still cannot reach the
    SIBLING transformer holding none of their RTLs. The second PLANT matters
    separately (AUTH-HARDEN-1R2): it is what proves a technician cannot reach
    a plant/transformer/device they have no relationship to at any level,
    not just a sibling within their own plant.
    """
    with session_scope() as session:
        for plant_id, name in (
            (PLANT_ID, "Route Scope Plant"),
            (UNRELATED_PLANT_ID, "Unrelated Scope Plant"),
        ):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.plants "
                    f"(plant_id, name, country, latitude, longitude) "
                    f"VALUES (:plant_id, :name, 'Testland', 0, 0) "
                    f"ON CONFLICT (plant_id) DO NOTHING"
                ),
                {"plant_id": plant_id, "name": name},
            )
        for transformer_id, plant_id, code in (
            (TRANSFORMER_ID, PLANT_ID, "t1"),
            (OTHER_TRANSFORMER_ID, PLANT_ID, "t2"),
            (UNRELATED_TRANSFORMER_ID, UNRELATED_PLANT_ID, "u1"),
        ):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.transformers "
                    f"(transformer_id, plant_id, transformer_code) "
                    f"VALUES (:transformer_id, :plant_id, :code) "
                    f"ON CONFLICT (transformer_id) DO NOTHING"
                ),
                {
                    "transformer_id": transformer_id,
                    "plant_id": plant_id,
                    "code": code,
                },
            )
        for device_id, transformer_id in (
            (ASSIGNED_DEVICE, TRANSFORMER_ID),
            (OTHER_DEVICE, OTHER_TRANSFORMER_ID),
            (UNRELATED_DEVICE_ID, UNRELATED_TRANSFORMER_ID),
        ):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    f"(device_id, transformer_id, device_code) "
                    f"VALUES (:device_id, :transformer_id, :device_id) "
                    f"ON CONFLICT (device_id) DO NOTHING"
                ),
                {"device_id": device_id, "transformer_id": transformer_id},
            )


def _auditor_id() -> int:
    """AUD-1: audited service writes require an authenticated actor; this
    one is created at repository level (no audit row)."""
    return repo.create_or_update_user(
        username="route-scope-auditor",
        full_name="route-scope-auditor",
        role="administrator",
        status="active",
    ).user_id


def _real_technician(username: str, *, assigned: list[str]) -> int:
    """A real user row and real assignments. Returns the trusted user_id."""
    # Audit rows before assignments before users: each FK-references the
    # table created before it in earlier flows.
    with session_scope() as session:
        session.execute(text(f"DELETE FROM {repo._SCHEMA}.audit_log"))
    repo.delete_all_assignments()
    clear_all_users()
    upsert_user(username, role="technician", actor_user_id=_auditor_id())
    record = repo.get_user_by_username(username)
    assert record is not None
    for device_id in assigned:
        repo.assign_device_to_user(device_id, username, None)
    return record.user_id


def test_assigned_device_renders_for_a_real_technician():
    _seed_tree()
    user_id = _real_technician("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render(f"/devices/{ASSIGNED_DEVICE}", user_id)

    assert ctx["route"] == "device"
    assert ctx["device_id"] == ASSIGNED_DEVICE


def test_unassigned_device_is_forbidden_for_a_real_technician():
    """The direct-URL bypass, closed against real data."""
    _seed_tree()
    user_id = _real_technician("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render(f"/devices/{OTHER_DEVICE}", user_id)

    assert ctx == {"route": "forbidden"}


def test_nonexistent_device_is_forbidden_not_not_found_for_a_real_technician():
    """AUTH-HARDEN-1R2 (Finding 1), against real data.

    Superseded assertion: this test previously asserted Not Found here,
    treating "no such device" as distinguishable from "a real device that
    is not yours" for a restricted Technician. That was itself the existence
    oracle AUTH-HARDEN-1R2 closes -- see `test_route_scope.py`'s module
    docstring for the full reasoning. A real technician session now gets the
    identical Forbidden outcome for both (`test_unassigned_device_is_forbidden
    _for_a_real_technician` above), proven here against a genuinely
    nonexistent id rather than a mocked lookup.
    """
    _seed_tree()
    user_id = _real_technician("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render("/devices/rs-no-such-device", user_id)

    assert ctx == {"route": "forbidden"}


def test_sibling_transformer_is_forbidden_for_a_real_technician():
    """A real transformer in a plant they CAN see, holding none of their RTLs."""
    _seed_tree()
    user_id = _real_technician("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render(
        f"/plants/{PLANT_ID}/{OTHER_TRANSFORMER_ID}", user_id
    )

    assert ctx == {"route": "forbidden"}


def test_own_transformer_renders_for_a_real_technician():
    _seed_tree()
    user_id = _real_technician("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render(f"/plants/{PLANT_ID}/{TRANSFORMER_ID}", user_id)

    assert ctx["route"] == "transformer"
    assert ctx["transformer_id"] == TRANSFORMER_ID


def test_plant_holding_an_assigned_device_renders_for_a_real_technician():
    _seed_tree()
    user_id = _real_technician("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render(f"/plants/{PLANT_ID}", user_id)

    assert ctx["route"] == "plant"


def test_technician_with_no_assignments_is_forbidden_everywhere():
    """Invariant 2: zero assignments resolves to EMPTY, never unrestricted.

    If a bug ever turned EMPTY into None, this technician would reach every
    resource below and all three assertions would fail at once.
    """
    _seed_tree()
    user_id = _real_technician("rs-lonely-tech", assigned=[])

    for path in (
        f"/devices/{ASSIGNED_DEVICE}",
        f"/plants/{PLANT_ID}",
        f"/plants/{PLANT_ID}/{TRANSFORMER_ID}",
    ):
        _layout, ctx = routing_render(path, user_id)
        assert ctx == {"route": "forbidden"}, path


def test_ended_assignment_does_not_grant_access():
    """Reassignment history must not grant visibility.

    The device was theirs and is not any more. `list_active_device_ids_for_user`
    filters on the active assignment, so the route must refuse.
    """
    _seed_tree()
    user_id = _real_technician("rs-tech", assigned=[ASSIGNED_DEVICE])
    repo.end_active_device_assignment(ASSIGNED_DEVICE)

    _layout, ctx = routing_render(f"/devices/{ASSIGNED_DEVICE}", user_id)

    assert ctx == {"route": "forbidden"}


# ---------------------------------------------------------------------------
# AUTH-HARDEN-1 - the forged-payload proof this file exists to make
# ---------------------------------------------------------------------------


def test_a_forged_administrator_role_does_not_widen_a_real_technicians_scope():
    """AUTH-HARDEN-02, against real data. `auth_data` claims administrator;
    the trusted Flask session says this user_id is a real technician with one
    assignment. The forgery must not be consulted."""
    _seed_tree()
    user_id = _real_technician("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render(
        f"/devices/{OTHER_DEVICE}", user_id, forged_role="administrator"
    )

    assert ctx == {"route": "forbidden"}


def test_a_forged_role_does_not_unlock_admin_devices_for_a_real_technician():
    """AUTH-HARDEN-02's route-level twin: forging the role in auth_data must
    not unlock an administrator-only route for a real technician user_id."""
    _seed_tree()
    user_id = _real_technician("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render(
        "/admin/devices", user_id, forged_role="administrator"
    )

    assert ctx == {"route": "forbidden"}


# ---------------------------------------------------------------------------
# AUTH-HARDEN-1R2 (Finding 1) - the full router existence-oracle matrix,
# against a real trusted Technician session and real seeded data. For every
# entity level: valid-but-unrelated and nonexistent must be INDISTINGUISHABLE
# (same {"route": "forbidden"} shape), while the assigned entity still
# renders normally. Administrator and General stay unrestricted throughout.
# ---------------------------------------------------------------------------


def _technician_with_assignment():
    _seed_tree()
    return _real_technician("rs-tech", assigned=[ASSIGNED_DEVICE])


def _administrator_id() -> int:
    return _auditor_id()


def _real_general(username: str) -> int:
    with session_scope() as session:
        session.execute(text(f"DELETE FROM {repo._SCHEMA}.audit_log"))
    repo.delete_all_assignments()
    clear_all_users()
    upsert_user(username, role="general", actor_user_id=_auditor_id())
    record = repo.get_user_by_username(username)
    assert record is not None
    return record.user_id


# -- Plant level: R2-01/R2-02/R2-03 --


def test_r2_01_technician_valid_unrelated_plant_is_forbidden():
    user_id = _technician_with_assignment()

    _layout, ctx = routing_render(f"/plants/{UNRELATED_PLANT_ID}", user_id)

    assert ctx == {"route": "forbidden"}


def test_r2_02_technician_nonexistent_plant_is_forbidden_same_shape_as_r2_01():
    user_id = _technician_with_assignment()

    _layout, ctx = routing_render("/plants/rs-no-such-plant", user_id)

    assert ctx == {"route": "forbidden"}, (
        "must be INDISTINGUISHABLE from R2-01's valid-but-unrelated plant"
    )


def test_r2_03_technician_assigned_plant_renders_normally():
    user_id = _technician_with_assignment()

    _layout, ctx = routing_render(f"/plants/{PLANT_ID}", user_id)

    assert ctx["route"] == "plant"
    assert ctx["plant_id"] == PLANT_ID


# -- Transformer level: R2-04/R2-05/R2-06 --


def test_r2_04_technician_valid_unrelated_transformer_is_forbidden():
    user_id = _technician_with_assignment()

    _layout, ctx = routing_render(
        f"/plants/{UNRELATED_PLANT_ID}/{UNRELATED_TRANSFORMER_ID}", user_id
    )

    assert ctx == {"route": "forbidden"}


def test_r2_05_technician_nonexistent_transformer_is_forbidden_same_shape_as_r2_04():
    user_id = _technician_with_assignment()

    _layout, ctx = routing_render(
        f"/plants/{PLANT_ID}/rs-no-such-transformer", user_id
    )

    assert ctx == {"route": "forbidden"}, (
        "must be INDISTINGUISHABLE from R2-04's valid-but-unrelated transformer"
    )


def test_r2_06_technician_assigned_transformer_renders_normally():
    user_id = _technician_with_assignment()

    _layout, ctx = routing_render(f"/plants/{PLANT_ID}/{TRANSFORMER_ID}", user_id)

    assert ctx["route"] == "transformer"
    assert ctx["transformer_id"] == TRANSFORMER_ID


# -- Device level: R2-07/R2-08/R2-09 --


def test_r2_07_technician_valid_unassigned_device_is_forbidden():
    user_id = _technician_with_assignment()

    _layout, ctx = routing_render(f"/devices/{UNRELATED_DEVICE_ID}", user_id)

    assert ctx == {"route": "forbidden"}


def test_r2_08_technician_nonexistent_device_is_forbidden_same_shape_as_r2_07():
    user_id = _technician_with_assignment()

    _layout, ctx = routing_render("/devices/rs-no-such-device-r2", user_id)

    assert ctx == {"route": "forbidden"}, (
        "must be INDISTINGUISHABLE from R2-07's valid-but-unassigned device"
    )


def test_r2_09_technician_assigned_device_renders_normally():
    user_id = _technician_with_assignment()

    _layout, ctx = routing_render(f"/devices/{ASSIGNED_DEVICE}", user_id)

    assert ctx["route"] == "device"
    assert ctx["device_id"] == ASSIGNED_DEVICE


# -- Administrator / General: unchanged, still genuinely unrestricted --


def test_r2_administrator_reaches_the_unrelated_plant_transformer_and_device():
    """Unrestricted scope: entity_in_scope short-circuits True, so the
    reorder in callbacks/routing.py changes nothing observable here."""
    _seed_tree()
    user_id = _administrator_id()

    _layout, plant_ctx = routing_render(f"/plants/{UNRELATED_PLANT_ID}", user_id)
    assert plant_ctx["route"] == "plant"

    _layout, transformer_ctx = routing_render(
        f"/plants/{UNRELATED_PLANT_ID}/{UNRELATED_TRANSFORMER_ID}", user_id
    )
    assert transformer_ctx["route"] == "transformer"

    _layout, device_ctx = routing_render(f"/devices/{UNRELATED_DEVICE_ID}", user_id)
    assert device_ctx["route"] == "device"


def test_r2_administrator_nonexistent_entities_are_still_not_found():
    """Administrator keeps the real existence answer -- only a restricted
    scope's existence check moved."""
    _seed_tree()
    user_id = _administrator_id()

    _layout, ctx = routing_render("/plants/rs-no-such-plant", user_id)
    assert ctx == {"route": "unknown"}


def test_r2_general_reaches_the_unrelated_plant_transformer_and_device():
    """General is read-only on actions, not blind (ROLE-3 invariant 3) --
    unchanged by this repair."""
    _seed_tree()
    user_id = _real_general("rs-general")

    _layout, plant_ctx = routing_render(f"/plants/{UNRELATED_PLANT_ID}", user_id)
    assert plant_ctx["route"] == "plant"

    _layout, transformer_ctx = routing_render(
        f"/plants/{UNRELATED_PLANT_ID}/{UNRELATED_TRANSFORMER_ID}", user_id
    )
    assert transformer_ctx["route"] == "transformer"

    _layout, device_ctx = routing_render(f"/devices/{UNRELATED_DEVICE_ID}", user_id)
    assert device_ctx["route"] == "device"
