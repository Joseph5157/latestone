"""The metric -> device -> plant -> fleet freshness chain.

Spec section 21 defines this as worst-of with affected counts at every level.
The rule exists to stop a single dead feed disappearing behind healthy siblings,
so the tests are mostly about the aggregate *not* being reassuring.

Freshness is data-delivery only. Nothing here becomes an electrical warning.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.monitoring_service import (
    Freshness,
    FreshnessRollup,
    aggregate_freshness,
    fleet_health_from_rows,
)

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
FRESH_TS = NOW - timedelta(minutes=10)
STALE_TS = NOW - timedelta(days=2)

F, S, N = Freshness.FRESH, Freshness.STALE, Freshness.NO_DATA


class TestAggregateWorstOf:
    def test_all_fresh_is_fresh(self):
        r = aggregate_freshness([F, F, F])
        assert r.state is F
        assert r.affected == 0
        assert r.total == 3

    def test_one_stale_among_seven_fresh_is_stale(self):
        """The headline case: 7 fresh + 1 stale must not read as Fresh."""
        r = aggregate_freshness([F] * 7 + [S])
        assert r.state is S
        assert r.affected == 1
        assert r.total == 8

    def test_no_data_outranks_stale(self):
        r = aggregate_freshness([F, S, N])
        assert r.state is N
        assert r.affected == 1

    def test_counts_are_kept_for_every_state(self):
        """Both counts survive so supporting text can explain a mixed rollup."""
        r = aggregate_freshness([F, F, S, S, S, N])
        assert r.state is N
        assert r.counts[S] == 3
        assert r.counts[F] == 2
        assert r.counts[N] == 1

    def test_empty_is_no_data_not_fresh(self):
        """A plant with nothing under it has no evidence of health."""
        r = aggregate_freshness([])
        assert r.state is N
        assert r.total == 0

    def test_all_stale_reports_every_child_affected(self):
        r = aggregate_freshness([S, S])
        assert (r.state, r.affected, r.total) == (S, 2, 2)

    @pytest.mark.parametrize("states", [[F], [S], [N]])
    def test_single_child_takes_its_own_state(self, states):
        assert aggregate_freshness(states).state is states[0]


class TestRollupDisplay:
    def test_fresh_rollup_needs_no_qualifier(self):
        assert FreshnessRollup(F, {F: 8}, 8).label() == "Fresh"

    def test_non_fresh_rollup_carries_the_affected_count(self):
        assert FreshnessRollup(S, {F: 7, S: 1}, 8).label("metrics") == "Stale · 1 of 8 metrics"

    def test_no_data_rollup_labels_itself(self):
        assert FreshnessRollup(N, {N: 3}, 3).label("devices") == "No data · 3 of 3 devices"

    def test_label_without_a_noun_still_reads(self):
        assert FreshnessRollup(S, {S: 2}, 5).label() == "Stale · 2 of 5"


class TestFleetHealthFromRows:
    """The whole chain, from what the repository actually returns."""

    def _row(self, plant, device, metric, ts):
        return type("R", (), {"plant_id": plant, "device_id": device,
                              "metric": metric, "reading_ts": ts})()

    def test_device_is_stale_when_any_metric_is_stale(self):
        rows = [
            self._row("p1", "d1", "temperature", FRESH_TS),
            self._row("p1", "d1", "voltage", STALE_TS),
        ]
        health = fleet_health_from_rows(rows, now=NOW)
        assert health.devices["d1"].state is S
        assert health.devices["d1"].affected == 1
        assert health.devices["d1"].total == 2

    def test_plant_is_worst_of_its_devices(self):
        rows = [
            self._row("p1", "d1", "temperature", FRESH_TS),
            self._row("p1", "d2", "temperature", STALE_TS),
            self._row("p1", "d3", "temperature", FRESH_TS),
        ]
        health = fleet_health_from_rows(rows, now=NOW)
        assert health.plants["p1"].state is S
        assert health.plants["p1"].affected == 1
        assert health.plants["p1"].total == 3

    def test_missing_reading_is_no_data(self):
        rows = [self._row("p1", "d1", "temperature", None)]
        health = fleet_health_from_rows(rows, now=NOW)
        assert health.devices["d1"].state is N

    def test_fleet_counts_devices_not_metrics(self):
        """The Data Health card counts devices; a device has 8 metrics."""
        rows = [
            self._row("p1", "d1", "temperature", FRESH_TS),
            self._row("p1", "d1", "voltage", FRESH_TS),
            self._row("p1", "d2", "temperature", STALE_TS),
        ]
        health = fleet_health_from_rows(rows, now=NOW)
        assert health.device_count == 2
        assert health.counts[F] == 1
        assert health.counts[S] == 1

    def test_plant_count_reflects_plants_present(self):
        rows = [
            self._row("p1", "d1", "temperature", FRESH_TS),
            self._row("p2", "d2", "temperature", FRESH_TS),
        ]
        health = fleet_health_from_rows(rows, now=NOW)
        assert health.plant_count == 2

    def test_one_dead_device_is_visible_in_a_healthy_fleet(self):
        """30 healthy devices must not bury the one that stopped reporting."""
        rows = [self._row("p1", f"d{i}", "temperature", FRESH_TS) for i in range(30)]
        rows.append(self._row("p2", "dead", "temperature", None))
        health = fleet_health_from_rows(rows, now=NOW)
        assert health.counts[N] == 1
        assert health.plants["p2"].state is N

    def test_empty_input_is_safe(self):
        health = fleet_health_from_rows([], now=NOW)
        assert health.device_count == 0
        assert health.plant_count == 0
        assert health.counts[F] == 0


class TestOldestMetricTimestamp:
    """`device_oldest_metric_updated` — the honest basis for a STALE age.

    ADR-009 D3. `device_last_updated` is a MAX and therefore describes
    whichever metric IS still reporting; ranking or ageing a stale device on
    it understates the outage. This field is the MIN, and it exists only
    when every metric of that device carries a timestamp — so a NO_DATA
    device holds None and no caller can manufacture a duration from it.
    """

    def _row(self, plant, device, metric, ts):
        return type("R", (), {"plant_id": plant, "device_id": device,
                              "metric": metric, "reading_ts": ts})()

    def test_it_is_the_oldest_metric_not_the_newest(self):
        rows = [
            self._row("p1", "d1", "temperature", FRESH_TS),
            self._row("p1", "d1", "voltage", STALE_TS),
        ]
        health = fleet_health_from_rows(rows, now=NOW)
        assert health.device_oldest_metric_updated["d1"] == STALE_TS
        # The existing field still answers its own question, unchanged.
        assert health.device_last_updated["d1"] == FRESH_TS

    def test_the_mixed_device_is_where_max_would_have_lied(self):
        """7 fresh + 1 stale: the case a max-based age gets wrong.

        The device is STALE, and the number an operator needs is the age of
        the feed that stopped — not the age of the seven that did not.
        """
        rows = [self._row("p1", "d1", f"m{i}", FRESH_TS) for i in range(7)]
        rows.append(self._row("p1", "d1", "voltage", STALE_TS))
        health = fleet_health_from_rows(rows, now=NOW)
        assert health.devices["d1"].state is S
        assert health.device_oldest_metric_updated["d1"] == STALE_TS

    def test_a_no_data_device_has_no_oldest_timestamp(self):
        """The guard is structural, not a convention callers must remember."""
        rows = [
            self._row("p1", "d1", "temperature", FRESH_TS),
            self._row("p1", "d1", "voltage", None),
        ]
        health = fleet_health_from_rows(rows, now=NOW)
        assert health.devices["d1"].state is N
        assert health.device_oldest_metric_updated["d1"] is None

    def test_a_never_reported_device_has_no_oldest_timestamp(self):
        rows = [self._row("p1", "d1", "temperature", None)]
        health = fleet_health_from_rows(rows, now=NOW)
        assert health.device_oldest_metric_updated["d1"] is None

    def test_a_fully_fresh_device_still_gets_one(self):
        """The field is about timestamp completeness, not about being stale."""
        rows = [
            self._row("p1", "d1", "temperature", FRESH_TS),
            self._row("p1", "d1", "voltage", FRESH_TS),
        ]
        health = fleet_health_from_rows(rows, now=NOW)
        assert health.device_oldest_metric_updated["d1"] == FRESH_TS
