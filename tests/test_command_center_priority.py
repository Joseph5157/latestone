"""Priority Investigation — the ranked per-RTL list (CC-1 Phase 10, ADR-009).

The panel answers "which exact RTLs do I open first?", and the danger the
whole phase is designed against is that a per-RTL ranked list drifts into an
alarm queue. So these tests are mostly about what must NOT influence the
order: no event, no severity vocabulary, no `device_last_updated`.

Same convention as tests/test_command_center_service.py — the two approved
read paths are monkeypatched and freshness aggregation runs for real, so
what is under test is the ranking, not a hand-built fixture of it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services import command_center_service as svc
from services.device_scope import EMPTY, UNRESTRICTED
from services.monitoring_service import Freshness, fleet_health_from_rows

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
FRESH_TS = NOW - timedelta(minutes=5)
STALE_2H = NOW - timedelta(hours=2)
STALE_9H = NOW - timedelta(hours=9)
STALE_3D = NOW - timedelta(days=3)

#: The eight metrics a real RTL carries (AGENTS.md scope).
METRICS = (
    "temperature", "voltage", "current", "active_power",
    "reactive_power", "power_factor", "frequency", "energy",
)


def _rows(device_id, *, plant_id, transformer_id, timestamps):
    """One (device, metric) latest-reading row per metric.

    `timestamps` is a list as long as the metrics it covers; `None` means the
    metric has never reported, which is what makes a device NO_DATA.
    """
    return [
        SimpleNamespace(
            plant_id=plant_id,
            transformer_id=transformer_id,
            device_id=device_id,
            metric=metric,
            reading_ts=ts,
        )
        for metric, ts in zip(METRICS, timestamps)
    ]


def _all(device_id, ts, *, plant_id="p1", transformer_id="t1"):
    """A device whose every metric shares one timestamp."""
    return _rows(
        device_id,
        plant_id=plant_id,
        transformer_id=transformer_id,
        timestamps=[ts] * len(METRICS),
    )


def _path(device_id, *, plant_name, transformer_code, device_code):
    """A DevicePath-shaped label row (hierarchy_service.list_device_paths)."""
    return SimpleNamespace(
        plant_id="p1",
        plant_name=plant_name,
        transformer_id="t1",
        transformer_code=transformer_code,
        device_id=device_id,
        device_code=device_code,
        device_status="active",
    )


def _snapshot(monkeypatch, rows, *, paths=(), events=(), scope=UNRESTRICTED):
    monkeypatch.setattr(
        svc, "get_fleet_health", lambda now, *, scope: fleet_health_from_rows(rows, NOW)
    )
    monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: list(events))
    monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
    monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
    monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: list(paths))
    # `now` is pinned: the rows' ages are measured against it, so leaving it
    # to wall-clock time would make every age assertion below drift.
    return svc.get_command_center_snapshot(scope=scope, now=NOW)


def _ids(snapshot):
    return [row.device_id for row in snapshot.priority_rtls]


class TestPopulation:
    """ADR-009 D1 — the attention population, and only it."""

    def test_only_stale_and_no_data_enter_the_list(self, monkeypatch):
        rows = (
            _all("fresh", FRESH_TS)
            + _all("stale", STALE_2H)
            + _rows("blind", plant_id="p1", transformer_id="t1",
                    timestamps=[FRESH_TS] * 7 + [None])
        )
        snapshot = _snapshot(monkeypatch, rows)
        assert set(_ids(snapshot)) == {"blind", "stale"}

    def test_a_fresh_rtl_never_appears(self, monkeypatch):
        snapshot = _snapshot(monkeypatch, _all("d1", FRESH_TS) + _all("d2", FRESH_TS))
        assert snapshot.priority_rtls == ()

    def test_one_fresh_metric_plus_one_never_reported_is_no_data(self, monkeypatch):
        """The delicate case: seven healthy feeds must not mask the missing one."""
        rows = _rows("mixed", plant_id="p1", transformer_id="t1",
                     timestamps=[FRESH_TS] * 7 + [None])
        snapshot = _snapshot(monkeypatch, rows)
        row = snapshot.priority_rtls[0]
        assert row.state is Freshness.NO_DATA
        assert row.badge_label == "NO DATA"

    def test_the_population_matches_the_attention_count(self, monkeypatch):
        """Priority is a lens on Needs Attention, never a second definition."""
        rows = (
            _all("f", FRESH_TS)
            + _all("s1", STALE_2H)
            + _all("s2", STALE_9H)
            + _rows("n1", plant_id="p1", transformer_id="t1",
                    timestamps=[None] * len(METRICS))
        )
        snapshot = _snapshot(monkeypatch, rows)
        assert len(snapshot.priority_rtls) == snapshot.attention_rtls == 3


class TestOrdering:
    """ADR-009 D2."""

    def test_no_data_ranks_before_stale(self, monkeypatch):
        """Even when the stale device has been silent far longer."""
        rows = (
            _all("stale-3d", STALE_3D)
            + _rows("blind", plant_id="p1", transformer_id="t1",
                    timestamps=[FRESH_TS] * 7 + [None])
        )
        snapshot = _snapshot(monkeypatch, rows)
        assert _ids(snapshot) == ["blind", "stale-3d"]

    def test_within_stale_the_oldest_lagging_metric_comes_first(self, monkeypatch):
        rows = _all("recent", STALE_2H) + _all("old", STALE_9H) + _all("oldest", STALE_3D)
        snapshot = _snapshot(monkeypatch, rows)
        assert _ids(snapshot) == ["oldest", "old", "recent"]

    def test_stale_order_uses_the_lagging_metric_not_the_freshest(self, monkeypatch):
        """The case a `device_last_updated` ranking gets backwards.

        `lagging` has one metric silent for three days and seven reporting
        moments ago, so its MAX is newer than `steady`'s. Ranked on the max it
        would sort second; ranked honestly it is the one to open first.
        """
        rows = (
            _rows("lagging", plant_id="p1", transformer_id="t1",
                  timestamps=[FRESH_TS] * 7 + [STALE_3D])
            + _all("steady", STALE_2H)
        )
        snapshot = _snapshot(monkeypatch, rows)
        assert _ids(snapshot) == ["lagging", "steady"]

    def test_within_no_data_the_order_is_hierarchy_then_device(self, monkeypatch):
        blind = [None] * len(METRICS)
        rows = (
            _rows("d-b", plant_id="p1", transformer_id="t1", timestamps=blind)
            + _rows("d-a", plant_id="p1", transformer_id="t1", timestamps=blind)
            + _rows("d-c", plant_id="p1", transformer_id="t1", timestamps=blind)
        )
        paths = [
            _path("d-a", plant_name="Zambezi", transformer_code="aa01", device_code="1"),
            _path("d-b", plant_name="Amazonas", transformer_code="bb02", device_code="2"),
            _path("d-c", plant_name="Amazonas", transformer_code="aa03", device_code="3"),
        ]
        snapshot = _snapshot(monkeypatch, rows, paths=paths)
        # Amazonas before Zambezi; within Amazonas, aa03 before bb02.
        assert _ids(snapshot) == ["d-c", "d-b", "d-a"]

    def test_plant_names_sort_case_insensitively(self, monkeypatch):
        """A raw ASCII sort blocks every all-caps name ahead of the rest —
        the same defect real fleet data exposed at plant level (ADR-009 D2)."""
        blind = [None] * len(METRICS)
        rows = (
            _rows("caps", plant_id="p1", transformer_id="t1", timestamps=blind)
            + _rows("mixed", plant_id="p1", transformer_id="t1", timestamps=blind)
        )
        paths = [
            _path("caps", plant_name="GRAVELINES", transformer_code="a", device_code="1"),
            _path("mixed", plant_name="Grand Coulee", transformer_code="a", device_code="2"),
        ]
        snapshot = _snapshot(monkeypatch, rows, paths=paths)
        assert _ids(snapshot) == ["mixed", "caps"]

    def test_ordering_is_fully_determined(self, monkeypatch):
        """Identical on every key but the id — still one stable order."""
        rows = _all("d2", STALE_2H) + _all("d1", STALE_2H) + _all("d3", STALE_2H)
        first = _ids(_snapshot(monkeypatch, rows))
        second = _ids(_snapshot(monkeypatch, list(reversed(rows))))
        assert first == second == ["d1", "d2", "d3"]

    def test_the_list_is_capped_at_eight(self, monkeypatch):
        rows = []
        for i in range(12):
            rows += _all(f"d{i:02d}", NOW - timedelta(hours=i + 2))
        snapshot = _snapshot(monkeypatch, rows)
        assert len(snapshot.priority_rtls) == svc.PRIORITY_ROWS == 8
        # The cap trims the least urgent, never the most.
        assert _ids(snapshot)[0] == "d11"

    def test_the_total_is_carried_even_when_capped(self, monkeypatch):
        rows = []
        for i in range(12):
            rows += _all(f"d{i:02d}", NOW - timedelta(hours=i + 2))
        snapshot = _snapshot(monkeypatch, rows)
        assert snapshot.priority_total == 12


class TestEventsDoNotParticipate:
    """ADR-009 D1 / ADR-002 — occurrence must not reorder current state."""

    def _event(self, event_id, device_id, event_type):
        return SimpleNamespace(
            event_id=event_id,
            device_id=device_id,
            transformer_id="t1",
            reported_uid=None,
            event_type=event_type,
            severity=None,
            battery_voltage=None,
            event_ts=NOW - timedelta(minutes=1),
        )

    def test_a_storm_of_critical_events_changes_no_position(self, monkeypatch):
        rows = _all("quiet", STALE_9H) + _all("noisy", STALE_2H)
        baseline = _ids(_snapshot(monkeypatch, rows))

        storm = [self._event(i, "noisy", "power_down") for i in range(20)]
        after = _ids(_snapshot(monkeypatch, rows, events=storm))

        assert baseline == after == ["quiet", "noisy"]

    def test_an_event_cannot_add_a_fresh_rtl_to_the_list(self, monkeypatch):
        rows = _all("fresh", FRESH_TS) + _all("stale", STALE_2H)
        storm = [self._event(1, "fresh", "power_down")]
        snapshot = _snapshot(monkeypatch, rows, events=storm)
        assert _ids(snapshot) == ["stale"]


class TestRowCopy:
    """ADR-009 D3/D4 — the sentence must name what it measures."""

    def test_no_data_gets_the_semantic_sentence_and_no_duration(self, monkeypatch):
        rows = _rows("blind", plant_id="p1", transformer_id="t1",
                     timestamps=[FRESH_TS] * 7 + [None])
        row = _snapshot(monkeypatch, rows).priority_rtls[0]
        assert row.reason == "At least one monitored metric has no reading."
        assert row.age_label is None

    def test_no_data_reuses_the_communication_card_sentence(self, monkeypatch):
        """One sentence, one definition — not two that can drift."""
        from components.command_center.situation_summary import NO_DATA_EXPLANATION

        rows = _rows("blind", plant_id="p1", transformer_id="t1",
                     timestamps=[None] * len(METRICS))
        row = _snapshot(monkeypatch, rows).priority_rtls[0]
        assert row.reason == NO_DATA_EXPLANATION

    @pytest.mark.parametrize("bad", ["ago", "0 min", "—", "never", "Never"])
    def test_no_data_never_carries_a_fabricated_duration(self, monkeypatch, bad):
        rows = _rows("blind", plant_id="p1", transformer_id="t1",
                     timestamps=[FRESH_TS] * 7 + [None])
        row = _snapshot(monkeypatch, rows).priority_rtls[0]
        assert bad not in row.reason

    def test_stale_reports_the_oldest_metric_age(self, monkeypatch):
        rows = _all("d1", NOW - timedelta(hours=3, minutes=41))
        row = _snapshot(monkeypatch, rows).priority_rtls[0]
        assert row.age_label == "3h 41m"
        assert row.reason == "Oldest monitored metric last reported 3h 41m ago"

    def test_the_stale_age_is_the_lagging_metric_not_the_freshest(self, monkeypatch):
        """A max-based age would print "5 min" beside a STALE badge."""
        rows = _rows("mixed", plant_id="p1", transformer_id="t1",
                     timestamps=[FRESH_TS] * 7 + [NOW - timedelta(hours=9)])
        row = _snapshot(monkeypatch, rows).priority_rtls[0]
        assert row.state is Freshness.STALE
        assert row.age_label == "9h 00m"

    def test_the_badge_label_is_the_state_not_an_alarm_word(self, monkeypatch):
        rows = _all("s", STALE_2H) + _rows(
            "n", plant_id="p1", transformer_id="t1", timestamps=[None] * len(METRICS)
        )
        labels = {row.device_id: row.badge_label for row in
                  _snapshot(monkeypatch, rows).priority_rtls}
        assert labels == {"n": "NO DATA", "s": "STALE"}
        assert "CRITICAL" not in labels.values()


class TestLabelsAndLinks:
    def test_the_hierarchy_label_is_plant_then_transformer(self, monkeypatch):
        rows = _all("d1", STALE_2H)
        paths = [_path("d1", plant_name="Three Gorges Dam",
                       transformer_code="aa12", device_code="29017")]
        row = _snapshot(monkeypatch, rows, paths=paths).priority_rtls[0]
        assert row.context_label == "Three Gorges Dam / aa12"
        assert row.device_label == "29017"

    def test_a_missing_label_falls_back_to_the_stable_id(self, monkeypatch):
        """It must NOT drop out: it is by definition a device the operator
        was just told to investigate first."""
        rows = _all("plant-01-t1-d1", STALE_2H)
        snapshot = _snapshot(monkeypatch, rows, paths=[])
        row = snapshot.priority_rtls[0]
        assert row.device_label == "plant-01-t1-d1"
        assert row.context_label is None

    def test_the_link_uses_the_existing_route_contract(self, monkeypatch):
        from routes import device_href

        rows = _all("plant-01-t1-d1", STALE_2H)
        row = _snapshot(monkeypatch, rows).priority_rtls[0]
        assert row.asset_href == device_href("plant-01-t1-d1")

    def test_an_unlabelled_device_still_gets_its_link(self, monkeypatch):
        """Unlike an event's unregistered UID, this device is REGISTERED — it
        came out of the monitored population. Only its name is missing."""
        rows = _all("plant-01-t1-d1", STALE_2H)
        row = _snapshot(monkeypatch, rows, paths=[]).priority_rtls[0]
        assert row.asset_href is not None

    def test_labels_are_fetched_in_one_batched_call(self, monkeypatch):
        """ADR-008's whole point: ONE lookup, never one per plant or device.

        It covers the whole attention population rather than the eight rows
        that survive the cap, because the NO_DATA order is by plant NAME —
        the names are what decide which eight those are. Still one query,
        still bounded by the caller's scope.
        """
        calls = []
        rows = []
        for i in range(12):
            rows += _all(f"d{i:02d}", NOW - timedelta(hours=i + 2))
        monkeypatch.setattr(
            svc, "get_fleet_health",
            lambda now, *, scope: fleet_health_from_rows(rows, NOW),
        )
        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: [])
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])

        def _paths(ids, *, scope):
            calls.append(list(ids))
            return []

        monkeypatch.setattr(svc, "list_device_paths", _paths)
        svc.get_command_center_snapshot(scope=UNRESTRICTED)

        priority_calls = [c for c in calls if c and c[0].startswith("d")]
        assert len(priority_calls) == 1
        assert len(priority_calls[0]) == 12


class TestEmptyStates:
    def test_an_all_fresh_fleet_is_calm_not_empty(self, monkeypatch):
        snapshot = _snapshot(monkeypatch, _all("d1", FRESH_TS))
        assert snapshot.priority_rtls == ()
        assert snapshot.priority_total == 0
        assert snapshot.has_monitored_devices is True

    def test_zero_monitored_is_distinct_from_zero_affected(self, monkeypatch):
        """Two different facts: "nothing to watch" and "nothing wrong"."""
        calm = _snapshot(monkeypatch, _all("d1", FRESH_TS))
        none_at_all = _snapshot(monkeypatch, [], scope=EMPTY)

        assert calm.priority_rtls == none_at_all.priority_rtls == ()
        assert calm.has_monitored_devices is True
        assert none_at_all.has_monitored_devices is False

    def test_an_empty_scope_asks_for_no_labels(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            svc, "get_fleet_health", lambda now, *, scope: fleet_health_from_rows([], NOW)
        )
        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: [])
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(
            svc, "list_device_paths", lambda ids, *, scope: calls.append(ids) or []
        )
        svc.get_command_center_snapshot(scope=EMPTY)
        assert all(not c for c in calls)


class TestPhase5To9AreUnchanged:
    """A new panel must not move a figure another panel already published."""

    def test_the_situation_summary_figures_are_untouched(self, monkeypatch):
        rows = (
            _all("f", FRESH_TS)
            + _all("s", STALE_2H)
            + _rows("n", plant_id="p1", transformer_id="t1",
                    timestamps=[None] * len(METRICS))
        )
        snapshot = _snapshot(monkeypatch, rows)
        assert snapshot.monitored_device_count == 3
        assert snapshot.fresh_rtls == 1
        assert snapshot.stale_rtls == 1
        assert snapshot.no_data_rtls == 1
        assert snapshot.attention_rtls == 2

    def test_the_affected_locations_ranking_is_untouched(self, monkeypatch):
        rows = _all("s", STALE_2H) + _all("f", FRESH_TS)
        snapshot = _snapshot(monkeypatch, rows)
        assert [loc.plant_id for loc in snapshot.affected_locations] == ["p1"]
        assert snapshot.affected_locations[0].affected_rtls == 1

    def test_the_electrical_conditions_stay_unavailable(self, monkeypatch):
        """Phase 6's contract: no current count exists (ADR-001)."""
        snapshot = _snapshot(monkeypatch, _all("s", STALE_2H))
        assert all(c.current_count is None for c in snapshot.electrical_conditions)


class TestOneSharedLabelLookup:
    """Both panels want device names; the facade may ask only once.

    Caught in Phase 10 development: the priority ranking added a second
    `list_device_paths` call beside the event rows' own. Two batched calls
    are still two queries, and this facade's contract is each approved read
    path AT MOST ONCE per render (ADR-008).
    """

    def _event(self, device_id):
        return SimpleNamespace(
            event_id=1,
            device_id=device_id,
            transformer_id="t1",
            reported_uid=None,
            event_type="power_down",
            severity=None,
            battery_voltage=None,
            event_ts=NOW - timedelta(minutes=1),
        )

    def _run(self, monkeypatch, rows, events):
        calls = []
        monkeypatch.setattr(
            svc, "get_fleet_health",
            lambda now, *, scope: fleet_health_from_rows(rows, NOW),
        )
        monkeypatch.setattr(
            svc, "list_recent_device_events", lambda **kw: list(events)
        )
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(
            svc, "list_device_paths",
            lambda ids, *, scope: calls.append(list(ids)) or [],
        )
        svc.get_command_center_snapshot(scope=UNRESTRICTED, now=NOW)
        return calls

    def test_events_and_priority_share_one_call(self, monkeypatch):
        rows = _all("stale-rtl", STALE_2H) + _all("fresh-rtl", FRESH_TS)
        calls = self._run(monkeypatch, rows, [self._event("fresh-rtl")])
        assert len(calls) == 1

    def test_the_one_call_covers_both_populations(self, monkeypatch):
        """The union, deduplicated — an event on a stale RTL is one id."""
        rows = _all("stale-rtl", STALE_2H) + _all("fresh-rtl", FRESH_TS)
        calls = self._run(
            monkeypatch, rows,
            [self._event("fresh-rtl"), self._event("stale-rtl")],
        )
        assert calls == [["fresh-rtl", "stale-rtl"]]

    def test_a_failed_event_read_contributes_no_ids(self, monkeypatch):
        """The events boundary holds: its failure must not widen or break
        the lookup the priority rows still depend on."""
        def _boom(**kwargs):
            raise RuntimeError("event read down")

        calls = []
        rows = _all("stale-rtl", STALE_2H)
        monkeypatch.setattr(
            svc, "get_fleet_health",
            lambda now, *, scope: fleet_health_from_rows(rows, NOW),
        )
        monkeypatch.setattr(svc, "list_recent_device_events", _boom)
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(
            svc, "list_device_paths",
            lambda ids, *, scope: calls.append(list(ids)) or [],
        )
        snapshot = svc.get_command_center_snapshot(scope=UNRESTRICTED, now=NOW)

        assert calls == [["stale-rtl"]]
        assert snapshot.recent_events_failed is True
        # The priority panel is unaffected — that is the whole point of the
        # one-directional boundary.
        assert _ids(snapshot) == ["stale-rtl"]


class TestTheCopyDoesNotNameAMetric:
    """The row may not identify the lagging metric — the model has no such
    field (ADR-009 D4).

    `device_oldest_metric_updated` carries a TIMESTAMP, not the identity of
    the metric that produced it. Naming one would mean inferring it, and an
    inferred metric name is a claim the snapshot cannot support: a device
    can have several metrics tied at the same oldest timestamp, and picking
    one to print would be arbitrary in a way the operator cannot see.

    So the copy stays generic ("Oldest monitored metric …") until the model
    carries the identity. These tests fail the day someone adds the word
    without adding the field.
    """

    def test_no_metric_name_appears_in_a_stale_reason(self, monkeypatch):
        rows = _rows("mixed", plant_id="p1", transformer_id="t1",
                     timestamps=[FRESH_TS] * 7 + [STALE_9H])
        row = _snapshot(monkeypatch, rows).priority_rtls[0]
        for metric in METRICS:
            assert metric not in row.reason.lower()

    def test_no_metric_name_appears_in_a_no_data_reason(self, monkeypatch):
        rows = _rows("blind", plant_id="p1", transformer_id="t1",
                     timestamps=[FRESH_TS] * 7 + [None])
        row = _snapshot(monkeypatch, rows).priority_rtls[0]
        for metric in METRICS:
            assert metric not in row.reason.lower()

    def test_the_row_exposes_no_metric_identity_to_infer_from(self):
        """A component cannot name what it was never handed."""
        assert not any(
            "metric" in field for field in svc.PriorityRTL.__dataclass_fields__
        )

    def test_the_generic_wording_is_what_ships(self, monkeypatch):
        rows = _all("d1", NOW - timedelta(hours=3, minutes=41))
        row = _snapshot(monkeypatch, rows).priority_rtls[0]
        assert row.reason == "Oldest monitored metric last reported 3h 41m ago"
