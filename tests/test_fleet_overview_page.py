"""Fleet Overview route policy and callback (SATURDAY-REAL-FLEET-01)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from dash import no_update

from callbacks import fleet_overview as cb
from repositories.rtl_temperature_repository import RTLLatestTemperature
from routes import FLEET_OVERVIEW_PATH, NAV_KEY_BY_ROUTE, parse_pathname
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN, may_access_route
from services.device_scope import EMPTY, UNRESTRICTED, DeviceScope
from services.rtl_fleet_service import FleetStatus, RealFleet, build_rows, summarise
from tests.dash_tree import find_by_class, text_of


def test_route_and_policy():
    # RTL-LIST-ROUTE-01: canonical at `/rtls`; `/plants` is a compatibility
    # alias that renders nothing of its own.
    assert FLEET_OVERVIEW_PATH == "/rtls"
    assert parse_pathname("/rtls").name == "overview"
    assert parse_pathname("/plants").name == "rtl_list_alias"
    assert parse_pathname("/plants-new").name == "unknown"
    assert parse_pathname("/rtls-new").name == "unknown"
    assert NAV_KEY_BY_ROUTE["overview"] == "overview"
    for role in (ADMINISTRATOR, TECHNICIAN, GENERAL):
        assert may_access_route(role, "overview")


def test_other_routes_do_nothing():
    assert cb.populate({"route": "plant"}) == (no_update,) * cb.OUTPUTS
    assert cb.populate(None) == (no_update,) * cb.OUTPUTS


def _fleet() -> RealFleet:
    rows = build_rows([2, 1], {}, {}, {})
    return RealFleet(FleetStatus.DATA, rows, summarise(rows))


def test_unrestricted_scope_reads_the_fleet_once():
    calls = []
    out = cb.populate({"route": "overview"}, fetch=lambda: calls.append(1) or _fleet(),
                      scope_for=lambda: UNRESTRICTED)
    stats, refreshed, listing, error, options = out
    assert calls == [1] and error is None
    assert "Registered RTLs" in text_of(stats)
    assert refreshed.startswith("Updated ")
    assert [o["value"] for o in options][0] == "all"
    assert "No temperature data" in text_of(listing)


def test_restricted_scopes_never_read_the_rtl_source():
    def fetch():
        raise AssertionError("RTL source must not be read for a restricted scope")

    for scope in (EMPTY, DeviceScope(frozenset({"plant-01-t1-d1"})), None):
        stats, _r, listing, error, options = cb.populate(
            {"route": "overview"}, fetch=fetch, scope_for=lambda s=scope: s)
        assert stats is None and error is None and options == []
        assert find_by_class(listing, "status-panel")
        assert "plant-01" not in text_of(listing)


def test_unavailable_source_shows_error_not_an_empty_fleet():
    out = cb.populate({"route": "overview"},
                      fetch=lambda: RealFleet(FleetStatus.UNAVAILABLE),
                      scope_for=lambda: UNRESTRICTED)
    stats, _r, listing, error, options = out
    assert stats is None and listing == [] and options == []
    assert find_by_class(error, "status-panel--error")
    assert "unavailable" in text_of(error)


def test_a_failing_read_shows_the_error_panel_without_internals():
    def boom():
        raise RuntimeError("password=hunter2 connection refused")

    _s, _r, listing, error, _o = cb.populate(
        {"route": "overview"}, fetch=boom, scope_for=lambda: UNRESTRICTED)
    assert listing == []
    assert find_by_class(error, "status-panel--error")
    assert "hunter2" not in text_of(error) and "RuntimeError" not in text_of(error)


def test_filter_reaches_the_list():
    latest = {1: RTLLatestTemperature(1, datetime(2026, 9, 1, 8, 0), Decimal("20"), 1, (Decimal("20"),))}
    rows = build_rows([1, 2], latest, {}, {})
    fleet = RealFleet(FleetStatus.DATA, rows, summarise(rows))
    out = cb.populate({"route": "overview"}, "no_temperature",
                      fetch=lambda: fleet, scope_for=lambda: UNRESTRICTED)
    text = text_of(out[2])
    assert "No temperature data" in text and "20.0" not in text
