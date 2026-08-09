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
    sort_device_rows_exception_first,
)
from components.fleet_summary import transformer_kpi_cards
from services.monitoring_service import Freshness, fleet_health_from_rows
from tests.dash_tree import find_by_class, text_of

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
        assert values == ["2", "1 fresh"]
        assert secondary[1] == "1 stale"

    def test_unknown_transformer_is_not_reported_as_healthy(self):
        cards = transformer_kpi_cards("nope", devices=0, health=self._health())
        secondary = [text_of(el) for el in find_by_class(cards, "kpi-card__secondary")]
        assert secondary[1] == "No devices reporting"


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
