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
