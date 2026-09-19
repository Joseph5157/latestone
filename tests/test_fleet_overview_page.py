"""FO-NEW-1 / SWITCH-OVER-1: route, policy and callback of the Fleet Overview."""
from __future__ import annotations

from datetime import datetime, timezone

from dash import no_update

from callbacks import fleet_overview as cb
from routes import FLEET_OVERVIEW_PATH, NAV_KEY_BY_ROUTE, parse_pathname
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN, ROUTE_POLICY, may_access_route
from services.device_scope import DeviceScope
from services.fleet_overview_service import FleetOverview


def _texts(node):
    if isinstance(node, str):
        yield node
        return
    kids = getattr(node, "children", None)
    for k in (kids if isinstance(kids, (list, tuple)) else [kids] if kids is not None else []):
        yield from _texts(k)


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

    summary, _, limits, plants, error, options = cb.populate(
        {"route": "overview"}, fetch=fetch, scope_for=lambda: scope
    )
    assert calls == [scope]
    assert "Reporting" in " ".join(n for n in _texts(summary))
    assert error is None
    assert [o["value"] for o in options] == ["all", "no_recent_data"]


def test_failed_read_shows_the_error_panel_not_an_empty_list():
    def fetch(s, *, now):
        raise RuntimeError("db down")

    out = cb.populate({"route": "overview"}, fetch=fetch, scope_for=lambda: None)
    assert out[3] == [] and out[4] is not None


def test_filter_and_sort_reach_the_list():
    from datetime import timedelta
    from decimal import Decimal
    from services.fleet_overview_service import ConditionCounts, PlantView, TransformerView
    from services.temperature_condition_service import (
        DeviceTemperature, TemperatureCondition as C, TemperatureLimits,
    )

    def plant(pid, value, counts):
        t = DeviceTemperature(pid, f"{pid}-t", "T", f"{pid}-d", "D", value,
                              datetime.now(timezone.utc) - timedelta(minutes=5), C.NORMAL)
        return PlantView(pid, pid.upper(), "ZA", (TransformerView(f"{pid}-t", "T", None, None, None, (t,)),),
                         t, counts)

    view = FleetOverview(datetime.now(timezone.utc), TemperatureLimits(Decimal(36), Decimal(40)), (
        plant("a", 30.0, ConditionCounts(normal=1)),
        plant("b", 41.0, ConditionCounts(hot=1)),
    ))
    out = cb.populate({"route": "overview"}, "hot", "name",
                      fetch=lambda s, *, now: view, scope_for=lambda: None)
    rows = out[3].children
    assert len(rows) == 1
    assert {o["value"]: o["label"] for o in out[5]}["hot"] == "Hot · 1"
