"""REPORT-2 Installed RTLs report tests — R2-D1..D7 frozen semantics.

Pure classes cover presentation shaping and service delegation without a
database. Database-backed suites run against the module-scoped
isolated_schema (tests/conftest.py), never the real plant_monitoring tables.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import report_service
from services.device_scope import DeviceScope, UNRESTRICTED
from services.report_service import (
    InstalledRtlsRow,
    ReportError,
    installed_rtls_rows,
)


# ---------------------------------------------------------------------------
# Pure — presentation shaping (callbacks/report_center.py helpers)
# ---------------------------------------------------------------------------


def _row(**overrides) -> InstalledRtlsRow:
    defaults = dict(
        ou=None,
        zone=None,
        sector=None,
        cnc=None,
        feeder_name=None,
        transformer="t1",
        uid="29017",
        last_recorded_at=datetime(2026, 8, 25, 13, 4, tzinfo=timezone.utc),
        last_temperature=72.8,
        rtl_status="active",
    )
    defaults.update(overrides)
    return InstalledRtlsRow(**defaults)


class TestInstalledRtlsPresentation:
    def test_none_taxonomy_renders_as_placeholder_r2d2(self):
        from callbacks.report_center import _build_installed_rtls_table

        table = _build_installed_rtls_table([_row()])
        data = table.children[0].data
        assert len(data) == 1
        assert data[0]["ou"] == "—"
        assert data[0]["zone"] == "—"
        assert data[0]["sector"] == "—"
        assert data[0]["cnc"] == "—"
        assert data[0]["feeder_name"] == "—"

    def test_column_headers_match_client_contract(self):
        from callbacks.report_center import _build_installed_rtls_table

        names = [c["name"] for c in _build_installed_rtls_table([_row()]).children[0].columns]
        assert names == [
            "OU", "Zone", "Sector", "CNC", "Feeder Name",
            "Transformer", "UID",
            "Timestamp of Last Recorded Data",
            "Last Recorded Temperature (°C)",
            "RTL Status",
        ]

    def test_timestamp_and_temperature_formatting(self):
        from callbacks.report_center import _build_installed_rtls_table

        data = _build_installed_rtls_table([_row()]).children[0].data
        assert data[0]["last_recorded_at"] == "2026-08-25 13:04 UTC"
        assert data[0]["last_temperature"] == "72.8"
        assert data[0]["transformer"] == "t1"
        assert data[0]["uid"] == "29017"
        assert data[0]["rtl_status"] == "active"

    def test_never_reported_device_renders_placeholders_not_zeros(self):
        from callbacks.report_center import _build_installed_rtls_table

        data = _build_installed_rtls_table(
            [_row(last_recorded_at=None, last_temperature=None)]
        ).children[0].data
        assert data[0]["last_recorded_at"] == "—"
        assert data[0]["last_temperature"] == "—"


# ---------------------------------------------------------------------------
# Pure — service contract and delegation
# ---------------------------------------------------------------------------


class TestReportServiceDelegation:
    def test_service_passes_scope_and_metric_to_repository(self, monkeypatch):
        captured = {}

        def fake_rows(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(
            report_service.repo, "installed_rtls_report_rows", fake_rows
        )
        scope = DeviceScope(device_ids=frozenset({"d1"}))
        installed_rtls_rows(plant_id="p1", device_scope=scope)

        assert captured["allowed_device_ids"] == frozenset({"d1"})
        assert captured["temperature_metric"] == "temperature"
        assert captured["plant_id"] == "p1"
        assert captured["transformer_id"] is None
        assert captured["device_id"] is None

    def test_domain_row_keeps_taxonomy_none_r2d2(self, monkeypatch):
        ts = datetime(2026, 8, 25, 12, 32, tzinfo=timezone.utc)
        record = repo.InstalledRtlsRecord(
            plant_id="p1", transformer_id="p1-t1", transformer_code="t1",
            device_id="p1-t1-d1", device_code="29017", status="active",
            last_recorded_at=ts, last_temperature=72.8,
        )
        monkeypatch.setattr(
            report_service.repo,
            "installed_rtls_report_rows",
            lambda **kwargs: [record],
        )
        rows = installed_rtls_rows(device_scope=UNRESTRICTED)
        assert rows[0].ou is None and rows[0].feeder_name is None
        assert rows[0].transformer == "t1"
        assert rows[0].uid == "29017"
        assert rows[0].last_recorded_at == ts
        assert rows[0].last_temperature == 72.8
        assert rows[0].rtl_status == "active"

    def test_repository_failure_raises_friendly_report_error(self, monkeypatch):
        def explode(**kwargs):
            raise RuntimeError("simulated store outage")

        monkeypatch.setattr(
            report_service.repo, "installed_rtls_report_rows", explode
        )
        with pytest.raises(ReportError):
            installed_rtls_rows(device_scope=UNRESTRICTED)


# ---------------------------------------------------------------------------
# Database-backed — seeded readings against isolated schema
# ---------------------------------------------------------------------------


def _seed_tree(plant_id="r2-p1", transformer_id="r2-p1-t1") -> str:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                f"(plant_id, name, country, latitude, longitude) "
                f"VALUES (:plant_id, 'Report Plant', 'Testland', 0, 0) "
                f"ON CONFLICT (plant_id) DO NOTHING"
            ),
            {"plant_id": plant_id},
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES (:tid, :plant_id, :tid) "
                f"ON CONFLICT (transformer_id) DO NOTHING"
            ),
            {"tid": transformer_id, "plant_id": plant_id},
        )
    return transformer_id


def _seed_device(device_id: str, code: str, status: str = "active") -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                f"(device_id, transformer_id, device_code, status) "
                f"VALUES (:device_id, :tid, :code, :status)"
            ),
            {
                "device_id": device_id,
                "tid": "r2-p1-t1",
                "code": code,
                "status": status,
            },
        )


def _seed_reading(device_id: str, metric: str, ts: datetime, value: float) -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.readings "
                f"(device_id, metric, reading_ts, value) "
                f"VALUES (:device_id, :metric, :ts, :value)"
            ),
            {"device_id": device_id, "metric": metric, "ts": ts, "value": value},
        )


def _wipe() -> None:
    """Reset everything this module touches, FK-safe order."""
    with session_scope() as session:
        for table in (
            "audit_log", "user_device_assignments", "readings",
            "devices", "transformers", "plants",
        ):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestInstalledRtlsQuery:
    def setup_method(self):
        _wipe()
        _seed_tree()
        self.d1, self.d2, self.d3 = "r2-p1-t1-d1", "r2-p1-t1-d2", "r2-p1-t1-d3"
        _seed_device(self.d1, "29017")
        _seed_device(self.d2, "29018")
        # R2-D3 freeze: an administratively inactive device stays reported.
        _seed_device(self.d3, "29019", status="inactive")
        # R2-D1 freeze: latest ANY metric vs latest temperature differ.
        _seed_reading(
            self.d1, "temperature", datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc), 71.5
        )
        _seed_reading(
            self.d1, "voltage", datetime(2026, 8, 25, 10, 30, tzinfo=timezone.utc), 11.2
        )

    def _uids(self, rows):
        return [r.device_code for r in rows]

    def test_last_data_is_any_metric_and_temperature_is_separate_r2d1(self):
        rows = repo.installed_rtls_report_rows(temperature_metric="temperature", allowed_device_ids=None)
        by_uid = {r.device_code: r for r in rows}
        assert by_uid["29017"].last_recorded_at == datetime(
            2026, 8, 25, 10, 30, tzinfo=timezone.utc
        )
        assert by_uid["29017"].last_temperature == 71.5

    def test_never_reported_device_stays_present_with_nulls_r2d4(self):
        rows = repo.installed_rtls_report_rows(temperature_metric="temperature", allowed_device_ids=None)
        by_uid = {r.device_code: r for r in rows}
        assert by_uid["29018"].last_recorded_at is None
        assert by_uid["29018"].last_temperature is None

    def test_inactive_administrative_status_remains_in_report_r2d3(self):
        rows = repo.installed_rtls_report_rows(temperature_metric="temperature", allowed_device_ids=None)
        by_uid = {r.device_code: r for r in rows}
        assert by_uid["29019"].status == "inactive"

    def test_rows_ordered_by_transformer_then_uid(self):
        rows = repo.installed_rtls_report_rows(temperature_metric="temperature", allowed_device_ids=None)
        assert self._uids(rows) == ["29017", "29018", "29019"]

    def test_technician_scope_narrows_rows(self):
        rows = repo.installed_rtls_report_rows(
            temperature_metric="temperature",
            allowed_device_ids=frozenset({self.d2}),
        )
        assert self._uids(rows) == ["29018"]

    def test_empty_scope_yields_no_rows_never_the_fleet(self):
        rows = repo.installed_rtls_report_rows(
            temperature_metric="temperature", allowed_device_ids=frozenset()
        )
        assert rows == []

    def test_plant_asset_scope_filters_other_plants(self):
        _seed_tree("r2-p2", "r2-p2-t1")
        _seed_tree("r2-p3", "r2-p3-t1")  # noise
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    f"(device_id, transformer_id, device_code) "
                    f"VALUES ('r2-p2-t1-d9', 'r2-p2-t1', '29999')"
                )
            )
        rows = repo.installed_rtls_report_rows(
            temperature_metric="temperature",
            plant_id="r2-p2",
            allowed_device_ids=None,
        )
        assert self._uids(rows) == ["29999"]

    def test_transformer_and_device_asset_scopes(self):
        rows = repo.installed_rtls_report_rows(
            temperature_metric="temperature",
            transformer_id="r2-p1-t1",
            allowed_device_ids=None,
        )
        assert self._uids(rows) == ["29017", "29018", "29019"]
        rows = repo.installed_rtls_report_rows(
            temperature_metric="temperature",
            device_id=self.d1,
            allowed_device_ids=None,
        )
        assert self._uids(rows) == ["29017"]

    def test_unknown_scope_is_empty_honest_result(self):
        rows = repo.installed_rtls_report_rows(
            temperature_metric="temperature",
            plant_id="no-such-plant",
            allowed_device_ids=None,
        )
        assert rows == []

    def test_service_layer_returns_domain_rows_for_scope(self):
        rows = installed_rtls_rows(
            device_scope=DeviceScope(device_ids=frozenset({self.d1}))
        )
        assert len(rows) == 1
        assert rows[0].uid == "29017"
        assert rows[0].ou is None  # R2-D2 at service level too

