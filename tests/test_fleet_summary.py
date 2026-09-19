"""KPI-card presentation of the freshness chain (plant / transformer pages).

What remains of the old Fleet Overview's tests after SWITCH-OVER-1: the
shared summary block, the health wording, and the injected-instant contract
of `get_fleet_health`.
"""
from __future__ import annotations

import pathlib
import re
from datetime import datetime, timedelta, timezone

from components.fleet_summary import entity_summary_block
from services.device_scope import UNRESTRICTED
from services.monitoring_service import (
    Freshness,
    FreshnessRollup,
    fleet_health_from_rows,
    severity_rank,
)
from tests.dash_tree import find_by_class, find_by_exact_class, text_of

CSS_TEXT = (
    pathlib.Path(__file__).resolve().parent.parent / "assets" / "app.css"
).read_text(encoding="utf-8")

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
FRESH_TS = NOW - timedelta(minutes=10)
STALE_TS = NOW - timedelta(days=2)

F, S, N = Freshness.FRESH, Freshness.STALE, Freshness.NO_DATA


class _Plant:
    def __init__(self, plant_id, name, country="Chile", fuel="Hydro", capacity=100.0):
        self.plant_id = plant_id
        self.name = name
        self.country = country
        self.primary_fuel = fuel
        self.capacity_mw = capacity


def _row(plant, device, metric, ts):
    return type("R", (), {"plant_id": plant, "device_id": device,
                          "metric": metric, "reading_ts": ts})()


def _health(pairs):
    """FleetHealth from (plant, device, ts) triples, one metric each."""
    return fleet_health_from_rows(
        [_row(p, d, "temperature", ts) for p, d, ts in pairs], now=NOW
    )


class TestEntitySummaryBlockContract:
    """`entity_summary_block` is what Fleet, Plant and Transformer cards now
    share. These pin its own contract directly, independent of any one
    page's wrapper."""

    def test_wrapper_keeps_the_frozen_kpi_row_class(self):
        block = entity_summary_block(counts=[("Devices", 5)], health_counts={})
        assert block.className == "kpi-row kpi-row--fleet"

    def test_count_cards_render_in_the_given_order_before_data_health(self):
        block = entity_summary_block(
            counts=[("Plants", 30), ("Transformers", 71), ("Devices", 120)],
            health_counts={Freshness.FRESH: 1},
        )
        labels = [text_of(el) for el in find_by_class(block, "kpi-card__label")]
        assert labels == ["Plants", "Transformers", "Devices", "Data Health"]

    def test_a_single_count_card_still_composes_correctly(self):
        """The transformer page's shape: one count card, then Data Health."""
        block = entity_summary_block(counts=[("Devices", 2)], health_counts={})
        labels = [text_of(el) for el in find_by_class(block, "kpi-card__label")]
        assert labels == ["Devices", "Data Health"]

    def test_data_health_card_is_never_accented(self):
        """Locks the "no accent" rule the three call sites used to repeat."""
        block = entity_summary_block(counts=[], health_counts={Freshness.FRESH: 1})
        [health_card] = find_by_exact_class(block, "kpi-card")
        assert "kpi-card--accent" not in health_card.className



class TestRollupLabelNounAgreement:
    def test_plant_level_counts_devices_not_metrics(self):
        rollup = FreshnessRollup(S, {F: 7, S: 1}, 8)
        assert rollup.label("devices").endswith("devices")
        assert "metrics" not in rollup.label("devices")


from components.fleet_summary import _health_summary


def test_health_summary_leads_with_stale_when_nothing_is_fresh():
    value, secondary = _health_summary({Freshness.FRESH: 0, Freshness.STALE: 120})
    assert value == "120 stale"
    assert secondary == "0 fresh"


def test_health_summary_leads_with_no_data_over_stale():
    """NO_DATA outranks STALE, the same worst-of order as aggregation.

    Guards the whole point of the change: the lead is derived from severity,
    never hardcoded to stale because stale is the common case today.
    """
    value, secondary = _health_summary(
        {Freshness.FRESH: 102, Freshness.STALE: 15, Freshness.NO_DATA: 3}
    )
    assert value == "3 no data"
    assert secondary == "102 fresh · 15 stale"


def test_health_summary_leads_with_health_when_all_fresh():
    value, secondary = _health_summary({Freshness.FRESH: 120})
    assert value == "120 fresh"
    assert secondary == "No stale or missing feeds"


def test_health_summary_omits_zero_exception_states():
    value, secondary = _health_summary(
        {Freshness.FRESH: 100, Freshness.STALE: 0, Freshness.NO_DATA: 20}
    )
    assert value == "20 no data"
    assert secondary == "100 fresh"


def test_health_summary_on_an_empty_population_does_not_read_as_healthy():
    """Zero devices is not zero problems.

    The wording is specified in the spec rather than read off the
    implementation, so this test asserts an intended sentence.
    """
    assert _health_summary({}) == ("No active devices", "No data available")


def test_get_fleet_health_accepts_an_injected_instant(monkeypatch):
    """The header stamp and the rows' freshness must share one instant.

    Without the pass-through, get_fleet_health called the clock itself, so the
    header could stamp T while the rows were evaluated at T minus a few
    hundred milliseconds. Asserting an injected value proves one instant is
    used, which comparing two generated times for proximity never could.
    """
    import services.monitoring_service as ms

    seen = {}
    # Captured before patching: `fake_from_rows` below replaces
    # `ms.fleet_health_from_rows`, so calling that name from inside the fake
    # would call the fake itself and recurse forever.
    real_from_rows = ms.fleet_health_from_rows

    def fake_from_rows(rows, now=None):
        seen["now"] = now
        return real_from_rows(rows, now)

    monkeypatch.setattr(
        ms.repo, "latest_reading_times",
        lambda keys, *, allowed_device_ids=None, include_inactive=False: [],
    )
    monkeypatch.setattr(ms, "fleet_health_from_rows", fake_from_rows)

    frozen = datetime(2026, 8, 9, 11, 24, tzinfo=timezone.utc)
    ms.get_fleet_health(now=frozen, scope=UNRESTRICTED)
    assert seen["now"] == frozen


