"""Phase 7 - Affected Locations ranking (service side).

Reuses the row/plant helpers from the facade's own test module so both
files agree on what a LatestReadingRow and a PlantRecord look like.
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest

from services import command_center_service as svc
from services.device_scope import EMPTY, UNRESTRICTED, DeviceScope
from services.monitoring_service import fleet_health_from_rows
from tests.test_command_center_service import NOW, RECENT, _plant, _row

STALE_TS = NOW - timedelta(days=2)


def _compose(monkeypatch, rows, *, plants, scope=UNRESTRICTED):
    monkeypatch.setattr(
        svc, "get_fleet_health", lambda now, *, scope: fleet_health_from_rows(rows, NOW)
    )
    monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: [])
    monkeypatch.setattr(svc, "list_plants", lambda *, scope: list(plants))
    # Phase 8: with no explicit selection the facade falls back to the
    # worst affected plant, which reaches the transformer label lookup.
    monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
    # Phase 10: the priority ranking labels the attention population
    # through the same batched lookup (ADR-008/ADR-009).
    monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])
    return svc.get_command_center_snapshot(scope=scope)



def _noisy_event(event_id, device_id):
    """A DeviceEventRecord-shaped stub. Full shape so the Phase 9 projection
    runs for real - a partial stub would make these tests pass by never
    exercising the code path they are guarding against."""
    return SimpleNamespace(
        event_id=event_id,
        device_id=device_id,
        transformer_id="t1",
        reported_uid=None,
        event_type="power_down",
        severity=None,
        event_ts=NOW,
        temperature=None,
        battery_voltage=None,
        message=None,
        source="test",
        created_at=NOW,
    )

class TestAffectedComposition:
    """p1: 2 stale + 1 no-data = 3 affected of 4 monitored.
    p2: 1 stale = 1 affected of 2 monitored."""

    ROWS = [
        _row("d1", "temperature", STALE_TS, plant_id="p1", transformer_id="t1"),
        _row("d2", "temperature", STALE_TS, plant_id="p1", transformer_id="t1"),
        _row("d3", "temperature", None, plant_id="p1", transformer_id="t2"),
        _row("d4", "temperature", RECENT, plant_id="p1", transformer_id="t2"),
        _row("d5", "temperature", STALE_TS, plant_id="p2", transformer_id="t3"),
        _row("d6", "temperature", RECENT, plant_id="p2", transformer_id="t3"),
    ]
    PLANTS = [_plant("p1", "Durban"), _plant("p2", "Newcastle")]

    def _rows(self, monkeypatch, plants=None):
        snap = _compose(monkeypatch, self.ROWS, plants=plants if plants is not None else self.PLANTS)
        return snap.affected_locations

    def test_affected_is_stale_plus_no_data(self, monkeypatch):
        top = self._rows(monkeypatch)[0]
        assert (top.affected_rtls, top.stale_rtls, top.no_data_rtls) == (3, 2, 1)

    def test_composition_sums_to_the_affected_total(self, monkeypatch):
        for row in self._rows(monkeypatch):
            assert row.stale_rtls + row.no_data_rtls == row.affected_rtls

    def test_ranked_by_affected_count_descending(self, monkeypatch):
        assert [r.plant_id for r in self._rows(monkeypatch)] == ["p1", "p2"]

    def test_totals_and_percent_are_per_plant(self, monkeypatch):
        top = self._rows(monkeypatch)[0]
        assert top.total_monitored_rtls == 4
        assert top.affected_percent == pytest.approx(75.0)

    def test_plant_names_come_from_the_label_lookup(self, monkeypatch):
        assert self._rows(monkeypatch)[0].plant_name == "Durban"

    def test_a_plant_missing_a_name_keeps_its_id_rather_than_disappearing(self, monkeypatch):
        """ADR-008: FleetHealth is the authority on which plants are in
        scope. A labelling call must never shrink the population the
        numbers were computed over."""
        rows = self._rows(monkeypatch, plants=[_plant("p1", "Durban")])
        assert [r.plant_id for r in rows] == ["p1", "p2"]
        assert rows[1].plant_name == "p2"


class TestRankingRules:
    def test_a_fresh_only_plant_ranks_below_every_affected_plant(self, monkeypatch):
        """Name order alone would put the fresh plant first; affected count
        must dominate."""
        rows = [
            _row("d1", "temperature", RECENT, plant_id="healthy", transformer_id="t1"),
            _row("d2", "temperature", STALE_TS, plant_id="affected", transformer_id="t2"),
        ]
        snap = _compose(
            monkeypatch, rows,
            plants=[_plant("healthy", "AAA Fresh"), _plant("affected", "ZZZ Stale")],
        )
        assert [r.plant_id for r in snap.affected_locations] == ["affected", "healthy"]
        assert snap.affected_locations[-1].affected_rtls == 0

    def test_ties_break_on_plant_name_ascending(self, monkeypatch):
        """Equal affected counts. "Alpha" precedes "Zulu" by NAME - a
        plant_id tie-break would have ordered pa before pz instead."""
        rows = [
            _row("d1", "temperature", STALE_TS, plant_id="pz", transformer_id="t1"),
            _row("d2", "temperature", STALE_TS, plant_id="pa", transformer_id="t2"),
        ]
        snap = _compose(
            monkeypatch, rows, plants=[_plant("pz", "Alpha"), _plant("pa", "Zulu")]
        )
        assert [r.plant_name for r in snap.affected_locations] == ["Alpha", "Zulu"]

    def test_the_name_tie_break_ignores_case(self, monkeypatch):
        """Real fleet data ranked "GRAVELINES" above "Grand Coulee" under a
        raw ASCII sort, which puts every all-caps name in its own block and
        reads as a bug to anyone scanning alphabetically."""
        rows = [
            _row("d1", "temperature", STALE_TS, plant_id="p1", transformer_id="t1"),
            _row("d2", "temperature", STALE_TS, plant_id="p2", transformer_id="t2"),
        ]
        snap = _compose(
            monkeypatch, rows,
            plants=[_plant("p1", "GRAVELINES"), _plant("p2", "Grand Coulee")],
        )
        assert [r.plant_name for r in snap.affected_locations] == [
            "Grand Coulee",
            "GRAVELINES",
        ]

    def test_names_differing_only_by_case_still_order_deterministically(self, monkeypatch):
        """plant_id is the final key, so the result never depends on dict
        iteration order."""
        rows = [
            _row("d1", "temperature", STALE_TS, plant_id="pb", transformer_id="t1"),
            _row("d2", "temperature", STALE_TS, plant_id="pa", transformer_id="t2"),
        ]
        plants = [_plant("pb", "ALPHA"), _plant("pa", "alpha")]
        first = [r.plant_id for r in _compose(monkeypatch, rows, plants=plants).affected_locations]
        second = [r.plant_id for r in _compose(monkeypatch, rows, plants=plants).affected_locations]
        assert first == second == ["pa", "pb"]

    def test_ranking_is_stable_across_repeated_composition(self, monkeypatch):
        rows = [
            _row(f"d{i}", "temperature", STALE_TS, plant_id=f"p{i}", transformer_id=f"t{i}")
            for i in range(5)
        ]
        plants = [_plant(f"p{i}", f"Plant {i}") for i in range(5)]
        first = [r.plant_id for r in _compose(monkeypatch, rows, plants=plants).affected_locations]
        second = [r.plant_id for r in _compose(monkeypatch, rows, plants=plants).affected_locations]
        assert first == second

    def test_no_event_data_reaches_the_ranking(self, monkeypatch):
        """Events answer whether something HAPPENED; this panel answers
        whether data is current NOW. Mixing the two time semantics is what
        ADR-002 forbids - so the ranking must be byte-identical with and
        without a flood of events present."""
        rows = [
            _row("d1", "temperature", STALE_TS, plant_id="p1", transformer_id="t1"),
            _row("d2", "temperature", RECENT, plant_id="p2", transformer_id="t2"),
        ]
        monkeypatch.setattr(
            svc, "get_fleet_health", lambda now, *, scope: fleet_health_from_rows(rows, NOW)
        )
        monkeypatch.setattr(
            svc, "list_plants", lambda *, scope: [_plant("p1", "One"), _plant("p2", "Two")]
        )
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])

        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: [])
        without = [
            (r.plant_id, r.affected_rtls)
            for r in svc.get_command_center_snapshot(scope=UNRESTRICTED).affected_locations
        ]

        noisy = [_noisy_event(i, "d2") for i in range(50)]
        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: noisy)
        with_events = [
            (r.plant_id, r.affected_rtls)
            for r in svc.get_command_center_snapshot(scope=UNRESTRICTED).affected_locations
        ]

        assert without == with_events


class TestEdgeCases:
    def test_a_zero_affected_plant_is_present_with_zero_not_omitted(self, monkeypatch):
        """Kept in the model so the COMPONENT decides whether to show it.
        Dropping it in the service would remove that choice and make 'all
        healthy' indistinguishable from 'no plants in scope'."""
        rows = [_row("d1", "temperature", RECENT, plant_id="p1", transformer_id="t1")]
        snap = _compose(monkeypatch, rows, plants=[_plant("p1", "Calm")])
        assert len(snap.affected_locations) == 1
        assert snap.affected_locations[0].affected_rtls == 0
        assert snap.affected_locations[0].affected_percent == 0.0

    def test_an_all_fresh_fleet_reports_nothing_affected(self, monkeypatch):
        rows = [
            _row("d1", "temperature", RECENT, plant_id="p1", transformer_id="t1"),
            _row("d2", "temperature", RECENT, plant_id="p2", transformer_id="t2"),
        ]
        snap = _compose(monkeypatch, rows, plants=[_plant("p1", "A"), _plant("p2", "B")])
        assert snap.has_affected_locations is False
        assert all(r.affected_rtls == 0 for r in snap.affected_locations)

    def test_an_empty_fleet_has_no_location_rows(self, monkeypatch):
        snap = _compose(monkeypatch, [], plants=[], scope=EMPTY)
        assert snap.affected_locations == ()
        assert snap.has_affected_locations is False

    def test_scope_is_passed_to_the_label_lookup(self, monkeypatch):
        """The label call is scoped like every other read, or an
        out-of-scope plant name could surface (ADR-004)."""
        captured = {}
        monkeypatch.setattr(
            svc, "get_fleet_health", lambda now, *, scope: fleet_health_from_rows([], NOW)
        )
        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: [])

        def _fake_plants(*, scope):
            captured["scope"] = scope
            return []

        monkeypatch.setattr(svc, "list_plants", _fake_plants)
        scope = DeviceScope(device_ids=frozenset({"d1"}))
        svc.get_command_center_snapshot(scope=scope)
        assert captured["scope"] is scope


class TestNoNewQueryForRanking:
    def test_the_facade_calls_each_approved_read_path_once(self, monkeypatch):
        """ADR-008 keeps the entry-point set small and closed. Ranking is
        composed from the FleetHealth already fetched - pushing an ORDER BY
        into SQL would be a second definition of "affected", free to
        disagree with the one Fleet Overview shares.

        The transformer lookup counts once because Phase 8 resolves a
        default selection (the worst affected plant) when none is given. It
        is called for that ONE plant, never per row - which is the property
        worth pinning here.
        """
        calls = {
            "fleet_health": 0, "events": 0, "plants": 0,
            "transformers": 0, "device_paths": 0,
        }

        def _fh(now, *, scope):
            calls["fleet_health"] += 1
            return fleet_health_from_rows(
                [
                    _row("d1", "temperature", STALE_TS, plant_id="p1", transformer_id="t1"),
                    _row("d2", "temperature", STALE_TS, plant_id="p1", transformer_id="t2"),
                ],
                NOW,
            )

        def _events(**kwargs):
            calls["events"] += 1
            return []

        def _plants(*, scope):
            calls["plants"] += 1
            return [_plant("p1", "One")]

        def _transformers(plant_id, *, scope):
            calls["transformers"] += 1
            return []

        def _device_paths(device_ids, *, scope):
            calls["device_paths"] += 1
            return []

        monkeypatch.setattr(svc, "get_fleet_health", _fh)
        monkeypatch.setattr(svc, "list_recent_device_events", _events)
        monkeypatch.setattr(svc, "list_plants", _plants)
        monkeypatch.setattr(svc, "list_transformers", _transformers)
        monkeypatch.setattr(svc, "list_device_paths", _device_paths)

        snap = svc.get_command_center_snapshot(scope=UNRESTRICTED)

        # Phase 10 added the priority ranking, which labels the attention
        # population through the SAME batched lookup — one more read path,
        # still exactly one call each (ADR-008/ADR-009).
        assert calls == {
            "fleet_health": 1, "events": 1, "plants": 1,
            "transformers": 1, "device_paths": 1,
        }
        assert snap.affected_locations[0].affected_rtls == 2
        # Two transformers in the plant, but still exactly one lookup.
        assert len(snap.selected_location.transformers) == 2
