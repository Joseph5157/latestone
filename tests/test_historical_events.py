"""HISTORICAL-EVENTS-01 - factual Historical Events."""
from __future__ import annotations

import dataclasses
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from dash import no_update

from callbacks import historical_events as cb
from components import historical_events as ui
from pages import historical_events as page
from repositories import rtl_events_repository as repo_mod
from repositories.rtl_events_repository import RTLEventRow, RTLEventsRepository
from repositories.rtl_temperature_repository import RTLTransformerHierarchy as H
from repositories.rtl_temperature_repository import RTLTransformerMapping as M
from services import rtl_events_service as svc
from services import rtl_network_service as net
from services.device_scope import EMPTY, UNRESTRICTED, DeviceScope
from tests.dash_tree import walk
from tests.test_rtl_network import FakeRepo

ROOT = Path(__file__).resolve().parents[1]
D = Decimal


def ev(kind, uid, when, value="80.00", code="TA1"):
    return RTLEventRow(kind, uid, code, when, D(value) if value is not None else None)


ROWS = [
    ev("high_temperature", 1, datetime(2026, 8, 10, 12, 0)),
    ev("high_temperature", 1, datetime(2026, 8, 10, 12, 0)),
    ev("battery_low", 2, datetime(2026, 8, 12, 9, 0), "3.61", "TA2"),
    ev("sensor_error", 1, datetime(2026, 8, 1, 8, 0), "999.00"),
    ev("powerdown", 77, datetime(2026, 7, 1, 8, 0), "3.60", "GONE"),   # not registered
    ev("high_temperature", 2, datetime(2020, 1, 1, 8, 0)),
]


class EventsRepo:
    """Duck-typed repository honouring window, types, UID and paging like the SQL does."""

    def __init__(self, rows=ROWS, latest=datetime(2026, 8, 12, 9, 0), fail=False):
        self.rows, self.latest, self.fail, self.calls = list(rows), latest, fail, []

    def _sel(self, start, end, uid):
        return [r for r in self.rows if start <= r.recorded_at < end and (uid is None or r.device_uid == uid)]

    def get_latest_event_time(self):
        return self.latest

    def count_events(self, start, end, uid=None):
        self.calls.append("count")
        if self.fail:
            raise svc.RTLTemperatureRepositoryError("down")
        out = {t.value: 0 for t in svc.EventType}
        for r in self._sel(start, end, uid):
            out[r.event_type] += 1
        return out

    def get_events(self, start, end, types, uid, limit, offset):
        self.calls.append("page")
        rows = sorted((r for r in self._sel(start, end, uid) if r.event_type in types),
                      key=lambda r: (-r.recorded_at.timestamp(), r.event_type, r.device_uid))
        return rows[offset:offset + limit]


def network_repo():
    return FakeRepo(
        registered=[1, 2, 3],
        mappings=[M(1, "TA1"), M(2, "TA2")],
        hierarchy=[H(1, "TA1", "OU", "Z1", "S1", "C1", "F1"), H(2, "TA2", None, None, None, None, None)],
    )


def fetch_page(repo=None, *args, netrepo=None, **kw):
    netrepo = netrepo or network_repo()
    return svc.get_events_page(*args, repository=repo or EventsRepo(),
                               network_fetch=lambda: net.get_current_network(netrepo), **kw)


FULL = (date(2026, 1, 1), date(2026, 12, 31))


def _text(c):
    parts = []
    for n in walk(c):
        kids = getattr(n, "children", None)
        if isinstance(kids, (str, int)):
            parts.append(str(kids))
        elif isinstance(kids, list):
            parts.extend(k for k in kids if isinstance(k, str))
    return " ".join(parts)


class FakeCursor:
    def __init__(self, log):
        self.log = log

    def execute(self, sql, params):
        self.log.append((sql, params))

    def fetchall(self):
        return []

    def close(self):
        pass


class FakeConn:
    def __init__(self, log):
        self.log = log

    def cursor(self):
        return FakeCursor(self.log)

    def close(self):
        pass


class TestSourceSemantics:
    def sql_for(self, method, *args):
        log = []
        getattr(RTLEventsRepository(lambda: FakeConn(log)), method)(*args)
        return log

    def test_each_class_reads_its_own_verified_source(self):
        s = repo_mod._SOURCES
        assert "dbo.alarm_log" in s["high_temperature"]
        assert "dbo.sensor_error_log" in s["sensor_error"]
        assert "dbo.startup_msg_log" in s["battery_low"] and "status = 'Battery Low'" in s["battery_low"]
        assert "dbo.powerdown_log" in s["powerdown"]
        assert svc.SOURCE_BY_TYPE[svc.EventType.BATTERY_LOW] is svc.EventSource.STARTUP_MSG_LOG
        assert svc.SOURCE_BY_TYPE[svc.EventType.HIGH_TEMPERATURE] is svc.EventSource.ALARM_LOG

    def test_type_filter_selects_only_that_source(self):
        (sql, params), = self.sql_for("get_events", datetime(2026, 1, 1), datetime(2026, 2, 1),
                                      ["powerdown"], None, 50, 0)
        assert "dbo.powerdown_log" in sql
        assert not any(t in sql for t in ("alarm_log", "sensor_error_log", "startup_msg_log"))

    def test_sql_is_select_only_bounded_ordered_and_parameterised(self):
        (sql, params), = self.sql_for("get_events", datetime(2026, 1, 1), datetime(2026, 2, 1),
                                      list(repo_mod._SOURCES), 29042, 50, 100)
        assert sql.lstrip().upper().startswith("SELECT")
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|EXEC|MERGE)\b", sql, re.I)
        assert "ORDER BY recorded_at DESC, event_type, device_uid" in sql
        assert "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY" in sql
        assert sql.count(">= %s") == 4 and sql.count("< %s") == 4 and sql.count("device_uid = %s") == 4
        assert "29042" not in sql and params[-2:] == (100, 50)

    def test_counts_are_grouped_in_sql_not_loaded(self):
        (sql, _), = self.sql_for("count_events", datetime(2026, 1, 1), datetime(2026, 2, 1), None)
        assert "GROUP BY event_type" in sql and "COUNT_BIG" in sql

    def test_repository_is_read_only_source(self):
        text = (ROOT / "repositories/rtl_events_repository.py").read_text(encoding="utf-8")
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE)\b\s", text.split('"""', 2)[2])

    def test_no_lifecycle_fields_are_modelled(self):
        names = {f.name for f in dataclasses.fields(svc.HistoricalEvent)} | \
                {f.name for f in dataclasses.fields(RTLEventRow)}
        assert not names & {"acknowledged", "resolved", "assigned_to", "severity", "escalation",
                            "status", "is_active", "online", "state"}

    def test_value_kinds_are_uninterpreted(self):
        assert svc.VALUE_KIND[svc.EventType.SENSOR_ERROR] == "recorded"
        e = fetch_page(None, *FULL, "sensor_error").events[0]
        assert ui.value_text(e) == "999.0"  # no unit, no error-code reading


class TestWindowOrderPaging:
    def test_default_window_is_thirty_days_ending_on_newest_event(self):
        assert svc.default_window(datetime(2026, 8, 12, 9, 0)) == (date(2026, 7, 14), date(2026, 8, 12))
        assert svc.default_window(None) is None

    def test_window_bounds_inclusive_start_and_end_day(self):
        p = fetch_page(None, date(2026, 8, 10), date(2026, 8, 10))
        assert p.total == 2 and all(e.recorded_at.date() == date(2026, 8, 10) for e in p.events)

    def test_old_history_is_outside_the_default_window(self):
        p = fetch_page(None, *svc.default_window(datetime(2026, 8, 12, 9, 0)))
        assert all(e.recorded_at.year == 2026 for e in p.events) and p.total == 4

    def test_newest_first_with_deterministic_tie_break(self):
        p = fetch_page(None, *FULL)
        times = [e.recorded_at for e in p.events]
        assert times == sorted(times, reverse=True)
        assert [e.event_type.value for e in p.events[:3]] == ["battery_low", "high_temperature", "high_temperature"]

    def test_pages_are_bounded_and_do_not_overlap(self):
        many = [RTLEventRow("battery_low", 1, "TA1", datetime(2026, 8, 1, i // 60, i % 60), D("3.60"))
                for i in range(120)]
        r = EventsRepo(many)
        p0 = fetch_page(r, *FULL, page=0)
        p1 = fetch_page(r, *FULL, page=1)
        p2 = fetch_page(r, *FULL, page=2)
        assert (p0.total, p0.page_count) == (120, 3)
        assert [len(p.events) for p in (p0, p1, p2)] == [50, 50, 20]
        seen = [e.recorded_at for p in (p0, p1, p2) for e in p.events]
        assert len(set(seen)) == 120 and seen == sorted(seen, reverse=True)

    def test_out_of_range_page_is_clamped(self):
        p = fetch_page(None, *FULL, page=99)
        assert p.page == 0 and p.events

    def test_counts_follow_the_window_not_lifetime(self):
        p = fetch_page(None, date(2026, 8, 1), date(2026, 8, 31))
        assert p.counts[svc.EventType.HIGH_TEMPERATURE] == 2 and p.counts[svc.EventType.POWERDOWN] == 0
        wide = fetch_page(None, date(2019, 1, 1), date(2026, 12, 31))
        assert wide.counts[svc.EventType.HIGH_TEMPERATURE] == 3

    def test_type_filter_and_uid_filter(self):
        assert fetch_page(None, *FULL, "battery_low").total == 1
        assert fetch_page(None, *FULL, None, "1").total == 3
        assert {e.device_uid for e in fetch_page(None, *FULL, None, " 1 ").events} == {1}

    def test_invalid_filters_are_refused_without_reading(self):
        for kw in ({"event_type": "bogus"}, {"uid_text": "12x"}, {"uid_text": "-4"}, {"uid_text": "٣"},
                   {"uid_text": "99999999999"}):
            r = EventsRepo()
            p = svc.get_events_page(*FULL, repository=r, **kw)
            assert p.status is svc.EventsStatus.INVALID and r.calls == []
        r = EventsRepo()
        assert svc.get_events_page(date(2026, 9, 1), date(2026, 8, 1), repository=r).status is svc.EventsStatus.INVALID
        assert r.calls == []

    def test_source_failure_is_unavailable(self):
        assert fetch_page(EventsRepo(fail=True), *FULL).status is svc.EventsStatus.UNAVAILABLE
        p = svc.get_events_page(*FULL, repository=EventsRepo(),
                                network_fetch=lambda: net.CurrentNetwork(net.NetworkStatus.UNAVAILABLE))
        assert p.status is svc.EventsStatus.UNAVAILABLE


class TestRegisteredVersusHistorical:
    def test_unregistered_uid_is_kept_and_flagged(self):
        p = fetch_page(None, date(2026, 7, 1), date(2026, 7, 1))
        e, = p.events
        assert e.device_uid == 77 and e.registered is False and e.current is None
        assert e.event_transformer_code == "GONE"

    def test_only_registered_uids_link_to_rtl_detail(self):
        p = fetch_page(None, *FULL)
        table = ui.events_table(p)
        hrefs = sorted(n.href for n in walk(table) if isinstance(getattr(n, "href", None), str))
        assert set(hrefs) <= {"/rtls/1", "/rtls/2"} and "/rtls/77" not in hrefs
        text = _text(table)
        assert "Historical RTL UID 77" in text
        assert "/rtls/77" not in str(table)

    def test_network_snapshot_is_read_once_and_only_when_needed(self):
        calls = []

        def nf():
            calls.append(1)
            return net.get_current_network(network_repo())

        svc.get_events_page(*FULL, repository=EventsRepo(), network_fetch=nf)
        assert calls == [1]
        calls.clear()
        svc.get_events_page(date(2001, 1, 1), date(2001, 1, 2), repository=EventsRepo(), network_fetch=nf)
        assert calls == []


class TestCurrentNetworkContext:
    def test_context_comes_from_the_shared_current_network_service(self):
        p = fetch_page(None, date(2026, 8, 12), date(2026, 8, 12))
        e, = p.events  # UID 2: mapped, hierarchy blank
        cur = net.get_current_network(network_repo()).rows
        assert e.current == next(r for r in cur if r.device_uid == 2)
        one = fetch_page(None, date(2026, 8, 1), date(2026, 8, 1)).events[0]
        assert one.current.hierarchy.zone == "Z1"

    def test_labels_say_current_and_recorded_is_kept_separate(self):
        table = ui.events_table(fetch_page(None, *FULL))
        heads = [n.children for n in walk(table) if type(n).__name__ == "Th"]
        assert "Current Transformer" in heads and "Current Network Context" in heads
        assert "Recorded Transformer" in heads
        assert "not where it was at the time" in ui.NOTE

    def test_unmapped_and_unavailable_wording(self):
        text = _text(ui.events_table(fetch_page(None, date(2026, 8, 12), date(2026, 8, 12))))
        assert ui.NO_HIERARCHY in text
        extra = EventsRepo([ev("powerdown", 3, datetime(2026, 8, 1, 1, 0), "3.5", "X")])
        assert ui.NO_MAPPING in _text(ui.events_table(fetch_page(extra, *FULL)))

    def test_no_fuzzy_matching_or_postgres(self):
        src = "".join((ROOT / f).read_text(encoding="utf-8") for f in (
            "services/rtl_events_service.py", "components/historical_events.py",
            "callbacks/historical_events.py", "pages/historical_events.py"))
        assert not re.search(r"plant_monitoring|sqlalchemy|pymssql|\bSELECT\b|difflib|fuzz|casefold|attention_service", src)


class TestRendering:
    def test_labels_filters_and_summary(self):
        p = fetch_page(None, *FULL)
        body = _text(ui.body(p))
        for word in ("High Temperature", "Sensor Error", "Battery Low", "Powerdown", "Recorded At",
                     "RTL UID", "Recorded Value", "newest first"):
            assert word in body
        assert [o["label"] for o in page.type_options()] == [
            "All events", "High Temperature", "Sensor Error", "Battery Low", "Powerdown"]
        ids = {n.id for n in walk(page.layout()) if isinstance(getattr(n, "id", None), str)}
        assert {page.START_ID, page.TYPE_ID, page.UID_ID, page.PREV_ID, page.NEXT_ID} <= ids
        assert "Historical Events" in _text(page.layout())

    def test_no_alarm_state_language_or_raw_nulls(self):
        text = _text(page.layout()) + " " + _text(ui.body(fetch_page(None, *FULL))) + " " + ui.NOTE
        for pat in (r"Active", r"Open", r"Unresolved", r"Needs Attention", r"Online", r"Offline",
                    r"Plants?", r"Alarms?", r"Voltage", r"Frequency", r"Energy", r"None", r"null", r"NaN",
                    r"alarm_log", r"sensor_error_log", r"startup_msg_log", r"powerdown_log"):
            assert not re.findall(rf"\b{pat}\b", text, re.I if pat.startswith("alarm") else 0), pat

    def test_missing_value_and_empty_state_are_words(self):
        e = fetch_page(EventsRepo([ev("powerdown", 1, datetime(2026, 8, 1), None)]), *FULL).events[0]
        assert ui.value_text(e) == "—"
        empty = fetch_page(None, date(2001, 1, 1), date(2001, 1, 2))
        assert ui.NO_EVENTS in _text(ui.body(empty))


class TestAuthorizationAndCallbacks:
    def test_policy_matches_the_network_route(self):
        from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN, may_access_route
        assert may_access_route(ADMINISTRATOR, "historical_events") and may_access_route(GENERAL, "historical_events")
        assert not may_access_route(TECHNICIAN, "historical_events")
        assert not may_access_route(None, "historical_events")

    def test_routing_checks_scope_before_the_layout(self):
        src = (ROOT / "callbacks/routing.py").read_text(encoding="utf-8")
        block = src[src.index('if route.name == "historical_events":'):][:600]
        assert block.index("may_view_real_fleet(scope)") < block.index("historical_events.layout()")

    def test_restricted_scopes_read_nothing(self):
        for scope in (None, EMPTY, DeviceScope(frozenset({"d"}))):
            calls = []
            ctx = {"route": "historical_events"}
            assert cb.initial_window(ctx, latest=lambda: calls.append(1), scope_for=lambda s=scope: s) == (None, None)
            out = cb.render(ctx, "2026-01-01", "2026-02-01", "all", "", None, 0,
                            fetch=lambda *a: calls.append(1), scope_for=lambda s=scope: s)
            assert out == (None, 0) and calls == []

    def test_permitted_scope_sets_window_and_renders(self):
        ctx = {"route": "historical_events"}
        w = cb.initial_window(ctx, latest=lambda: datetime(2026, 8, 12, 9), scope_for=lambda: UNRESTRICTED)
        assert w == ("2026-07-14", "2026-08-12")
        body, pg = cb.render(ctx, "2026-01-01", "2026-12-31", "all", "", None, 0,
                             fetch=lambda *a, **k: fetch_page(None, *a, **k), scope_for=lambda: UNRESTRICTED)
        assert "Recorded At" in _text(body) and pg == 0

    def test_other_routes_are_ignored(self):
        assert cb.initial_window({"route": "overview"}) == (no_update, no_update)
        assert cb.render({"route": "overview"}, None, None, None, None, None, 0) == (no_update, no_update)

    def test_paging_moves_and_filters_reset(self):
        seen = []
        ctx = {"route": "historical_events"}

        def fetch(s, e, t, u, p):
            seen.append(p)
            return fetch_page(None, s, e, t, u, p)

        kw = dict(fetch=fetch, scope_for=lambda: UNRESTRICTED)
        cb.render(ctx, "2026-01-01", "2026-12-31", "all", "", page.NEXT_ID, 0, **kw)
        cb.render(ctx, "2026-01-01", "2026-12-31", "all", "", page.PREV_ID, 3, **kw)
        cb.render(ctx, "2026-01-01", "2026-12-31", "battery_low", "", page.TYPE_ID, 3, **kw)
        assert seen == [1, 2, 0]

    def test_invalid_input_shows_a_message(self):
        out, _ = cb.render({"route": "historical_events"}, "2026-01-01", "2026-12-31", "all", "abc", None, 0,
                           fetch=lambda *a, **k: fetch_page(None, *a, **k), scope_for=lambda: UNRESTRICTED)
        assert "whole number" in _text(out)

    def test_dashboard_and_legacy_are_not_changed_by_the_route(self):
        assert "attention" not in (ROOT / "callbacks/historical_events.py").read_text(encoding="utf-8").lower()
