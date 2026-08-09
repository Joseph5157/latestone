"""Fleet Overview consumption of the freshness chain.

The Fleet screen shows two things that must never disagree: the Data Health card
counts devices, and the plant table labels each plant's rollup. Both are derived
from a single FleetHealth built from a single query — these tests exist mainly to
keep it that way, because two independent freshness computations would look
correct on the seeded data and diverge only once real feeds start failing.
"""
from __future__ import annotations

import pathlib
import re
from datetime import datetime, timedelta, timezone

from callbacks.listings import (
    PLANT_COLUMNS,
    build_plant_rows,
    sort_plant_rows_exception_first,
)
from components.fleet_summary import fleet_health_summary, fleet_kpi_cards
from services.monitoring_service import (
    Freshness,
    FreshnessRollup,
    fleet_health_from_rows,
)
from tests.dash_tree import find_by_class, text_of

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


class TestPlantRowFreshness:
    def test_row_carries_the_plants_rollup_label(self):
        health = _health([("p1", "d1", FRESH_TS), ("p1", "d2", STALE_TS)])
        rows = build_plant_rows([_Plant("p1", "Itaipu")], {"p1": (1, 2)}, health)
        assert rows[0]["freshness"] == "Stale · 1 of 2 devices"

    def test_all_fresh_plant_reads_as_a_bare_state(self):
        health = _health([("p1", "d1", FRESH_TS)])
        rows = build_plant_rows([_Plant("p1", "Itaipu")], {"p1": (1, 1)}, health)
        assert rows[0]["freshness"] == "Fresh"

    def test_plant_absent_from_health_is_no_data_not_blank(self):
        """A plant the freshness query returned nothing for has no evidence of
        health; a blank cell would read as 'fine'."""
        rows = build_plant_rows([_Plant("p9", "Ghost")], {"p9": (0, 0)}, _health([]))
        assert rows[0]["freshness"] == "No data · 0 of 0 devices"

    def test_freshness_is_a_declared_column(self):
        assert any(c["id"] == "freshness" for c in PLANT_COLUMNS)

    def test_row_identity_still_drives_navigation(self):
        """Adding a column must not disturb the row_id contract (§11)."""
        health = _health([("p1", "d1", FRESH_TS)])
        rows = build_plant_rows([_Plant("p1", "Itaipu")], {"p1": (1, 1)}, health)
        assert rows[0]["id"] == "p1"


class TestExceptionFirstOrdering:
    def _rows(self):
        health = _health([
            ("p_fresh", "d1", FRESH_TS),
            ("p_stale", "d2", STALE_TS),
            ("p_none", "d3", None),
        ])
        plants = [
            _Plant("p_fresh", "Aaa Fresh"),
            _Plant("p_stale", "Zzz Stale"),
            _Plant("p_none", "Mmm Nodata"),
        ]
        counts = {"p_fresh": (1, 1), "p_stale": (1, 1), "p_none": (1, 1)}
        return build_plant_rows(plants, counts, health)

    def test_no_data_sorts_above_stale_above_fresh(self):
        ordered = sort_plant_rows_exception_first(self._rows())
        assert [r["id"] for r in ordered] == ["p_none", "p_stale", "p_fresh"]

    def test_ties_fall_back_to_plant_name(self):
        health = _health([("p1", "d1", FRESH_TS), ("p2", "d2", FRESH_TS)])
        rows = build_plant_rows(
            [_Plant("p2", "Zzz"), _Plant("p1", "Aaa")],
            {"p1": (1, 1), "p2": (1, 1)},
            health,
        )
        assert [r["plant"] for r in sort_plant_rows_exception_first(rows)] == ["Aaa", "Zzz"]

    def test_ordering_does_not_drop_or_duplicate_rows(self):
        rows = self._rows()
        assert sorted(r["id"] for r in sort_plant_rows_exception_first(rows)) == sorted(
            r["id"] for r in rows
        )

    def test_severity_key_is_not_rendered_as_a_column(self):
        """The sort key lives on the row like `id` does, never as a visible column."""
        rows = self._rows()
        assert "_severity" in rows[0]
        assert not any(c["id"] == "_severity" for c in PLANT_COLUMNS)


class TestFleetHealthSummary:
    def test_counts_devices_by_state(self):
        health = _health(
            [("p1", f"d{i}", FRESH_TS) for i in range(118)]
            + [("p2", "x1", STALE_TS), ("p2", "x2", STALE_TS)]
        )
        value, secondary = fleet_health_summary(health)
        assert value == "118 fresh"
        assert secondary == "2 stale"

    def test_both_exception_states_are_carried(self):
        health = _health([
            ("p1", "d1", FRESH_TS), ("p2", "d2", STALE_TS), ("p3", "d3", None),
        ])
        value, secondary = fleet_health_summary(health)
        assert value == "1 fresh"
        assert secondary == "1 stale · 1 no data"

    def test_a_fully_healthy_fleet_says_so_without_inventing_a_judgement(self):
        health = _health([("p1", "d1", FRESH_TS), ("p1", "d2", FRESH_TS)])
        value, secondary = fleet_health_summary(health)
        assert value == "2 fresh"
        assert secondary == "No stale or missing feeds"

    def test_empty_fleet_is_not_reported_as_healthy(self):
        value, secondary = fleet_health_summary(_health([]))
        assert value == "0 fresh"
        assert secondary == "No devices reporting"


class TestFleetKpiCards:
    def _cards(self):
        health = _health([("p1", "d1", FRESH_TS), ("p1", "d2", STALE_TS)])
        return fleet_kpi_cards(plants=30, transformers=71, devices=120, health=health)

    def test_renders_the_four_required_cards(self):
        labels = [text_of(el) for el in find_by_class(self._cards(), "kpi-card__label")]
        assert labels == ["Plants", "Transformers", "Devices", "Data Health"]

    def test_hierarchy_totals_come_from_the_counts_not_the_health_rows(self):
        """Devices shows every active device, including any the freshness query
        has no row for — the two must not be silently conflated."""
        values = [text_of(el) for el in find_by_class(self._cards(), "kpi-card__value")]
        assert values[:3] == ["30", "71", "120"]

    def test_data_health_card_reports_the_rollup(self):
        values = [text_of(el) for el in find_by_class(self._cards(), "kpi-card__value")]
        assert values[3] == "1 fresh"


class TestSingleSourceOfFreshness:
    """The constraint that keeps one definition of freshness in the UI."""

    def test_overview_issues_exactly_one_freshness_query(self, monkeypatch):
        from repositories import plant_monitoring_repository as repo
        from services import monitoring_service

        calls = []
        monkeypatch.setattr(
            repo, "latest_reading_times",
            lambda metrics, include_inactive=False: calls.append(metrics) or [],
        )
        monitoring_service.get_fleet_health()
        assert len(calls) == 1

    def test_fleet_health_query_covers_every_configured_metric(self, monkeypatch):
        """A device is only FRESH if all its metrics are; querying a subset
        would report a device fresh on the strength of one working feed."""
        from config.metrics import ordered_metrics
        from repositories import plant_monitoring_repository as repo
        from services import monitoring_service

        captured = {}
        monkeypatch.setattr(
            repo, "latest_reading_times",
            lambda metrics, include_inactive=False: captured.update(m=metrics) or [],
        )
        monitoring_service.get_fleet_health()
        assert captured["m"] == [m.key for m in ordered_metrics()]

    def test_card_and_table_agree_on_every_plant(self):
        """Derived from one object, so the card's stale count must equal the
        number of stale devices implied by the table's plant labels."""
        health = _health([
            ("p1", "d1", FRESH_TS), ("p1", "d2", STALE_TS), ("p2", "d3", STALE_TS),
        ])
        rows = build_plant_rows(
            [_Plant("p1", "One"), _Plant("p2", "Two")],
            {"p1": (1, 2), "p2": (1, 1)},
            health,
        )
        _value, secondary = fleet_health_summary(health)
        assert secondary == "2 stale"
        assert [r["freshness"] for r in rows] == [
            "Stale · 1 of 2 devices", "Stale · 1 of 1 devices",
        ]


class TestTableOverflow:
    """OBS-2 from the device acceptance pass: dash_table's default is
    `text-overflow: clip`, so a name wider than its column disappears with no
    indication anything was cut. Nothing in the current dataset hits it, which
    is exactly why it needs an assertion rather than an eyeball."""

    def test_identity_column_wraps_rather_than_truncating(self):
        """A plant name is the row's identity and the thing you click. Half of
        'Itaipu Binacional Dam (Paraguay part)' is not an identity."""
        from components.entity_table import entity_table
        from tests.dash_tree import walk

        table = next(
            n for n in walk(entity_table("t", [{"name": "P", "id": "plant"}], [],
                                         link_column_id="plant"))
            if getattr(n, "style_cell_conditional", None)
        )
        rule = next(
            r for r in table.style_cell_conditional
            if r["if"].get("column_id") == "plant"
        )
        assert rule["whiteSpace"] == "normal"
        assert rule["overflowWrap"] == "anywhere"

    def test_other_columns_show_an_ellipsis_instead_of_clipping(self):
        """Asserted on `style_cell`, which lands on the `td`.

        An earlier version of this test matched the rule in app.css and passed
        while the browser still computed `text-overflow: clip`: dash_table sets
        `text-overflow: inherit` on `td div.dash-cell-value` with four classes,
        which outranks anything this app's stylesheet can say about that div.
        A stylesheet-source assertion cannot see a lost cascade — the same way
        DEF-1's `:where()` focus ring was present in the CSS and absent on
        screen.
        """
        from components.entity_table import entity_table
        from tests.dash_tree import walk

        table = next(
            n for n in walk(entity_table("t", [{"name": "P", "id": "plant"}], []))
            if getattr(n, "style_cell", None)
        )
        assert table.style_cell["textOverflow"] == "ellipsis"
        assert table.style_cell["overflow"] == "hidden"

    def test_stylesheet_does_not_re_add_the_rule_that_cannot_win(self):
        """Putting it back in app.css would look like a fix and change nothing."""
        assert not re.search(
            r"\.entity-table-wrapper[^{]*\.dash-cell-value\s*\{[^}]*text-overflow",
            CSS_TEXT, re.S,
        )


class TestRollupLabelNounAgreement:
    def test_plant_level_counts_devices_not_metrics(self):
        rollup = FreshnessRollup(S, {F: 7, S: 1}, 8)
        assert rollup.label("devices").endswith("devices")
        assert "metrics" not in rollup.label("devices")
