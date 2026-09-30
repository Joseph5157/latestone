"""RTL-NETWORK-USE-01 - the network context reused on RTL detail and the dashboard."""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from dash import no_update

from callbacks import fleet_overview, rtl_summary
from components import rtl_detail as detail_ui
from components import rtl_fleet as fleet_ui
from pages import command_center
from repositories.rtl_temperature_repository import RTLLatestTemperature as Latest
from repositories.rtl_temperature_repository import RTLReportedTransformerCode as Code
from repositories.rtl_temperature_repository import RTLTransformerHierarchy as H
from repositories.rtl_temperature_repository import RTLTransformerMapping as M
from services import rtl_detail_service as detail
from services import rtl_fleet_service as fleet
from services import rtl_network_service as net
from services.device_scope import EMPTY, UNRESTRICTED, DeviceScope
from tests.dash_tree import walk
from tests.test_rtl_network import FakeRepo

ROOT = Path(__file__).resolve().parents[1]


class Repo(FakeRepo):
    """Network FakeRepo plus the temperature read the detail/fleet pages make."""

    def get_latest_temperatures(self, uids):
        return {u: Latest(u, datetime(2022, 1, 1), Decimal("20.0"), 1, (Decimal("20.0"),))
                for u in uids if u in (1, 2)}


def _repo():
    return Repo(
        registered=[1, 2, 3, 4],
        mappings=[M(1, "TA1"), M(2, "TA2"), M(3, "TX9")],
        hierarchy=[H(1, "TA1", "OU", "Z1", "S1", "C1", "F1"), H(2, "TA2", "OU", "Z1", "S1", "C1", "F2"),
                   H(3, "TX9", None, None, None, None, None)],
        telemetry=[Code(2, "OTHER")],
    )


def _text(c):
    parts = []
    for n in walk(c):
        kids = getattr(n, "children", None)
        if isinstance(kids, (str, int)):
            parts.append(str(kids))
        elif isinstance(kids, list):
            parts.extend(k for k in kids if isinstance(k, str))
    return " ".join(parts)


class TestDetailReusesNetworkService:
    def test_same_values_as_network_page_for_every_uid(self):
        repo = _repo()
        for row in net.get_current_network(repo).rows:
            rtl = detail.get_rtl_detail(row.device_uid, repo).rtl
            assert rtl.hierarchy == row.hierarchy
            assert rtl.hierarchy_state is row.hierarchy_state
            assert rtl.transformer_codes == row.mapping_codes
            assert rtl.disagreements == row.disagreements

    def test_mapped_rtl_shows_all_five_levels(self):
        text = _text(detail_ui.network_context(detail.get_rtl_detail(1, _repo()).rtl))
        for word in ("Transformer", "TA1", "Zone", "Z1", "Sector", "S1", "CNC", "C1", "Feeder", "F1"):
            assert word in text

    def test_unmapped_and_unavailable_states_are_worded(self):
        assert "No current transformer mapping" in _text(
            detail_ui.network_context(detail.get_rtl_detail(4, _repo()).rtl))
        assert "Hierarchy unavailable" in _text(
            detail_ui.network_context(detail.get_rtl_detail(3, _repo()).rtl))

    def test_disagreement_note_is_informational(self):
        text = _text(detail_ui.network_context(detail.get_rtl_detail(2, _repo()).rtl))
        assert "Mapping review:" in text and "OTHER" in text and "TA2" in text
        assert not re.search(r"\b(wrong|error|incorrect|invalid)\b", text, re.I)
        assert "Mapping review" not in _text(
            detail_ui.network_context(detail.get_rtl_detail(1, _repo()).rtl))

    def test_no_raw_nulls_or_forbidden_words(self):
        for uid in (1, 2, 3, 4):
            text = _text(detail_ui.network_context(detail.get_rtl_detail(uid, _repo()).rtl))
            assert not re.search(r"\b(None|null|nan|Plant|Online|Offline|Active)\b", text), uid

    def test_temperature_behaviour_unchanged(self):
        rtl = detail.get_rtl_detail(1, _repo()).rtl
        assert str(rtl.temperature) == "20.0" and rtl.last_reported is not None

    def test_unregistered_uid_is_still_refused_without_network_reads(self):
        repo = _repo()
        assert detail.get_rtl_detail(99, repo).status is detail.DetailStatus.NOT_REGISTERED
        assert repo.calls == ["registered"]

    def test_source_failure_is_unavailable(self):
        repo = _repo()
        repo.fail = True
        assert detail.get_rtl_detail(1, repo).status is detail.DetailStatus.UNAVAILABLE


class TestDashboardSummary:
    def summary(self):
        return fleet.get_real_fleet(_repo()).summary

    def test_summary_properties_match_the_network_service(self):
        s = self.summary()
        n = net.summarise(net.get_current_network(_repo()).rows)
        assert (s.registered, s.mapped, s.unmapped) == (n.registered, n.mapped, n.unmapped)
        assert (s.hierarchy_resolved, s.hierarchy_unavailable) == (
            n.hierarchy_resolved, n.hierarchy_unavailable)

    def test_panel_is_factual_with_links_to_real_routes(self):
        panel = fleet_ui.rtl_summary_panel(self.summary())
        text = _text(panel)
        for word in ("Registered RTLs", "Mapped RTLs", "Unmapped RTLs",
                     "Temperature data available", "Network coverage"):
            assert word in text
        hrefs = sorted(n.href for n in walk(panel) if isinstance(getattr(n, "href", None), str))
        assert hrefs == ["/rtls", "/rtls/network"]
        assert not re.search(r"\b(Active|Online|Offline|Healthy|Inactive|Plants?)\b", text)

    def test_rtls_page_gets_coverage_line_from_the_same_snapshot(self):
        out = fleet_overview.populate({"route": "overview"},
                                      fetch=lambda: fleet.get_real_fleet(_repo()),
                                      scope_for=lambda: UNRESTRICTED)
        assert "Network coverage" in _text(out[0]) and "View Network" in _text(out[0])

    def test_panel_loads_once_from_the_real_fleet_service(self):
        calls = []

        def fetch():
            calls.append(1)
            return fleet.get_real_fleet(_repo())

        out = rtl_summary.populate({"route": "command_center"}, fetch=fetch,
                                   scope_for=lambda: UNRESTRICTED)
        assert out is not None and calls == [1]

    def test_restricted_scopes_get_nothing_and_no_read(self):
        for scope in (None, EMPTY, DeviceScope(frozenset({"d"}))):
            calls = []
            out = rtl_summary.populate({"route": "command_center"},
                                       fetch=lambda: calls.append(1), scope_for=lambda s=scope: s)
            assert out is None and calls == []

    def test_other_routes_are_ignored(self):
        assert rtl_summary.populate({"route": "overview"}) is no_update

    def test_source_failure_hides_the_panel(self):
        bad = lambda: fleet.RealFleet(fleet.FleetStatus.UNAVAILABLE)  # noqa: E731
        assert rtl_summary.populate({"route": "command_center"}, fetch=bad,
                                    scope_for=lambda: UNRESTRICTED) is None

    def test_command_center_slot_exists_and_callback_touches_no_sql_or_postgres(self):
        ids = [n.id for n in walk(command_center.layout()) if isinstance(getattr(n, "id", None), str)]
        assert command_center.RTL_SUMMARY_ID in ids
        text = (ROOT / "callbacks/rtl_summary.py").read_text(encoding="utf-8")
        assert not re.search(r"plant_monitoring|sqlalchemy|pymssql|\bSELECT\b|fleet_overview_service", text)
