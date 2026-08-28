"""insert_readings() round-trip — backs db/live_simulator.py's per-tick writes.

Database-backed: runs against the module-scoped isolated_schema
(tests/conftest.py), never the real plant_monitoring tables.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo

PLANT = "live-p1"
TRANSFORMER = "live-p1-t1"
DEVICE = "live-p1-t1-d1"

TS = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)


def _wipe() -> None:
    with session_scope() as session:
        for table in ("readings", "devices", "transformers", "plants"):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


def _seed_one_device() -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                "(plant_id, name, country, latitude, longitude) "
                f"VALUES ('{PLANT}', 'Live Sim Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                "(transformer_id, plant_id, transformer_code) "
                f"VALUES ('{TRANSFORMER}', '{PLANT}', 't1')"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                "(device_id, transformer_id, device_code) "
                f"VALUES ('{DEVICE}', '{TRANSFORMER}', '90001')"
            )
        )


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestInsertReadings:
    def setup_method(self):
        _wipe()
        _seed_one_device()

    def test_inserted_reading_is_readable_back(self):
        repo.insert_readings([repo.RawReading(DEVICE, "temperature", TS, 42.5)])
        latest = repo.get_latest_reading(DEVICE, "temperature")
        assert latest is not None
        assert latest.value == 42.5
        assert latest.timestamp == TS

    def test_inserts_multiple_rows_across_metrics(self):
        repo.insert_readings([
            repo.RawReading(DEVICE, "temperature", TS, 42.5),
            repo.RawReading(DEVICE, "voltage", TS, 11.02),
        ])
        assert repo.get_latest_reading(DEVICE, "temperature").value == 42.5
        assert repo.get_latest_reading(DEVICE, "voltage").value == 11.02

    def test_empty_list_is_a_no_op(self):
        repo.insert_readings([])
        assert repo.get_latest_reading(DEVICE, "temperature") is None
