"""Unit tests for db.live_simulator's scope-validation logic.

Pure functions, no database required. The run() loop itself is thin
orchestration (I/O, time.sleep) and isn't unit tested, matching how
db/seed_plant_monitoring.py's seed() orchestration isn't either.
"""
from __future__ import annotations

import pytest

from db.live_simulator import (
    ConfigurationError,
    resolve_device_scope,
    resolve_metric_scope,
)

KNOWN_DEVICES = {"plant-01-t1-d1", "plant-01-t1-d2", "plant-02-t1-d1"}


class TestResolveDeviceScope:
    def test_empty_configuration_means_every_known_device(self):
        assert resolve_device_scope((), KNOWN_DEVICES) == sorted(KNOWN_DEVICES)

    def test_configured_subset_is_returned_as_given(self):
        result = resolve_device_scope(("plant-02-t1-d1", "plant-01-t1-d1"), KNOWN_DEVICES)
        assert result == ["plant-02-t1-d1", "plant-01-t1-d1"]

    def test_unknown_device_id_raises_configuration_error(self):
        with pytest.raises(ConfigurationError):
            resolve_device_scope(("plant-99-t1-d1",), KNOWN_DEVICES)

    def test_error_message_names_the_unknown_id(self):
        with pytest.raises(ConfigurationError, match="plant-99-t1-d1"):
            resolve_device_scope(("plant-99-t1-d1",), KNOWN_DEVICES)


class TestResolveMetricScope:
    KNOWN_METRICS = ("temperature", "voltage", "energy")

    def test_empty_configuration_means_every_metric(self):
        assert resolve_metric_scope((), self.KNOWN_METRICS) == list(self.KNOWN_METRICS)

    def test_configured_subset_is_returned_as_given(self):
        result = resolve_metric_scope(("energy", "temperature"), self.KNOWN_METRICS)
        assert result == ["energy", "temperature"]

    def test_unknown_metric_raises_configuration_error(self):
        with pytest.raises(ConfigurationError):
            resolve_metric_scope(("not_a_metric",), self.KNOWN_METRICS)

    def test_error_message_names_the_unknown_metric(self):
        with pytest.raises(ConfigurationError, match="not_a_metric"):
            resolve_metric_scope(("not_a_metric",), self.KNOWN_METRICS)


class TestSilencedFeedsInSimulator:
    def test_empty_when_no_capture_file(self, monkeypatch, tmp_path):
        from db import live_simulator
        monkeypatch.setattr(live_simulator, "CAPTURE_PATH", tmp_path / "absent.json")
        assert live_simulator.active_silenced_feeds() == frozenset()

    def test_demo_feeds_when_capture_file_exists(self, monkeypatch, tmp_path):
        from db import live_simulator
        capture = tmp_path / "capture.json"
        capture.write_text("[]")
        monkeypatch.setattr(live_simulator, "CAPTURE_PATH", capture)
        assert ("plant-03-t1-d1", "temperature") in live_simulator.active_silenced_feeds()

    def test_is_silenced(self):
        from db import live_simulator
        silenced = frozenset({("d1", "voltage")})
        assert live_simulator.is_silenced("d1", "voltage", silenced)
        assert not live_simulator.is_silenced("d1", "temperature", silenced)


class TestParseArgs:
    def test_no_arguments_means_run_forever(self):
        from db import live_simulator
        assert live_simulator.parse_args([]).backfill_events_days is None

    def test_backfill_days(self):
        from db import live_simulator
        args = live_simulator.parse_args(["--backfill-events-days", "7"])
        assert args.backfill_events_days == 7.0


class TestBackfillEvents:
    NOW = __import__("datetime").datetime(2026, 9, 19, tzinfo=__import__("datetime").timezone.utc)

    def _with_rate(self, monkeypatch, rate):
        import dataclasses
        from db import live_simulator
        monkeypatch.setattr(
            live_simulator, "live_sim",
            dataclasses.replace(live_simulator.live_sim, events_per_day=rate),
        )
        return live_simulator

    def test_plans_the_whole_window_and_emits(self, monkeypatch):
        import random
        live_simulator = self._with_rate(monkeypatch, 12.0)
        emitted = []
        monkeypatch.setattr(live_simulator, "_device_transformers",
                            lambda: {"d1": "t1", "d2": "t1"})
        monkeypatch.setattr(live_simulator, "emit_planned",
                            lambda planned, transformer_of: emitted.extend(planned) or len(planned))
        assert live_simulator.backfill_events(7, self.NOW, random.Random(1)) == 84
        assert len(emitted) == 84
        assert {e.device_id for e in emitted} <= {"d1", "d2"}

    def test_does_nothing_when_events_are_off(self, monkeypatch):
        import random
        live_simulator = self._with_rate(monkeypatch, 0.0)
        monkeypatch.setattr(live_simulator, "_device_transformers", lambda: 1 / 0)
        assert live_simulator.backfill_events(7, self.NOW, random.Random(1)) == 0
