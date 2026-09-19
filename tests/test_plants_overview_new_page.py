"""FO-NEW-1: route, policy and callback body of the new Fleet Overview."""
from __future__ import annotations

from datetime import datetime, timezone

from dash import no_update

from callbacks import plants_overview_new as cb
from routes import FLEET_OVERVIEW_NEW_PATH, NAV_KEY_BY_ROUTE, parse_pathname
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN, ROUTE_POLICY, may_access_route
from services.device_scope import DeviceScope
from services.fleet_overview_service import FleetOverview


def test_route_and_policy():
    assert FLEET_OVERVIEW_NEW_PATH == "/plants-new"
    assert parse_pathname("/plants-new").name == "overview_new"
    assert NAV_KEY_BY_ROUTE["overview_new"] == "overview"
    assert ROUTE_POLICY["overview_new"] == ROUTE_POLICY["overview"]
    for role in (ADMINISTRATOR, TECHNICIAN, GENERAL):
        assert may_access_route(role, "overview_new")


def test_other_routes_do_nothing():
    assert cb.populate({"route": "overview"}) == (no_update,) * cb.OUTPUTS


def test_fetches_once_with_the_resolved_scope():
    scope = DeviceScope(device_ids=frozenset({"d1"}))
    calls = []

    def fetch(s, *, now):
        calls.append(s)
        return FleetOverview(now, None, ())

    summary, _, limits, plants, error = cb.populate(
        {"route": "overview_new"}, fetch=fetch, scope_for=lambda: scope
    )
    assert calls == [scope]
    assert summary == "0 plants · 0 transformers · 0 RTLs"
    assert error is None


def test_failed_read_shows_the_error_panel_not_an_empty_list():
    def fetch(s, *, now):
        raise RuntimeError("db down")

    out = cb.populate({"route": "overview_new"}, fetch=fetch, scope_for=lambda: None)
    assert out[3] == [] and out[4] is not None
