"""Needs Attention panel — correctness of exception list rows.

Pin the contract that:
- only NO_DATA / STALE plants appear
- FRESH plants are excluded
- NO_DATA sorts above STALE
- empty state shows the truthful "No current data-freshness exceptions."
- links point at stable /plants/<plant_id> routes
- the panel does not touch PLANT_COLUMNS or the fleet table behaviour
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from callbacks.listings import (
    build_needs_attention_rows,
    sort_needs_attention_rows,
)
from components.needs_attention import needs_attention
from services.monitoring_service import (
    Freshness,
    fleet_health_from_rows,
    severity_rank,
)
from tests.dash_tree import find_by_class, links, text_of

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
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
    return type("R", (), {
        "plant_id": plant, "device_id": device,
        "metric": metric, "reading_ts": ts,
    })()


def _health(pairs):
    """FleetHealth from (plant, device, ts) triples, one metric each."""
    return fleet_health_from_rows(
        [_row(p, d, "temperature", ts) for p, d, ts in pairs], now=NOW
    )


class TestSortNeedsAttentionRows:
    def test_no_data_sorts_above_stale(self):
        rows = [
            {"_severity": 1, "entity": "Zzz Stale", "_state": "stale"},
            {"_severity": 2, "entity": "Aaa NoData", "_state": "no_data"},
            {"_severity": 0, "entity": "Mmm Fresh", "_state": "fresh"},
        ]
        ordered = sort_needs_attention_rows(rows)
        # FRESH is excluded by the builder, but the sort handles it too
        assert [r["entity"] for r in ordered] == [
            "Aaa NoData", "Zzz Stale", "Mmm Fresh"
        ]

    def test_ties_fall_back_to_entity_name(self):
        rows = [
            {"_severity": 2, "entity": "Zzz", "_state": "no_data"},
            {"_severity": 2, "entity": "Aaa", "_state": "no_data"},
        ]
        ordered = sort_needs_attention_rows(rows)
        assert [r["entity"] for r in ordered] == ["Aaa", "Zzz"]

    def test_ordering_does_not_drop_or_duplicate_rows(self):
        rows = [
            {"_severity": 1, "entity": "A", "_state": "stale"},
            {"_severity": 2, "entity": "B", "_state": "no_data"},
        ]
        ordered = sort_needs_attention_rows(rows)
        assert sorted(r["entity"] for r in ordered) == ["A", "B"]


class TestBuildNeedsAttentionRows:
    def test_fresh_plants_are_excluded(self):
        health = _health([("p1", "d1", FRESH_TS), ("p2", "d2", FRESH_TS)])
        plants = [_Plant("p1", "Aaa"), _Plant("p2", "Zzz")]
        rows = build_needs_attention_rows(plants, health, NOW)
        assert rows == []

    def test_stale_plant_appears(self):
        health = _health([("p1", "d1", FRESH_TS), ("p2", "d2", STALE_TS)])
        plants = [_Plant("p1", "Aaa"), _Plant("p2", "Zzz")]
        rows = build_needs_attention_rows(plants, health, NOW)
        assert len(rows) == 1
        assert rows[0]["entity"] == "Zzz"
        assert rows[0]["_state"] == "stale"

    def test_no_data_plant_appears(self):
        health = _health([("p1", "d1", None)])
        plants = [_Plant("p1", "Aaa")]
        rows = build_needs_attention_rows(plants, health, NOW)
        assert len(rows) == 1
        assert rows[0]["entity"] == "Aaa"
        assert rows[0]["_state"] == "no_data"

    def test_plant_absent_from_health_is_no_data(self):
        """A plant with no rows is NO_DATA, not missing."""
        health = _health([("p1", "d1", FRESH_TS)])
        plants = [_Plant("p1", "Fresh"), _Plant("p9", "Ghost")]
        rows = build_needs_attention_rows(plants, health, NOW)
        assert len(rows) == 1
        assert rows[0]["entity"] == "Ghost"
        assert rows[0]["_state"] == "no_data"

    def test_exception_first_ordering(self):
        health = _health([
            ("p_fresh", "d1", FRESH_TS),
            ("p_stale", "d2", STALE_TS),
            ("p_none", "d3", None),
        ])
        plants = [
            _Plant("p_fresh", "Aaa"),
            _Plant("p_stale", "Zzz"),
            _Plant("p_none", "Mmm"),
        ]
        rows = build_needs_attention_rows(plants, health, NOW)
        states = [r["_state"] for r in rows]
        assert states == ["no_data", "stale"]

    def test_row_carries_entity_id_and_href(self):
        health = _health([("p1", "d1", STALE_TS)])
        plants = [_Plant("p1", "Itaipu")]
        rows = build_needs_attention_rows(plants, health, NOW)
        assert rows[0]["id"] == "p1"
        assert rows[0]["href"] == "/plants/p1"

    def test_row_type_is_plant(self):
        health = _health([("p1", "d1", STALE_TS)])
        plants = [_Plant("p1", "Itaipu")]
        rows = build_needs_attention_rows(plants, health, NOW)
        assert rows[0]["type"] == "Plant"

    def test_last_update_contains_ago_for_stale(self):
        health = _health([("p1", "d1", STALE_TS)])
        plants = [_Plant("p1", "Itaipu")]
        rows = build_needs_attention_rows(plants, health, NOW)
        assert "ago" in rows[0]["last_update"]

    def test_last_update_is_no_readings_for_no_data(self):
        """A plant with all-None reading_ts has no last update."""
        health = _health([("p1", "d1", None)])
        plants = [_Plant("p1", "Itaipu")]
        rows = build_needs_attention_rows(plants, health, NOW)
        assert "No readings" in rows[0]["last_update"]


class TestNeedsAttentionComponent:
    def _rows(self):
        return [
            {
                "id": "p1", "entity": "Itaipu", "type": "Plant",
                "issue": "No data · 0 of 2 devices", "last_update": "No readings",
                "href": "/plants/p1", "_state": "no_data", "_severity": 2,
            },
            {
                "id": "p2", "entity": "Three Gorges", "type": "Plant",
                "issue": "Stale · 1 of 3 devices",
                "last_update": "2h 17m ago · 18 Aug 2026 09:43 UTC",
                "href": "/plants/p2", "_state": "stale", "_severity": 1,
            },
        ]

    def test_renders_heading(self):
        panel = needs_attention(self._rows())
        titles = [text_of(n) for n in find_by_class(panel, "needs-attention__title")]
        assert titles == ["Needs attention"]

    def test_renders_rows_in_order(self):
        panel = needs_attention(self._rows())
        entities = [
            text_of(n) for n in find_by_class(panel, "needs-attention__entity")
        ]
        assert entities == ["Itaipu", "Three Gorges"]

    def test_each_row_has_a_link_to_plant_route(self):
        panel = needs_attention(self._rows())
        plant_links = [
            (label, href) for label, href in links(panel) if "/plants/" in href
        ]
        assert len(plant_links) == 2
        assert plant_links[0] == ("Open", "/plants/p1")
        assert plant_links[1] == ("Open", "/plants/p2")

    def test_discloses_the_actual_affected_total(self):
        panel = needs_attention(self._rows())
        assert "2 affected plants" in text_of(panel)

    def test_large_population_renders_only_representative_subset(self):
        rows = [
            {
                "id": f"p{i}", "entity": f"Plant {i}", "type": "Plant",
                "issue": "Stale · 1 of 1 devices", "last_update": "2h ago",
                "href": f"/plants/p{i}", "_state": "stale", "_severity": 1,
            }
            for i in range(30)
        ]
        panel = needs_attention(rows)
        assert len(find_by_class(panel, "needs-attention__row")) == 5
        assert "Showing 5 of 30 affected plants" in text_of(panel)
        assert ("View full fleet", "#fleet-plants") in links(panel)

    def test_empty_state_message(self):
        panel = needs_attention([])
        assert "No current data-freshness exceptions." in text_of(panel)

    def test_empty_panel_has_heading(self):
        panel = needs_attention([])
        titles = [text_of(n) for n in find_by_class(panel, "needs-attention__title")]
        assert titles == ["Needs attention"]

    def test_no_fresh_rows_in_exception_list(self):
        """Only NO_DATA and STALE plants appear; FRESH is excluded by the
        builder, and the component does not invent rows."""
        panel = needs_attention([])
        rows = find_by_class(panel, "needs-attention__row")
        assert rows == []


class TestNoRegressionToOverviewTable:
    def test_plant_columns_unchanged(self):
        """PLANT_COLUMNS is still the same set of ids as before Phase 2."""
        from callbacks.listings import PLANT_COLUMNS
        assert [c["id"] for c in PLANT_COLUMNS] == [
            "plant", "country", "fuel", "capacity_mw",
            "transformers", "devices", "freshness",
        ]

    def test_build_plant_rows_unaffected(self):
        """build_plant_rows still works and ignores the needs attention rows."""
        from callbacks.listings import build_plant_rows
        health = _health([
            ("p_fresh", "d1", FRESH_TS), ("p_stale", "d2", STALE_TS),
        ])
        plants = [_Plant("p_fresh", "Aaa"), _Plant("p_stale", "Zzz")]
        rows = build_plant_rows(plants, {"p_fresh": (1, 1), "p_stale": (1, 1)}, health)
        assert len(rows) == 2
        assert {r["plant"] for r in rows} == {"Aaa", "Zzz"}


class TestPlantLastUpdated:
    def test_plant_last_updated_populated(self):
        """FleetHealth carries per-plant latest reading timestamps."""
        health = _health([
            ("p1", "d1", FRESH_TS),
            ("p1", "d2", STALE_TS),
            ("p2", "d3", None),
        ])
        assert "p1" in health.plant_last_updated
        # FRESH_TS (10 min ago) is newer than STALE_TS (2 days ago)
        assert health.plant_last_updated["p1"] == FRESH_TS
        # p2 has all-None rows, so plant_last_updated has no entry
        assert health.plant_last_updated.get("p2") is None

    def test_plant_with_mixed_timestamps_keeps_latest(self):
        t1 = NOW - timedelta(hours=1)
        t2 = NOW - timedelta(hours=5)
        health = _health([
            ("p1", "d1", t1),
            ("p1", "d2", t2),
        ])
        assert health.plant_last_updated["p1"] == t1
