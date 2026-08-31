"""The Device Administration Status filter, at the callback (FIX-1A2).

`pages/device_admin.py` offers All / Active / Inactive, but the callback read
the fleet with `list_all_devices()` and its `include_inactive=False` default,
so inactive devices never entered the table for the filter to match. The
filter was not broken — it was correct code filtering a population that could
not contain what it was asked for.

Two consequences, both covered here: choosing "Inactive" returned nothing,
and the summary line's inactive count was structurally always 0.

The gate forbids changing `list_all_devices()`'s default, because
`db/live_simulator.py`, `db/seed_admin_demo.py`, `db/seed_events_demo.py` and
`callbacks/listings.py` rely on it. So the assertion here is specifically that
DEVICE ADMINISTRATION asks for the population its own filter advertises —
`test_device_admin_explicitly_requests_inactive_devices` pins that, and fails
if someone later "fixes" this by moving the default instead.

Nothing here touches a database: the fleet read, freshness and assignment
lookups are all replaced.
"""
from __future__ import annotations

import types

import pytest

from callbacks import device_admin

ADMIN_CONTEXT = {"route": "admin_devices"}


def _device(device_id, code, status):
    return types.SimpleNamespace(
        device_id=device_id,
        device_code=code,
        status=status,
        transformer_id="t1",
        transformer_code="T1",
        plant_name="Plant One",
    )


#: One active and one inactive device. The inactive one is the whole point:
#: before the fix the fleet read could not return it at all.
ACTIVE_DEVICE = _device("d-active", "aa01", "active")
INACTIVE_DEVICE = _device("d-inactive", "aa02", "inactive")


class _FleetReadSpy:
    """Records how Device Administration asked for the fleet."""

    def __init__(self, devices):
        self.devices = devices
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append(kwargs)
        # Honour the real contract: without include_inactive, inactive rows
        # are not returned. A spy that ignored the flag would let the broken
        # call site pass.
        if kwargs.get("include_inactive"):
            return list(self.devices)
        return [d for d in self.devices if d.status == "active"]


class _CapturingApp:
    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


@pytest.fixture
def fleet(monkeypatch):
    """Device Administration wired to a two-device fleet, no database."""
    spy = _FleetReadSpy([ACTIVE_DEVICE, INACTIVE_DEVICE])
    monkeypatch.setattr(device_admin.hierarchy_service, "list_all_devices", spy)

    health = types.SimpleNamespace(devices={}, device_last_updated={})
    monkeypatch.setattr(
        device_admin.monitoring_service, "get_fleet_health", lambda *a, **k: health
    )
    monkeypatch.setattr(
        device_admin.prototype_assignments,
        "assigned_technicians",
        lambda: {"d-inactive": "tech1"},
    )

    app = _CapturingApp()
    device_admin.register(app)
    return app.functions["populate_device_admin"], spy


def _run(handler, status):
    """Render the table with the given Status filter."""
    rows, _columns, error, summary, _empty = handler(ADMIN_CONTEXT, "", status)
    assert error is None, "the fixture fleet must render without an error panel"
    return rows, summary


# --------------------------------------------------------------------------
# The defect
# --------------------------------------------------------------------------


def test_inactive_filter_returns_inactive_devices(fleet):
    handler, _spy = fleet

    rows, _summary = _run(handler, "inactive")

    assert [r["id"] for r in rows] == ["d-inactive"], (
        "choosing Inactive must return the inactive device; before the fix the "
        "fleet read excluded it, so this returned nothing"
    )


def test_device_admin_explicitly_requests_inactive_devices(fleet):
    """The population must be asked for at the call site, not by moving the
    shared default that other callers depend on."""
    handler, spy = fleet

    _run(handler, "all")

    assert spy.calls, "the fleet read must happen"
    assert all(call.get("include_inactive") is True for call in spy.calls), (
        "Device Administration must request the population its advertised "
        "filter needs"
    )


def test_summary_counts_inactive_devices(fleet):
    """The split under the toolbar was structurally always '0 inactive'."""
    handler, _spy = fleet

    _rows, summary = _run(handler, "all")

    assert "1 inactive" in summary, summary


# --------------------------------------------------------------------------
# Guards — these must not regress while the population widens
# --------------------------------------------------------------------------


def test_active_filter_still_returns_only_active_devices(fleet):
    handler, _spy = fleet

    rows, _summary = _run(handler, "active")

    assert [r["id"] for r in rows] == ["d-active"], (
        "widening the read must not leak inactive devices into the Active view"
    )


def test_all_filter_returns_both(fleet):
    handler, _spy = fleet

    rows, _summary = _run(handler, "all")

    assert sorted(r["id"] for r in rows) == ["d-active", "d-inactive"]


def test_enrichment_survives_for_inactive_rows(fleet):
    """Freshness and technician assignment must still be attached — a device
    that appears only because the population widened must not arrive bare."""
    handler, _spy = fleet

    rows, _summary = _run(handler, "inactive")

    row = rows[0]
    assert row["technician"] == "tech1", "assignment enrichment must survive"
    assert row["freshness"] == "No data", "freshness must still be resolved"
    assert row["status"] == "Inactive"
    assert row["plant"] == "Plant One" and row["transformer"] == "T1"
