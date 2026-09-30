"""LATEST-NETWORK-CONTEXT-01 - the current Network view of the registered RTLs.

Pins: the population is ``device_list`` only; the current transformer is the
``trfr_list`` mapping; hierarchy is exact-match enrichment; corroborating
sources flag but never override; filters cascade over registered RTLs only;
authorization is the detail route's; and the reads are static, bounded SQL.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from callbacks import rtl_network as callbacks
from components import rtl_network as ui
from components.app_sidebar import SIDEBAR_SECTIONS, sidebar_nav
from pages import rtl_network as page
from repositories import rtl_temperature_repository as repo_module
from repositories.rtl_temperature_repository import (
    RTLReportedTransformerCode as Code,
    RTLTemperatureRepositoryError,
    RTLTransformerHierarchy as H,
    RTLTransformerMapping as M,
)
from routes import NAV_KEY_BY_ROUTE, RTL_NETWORK_PATH, Route, parse_pathname, rtl_detail_href
from services import rtl_network_service as svc
from services.authorization import (
    ADMINISTRATOR, GENERAL, ROUTE_POLICY, TECHNICIAN, may_access_route, visible_nav_keys,
)
from services.rtl_scope import DENIED as EMPTY, UNRESTRICTED, RtlScope as DeviceScope
from services.rtl_fleet_service import HierarchyState
from tests.dash_tree import walk

ROOT = Path(__file__).resolve().parents[1]
S, U, T = svc.EvidenceSource.SETTINGS, svc.EvidenceSource.STARTUP, svc.EvidenceSource.TELEMETRY


def _h(uid, code, zone="Z1", sector="S1", cnc="C1", feeder="F1", ou="OU"):
    return H(uid, code, ou, zone, sector, cnc, feeder)


class FakeRepo:
    """Duck-typed repository recording every call."""

    def __init__(self, registered, mappings=(), hierarchy=(), settings=(), startup=(),
                 telemetry=(), fail=False):
        self.registered, self.mappings, self.hierarchy = list(registered), list(mappings), list(hierarchy)
        self.settings, self.startup, self.telemetry, self.fail = list(settings), list(startup), list(telemetry), fail
        self.calls: list[str] = []

    def _do(self, name, value):
        self.calls.append(name)
        if self.fail:
            raise RTLTemperatureRepositoryError("down")
        return value

    def get_registered_device_uids(self): return self._do("registered", self.registered)
    def get_transformer_mappings(self): return self._do("mappings", self.mappings)
    def get_transformer_hierarchy(self): return self._do("hierarchy", self.hierarchy)
    def get_latest_settings_transformer_codes(self): return self._do("settings", self.settings)
    def get_latest_startup_transformer_codes(self): return self._do("startup", self.startup)
    def get_latest_telemetry_transformer_codes(self): return self._do("telemetry", self.telemetry)


def _network(repo):
    return svc.get_current_network(repo)


def _by_uid(network):
    return {r.device_uid: r for r in network.rows}


@pytest.fixture
def fleet():
    """Six registered RTLs: two feeders, one hierarchy-unavailable, one unmapped, one disputed."""
    return FakeRepo(
        registered=[1, 2, 3, 4, 5, 6],
        mappings=[M(1, "TA1"), M(2, "TA2"), M(3, "TB1"), M(4, "TX9"), M(6, "TD1")],
        hierarchy=[
            _h(1, "TA1", feeder="F1"), _h(2, "TA2", feeder="F2"),
            _h(3, "TB1", zone="Z2", sector="S9", cnc="C9", feeder="F9"),
            H(4, "TX9", None, None, None, None, None),
            _h(6, "TD1"),
        ],
        settings=[Code(1, "ta1"), Code(6, "TD1")],
        startup=[Code(1, "TA1")],
        telemetry=[Code(1, "TA1"), Code(6, "OTHER"), Code(99, "TZ")],  # 99 unregistered
    )


class TestPopulationAndMapping:
    def test_population_is_device_list_only(self, fleet):
        fleet.mappings.append(M(99, "TZ"))  # mapped but not registered
        fleet.hierarchy.append(_h(99, "TZ"))
        net = _network(fleet)
        assert [r.device_uid for r in net.rows] == [1, 2, 3, 4, 5, 6]

    def test_telemetry_only_uid_is_excluded(self, fleet):
        assert 99 not in _by_uid(_network(fleet))

    def test_current_mapping_comes_from_trfr_list(self, fleet):
        rows = _by_uid(_network(fleet))
        assert rows[1].transformer_code == "TA1"
        assert rows[1].mapping_status is svc.MappingStatus.MAPPED

    def test_unmapped_rtl_has_no_transformer_even_with_history_elsewhere(self, fleet):
        fleet.settings.append(Code(5, "OLDCODE"))
        fleet.startup.append(Code(5, "OLDCODE"))
        fleet.telemetry.append(Code(5, "OLDCODE"))
        row = _by_uid(_network(fleet))[5]
        assert row.mapping_status is svc.MappingStatus.NOT_MAPPED
        assert row.transformer_code is None
        assert row.hierarchy is None and row.disagreements == ()

    def test_several_mapping_codes_are_ambiguous_not_chosen(self):
        repo = FakeRepo([1], [M(1, "A"), M(1, "B")], [_h(1, "A")])
        row = _network(repo).rows[0]
        assert row.mapping_status is svc.MappingStatus.AMBIGUOUS
        assert row.transformer_code is None and row.hierarchy is None
        assert row.needs_review


class TestHierarchy:
    def test_exact_hierarchy_resolution(self, fleet):
        row = _by_uid(_network(fleet))[1]
        assert row.hierarchy_state is HierarchyState.AVAILABLE
        assert (row.hierarchy.zone, row.hierarchy.sector, row.hierarchy.cnc, row.hierarchy.feeder) == (
            "Z1", "S1", "C1", "F1")

    def test_blank_hierarchy_row_is_unavailable(self, fleet):
        row = _by_uid(_network(fleet))[4]
        assert row.hierarchy_state is HierarchyState.UNAVAILABLE and row.hierarchy is None
        assert row.transformer_code == "TX9"

    def test_no_fuzzy_matching(self):
        """A near-miss code in the view is not the mapped transformer."""
        repo = FakeRepo([1], [M(1, "TA1")], [_h(1, "TA10"), _h(1, "TA")])
        row = _network(repo).rows[0]
        assert row.hierarchy_state is HierarchyState.UNAVAILABLE

    def test_hierarchy_for_another_uid_is_not_borrowed(self):
        repo = FakeRepo([1, 2], [M(1, "TA1"), M(2, "TA2")], [_h(2, "TA1")])
        assert _by_uid(_network(repo))[1].hierarchy_state is HierarchyState.UNAVAILABLE

    def test_case_and_whitespace_only_differences_match(self):
        """The database's own comparison, not similarity."""
        repo = FakeRepo([1], [M(1, "TA1")], [_h(1, " ta1 ")])
        assert _network(repo).rows[0].hierarchy_state is HierarchyState.AVAILABLE

    def test_conflicting_hierarchy_rows_are_not_guessed(self):
        repo = FakeRepo([1], [M(1, "TA1")], [_h(1, "TA1", zone="Z1"), _h(1, "TA1", zone="Z2")])
        row = _network(repo).rows[0]
        assert row.hierarchy_state is HierarchyState.UNAVAILABLE
        assert row.hierarchy_conflict and row.needs_review


class TestCurrentSourcePrecedence:
    def test_agreeing_evidence_raises_no_flag(self, fleet):
        row = _by_uid(_network(fleet))[1]  # settings 'ta1' vs 'TA1' - same code
        assert row.disagreements == () and not row.needs_review

    def test_missing_evidence_is_silent(self, fleet):
        assert _by_uid(_network(fleet))[2].disagreements == ()

    def test_disagreement_is_surfaced_not_resolved(self, fleet):
        row = _by_uid(_network(fleet))[6]
        assert row.transformer_code == "TD1"  # trfr_list still wins the display
        assert row.hierarchy_state is HierarchyState.AVAILABLE
        assert row.disagreements == (svc.SourceDisagreement(T, ("OTHER",)),)
        assert row.needs_review

    def test_tie_at_latest_timestamp_between_codes_is_a_disagreement(self):
        repo = FakeRepo([1], [M(1, "A")], [_h(1, "A")], settings=[Code(1, "A"), Code(1, "B")])
        row = _network(repo).rows[0]
        assert row.disagreements == (svc.SourceDisagreement(S, ("A", "B")),)

    def test_selection_is_deterministic_regardless_of_input_order(self, fleet):
        a = _network(fleet)
        fleet.registered.reverse(); fleet.mappings.reverse(); fleet.hierarchy.reverse()
        fleet.telemetry.reverse()
        assert _network(fleet) == a

    def test_most_frequent_or_earliest_history_never_becomes_current(self):
        """Only trfr_list feeds `transformer_code`; evidence cannot replace it."""
        repo = FakeRepo([1], [M(1, "NOW")], [_h(1, "NOW")],
                        settings=[Code(1, "OLD")], startup=[Code(1, "OLD")], telemetry=[Code(1, "OLD")])
        row = _network(repo).rows[0]
        assert row.transformer_code == "NOW"
        assert {d.source for d in row.disagreements} == {S, U, T}


class TestSummary:
    def test_counts_are_derived(self, fleet):
        s = svc.summarise(_network(fleet).rows)
        assert (s.registered, s.mapped, s.unmapped) == (6, 5, 1)
        assert (s.hierarchy_resolved, s.hierarchy_unavailable, s.needs_review) == (4, 1, 1)


class TestFiltersAndCascade:
    def rows(self, fleet):
        return _network(fleet).rows

    def test_options_come_from_registered_rtls_only(self, fleet):
        fleet.hierarchy.append(_h(77, "TQ", zone="ZOMBIE"))  # reference-only, no registered RTL
        opts = svc.cascade_options(self.rows(fleet), svc.NetworkFilter())
        assert opts["zone"] == ("Z1", "Z2")

    def test_higher_level_constrains_lower(self, fleet):
        opts = svc.cascade_options(self.rows(fleet), svc.NetworkFilter(zone="Z1"))
        assert opts["sector"] == ("S1",) and opts["feeder"] == ("F1", "F2")
        assert "F9" not in opts["feeder"]

    def test_filtering_returns_matching_rtls(self, fleet):
        got = svc.filter_rows(self.rows(fleet), svc.NetworkFilter(zone="Z1", feeder="F2"))
        assert [r.device_uid for r in got] == [2]

    def test_full_path_to_transformer(self, fleet):
        sel = svc.NetworkFilter(zone="Z2", sector="S9", cnc="C9", feeder="F9", transformer="TB1")
        assert [r.device_uid for r in svc.filter_rows(self.rows(fleet), sel)] == [3]

    def test_stale_child_is_cleared_when_parent_changes(self, fleet):
        norm = svc.normalise_filter(self.rows(fleet), svc.NetworkFilter(zone="Z2", feeder="F1"))
        assert norm.zone == "Z2" and norm.feeder is None

    def test_levels_may_be_skipped(self, fleet):
        norm = svc.normalise_filter(self.rows(fleet), svc.NetworkFilter(zone=None, sector="S1"))
        assert norm.sector == "S1"

    def test_child_no_longer_offered_by_a_selected_parent_is_cleared(self, fleet):
        norm = svc.normalise_filter(self.rows(fleet), svc.NetworkFilter(zone="Z2", sector="S1"))
        assert norm.zone == "Z2" and norm.sector is None

    def test_unknown_value_is_dropped(self, fleet):
        assert svc.normalise_filter(self.rows(fleet), svc.NetworkFilter(zone="nope")).zone is None

    def test_same_cnc_name_under_two_parents_stays_separate(self):
        repo = FakeRepo([1, 2], [M(1, "A"), M(2, "B")],
                        [_h(1, "A", zone="Z1", cnc="X"), _h(2, "B", zone="Z2", cnc="X")])
        rows = _network(repo).rows
        assert [r.device_uid for r in svc.filter_rows(rows, svc.NetworkFilter(zone="Z2", cnc="X"))] == [2]

    def test_unmapped_scope_lists_unmapped_rtls(self, fleet):
        got = svc.filter_rows(self.rows(fleet), svc.NetworkFilter(scope=svc.SCOPE_UNMAPPED))
        assert [r.device_uid for r in got] == [5]

    def test_hierarchy_unavailable_scope_keeps_mapped_rtls_visible(self, fleet):
        got = svc.filter_rows(self.rows(fleet), svc.NetworkFilter(scope=svc.SCOPE_HIERARCHY_UNAVAILABLE))
        assert [r.device_uid for r in got] == [4]

    def test_unfiltered_view_keeps_every_registered_rtl(self, fleet):
        assert len(svc.filter_rows(self.rows(fleet), svc.NetworkFilter())) == 6

    def test_payload_round_trips(self, fleet):
        rows = self.rows(fleet)
        assert svc.from_payload(svc.to_payload(rows)) == rows

    def test_malformed_payload_entries_are_dropped(self):
        assert svc.from_payload([{"uid": "x"}, "junk", None]) == ()
        assert svc.from_payload("not a list") == ()


class TestBoundedReads:
    def test_fixed_read_count_independent_of_fleet_size(self, fleet):
        _network(fleet)
        assert sorted(fleet.calls) == sorted(
            ["registered", "mappings", "hierarchy", "settings", "startup", "telemetry"])
        big = FakeRepo(range(1, 2001), [M(i, f"T{i}") for i in range(1, 1001)])
        _network(big)
        assert len(big.calls) == 6

    def test_source_failure_is_unavailable_without_rows(self):
        net = _network(FakeRepo([1], fail=True))
        assert net.status is svc.NetworkStatus.UNAVAILABLE and net.rows == ()

    def test_evidence_sql_is_static_and_registered_bounded(self):
        for sql in (repo_module._SETTINGS_CODE_SQL, repo_module._STARTUP_CODE_SQL,
                    repo_module._TELEMETRY_CODE_SQL):
            assert "dbo.device_list" in sql
            assert "%s" not in sql and "{" not in sql
            assert not re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|EXEC)\b", sql, re.I)

    def test_network_stack_has_no_postgres_or_page_sql(self):
        for rel in ("services/rtl_network_service.py", "components/rtl_network.py",
                    "pages/rtl_network.py", "callbacks/rtl_network.py"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            assert not re.search(r"plant_monitoring|sqlalchemy|db\.engine|psycopg", text, re.I), rel
            assert not re.search(r"\b(SELECT|INSERT)\b\s", text), rel


class TestRoutesAndAuthorization:
    def test_route_parses(self):
        assert parse_pathname("/rtls/network") == Route(name="rtl_network")
        assert parse_pathname("/rtls/network/") == Route(name="rtl_network")
        assert RTL_NETWORK_PATH == "/rtls/network"

    def test_list_and_detail_are_unchanged(self):
        assert parse_pathname("/rtls").name == "overview"
        assert parse_pathname("/rtls/29042").name == "rtl_detail"
        assert parse_pathname("/rtls/networks").name == "unknown"

    def test_policy_matches_rtl_detail(self):
        assert ROUTE_POLICY["rtl_network"] == ROUTE_POLICY["rtl_detail"]
        assert may_access_route(ADMINISTRATOR, "rtl_network")
        assert may_access_route(GENERAL, "rtl_network")
        # ADR-032: the route gate admits a Technician; the shared RTL scope
        # then narrows every read to their assigned RTLs.
        assert may_access_route(TECHNICIAN, "rtl_network")
        assert not may_access_route("Administrator", "rtl_network")
        assert not may_access_route(None, "rtl_network")

    def test_sidebar_entry_follows_the_policy(self):
        assert NAV_KEY_BY_ROUTE["rtl_network"] == "network"
        labels = {item[1]: item for _, items in SIDEBAR_SECTIONS for item in items}
        assert labels["Network"][2] == "/rtls/network"
        assert "network" in visible_nav_keys(GENERAL) and "network" in visible_nav_keys(ADMINISTRATOR)
        assert "network" in visible_nav_keys(TECHNICIAN)
        assert "Network" in repr(sidebar_nav("overview", TECHNICIAN))

    def test_load_refuses_restricted_scopes_without_reading(self):
        for scope in (None, EMPTY):
            calls = []
            payload, error = callbacks.load({"route": "rtl_network"},
                                            fetch=lambda **_: calls.append(1), scope_for=lambda s=scope: s)
            assert payload is None and calls == []
            assert "not available" in repr(error)

    def test_load_reads_for_unrestricted_scope(self, fleet):
        payload, error = callbacks.load({"route": "rtl_network"},
                                        fetch=lambda **_: _network(fleet), scope_for=lambda: UNRESTRICTED)
        assert error is None and len(payload) == 6

    def test_load_ignores_other_routes(self):
        from dash import no_update
        assert callbacks.load({"route": "overview"}) == (no_update, no_update)

    def test_source_failure_shows_error_not_empty_network(self):
        payload, error = callbacks.load(
            {"route": "rtl_network"},
            fetch=lambda **_: svc.CurrentNetwork(svc.NetworkStatus.UNAVAILABLE), scope_for=lambda: UNRESTRICTED)
        assert payload is None and "unavailable" in repr(error)


def _text(component) -> str:
    return " ".join(str(getattr(n, "children", "")) for n in walk(component)
                    if isinstance(getattr(n, "children", None), (str, int)))


def _cards(component):
    """(label value) text of each KPI card, in order."""
    out, cur = [], []
    for n in walk(component):
        c = getattr(n, "children", None)
        if isinstance(c, str):
            cur.append(c)
    return [" ".join(cur[i:i + 3]) for i in range(0, len(cur), 3)]


class TestRendering:
    def render(self, fleet, scope="all", *levels):
        payload = svc.to_payload(_network(fleet).rows)
        return callbacks.render(payload, scope, *(levels or (None,) * 5))

    def test_links_go_to_canonical_rtl_detail(self, fleet):
        table = self.render(fleet)[2]
        hrefs = [n.href for n in walk(table) if isinstance(getattr(n, "href", None), str)]
        assert sorted(hrefs) == sorted(rtl_detail_href(u) for u in range(1, 7))
        assert not any("/devices" in h for h in hrefs)

    def test_states_are_worded_not_null(self, fleet):
        text = _text(self.render(fleet)[2])
        assert "No current transformer mapping" in text and "Hierarchy unavailable" in text
        assert "None" not in text and "null" not in text.lower() and "nan" not in text.lower()
        assert "Needs review" in text

    def test_counts_reflect_the_view(self, fleet):
        stats = _text(self.render(fleet, "all", "Z2")[0])
        assert "Registered RTLs in view" in stats and "of 6 registered" in stats
        # Every card counts the view (RTL 3 only), not the whole fleet.
        assert "Mapped RTLs 1" in re.sub(r"\s+", " ", " ".join(_cards(self.render(fleet, "all", "Z2")[0])))
        assert "Unmapped RTLs 0" in re.sub(r"\s+", " ", " ".join(_cards(self.render(fleet, "all", "Z2")[0])))

    def test_render_returns_normalised_selection(self, fleet):
        out = self.render(fleet, "all", "Z2", None, None, "F1", None)
        assert out[4 + 5] == "Z2" and out[4 + 5 + 3] is None  # feeder F1 not offered under Z2

    def test_empty_snapshot_renders_nothing(self):
        out = callbacks.render(None, "all", *(None,) * 5)
        assert out[:3] == (None, None, None)

    def test_no_forbidden_state_words_or_metrics(self, fleet):
        everything = _text(page.layout()) + _text(self.render(fleet)[0]) + _text(self.render(fleet)[2]) + ui.SCOPE_NOTE
        for word in ("Online", "Offline", "Healthy", "Inactive", "Active", "Plant", "Asset Navigator",
                     "voltage", "amps", "kW", "power factor", "frequency", "reactive"):
            assert not re.search(rf"\b{word}\b", everything, re.I), word

    def test_page_labels_cascade_levels_in_order(self):
        ids = [n.id for n in walk(page.layout()) if isinstance(getattr(n, "id", None), str)
               and n.id.startswith("rtl-network-filter-")]
        assert ids == [f"rtl-network-filter-{lv}" for lv in ("zone", "sector", "cnc", "feeder", "transformer")]


class TestNoUnsupportedMetricsOrWrites:
    def test_repository_stays_select_only(self):
        text = (ROOT / "repositories/rtl_temperature_repository.py").read_text(encoding="utf-8")
        assert not re.search(r"\b(INSERT\s+INTO|UPDATE\s+dbo|DELETE\s+FROM|DROP\s+TABLE)\b", text, re.I)

    def test_service_module_derives_no_communication_state(self):
        text = (ROOT / "services/rtl_network_service.py").read_text(encoding="utf-8")
        assert not re.search(r"\b(online|offline|last_comms_ok|comms_alarm)\b", text.split('"""', 2)[2], re.I)
