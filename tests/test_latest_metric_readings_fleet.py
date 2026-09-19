"""`latest_metric_readings(..., fleet=True)` — the fleet-wide single-metric read
(TEMP-CONDITION-1). Still one bounded seek per device (ADR-014)."""
from __future__ import annotations

import pytest

from repositories import plant_monitoring_repository as repo


class TestScopeGuard:
    """Refused before any connection is opened, so these stay non-DB."""

    def test_no_scope_and_no_fleet_is_refused(self):
        with pytest.raises(ValueError):
            repo.latest_metric_readings("temperature", allowed_device_ids=None)

    def test_fleet_with_a_plant_is_refused(self):
        with pytest.raises(ValueError):
            repo.latest_metric_readings(
                "temperature", fleet=True, plant_id="plant-01", allowed_device_ids=None
            )

    def test_fleet_with_a_transformer_is_refused(self):
        with pytest.raises(ValueError):
            repo.latest_metric_readings(
                "temperature", fleet=True, transformer_id="plant-01-t1",
                allowed_device_ids=None,
            )


@pytest.mark.db
class TestFleetRead:
    def test_one_row_per_active_device(self):
        rows = repo.latest_metric_readings("temperature", fleet=True, allowed_device_ids=None)
        ids = [r.device_id for r in rows]
        assert len(ids) == len(set(ids)) == 120

    def test_respects_device_scope(self):
        allowed = frozenset({"plant-01-t1-d1", "plant-02-t1-d1"})
        rows = repo.latest_metric_readings("temperature", fleet=True, allowed_device_ids=allowed)
        assert {r.device_id for r in rows} == allowed
