"""Plant screen: "within this plant, which transformer needs attention?"

Reuses the Fleet patterns rather than inventing new ones — same rollup chain,
same exception-first ordering, same one-object-per-render rule. The tests here
are mostly about that reuse being real and not a parallel implementation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from callbacks.listings import (
    TRANSFORMER_COLUMNS,
    build_transformer_rows,
    sort_transformer_rows_exception_first,
)
from components.fleet_summary import plant_kpi_cards
from services.monitoring_service import Freshness, fleet_health_from_rows
from tests.dash_tree import find_by_class, text_of

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
