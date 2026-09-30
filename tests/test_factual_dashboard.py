"""FACTUAL-DASHBOARD-01 - the factual RTL dashboard."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from dash import no_update

from callbacks import rtl_dashboard as cb
from components import rtl_dashboard as ui
from pages import rtl_dashboard as page
from repositories.rtl_temperature_repository import RTLLatestTemperature as Latest
from repositories.rtl_temperature_repository import RTLReportedTransformerCode as Code
from repositories.rtl_temperature_repository import RTLTransformerHierarchy as H
from repositories.rtl_temperature_repository import RTLTransformerMapping as M
from services import rtl_dashboard_service as svc
from services import rtl_fleet_service as fleet
from services import rtl_network_service as net
from services.device_scope import EMPTY, UNRESTRICTED, DeviceScope
from tests.dash_tree import walk
from tests.test_rtl_network import FakeRepo

ROOT = Path(__file__).resolve().parents[1]
WHEN = datetime(2022, 3, 4, 5, 6)


class Repo(FakeRepo):
    def get_latest_temperatures(self, uids):
        return {u: Latest(u, WHEN if u == 1 else datetime(2022, 1, 1), Decimal("20.0"), 1, (Decimal("20.0"),))
                for u in uids if u in (1, 2)}


def _repo(extra_registered=()):
    return Repo(
        registered=[1, 2, 3, 4, *extra_registered],
        mappings=[M(1, "TA1"), M(2, "TA2"), M(3, "TX9")],
        hierarchy=[H(1, "TA1", "OU", "Z1", "S1", "C1", "F1"), H(2, "TA2", "OU", "Z2", "S1", "C1", "F2"),
                   H(3, "TX9", None, None, None, None, None)],
        telemetry=[Code(2, "OTHER")],
    )


def _dash(repo=None):
    repo = repo or _repo()
    return svc.get_dashboard(fleet_fetch=lambda: fleet.get_real_fleet(repo),
                             network_fetch=lambda: net.get_current_network(repo))


def _text(c):
    parts = []
    for n in walk(c):
        kids = getattr(n, "children", None)
        if isinstance(kids, (str, int)):
            parts.append(str(kids))
        elif isinstance(kids, list):
            parts.extend(k for k in kids if isinstance(k, str))
    return " ".join(parts)


class TestDataDerivedFromServices:
    def test_counts_match_fleet_and_network_services(self):
        repo = _repo()
        d = _dash(repo)
        f = fleet.get_real_fleet(repo).summary
        n = net.summarise(net.get_current_network(repo).rows)
        assert d.status is svc.DashboardStatus.DATA
        assert (d.fleet.registered, d.fleet.with_temperature, d.fleet.no_temperature) == (
            f.registered, f.with_temperature, f.no_temperature)
        assert (d.network.mapped, d.network.unmapped, d.network.hierarchy_resolved,
                d.network.hierarchy_unavailable, d.network.needs_review) == (
            n.mapped, n.unmapped, n.hierarchy_resolved, n.hierarchy_unavailable, n.needs_review)
        assert (f.registered, n.mapped, n.unmapped, n.hierarchy_resolved,
                n.hierarchy_unavailable, n.needs_review) == (4, 3, 1, 2, 1, 1)
        assert (f.with_temperature, f.no_temperature) == (2, 2)

    def test_values_follow_the_source_not_constants(self):
        d = _dash(_repo(extra_registered=(7, 8, 9)))
        assert d.fleet.registered == 7 and d.network.unmapped == 4 and d.fleet.no_temperature == 5

    def test_latest_reading_and_zone_distribution(self):
        d = _dash()
        assert d.latest_reading == WHEN
        assert d.by_zone == (("Z1", 1), ("Z2", 1))

    def test_one_snapshot_each_and_no_per_rtl_reads(self):
        for count in (4, 30):
            repo = _repo(extra_registered=range(10, 10 + count))
            _dash(repo)
            assert len(repo.calls) <= 10 and len(set(repo.calls)) <= 6

    def test_either_source_failing_is_unavailable(self):
        repo = _repo()
        repo.fail = True
        assert _dash(repo).status is svc.DashboardStatus.UNAVAILABLE
        ok = _repo()
        d = svc.get_dashboard(fleet_fetch=lambda: fleet.get_real_fleet(ok),
                              network_fetch=lambda: net.CurrentNetwork(net.NetworkStatus.UNAVAILABLE))
        assert d.status is svc.DashboardStatus.UNAVAILABLE

    def test_service_has_no_sql_and_no_postgres(self):
        text = (ROOT / "services/rtl_dashboard_service.py").read_text(encoding="utf-8")
        assert not re.search(r"plant_monitoring|sqlalchemy|pymssql|\bSELECT\b|attention_service|fleet_overview_service", text)


class TestRendering:
    def test_factual_content_and_links(self):
        body = ui.dashboard_body(_dash())
        text = _text(body)
        for word in ("Registered RTLs", "Mapped RTLs", "Unmapped RTLs", "Temperature data available",
                     "No temperature data", "Hierarchy resolved", "Hierarchy unavailable",
                     "Mapping review", "RTLs by zone", "Most recent reading on record"):
            assert word in text
        hrefs = sorted(n.href for n in walk(body) if isinstance(getattr(n, "href", None), str))
        assert hrefs == ["/rtls", "/rtls/network"]

    def test_no_synthetic_or_unsupported_concepts(self):
        page_text = _text(page.layout()) + " " + _text(ui.dashboard_body(_dash())) + " " + ui.NOTE
        banned = (r"Plants?", r"Devices?", r"Online", r"Offline", r"Active", r"Inactive", r"Healthy",
                  r"Needs Attention", r"Asset Navigator", r"Command Center", r"Voltage", r"Current",
                  r"Power factor", r"Frequency", r"Energy", r"Active power", r"alarms?\b(?! state)",
                  r"None", r"null", r"NaN")
        for pat in banned:
            hits = re.findall(rf"\b{pat}\b", page_text)
            assert not hits, (pat, hits)

    def test_mapping_review_is_not_called_an_error(self):
        text = _text(ui.network_section(_dash()))
        assert not re.search(r"\b(error|invalid|wrong|incorrect)\b", text, re.I)

    def test_no_dashboard_href_to_synthetic_routes(self):
        body = _text(ui.dashboard_body(_dash()))
        assert "/plants/" not in body and "/devices" not in body
        src = "".join((ROOT / f).read_text(encoding="utf-8")
                      for f in ("components/rtl_dashboard.py", "pages/rtl_dashboard.py", "callbacks/rtl_dashboard.py"))
        assert not re.search(r"/plants/|/devices/|plant_monitoring|attention_service", src)

    def test_page_title_is_neutral(self):
        assert "Dashboard" in _text(page.layout()) and "Plant" not in _text(page.layout())


class TestCallbackAuthorization:
    def test_permitted_scope_loads_once(self):
        calls = []

        def fetch():
            calls.append(1)
            return _dash()

        out = cb.populate({"route": "rtl_dashboard"}, fetch=fetch, scope_for=lambda: UNRESTRICTED)
        assert out is not None and calls == [1]

    def test_restricted_scopes_get_nothing_and_no_read(self):
        for scope in (None, EMPTY, DeviceScope(frozenset({"d"}))):
            calls = []
            out = cb.populate({"route": "rtl_dashboard"}, fetch=lambda: calls.append(1),
                              scope_for=lambda s=scope: s)
            assert out is None and calls == []

    def test_other_routes_are_ignored(self):
        assert cb.populate({"route": "command_center"}) is no_update

    def test_source_failure_shows_unavailable_notice(self):
        bad = lambda: svc.RTLDashboard(svc.DashboardStatus.UNAVAILABLE)  # noqa: E731
        out = cb.populate({"route": "rtl_dashboard"}, fetch=bad, scope_for=lambda: UNRESTRICTED)
        assert "unavailable" in _text(out).lower()


class TestLegacyCommandCenterIsIsolated:
    def test_dashboard_page_has_none_of_the_legacy_slots(self):
        from pages import command_center
        ids = {n.id for n in walk(page.layout()) if isinstance(getattr(n, "id", None), str)}
        legacy = {n.id for n in walk(command_center.layout()) if isinstance(getattr(n, "id", None), str)}
        assert ids == {page.BODY_ID} and not (ids & legacy)

    def test_routing_sends_only_real_fleet_scopes_to_the_dashboard(self):
        src = (ROOT / "callbacks/routing.py").read_text(encoding="utf-8")
        i = src.index('if route.name == "command_center":')
        block = src[i:i + 700]
        assert "may_view_real_fleet(scope)" in block and "rtl_dashboard.layout()" in block
        assert "command_center.layout()" in block
