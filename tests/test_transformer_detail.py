"""Transformer screen: "within this transformer, which device needs attention?"

The last link in the investigation chain before the device workspace. Same
patterns as Fleet and Plant; the one thing genuinely different here is the noun,
because a device rolls up its *metrics* rather than its children.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from callbacks.listings import (
    DEVICE_COLUMNS,
    build_device_rows,
    build_transformer_detail_view,
    sort_device_rows_exception_first,
)
from components.fleet_summary import transformer_kpi_cards
from config.metrics import ATTRIBUTION_METRIC_KEY, ordered_metrics
from services.device_scope import UNRESTRICTED
from services.monitoring_service import Freshness, fleet_health_from_rows
from tests.dash_tree import find_by_class, find_by_id, text_of

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
FRESH_TS = NOW - timedelta(minutes=10)
STALE_TS = NOW - timedelta(days=2)

F, S, N = Freshness.FRESH, Freshness.STALE, Freshness.NO_DATA


def _row(device, metric, ts, transformer="t1", plant="p1"):
    return type("R", (), {"plant_id": plant, "transformer_id": transformer,
                          "device_id": device, "metric": metric,
                          "reading_ts": ts})()


class _Device:
    def __init__(self, did, code, status="active"):
        self.device_id = did
        self.device_code = code
        self.status = status


class TestDeviceRows:
    def test_device_label_counts_metrics_not_devices(self):
        """A device rolls up its own metrics. '1 of 8 devices' on a device row
        would be nonsense, and it is the kind of nonsense a shared helper with a
        hardcoded noun produces."""
        health = fleet_health_from_rows(
            [_row("d1", "temperature", FRESH_TS), _row("d1", "voltage", STALE_TS)],
            now=NOW,
        )
        rows = build_device_rows([_Device("d1", "29017")], health)
        assert rows[0]["freshness"] == "Stale · 1 of 2 metrics"

    def test_device_absent_from_health_is_no_data(self):
        rows = build_device_rows([_Device("d9", "99999")], fleet_health_from_rows([]))
        assert rows[0]["freshness"] == "No data · 0 of 0 metrics"

    def test_row_identity_is_the_device_id(self):
        health = fleet_health_from_rows([_row("d1", "temperature", FRESH_TS)], now=NOW)
        rows = build_device_rows([_Device("d1", "29017")], health)
        assert rows[0]["id"] == "d1"

    def test_freshness_and_status_are_separate_columns(self):
        ids = [c["id"] for c in DEVICE_COLUMNS]
        assert "status" in ids and "freshness" in ids

    def test_exception_first_then_device_code(self):
        health = fleet_health_from_rows([
            _row("d_f", "temperature", FRESH_TS),
            _row("d_s", "temperature", STALE_TS),
            _row("d_n", "temperature", None),
        ], now=NOW)
        rows = build_device_rows(
            [_Device("d_f", "10001"), _Device("d_s", "99999"), _Device("d_n", "50000")],
            health,
        )
        assert [r["id"] for r in sort_device_rows_exception_first(rows)] == [
            "d_n", "d_s", "d_f"
        ]

    def test_ties_fall_back_to_device_code(self):
        health = fleet_health_from_rows([
            _row("d1", "temperature", FRESH_TS), _row("d2", "temperature", FRESH_TS),
        ], now=NOW)
        rows = build_device_rows(
            [_Device("d2", "99999"), _Device("d1", "10001")], health
        )
        ordered = sort_device_rows_exception_first(rows)
        assert [r["device"] for r in ordered] == ["10001", "99999"]


class TestTransformerKpiCards:
    def _health(self):
        return fleet_health_from_rows([
            _row("d1", "temperature", FRESH_TS, transformer="t1"),
            _row("d2", "temperature", STALE_TS, transformer="t1"),
            _row("d9", "temperature", STALE_TS, transformer="t2"),
        ], now=NOW)

    def test_renders_two_cards(self):
        cards = transformer_kpi_cards("t1", devices=2, health=self._health())
        labels = [text_of(el) for el in find_by_class(cards, "kpi-card__label")]
        assert labels == ["Devices", "Data Health"]

    def test_data_health_is_scoped_to_this_transformer(self):
        """t2's stale device belongs to a sibling transformer and must not
        appear in this transformer's card."""
        cards = transformer_kpi_cards("t1", devices=2, health=self._health())
        values = [text_of(el) for el in find_by_class(cards, "kpi-card__value")]
        secondary = [text_of(el) for el in find_by_class(cards, "kpi-card__secondary")]
        assert values == ["2", "1 stale"]
        assert secondary[1] == "1 fresh"

    def test_unknown_transformer_is_not_reported_as_healthy(self):
        cards = transformer_kpi_cards("nope", devices=0, health=self._health())
        secondary = [text_of(el) for el in find_by_class(cards, "kpi-card__secondary")]
        assert secondary[1] == "No data available"


class TestInvestigationChainConsistency:
    """Fleet, Plant and Transformer must describe the same devices identically."""

    def _health(self):
        return fleet_health_from_rows([
            _row("d1", "temperature", FRESH_TS, transformer="t1", plant="p1"),
            _row("d2", "temperature", STALE_TS, transformer="t1", plant="p1"),
            _row("d3", "temperature", None, transformer="t2", plant="p1"),
        ], now=NOW)

    def test_plant_counts_equal_the_sum_of_its_transformer_counts(self):
        health = self._health()
        plant = health.device_counts_for_plant("p1")
        summed = {state: 0 for state in Freshness}
        for tid in ("t1", "t2"):
            for state, n in health.transformers[tid].counts.items():
                summed[state] += n
        assert plant == summed

    def test_worst_state_propagates_all_the_way_up(self):
        """One device with no readings must be visible at every level above it."""
        health = self._health()
        assert health.devices["d3"].state is N
        assert health.transformers["t2"].state is N
        assert health.plants["p1"].state is N
        assert health.counts[N] == 1


# --------------------------------------------------------------------------
# Phase 5 integration: build_transformer_detail_view
# --------------------------------------------------------------------------

def _stub_devices(monkeypatch, devices=()):
    from repositories import plant_monitoring_repository as repo

    monkeypatch.setattr(
        repo, "list_devices",
        lambda transformer_id, *, allowed_device_ids: list(devices),
    )


class TestBuildTransformerDetailViewQueryCounts:
    def test_fetches_latest_reading_rows_exactly_once(self, monkeypatch):
        from repositories import plant_monitoring_repository as repo

        _stub_devices(monkeypatch, devices=[_Device("d1", "29017")])
        calls = []
        monkeypatch.setattr(
            repo, "latest_reading_times",
            lambda metrics, *, allowed_device_ids=None, include_inactive=False: calls.append(metrics) or [],
        )
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        build_transformer_detail_view("t1", "Itaipu", "aa12", NOW, scope=UNRESTRICTED)
        assert len(calls) == 1

    def test_fetches_latest_metric_readings_exactly_once_scoped_to_the_transformer(self, monkeypatch):
        from repositories import plant_monitoring_repository as repo

        _stub_devices(monkeypatch, devices=[])
        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        calls = []
        monkeypatch.setattr(
            repo, "latest_metric_readings",
            lambda metric, plant_id=None, transformer_id=None, allowed_device_ids=None, include_inactive=False: (
                calls.append((metric, plant_id, transformer_id)) or []
            ),
        )

        build_transformer_detail_view("t1", "Itaipu", "aa12", NOW, scope=UNRESTRICTED)
        assert calls == [(ATTRIBUTION_METRIC_KEY, None, "t1")]

    def test_no_per_metric_query_loop(self, monkeypatch):
        from repositories import plant_monitoring_repository as repo

        _stub_devices(monkeypatch, devices=[])
        reading_calls = []
        monkeypatch.setattr(
            repo, "latest_reading_times",
            lambda metrics, *, allowed_device_ids=None, include_inactive=False: reading_calls.append(metrics) or [],
        )
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        build_transformer_detail_view("t1", "Itaipu", "aa12", NOW, scope=UNRESTRICTED)
        assert len(reading_calls) == 1
        assert len(reading_calls[0]) == len(ordered_metrics())

    def test_one_timestamp_feeds_data_health_metric_health_and_attribution(self, monkeypatch):
        import services.monitoring_service as ms
        from repositories import plant_monitoring_repository as repo

        _stub_devices(monkeypatch, devices=[])
        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        seen = {}
        real_fleet, real_metric, real_hot = (
            ms.fleet_health_from_rows, ms.metric_health_from_rows, ms.hottest_temperature,
        )

        def spy_fleet(rows, now=None):
            seen["fleet"] = now
            return real_fleet(rows, now)

        def spy_metric(rows, **kw):
            seen["metric"] = kw.get("now")
            return real_metric(rows, **kw)

        def spy_hot(readings, now=None):
            seen["hot"] = now
            return real_hot(readings, now=now)

        monkeypatch.setattr(ms, "fleet_health_from_rows", spy_fleet)
        monkeypatch.setattr(ms, "metric_health_from_rows", spy_metric)
        monkeypatch.setattr(ms, "hottest_temperature", spy_hot)

        build_transformer_detail_view("t1", "Itaipu", "aa12", NOW, scope=UNRESTRICTED)
        assert seen["fleet"] == seen["metric"] == seen["hot"] == NOW


class TestBuildTransformerDetailViewContent:
    def test_context_carries_plant_transformer_and_device_count(self, monkeypatch):
        _stub_devices(monkeypatch, devices=[_Device("d1", "29017"), _Device("d2", "29018")])
        from repositories import plant_monitoring_repository as repo

        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        result = build_transformer_detail_view("t1", "Itaipu", "aa12", NOW, scope=UNRESTRICTED)
        assert result["context_fields"] == [
            ("Plant", "Itaipu"),
            ("Transformer", "aa12"),
            ("Devices", 2),
        ]

    def test_metric_health_covers_all_eight_configured_metrics(self, monkeypatch):
        _stub_devices(monkeypatch, devices=[])
        from repositories import plant_monitoring_repository as repo

        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        result = build_transformer_detail_view("t1", "Itaipu", "aa12", NOW, scope=UNRESTRICTED)
        assert len(result["metric_health_items"]) == 8

    def test_existing_device_table_rows_still_populate(self, monkeypatch):
        _stub_devices(monkeypatch, devices=[_Device("d1", "29017")])
        from repositories import plant_monitoring_repository as repo

        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        result = build_transformer_detail_view("t1", "Itaipu", "aa12", NOW, scope=UNRESTRICTED)
        assert [r["id"] for r in result["table_rows"]] == ["d1"]

    def test_stale_attribution_reading_survives_into_the_view(self, monkeypatch):
        from repositories.plant_monitoring_repository import DeviceMetricReading

        stale_reading = DeviceMetricReading(
            plant_id="p1", transformer_id="t1", transformer_code="aa12",
            device_id="d1", device_code="29044", metric="temperature",
            reading_ts=NOW - timedelta(days=2), value=41.0,
        )
        _stub_devices(monkeypatch, devices=[])
        from repositories import plant_monitoring_repository as repo

        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [stale_reading])

        result = build_transformer_detail_view("t1", "Itaipu", "aa12", NOW, scope=UNRESTRICTED)
        attribution = result["attribution"]
        assert attribution.has_data is True
        assert attribution.value == 41.0
        assert attribution.freshness is Freshness.STALE

    def test_attribution_omits_transformer_emphasis_for_transformer_scope(self, monkeypatch):
        """Transformer scope: the page header already names this transformer,
        so the card built from it must not repeat the transformer code."""
        from components.temperature_attribution import temperature_attribution
        from repositories.plant_monitoring_repository import DeviceMetricReading

        reading = DeviceMetricReading(
            plant_id="p1", transformer_id="t1", transformer_code="aa12",
            device_id="d1", device_code="29044", metric="temperature",
            reading_ts=NOW, value=30.0,
        )
        _stub_devices(monkeypatch, devices=[])
        from repositories import plant_monitoring_repository as repo

        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [reading])

        result = build_transformer_detail_view("t1", "Itaipu", "aa12", NOW, scope=UNRESTRICTED)
        card = temperature_attribution(result["attribution"], show_transformer=False)
        assert "aa12" not in text_of(card)
        assert "29044" in text_of(card)


class TestTransformerPageLayout:
    def test_uses_the_monitoring_width_class(self):
        from pages import transformer_detail

        layout = transformer_detail.layout("Plant", "T1", "p1")
        assert "page--monitoring" in layout.className

    def test_contains_the_new_container_ids(self):
        from pages import transformer_detail

        layout = transformer_detail.layout("Plant", "T1", "p1")
        for container_id in (
            "transformer-context", "transformer-metric-health", "transformer-attribution",
        ):
            assert find_by_id(layout, container_id) is not None, container_id

    def test_new_containers_start_empty(self):
        from pages import transformer_detail

        layout = transformer_detail.layout("Plant", "T1", "p1")
        for container_id in (
            "transformer-context", "transformer-metric-health", "transformer-attribution",
        ):
            node = find_by_id(layout, container_id)
            assert getattr(node, "children", None) is None
