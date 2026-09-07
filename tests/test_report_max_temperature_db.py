"""REPORT-MAXTEMP-1 database-backed tests — one row per transformer, its
single highest temperature reading in the window, on the isolated schema
(tests/conftest.py). Never runs against the real plant_monitoring schema.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services.device_scope import DeviceScope
from services.report_service import max_temperature_rows

NOW = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)


def _wipe() -> None:
    with session_scope() as session:
        for table in (
            "audit_log", "user_device_assignments", "readings",
            "devices", "transformers", "plants",
        ):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


def _seed_tree(plant_id: str, transformer_id: str) -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                "(plant_id, name, country, latitude, longitude) "
                "VALUES (:plant_id, 'Report Plant', 'Testland', 0, 0) "
                "ON CONFLICT (plant_id) DO NOTHING"
            ),
            {"plant_id": plant_id},
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                "(transformer_id, plant_id, transformer_code) "
                "VALUES (:tid, :plant_id, :tid) "
                "ON CONFLICT (transformer_id) DO NOTHING"
            ),
            {"tid": transformer_id, "plant_id": plant_id},
        )


def _seed_device(device_id: str, transformer_id: str, code: str,
                  installed_at: datetime | None = None) -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                "(device_id, transformer_id, device_code, installed_at) "
                "VALUES (:device_id, :tid, :code, :installed_at)"
            ),
            {
                "device_id": device_id,
                "tid": transformer_id,
                "code": code,
                "installed_at": installed_at,
            },
        )


def _seed_reading(device_id: str, metric: str, ts: datetime, value: float) -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.readings "
                "(device_id, metric, reading_ts, value) "
                "VALUES (:device_id, :metric, :ts, :value)"
            ),
            {"device_id": device_id, "metric": metric, "ts": ts, "value": value},
        )


PLANT = "rmt-p1"
T1 = "rmt-p1-t1"


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestPerTransformerMaximum:
    def setup_method(self):
        _wipe()
        _seed_tree(PLANT, T1)
        self.d1 = "rmt-p1-t1-d1"
        self.d2 = "rmt-p1-t1-d2"
        _seed_device(self.d1, T1, "29601",
                     installed_at=datetime(2025, 3, 1, tzinfo=timezone.utc))
        _seed_device(self.d2, T1, "29602",
                     installed_at=datetime(2025, 6, 1, tzinfo=timezone.utc))

    def test_max_is_taken_across_all_devices_on_the_transformer(self):
        _seed_reading(self.d1, "temperature", NOW - timedelta(days=1), 80.0)
        _seed_reading(self.d2, "temperature", NOW - timedelta(days=2), 95.5)

        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            allowed_device_ids=None,
        )

        assert len(rows) == 1
        assert rows[0].max_temperature == 95.5
        assert rows[0].device_id == self.d2

    def test_date_installed_is_the_winning_devices_own_value_rmt_d2(self):
        """The transformer's row must report installed_at from the SAME
        device that produced the max, not the other device on it."""
        _seed_reading(self.d1, "temperature", NOW - timedelta(days=1), 99.0)
        _seed_reading(self.d2, "temperature", NOW - timedelta(days=2), 50.0)

        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            allowed_device_ids=None,
        )

        assert rows[0].device_id == self.d1
        assert rows[0].installed_at == datetime(2025, 3, 1, tzinfo=timezone.utc)

    def test_device_with_no_installed_at_reports_none_not_invented_rmt_d2(self):
        d3 = "rmt-p1-t1-d3"
        _seed_device(d3, T1, "29603", installed_at=None)
        _seed_reading(d3, "temperature", NOW, 120.0)

        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            allowed_device_ids=None,
        )

        assert rows[0].device_id == d3
        assert rows[0].installed_at is None

    def test_tie_break_is_deterministic_earliest_reading_wins_rmt_d1(self):
        tie_ts_early = NOW - timedelta(days=3)
        tie_ts_late = NOW - timedelta(days=1)
        _seed_reading(self.d1, "temperature", tie_ts_late, 88.0)
        _seed_reading(self.d2, "temperature", tie_ts_early, 88.0)

        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            allowed_device_ids=None,
        )

        assert rows[0].max_temperature == 88.0
        assert rows[0].max_reading_at == tie_ts_early
        assert rows[0].device_id == self.d2

    def test_transformer_with_zero_readings_in_window_is_a_real_row_with_nulls(self):
        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            allowed_device_ids=None,
        )

        assert len(rows) == 1
        assert rows[0].transformer_code == T1
        assert rows[0].max_temperature is None
        assert rows[0].max_reading_at is None
        assert rows[0].installed_at is None

    def test_reading_outside_window_is_excluded(self):
        _seed_reading(self.d1, "temperature", NOW - timedelta(days=31), 200.0)

        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            allowed_device_ids=None,
        )

        assert rows[0].max_temperature is None

    def test_window_boundaries_are_inclusive(self):
        lower = NOW - timedelta(days=30)
        _seed_reading(self.d1, "temperature", lower, 70.0)
        _seed_reading(self.d2, "temperature", NOW, 71.0)

        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=lower, until=NOW,
            allowed_device_ids=None,
        )

        assert rows[0].max_temperature == 71.0  # both in range; higher wins

    def test_non_temperature_metric_never_wins(self):
        _seed_reading(self.d1, "voltage", NOW, 400.0)

        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            allowed_device_ids=None,
        )

        assert rows[0].max_temperature is None


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestScopeAndAssetFilters:
    def setup_method(self):
        _wipe()
        _seed_tree(PLANT, T1)
        self.d1 = "rmt-p1-t1-d1"
        self.d2 = "rmt-p1-t1-d2"
        _seed_device(self.d1, T1, "29601")
        _seed_device(self.d2, T1, "29602")
        _seed_reading(self.d1, "temperature", NOW, 80.0)
        _seed_reading(self.d2, "temperature", NOW, 95.5)

    def test_technician_scope_excludes_out_of_scope_devices_reading(self):
        """A Technician scoped to only d1 must never see d2's higher
        reading win the transformer's maximum."""
        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            allowed_device_ids=frozenset({self.d1}),
        )

        assert len(rows) == 1
        assert rows[0].max_temperature == 80.0
        assert rows[0].device_id == self.d1

    def test_transformer_with_zero_in_scope_devices_is_hidden_not_a_null_row(self):
        """No Technician data leakage: a transformer the caller cannot see
        any device on must not appear at all, not even as a bare code with
        null data."""
        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            allowed_device_ids=frozenset({"some-other-device"}),
        )

        assert rows == []

    def test_empty_scope_yields_no_rows_never_the_fleet(self):
        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            allowed_device_ids=frozenset(),
        )
        assert rows == []

    def test_plant_asset_scope_filters_other_plants(self):
        other_plant, other_t = "rmt-p2", "rmt-p2-t1"
        _seed_tree(other_plant, other_t)
        _seed_device("rmt-p2-t1-d1", other_t, "29999")

        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            plant_id=other_plant,
            allowed_device_ids=None,
        )

        assert [r.transformer_code for r in rows] == [other_t]

    def test_transformer_asset_scope_filters(self):
        other_t = "rmt-p1-t2"
        _seed_tree(PLANT, other_t)

        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            transformer_id=T1,
            allowed_device_ids=None,
        )

        assert [r.transformer_code for r in rows] == [T1]

    def test_device_asset_scope_narrows_which_reading_can_win(self):
        rows = repo.max_temperature_report_rows(
            temperature_metric="temperature",
            since=NOW - timedelta(days=30), until=NOW,
            device_id=self.d1,
            allowed_device_ids=None,
        )

        assert len(rows) == 1
        assert rows[0].max_temperature == 80.0
        assert rows[0].device_id == self.d1

    def test_service_layer_returns_domain_rows_for_scope(self):
        rows = max_temperature_rows(
            device_scope=DeviceScope(device_ids=frozenset({self.d1})),
            since=NOW - timedelta(days=30), until=NOW,
        )
        assert len(rows) == 1
        assert rows[0].max_temperature == 80.0
        assert rows[0].ou is None  # R2-D2 at service level too
