"""FO-NEW-1 / SWITCH-OVER-1: route, policy and callback of the Fleet Overview."""
from __future__ import annotations

from datetime import datetime, timezone

from dash import no_update

from callbacks import fleet_overview as cb
from routes import FLEET_OVERVIEW_PATH, NAV_KEY_BY_ROUTE, parse_pathname
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN, ROUTE_POLICY, may_access_route
from services.device_scope import DeviceScope
from services.fleet_overview_service import FleetOverview


def test_route_and_policy():
    assert FLEET_OVERVIEW_PATH == "/plants"
    assert parse_pathname("/plants").name == "overview"
    assert parse_pathname("/plants-new").name == "unknown"
    assert NAV_KEY_BY_ROUTE["overview"] == "overview"
    for role in (ADMINISTRATOR, TECHNICIAN, GENERAL):
        assert may_access_route(role, "overview")


def test_other_routes_do_nothing():
    assert cb.populate({"route": "plant"}) == (no_update,) * cb.OUTPUTS


def test_fetches_once_with_the_resolved_scope():
    scope = DeviceScope(device_ids=frozenset({"d1"}))
    calls = []

    def fetch(s, *, now):
        calls.append(s)
        return FleetOverview(now, None, ())

    summary, _, limits, plants, error = cb.populate(
        {"route": "overview"}, fetch=fetch, scope_for=lambda: scope
    )
    assert calls == [scope]
    assert summary == "0 plants · 0 transformers · 0 RTLs"
    assert error is None


def test_failed_read_shows_the_error_panel_not_an_empty_list():
    def fetch(s, *, now):
        raise RuntimeError("db down")

    out = cb.populate({"route": "overview"}, fetch=fetch, scope_for=lambda: None)
    assert out[3] == [] and out[4] is not None
