"""Plant screen: "within this plant, which transformer needs attention?"

Reuses the Fleet patterns rather than inventing new ones — same rollup chain,
same exception-first ordering, same one-object-per-render rule. The tests here
are mostly about that reuse being real and not a parallel implementation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from callbacks.listings import (
    TRANSFORMER_COLUMNS,
    build_plant_detail_view,
    build_transformer_rows,
    sort_transformer_rows_exception_first,
)
from components.fleet_summary import plant_kpi_cards
from config.metrics import ATTRIBUTION_METRIC_KEY, ordered_metrics
from services.device_scope import UNRESTRICTED
from services.monitoring_service import Freshness, fleet_health_from_rows
from tests.dash_tree import find_by_class, find_by_id, text_of

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
FRESH_TS = NOW - timedelta(minutes=10)
STALE_TS = NOW - timedelta(days=2)

F, S, N = Freshness.FRESH, Freshness.STALE, Freshness.NO_DATA


def _row(plant, transformer, device, ts, metric="temperature"):
    return type("R", (), {"plant_id": plant, "transformer_id": transformer,
                          "device_id": device, "metric": metric,
                          "reading_ts": ts})()


def _health(triples):
    return fleet_health_from_rows(
        [_row(p, t, d, ts) for p, t, d, ts in triples], now=NOW
    )


class _Transformer:
    def __init__(self, tid, code, status="active"):
        self.transformer_id = tid
        self.transformer_code = code
        self.status = status


class TestTransformerRollup:
    def test_transformer_is_worst_of_its_devices(self):
        health = _health([
            ("p1", "t1", "d1", FRESH_TS),
            ("p1", "t1", "d2", STALE_TS),
        ])
        assert health.transformers["t1"].state is S
        assert health.transformers["t1"].affected == 1
        assert health.transformers["t1"].total == 2

    def test_no_data_device_outranks_a_stale_sibling(self):
        health = _health([
            ("p1", "t1", "d1", STALE_TS),
            ("p1", "t1", "d2", None),
        ])
        assert health.transformers["t1"].state is N

    def test_transformer_rollup_does_not_disturb_the_plant_rollup(self):
        """Plant is worst-of its devices, however they are grouped below it."""
        health = _health([
            ("p1", "t1", "d1", FRESH_TS),
            ("p1", "t2", "d2", STALE_TS),
        ])
        assert health.plants["p1"].state is S
        assert health.plants["p1"].total == 2
        assert health.transformers["t1"].state is F
        assert health.transformers["t2"].state is S

    def test_transformers_can_be_selected_for_one_plant(self):
        health = _health([
            ("p1", "t1", "d1", FRESH_TS),
            ("p2", "t2", "d2", STALE_TS),
        ])
        assert set(health.transformers_for_plant("p1")) == {"t1"}
        assert set(health.transformers_for_plant("p2")) == {"t2"}

    def test_unknown_plant_selects_nothing_rather_than_everything(self):
        health = _health([("p1", "t1", "d1", FRESH_TS)])
        assert health.transformers_for_plant("nope") == {}


class TestTransformerRows:
    def test_row_carries_the_transformer_rollup_label(self):
        health = _health([
            ("p1", "t1", "d1", FRESH_TS), ("p1", "t1", "d2", STALE_TS),
        ])
        rows = build_transformer_rows([_Transformer("t1", "aa12")], {"t1": 2}, health)
        assert rows[0]["freshness"] == "Stale · 1 of 2 devices"

    def test_transformer_absent_from_health_is_no_data(self):
        rows = build_transformer_rows([_Transformer("t9", "zz99")], {"t9": 0}, _health([]))
        assert rows[0]["freshness"] == "No data · 0 of 0 devices"

    def test_row_identity_is_the_transformer_id(self):
        health = _health([("p1", "t1", "d1", FRESH_TS)])
        rows = build_transformer_rows([_Transformer("t1", "aa12")], {"t1": 1}, health)
        assert rows[0]["id"] == "t1"

    def test_freshness_is_a_declared_column(self):
        assert any(c["id"] == "freshness" for c in TRANSFORMER_COLUMNS)

    def test_administrative_status_stays_a_separate_column(self):
        """Status is active/inactive and must never be conflated with freshness."""
        ids = [c["id"] for c in TRANSFORMER_COLUMNS]
        assert "status" in ids and "freshness" in ids

    def test_exception_first_then_code(self):
        health = _health([
            ("p1", "t_f", "d1", FRESH_TS),
            ("p1", "t_s", "d2", STALE_TS),
            ("p1", "t_n", "d3", None),
        ])
        rows = build_transformer_rows(
            [_Transformer("t_f", "aa01"), _Transformer("t_s", "zz99"),
             _Transformer("t_n", "mm50")],
            {"t_f": 1, "t_s": 1, "t_n": 1},
            health,
        )
        assert [r["id"] for r in sort_transformer_rows_exception_first(rows)] == [
            "t_n", "t_s", "t_f"
        ]

    def test_ties_fall_back_to_transformer_code(self):
        health = _health([
            ("p1", "t1", "d1", FRESH_TS), ("p1", "t2", "d2", FRESH_TS),
        ])
        rows = build_transformer_rows(
            [_Transformer("t2", "zz99"), _Transformer("t1", "aa01")],
            {"t1": 1, "t2": 1}, health,
        )
        ordered = sort_transformer_rows_exception_first(rows)
        assert [r["transformer"] for r in ordered] == ["aa01", "zz99"]


class TestPlantKpiCards:
    def _cards(self):
        health = _health([
            ("p1", "t1", "d1", FRESH_TS), ("p1", "t1", "d2", STALE_TS),
            ("p2", "t9", "d9", STALE_TS),
        ])
        return plant_kpi_cards(
            plant_id="p1", transformers=1, devices=2, health=health
        )

    def test_renders_three_cards(self):
        labels = [text_of(el) for el in find_by_class(self._cards(), "kpi-card__label")]
        assert labels == ["Transformers", "Devices", "Data Health"]

    def test_data_health_is_scoped_to_this_plant_only(self):
        """The card must not report the fleet's counts on a plant page — p2's
        stale device belongs to another plant and must not appear here."""
        values = [text_of(el) for el in find_by_class(self._cards(), "kpi-card__value")]
        secondary = [text_of(el) for el in find_by_class(self._cards(), "kpi-card__secondary")]
        assert values == ["1", "2", "1 stale"]
        assert secondary[2] == "1 fresh"

    def test_reuses_the_frozen_card_component(self):
        """Same kpi-card language as Fleet and Device, not a new card type."""
        assert len(find_by_class(self._cards(), "kpi-card__value")) == 3

    def test_plant_with_no_devices_is_not_reported_as_healthy(self):
        cards = plant_kpi_cards(plant_id="empty", transformers=0, devices=0,
                                health=_health([]))
        secondary = [text_of(el) for el in find_by_class(cards, "kpi-card__secondary")]
        assert secondary[2] == "No data available"


# --------------------------------------------------------------------------
# Phase 5 integration: build_plant_detail_view
# --------------------------------------------------------------------------

class _Device:
    """Only `.status` matters to `hierarchy_service.list_devices`'s active
    filter; the row-building code under test never reads device identity."""
    def __init__(self, status="active"):
        self.status = status


class _PlantRecord:
    def __init__(self, plant_id, name, country="Chile", primary_fuel="Hydro", capacity_mw=450.0):
        self.plant_id = plant_id
        self.name = name
        self.country = country
        self.primary_fuel = primary_fuel
        self.capacity_mw = capacity_mw


def _stub_hierarchy(monkeypatch, plant=None, transformers=(), devices_by_transformer=None):
    from repositories import plant_monitoring_repository as repo

    monkeypatch.setattr(repo, "get_plant", lambda plant_id: plant)
    monkeypatch.setattr(
        repo, "list_transformers",
        lambda plant_id, *, allowed_device_ids: list(transformers),
    )
    by_transformer = devices_by_transformer or {}
    monkeypatch.setattr(
        repo, "list_devices",
        lambda transformer_id, *, allowed_device_ids: list(
            by_transformer.get(transformer_id, [])
        ),
    )


class TestBuildPlantDetailViewQueryCounts:
    """The whole point of splitting latest_reading_rows() out: Data Health and
    Metric Health must share one fetch, and attribution must not add a loop."""

    def test_fetches_latest_reading_rows_exactly_once(self, monkeypatch):
        from repositories import plant_monitoring_repository as repo

        _stub_hierarchy(
            monkeypatch, plant=_PlantRecord("p1", "Itaipu"),
            transformers=[_Transformer("t1", "aa12")],
            devices_by_transformer={"t1": [_Device()]},
        )
        calls = []
        monkeypatch.setattr(
            repo, "latest_reading_times",
            lambda metrics, *, allowed_device_ids=None, include_inactive=False: calls.append(metrics) or [],
        )
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        build_plant_detail_view("p1", NOW, scope=UNRESTRICTED)
        assert len(calls) == 1

    def test_fetches_latest_metric_readings_exactly_once_scoped_to_the_plant(self, monkeypatch):
        from repositories import plant_monitoring_repository as repo

        _stub_hierarchy(monkeypatch, plant=_PlantRecord("p1", "Itaipu"), transformers=[])
        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        calls = []
        monkeypatch.setattr(
            repo, "latest_metric_readings",
            lambda metric, plant_id=None, transformer_id=None, include_inactive=False: (
                calls.append((metric, plant_id, transformer_id)) or []
            ),
        )

        build_plant_detail_view("p1", NOW, scope=UNRESTRICTED)
        assert calls == [(ATTRIBUTION_METRIC_KEY, "p1", None)]

    def test_no_per_metric_query_loop(self, monkeypatch):
        """One latest_reading_times() call covers all 8 metrics via its own
        CROSS JOIN - metric_health_from_rows must not issue one per metric."""
        from repositories import plant_monitoring_repository as repo

        _stub_hierarchy(monkeypatch, plant=_PlantRecord("p1", "Itaipu"), transformers=[])
        reading_calls = []
        monkeypatch.setattr(
            repo, "latest_reading_times",
            lambda metrics, *, allowed_device_ids=None, include_inactive=False: reading_calls.append(metrics) or [],
        )
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        build_plant_detail_view("p1", NOW, scope=UNRESTRICTED)
        assert len(reading_calls) == 1
        assert len(reading_calls[0]) == len(ordered_metrics())

    def test_one_timestamp_feeds_data_health_metric_health_and_attribution(self, monkeypatch):
        import services.monitoring_service as ms
        from repositories import plant_monitoring_repository as repo

        _stub_hierarchy(monkeypatch, plant=_PlantRecord("p1", "Itaipu"), transformers=[])
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

        build_plant_detail_view("p1", NOW, scope=UNRESTRICTED)
        assert seen["fleet"] == seen["metric"] == seen["hot"] == NOW


class TestBuildPlantDetailViewContent:
    def test_context_carries_country_fuel_capacity_and_counts(self, monkeypatch):
        from repositories import plant_monitoring_repository as repo

        _stub_hierarchy(
            monkeypatch,
            plant=_PlantRecord("p1", "Itaipu", country="Brazil", primary_fuel="Hydro", capacity_mw=450.0),
            transformers=[_Transformer("t1", "aa12"), _Transformer("t2", "aa13")],
            devices_by_transformer={"t1": [_Device()], "t2": [_Device(), _Device()]},
        )
        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        result = build_plant_detail_view("p1", NOW, scope=UNRESTRICTED)
        assert result["context_fields"] == [
            ("Country", "Brazil"),
            ("Primary fuel", "Hydro"),
            ("Capacity", "450 MW"),
            ("Transformers", 2),
            ("Devices", 3),
        ]

    def test_metric_health_covers_all_eight_configured_metrics(self, monkeypatch):
        from repositories import plant_monitoring_repository as repo

        _stub_hierarchy(monkeypatch, plant=_PlantRecord("p1", "Itaipu"), transformers=[])
        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        result = build_plant_detail_view("p1", NOW, scope=UNRESTRICTED)
        assert len(result["metric_health_items"]) == 8

    def test_capacity_formats_a_decimal_column_value_without_a_trailing_zero(self, monkeypatch):
        """`capacity_mw` is a NUMERIC column: psycopg2 hands back a
        `decimal.Decimal`, not a `float`. `f"{Decimal('5805.0'):g}"` renders
        "5805.0" (it preserves the column's stored scale); the Fleet table's
        own numeric cell for this same value renders "5805" — this must
        match that, not the Decimal's raw scale. Caught live in the browser,
        not just reasoned about."""
        from decimal import Decimal

        from repositories import plant_monitoring_repository as repo

        _stub_hierarchy(
            monkeypatch,
            plant=_PlantRecord("p1", "Az Zour South CCGT", capacity_mw=Decimal("5805.0")),
            transformers=[],
        )
        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        result = build_plant_detail_view("p1", NOW, scope=UNRESTRICTED)
        capacity_field = dict(result["context_fields"])["Capacity"]
        assert capacity_field == "5805 MW"

    def test_existing_transformer_table_rows_still_populate(self, monkeypatch):
        from repositories import plant_monitoring_repository as repo

        _stub_hierarchy(
            monkeypatch, plant=_PlantRecord("p1", "Itaipu"),
            transformers=[_Transformer("t1", "aa12")],
            devices_by_transformer={"t1": [_Device()]},
        )
        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        result = build_plant_detail_view("p1", NOW, scope=UNRESTRICTED)
        assert [r["id"] for r in result["table_rows"]] == ["t1"]

    def test_stale_attribution_reading_survives_into_the_view(self, monkeypatch):
        """A hotter stale reading must reach the component, not get filtered
        out along the way."""
        from repositories.plant_monitoring_repository import DeviceMetricReading

        stale_reading = DeviceMetricReading(
            plant_id="p1", transformer_id="t1", transformer_code="aa12",
            device_id="d1", device_code="29044", metric="temperature",
            reading_ts=NOW - timedelta(days=2), value=41.0,
        )
        from repositories import plant_monitoring_repository as repo

        _stub_hierarchy(monkeypatch, plant=_PlantRecord("p1", "Itaipu"), transformers=[])
        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [stale_reading])

        result = build_plant_detail_view("p1", NOW, scope=UNRESTRICTED)
        attribution = result["attribution"]
        assert attribution.has_data is True
        assert attribution.value == 41.0
        assert attribution.freshness is Freshness.STALE

    def test_missing_plant_record_does_not_crash_the_context(self, monkeypatch):
        """get_plant_or_none can return None (e.g. a race with deletion) -
        context fields fall back to None rather than raising."""
        from repositories import plant_monitoring_repository as repo

        _stub_hierarchy(monkeypatch, plant=None, transformers=[])
        monkeypatch.setattr(repo, "latest_reading_times", lambda metrics, *, allowed_device_ids=None, include_inactive=False: [])
        monkeypatch.setattr(repo, "latest_metric_readings", lambda metric, **kw: [])

        result = build_plant_detail_view("p1", NOW, scope=UNRESTRICTED)
        assert result["context_fields"][0] == ("Country", None)


class TestPlantPageLayout:
    def test_uses_the_monitoring_width_class(self):
        from pages import plant_detail

        assert "page--monitoring" in plant_detail.layout("Plant").className

    def test_contains_the_new_container_ids(self):
        from pages import plant_detail

        layout = plant_detail.layout("Plant")
        for container_id in ("plant-context", "plant-metric-health", "plant-attribution"):
            assert find_by_id(layout, container_id) is not None, container_id

    def test_new_containers_start_empty(self):
        """Nothing renders until the callback fires."""
        from pages import plant_detail

        layout = plant_detail.layout("Plant")
        for container_id in ("plant-context", "plant-metric-health", "plant-attribution"):
            node = find_by_id(layout, container_id)
            assert getattr(node, "children", None) is None
