"""Phase 8 - Selected Location / Transformer Concentration (service side).

"Which transformers inside this Plant are driving the attention?" - one
level below the Phase 7 ranking, from the same FleetHealth.
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest

from services import command_center_service as svc
from services.device_scope import UNRESTRICTED, DeviceScope
from services.monitoring_service import fleet_health_from_rows
from tests.test_command_center_service import NOW, RECENT, _plant, _row

STALE_TS = NOW - timedelta(days=2)


def _transformer(transformer_id, code, plant_id="p1"):
    """A TransformerRecord-shaped label source."""
    return SimpleNamespace(
        transformer_id=transformer_id,
        plant_id=plant_id,
        transformer_code=code,
        status="active",
    )


def _compose(monkeypatch, rows, *, plants=(), transformers=(), selected=None,
             scope=UNRESTRICTED):
    monkeypatch.setattr(
        svc, "get_fleet_health", lambda now, *, scope: fleet_health_from_rows(rows, NOW)
    )
    monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: [])
    monkeypatch.setattr(svc, "list_plants", lambda *, scope: list(plants))
    monkeypatch.setattr(
        svc, "list_transformers", lambda plant_id, *, scope: list(transformers)
    )
    return svc.get_command_center_snapshot(scope=scope, selected_plant_id=selected)


#: p1 has t1 (2 stale + 1 no-data of 4) and t2 (1 stale of 2).
ROWS = [
    _row("d1", "temperature", STALE_TS, plant_id="p1", transformer_id="t1"),
    _row("d2", "temperature", STALE_TS, plant_id="p1", transformer_id="t1"),
    _row("d3", "temperature", None, plant_id="p1", transformer_id="t1"),
    _row("d4", "temperature", RECENT, plant_id="p1", transformer_id="t1"),
    _row("d5", "temperature", STALE_TS, plant_id="p1", transformer_id="t2"),
    _row("d6", "temperature", RECENT, plant_id="p1", transformer_id="t2"),
    # A second plant, to prove selection actually narrows.
    _row("d7", "temperature", STALE_TS, plant_id="p2", transformer_id="t9"),
]
PLANTS = [_plant("p1", "Durban"), _plant("p2", "Newcastle")]
TRANSFORMERS = [_transformer("t1", "TRF-04"), _transformer("t2", "TRF-07")]



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

class TestDefaultAndFallbackSelection:
    """Nothing chosen, an unknown id, or a plant that has dropped out of
    scope all resolve to the WORST AFFECTED plant - the panel opens on the
    thing most worth looking at rather than on a prompt. The fallback also
    future-proofs polling, where a refresh can invalidate a selection made
    a moment earlier."""

    def test_no_selection_defaults_to_the_worst_affected_plant(self, monkeypatch):
        snap = _compose(monkeypatch, ROWS, plants=PLANTS, transformers=TRANSFORMERS)
        # p1 has 4 affected, p2 has 1.
        assert snap.selected_location.plant_id == "p1"

    def test_the_default_matches_the_top_of_the_ranking(self, monkeypatch):
        """Stated as a relationship, not a hard-coded id: the panel and the
        Affected Locations ranking must never disagree about which plant is
        worst."""
        snap = _compose(monkeypatch, ROWS, plants=PLANTS, transformers=TRANSFORMERS)
        assert snap.selected_location.plant_id == snap.affected_locations[0].plant_id

    def test_an_unknown_plant_falls_back_rather_than_erroring(self, monkeypatch):
        """A hand-edited URL must not break the page, and must not blank a
        panel that has something useful to show."""
        snap = _compose(
            monkeypatch, ROWS, plants=PLANTS, transformers=TRANSFORMERS,
            selected="no-such-plant",
        )
        assert snap.selected_location.plant_id == "p1"

    def test_an_out_of_scope_plant_falls_back(self, monkeypatch):
        """Never an error, and never a message confirming that a plant the
        caller cannot see exists."""
        rows = [_row("d1", "temperature", STALE_TS, plant_id="visible", transformer_id="t1")]
        snap = _compose(
            monkeypatch, rows, plants=[_plant("visible", "Visible")],
            transformers=[_transformer("t1", "T1", plant_id="visible")],
            selected="hidden", scope=DeviceScope(device_ids=frozenset({"d1"})),
        )
        assert snap.selected_location.plant_id == "visible"

    def test_an_explicit_valid_selection_wins_over_the_default(self, monkeypatch):
        snap = _compose(
            monkeypatch, ROWS, plants=PLANTS, transformers=TRANSFORMERS, selected="p2"
        )
        assert snap.selected_location.plant_id == "p2"

    def test_a_calm_fleet_selects_nothing(self, monkeypatch):
        """With nothing affected there is no worst plant to fall back to.
        The panel states that calmly rather than treating it as an error."""
        rows = [_row("d1", "temperature", RECENT, plant_id="p1", transformer_id="t1")]
        snap = _compose(monkeypatch, rows, plants=[_plant("p1", "Calm")])
        assert snap.selected_location is None

    def test_the_transformer_lookup_is_skipped_when_nothing_resolves(self, monkeypatch):
        """The label call is for the ONE selected plant. With no plant
        resolved there is nothing to label, so it must not run."""
        calls = {"n": 0}
        rows = [_row("d1", "temperature", RECENT, plant_id="p1", transformer_id="t1")]

        monkeypatch.setattr(
            svc, "get_fleet_health", lambda now, *, scope: fleet_health_from_rows(rows, NOW)
        )
        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: [])
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [_plant("p1", "Calm")])

        def _counted(plant_id, *, scope):
            calls["n"] += 1
            return []

        monkeypatch.setattr(svc, "list_transformers", _counted)
        svc.get_command_center_snapshot(scope=UNRESTRICTED)
        assert calls["n"] == 0


class TestPlantLevelComposition:
    def test_the_stale_and_no_data_split_is_carried(self, monkeypatch):
        """"18 affected" alone does not say whether the plant stopped
        reporting or never started."""
        loc = _compose(
            monkeypatch, ROWS, plants=PLANTS, transformers=TRANSFORMERS, selected="p1"
        ).selected_location
        assert (loc.stale_rtls, loc.no_data_rtls) == (3, 1)
        assert loc.stale_rtls + loc.no_data_rtls == loc.affected_rtls

    def test_a_plant_with_monitored_rtls_reports_so(self, monkeypatch):
        loc = _compose(
            monkeypatch, ROWS, plants=PLANTS, transformers=TRANSFORMERS, selected="p1"
        ).selected_location
        assert loc.has_monitored_rtls is True


class TestSelectedLocation:
    def _selected(self, monkeypatch, **kw):
        snap = _compose(
            monkeypatch, ROWS, plants=PLANTS, transformers=TRANSFORMERS,
            selected="p1", **kw,
        )
        return snap.selected_location

    def test_carries_the_plant_identity_and_totals(self, monkeypatch):
        loc = self._selected(monkeypatch)
        assert loc.plant_id == "p1"
        assert loc.plant_name == "Durban"
        assert loc.affected_rtls == 4          # 3 in t1 + 1 in t2
        assert loc.total_monitored_rtls == 6

    def test_lists_only_this_plants_transformers(self, monkeypatch):
        loc = self._selected(monkeypatch)
        assert [t.transformer_id for t in loc.transformers] == ["t1", "t2"]

    def test_affected_is_stale_plus_no_data_per_transformer(self, monkeypatch):
        worst = self._selected(monkeypatch).transformers[0]
        assert (worst.affected_rtls, worst.stale_rtls, worst.no_data_rtls) == (3, 2, 1)
        assert worst.total_monitored_rtls == 4

    def test_composition_sums_to_the_affected_total(self, monkeypatch):
        for t in self._selected(monkeypatch).transformers:
            assert t.stale_rtls + t.no_data_rtls == t.affected_rtls

    def test_ranked_by_affected_count_descending(self, monkeypatch):
        counts = [t.affected_rtls for t in self._selected(monkeypatch).transformers]
        assert counts == sorted(counts, reverse=True)

    def test_transformer_codes_come_from_the_label_lookup(self, monkeypatch):
        assert self._selected(monkeypatch).transformers[0].transformer_code == "TRF-04"

    def test_a_transformer_missing_a_code_keeps_its_id(self, monkeypatch):
        """FleetHealth is the authority on what exists in scope; a labelling
        call must never shrink the population the numbers came from."""
        snap = _compose(
            monkeypatch, ROWS, plants=PLANTS,
            transformers=[_transformer("t1", "TRF-04")], selected="p1",
        )
        codes = {t.transformer_id: t.transformer_code for t in snap.selected_location.transformers}
        assert codes == {"t1": "TRF-04", "t2": "t2"}


class TestTransformerRankingRules:
    def _ranked(self, monkeypatch, rows, transformers):
        snap = _compose(
            monkeypatch, rows, plants=[_plant("p1", "P")],
            transformers=transformers, selected="p1",
        )
        return snap.selected_location.transformers

    def test_ties_break_on_code_ascending_case_insensitively(self, monkeypatch):
        rows = [
            _row("d1", "temperature", STALE_TS, plant_id="p1", transformer_id="tz"),
            _row("d2", "temperature", STALE_TS, plant_id="p1", transformer_id="ta"),
        ]
        ranked = self._ranked(
            monkeypatch, rows,
            [_transformer("tz", "ALPHA"), _transformer("ta", "beta")],
        )
        assert [t.transformer_code for t in ranked] == ["ALPHA", "beta"]

    def test_a_fresh_transformer_ranks_below_an_affected_one(self, monkeypatch):
        rows = [
            _row("d1", "temperature", RECENT, plant_id="p1", transformer_id="tfresh"),
            _row("d2", "temperature", STALE_TS, plant_id="p1", transformer_id="tstale"),
        ]
        ranked = self._ranked(
            monkeypatch, rows,
            [_transformer("tfresh", "AAA"), _transformer("tstale", "ZZZ")],
        )
        assert [t.transformer_id for t in ranked] == ["tstale", "tfresh"]
        assert ranked[-1].affected_rtls == 0

    def test_ordering_is_stable_across_repeated_composition(self, monkeypatch):
        rows = [
            _row(f"d{i}", "temperature", STALE_TS, plant_id="p1", transformer_id=f"t{i}")
            for i in range(5)
        ]
        transformers = [_transformer(f"t{i}", f"TRF-{i:02d}") for i in range(5)]
        first = [t.transformer_id for t in self._ranked(monkeypatch, rows, transformers)]
        second = [t.transformer_id for t in self._ranked(monkeypatch, rows, transformers)]
        assert first == second

    def test_no_event_data_reaches_the_transformer_ranking(self, monkeypatch):
        """Same time-semantics separation as the plant ranking (ADR-002)."""
        monkeypatch.setattr(
            svc, "get_fleet_health", lambda now, *, scope: fleet_health_from_rows(ROWS, NOW)
        )
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: list(PLANTS))
        monkeypatch.setattr(
            svc, "list_transformers", lambda plant_id, *, scope: list(TRANSFORMERS)
        )
        monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])

        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: [])
        without = [
            (t.transformer_id, t.affected_rtls)
            for t in svc.get_command_center_snapshot(
                scope=UNRESTRICTED, selected_plant_id="p1"
            ).selected_location.transformers
        ]

        noisy = [_noisy_event(i, "d1") for i in range(50)]
        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: noisy)
        with_events = [
            (t.transformer_id, t.affected_rtls)
            for t in svc.get_command_center_snapshot(
                scope=UNRESTRICTED, selected_plant_id="p1"
            ).selected_location.transformers
        ]

        assert without == with_events


class TestPhase5To7ValuesAreUnchangedBySelection:
    def test_selecting_a_plant_changes_no_fleet_wide_figure(self, monkeypatch):
        """Selection is a lens on one plant, not a filter on the fleet. The
        Situation Summary must read identically either way."""
        unselected = _compose(monkeypatch, ROWS, plants=PLANTS)
        selected = _compose(
            monkeypatch, ROWS, plants=PLANTS, transformers=TRANSFORMERS, selected="p1"
        )
        for field in (
            "monitored_device_count", "fresh_rtls", "stale_rtls", "no_data_rtls",
            "attention_rtls", "plant_count", "transformer_count",
        ):
            assert getattr(unselected, field) == getattr(selected, field), field
        assert [r.plant_id for r in unselected.affected_locations] == [
            r.plant_id for r in selected.affected_locations
        ]
