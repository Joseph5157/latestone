"""Route scope gating against a real database (ROLE-3 Task 9).

WHY THIS FILE EXISTS SEPARATELY FROM tests/test_route_scope.py.

Those tests patch `routing.scope_from_session` so they can state each gating
outcome without a database. That makes them precise about the RULE and
completely blind to the WIRING: if the router resolved scope from the wrong
function — or from the raw `auth-store` role instead of the validated
identity — every one of them would still pass.

These tests patch nothing. A real technician row, a real assignment row, and
a real session payload go in; the assignment lookup, `from_session`
validation and `DeviceScope` resolution all run for real. This is the test
that fails if the router is wired to the wrong resolver.

Runs against a disposable schema — never the developer's real
plant_monitoring.* tables. See tests/conftest.py::isolated_schema.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services.prototype_users import clear_all_users, upsert_user
from tests.test_route_scope import routing_render

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

PLANT_ID = "rs-p01"
TRANSFORMER_ID = "rs-p01-t1"
OTHER_TRANSFORMER_ID = "rs-p01-t2"
ASSIGNED_DEVICE = "rs-mine"
OTHER_DEVICE = "rs-theirs"


def _seed_tree() -> None:
    """Two transformers under one plant; one device beneath each.

    The second transformer matters: it is the mixed-visibility shape that a
    single-transformer fixture cannot express, and it is what proves a
    technician assigned inside a plant still cannot reach the SIBLING
    transformer holding none of their RTLs.
    """
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                f"(plant_id, name, country, latitude, longitude) "
                f"VALUES (:plant_id, 'Route Scope Plant', 'Testland', 0, 0) "
                f"ON CONFLICT (plant_id) DO NOTHING"
            ),
            {"plant_id": PLANT_ID},
        )
        for transformer_id, code in (
            (TRANSFORMER_ID, "t1"),
            (OTHER_TRANSFORMER_ID, "t2"),
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
                    "plant_id": PLANT_ID,
                    "code": code,
                },
            )
        for device_id, transformer_id in (
            (ASSIGNED_DEVICE, TRANSFORMER_ID),
            (OTHER_DEVICE, OTHER_TRANSFORMER_ID),
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


def _technician_session(username: str, *, assigned: list[str]) -> dict:
    """A real user row, real assignments, and the session payload for them."""
    # Child table (assignments) before parent (users): a prior test in this
    # module-scoped schema may have left assignment rows FK-referencing its
    # users.
    repo.delete_all_assignments()
    clear_all_users()
    upsert_user(username, role="technician")
    record = repo.get_user_by_username(username)
    assert record is not None
    for device_id in assigned:
        repo.assign_device_to_user(device_id, username, None)
    return {
        "authenticated": True,
        "user_id": record.user_id,
        "username": username,
        "full_name": "Route Scope Tech",
        "role": "technician",
    }


def test_assigned_device_renders_for_a_real_technician():
    _seed_tree()
    session = _technician_session("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render(f"/devices/{ASSIGNED_DEVICE}", session=session)

    assert ctx["route"] == "device"
    assert ctx["device_id"] == ASSIGNED_DEVICE


def test_unassigned_device_is_forbidden_for_a_real_technician():
    """The direct-URL bypass, closed against real data."""
    _seed_tree()
    session = _technician_session("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render(f"/devices/{OTHER_DEVICE}", session=session)

    assert ctx == {"route": "forbidden"}


def test_nonexistent_device_is_not_found_for_a_real_technician():
    """Invariant 5 against real data: the two refusals stay distinct."""
    _seed_tree()
    session = _technician_session("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render("/devices/rs-no-such-device", session=session)

    assert ctx == {"route": "unknown"}


def test_sibling_transformer_is_forbidden_for_a_real_technician():
    """A real transformer in a plant they CAN see, holding none of their RTLs."""
    _seed_tree()
    session = _technician_session("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render(
        f"/plants/{PLANT_ID}/{OTHER_TRANSFORMER_ID}", session=session
    )

    assert ctx == {"route": "forbidden"}


def test_own_transformer_renders_for_a_real_technician():
    _seed_tree()
    session = _technician_session("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render(
        f"/plants/{PLANT_ID}/{TRANSFORMER_ID}", session=session
    )

    assert ctx["route"] == "transformer"
    assert ctx["transformer_id"] == TRANSFORMER_ID


def test_plant_holding_an_assigned_device_renders_for_a_real_technician():
    _seed_tree()
    session = _technician_session("rs-tech", assigned=[ASSIGNED_DEVICE])

    _layout, ctx = routing_render(f"/plants/{PLANT_ID}", session=session)

    assert ctx["route"] == "plant"


def test_technician_with_no_assignments_is_forbidden_everywhere():
    """Invariant 2: zero assignments resolves to EMPTY, never unrestricted.

    If a bug ever turned EMPTY into None, this technician would reach every
    resource below and all three assertions would fail at once.
    """
    _seed_tree()
    session = _technician_session("rs-lonely-tech", assigned=[])

    for path in (
        f"/devices/{ASSIGNED_DEVICE}",
        f"/plants/{PLANT_ID}",
        f"/plants/{PLANT_ID}/{TRANSFORMER_ID}",
    ):
        _layout, ctx = routing_render(path, session=session)
        assert ctx == {"route": "forbidden"}, path


def test_ended_assignment_does_not_grant_access():
    """Reassignment history must not grant visibility.

    The device was theirs and is not any more. `list_active_device_ids_for_user`
    filters on the active assignment, so the route must refuse.
    """
    _seed_tree()
    session = _technician_session("rs-tech", assigned=[ASSIGNED_DEVICE])
    repo.end_active_device_assignment(ASSIGNED_DEVICE)

    _layout, ctx = routing_render(f"/devices/{ASSIGNED_DEVICE}", session=session)

    assert ctx == {"route": "forbidden"}
