"""REPORT-3 pure tests — RTL Alarms (30 Days) service logic.

Covers R3-D1 (semantics authority), R3-D5 (column mapping/labels),
R3-D6 (strict transformer snapshot rule), R3-D7 (fixed horizon from an
injectable clock). Database-backed proofs live in
test_rtl_alarms_report_db.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from config.events import (
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_CHECK_IN,
    EVENT_TYPE_POWER_DOWN,
    EVENT_TYPE_SENSOR_ERROR,
    EVENT_TYPE_STARTUP,
)
from repositories import plant_monitoring_repository as repo
from services.device_scope import DeviceScope
from services import report_service
from services.report_service import ReportError, RtlAlarms30dRow, rtl_alarms_30d_rows

NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
SCOPE = DeviceScope(device_ids=None)


@dataclass(frozen=True)
class FakeRecord:
    event_id: int = 1
    event_type: str = EVENT_TYPE_BATTERY_LOW
    alarm_at: datetime = NOW - timedelta(hours=1)
    event_transformer_id: str | None = "t1"
    event_transformer_code: str | None = "t1code"
    current_transformer_code: str | None = "t9code"
    device_code: str = "29101"
    firmware_version: str | None = "v7"
    temperature: float | None = 85.0
    battery_voltage: float | None = 3.52


@pytest.fixture
def capture_repo(monkeypatch):
    """Replace the repository query; capture kwargs for assertions."""
    captured = {}
    records: list = []

    def fake(**kwargs):
        captured.update(kwargs)
        return list(records)

    monkeypatch.setattr(repo, "rtl_alarms_30d_report_rows", fake)
    return captured, records


# ---------------------------------------------------------------------------
# R3-D1 — semantics is the only inclusion authority
# ---------------------------------------------------------------------------


class TestAlarmTypeAuthority:
    def test_service_queries_exactly_the_reportable_types(self, capture_repo):
        captured, _ = capture_repo
        rtl_alarms_30d_rows(device_scope=SCOPE, now=NOW)

        assert set(captured["event_types"]) == {
            EVENT_TYPE_BATTERY_LOW,
            EVENT_TYPE_POWER_DOWN,
            EVENT_TYPE_SENSOR_ERROR,
        }

    def test_startup_checkin_invalid_uid_never_reported(self):
        from services.event_semantics import (
            reportable_alarm_event_types,
            semantics_for,
        )

        assert EVENT_TYPE_STARTUP not in reportable_alarm_event_types()
        assert EVENT_TYPE_CHECK_IN not in reportable_alarm_event_types()
        assert not any(
            t in reportable_alarm_event_types()
            for t in ("invalid_uid", "high_temperature", "vibration_event")
        )
        assert all(
            semantics_for(t).is_reportable_alarm
            for t in reportable_alarm_event_types()
        )

    def test_no_event_type_literals_in_the_service(self):
        import inspect

        source = inspect.getsource(report_service)
        assert '"battery_low"' not in source
        assert "'battery_low'" not in source
        assert '"power_down"' not in source
        assert '"sensor_error"' not in source


# ---------------------------------------------------------------------------
# R3-D7 — fixed horizon from an injectable clock
# ---------------------------------------------------------------------------


class TestHorizon:
    def test_since_is_reference_minus_thirty_days(self, capture_repo):
        captured, _ = capture_repo
        rtl_alarms_30d_rows(device_scope=SCOPE, now=NOW)

        assert captured["since"] == NOW - timedelta(days=30)


# ---------------------------------------------------------------------------
# R3-D5 — column mapping and label resolution
# ---------------------------------------------------------------------------


class TestColumnMapping:
    def test_labels_come_from_the_shared_semantics_mapping(self, capture_repo):
        captured, records = capture_repo
        records.extend(
            [
                FakeRecord(event_id=1, event_type=EVENT_TYPE_BATTERY_LOW),
                FakeRecord(
                    event_id=2,
                    event_type=EVENT_TYPE_POWER_DOWN,
                    temperature=None,
                    battery_voltage=None,
                    firmware_version=None,
                ),
                FakeRecord(event_id=3, event_type=EVENT_TYPE_SENSOR_ERROR),
            ]
        )

        rows = rtl_alarms_30d_rows(device_scope=SCOPE, now=NOW)

        labels = {r.alarm_label for r in rows}
        assert labels == {"Battery Alarm", "Power Down", "Sensor Error"}

    def test_taxonomy_fields_are_actual_none(self, capture_repo):
        _, records = capture_repo
        records.append(FakeRecord())

        row = rtl_alarms_30d_rows(device_scope=SCOPE, now=NOW)[0]

        assert row.ou is None and row.zone is None and row.sector is None
        assert row.cnc is None and row.feeder_name is None

    def test_payload_payloads_pass_through_raw_typed(self, capture_repo):
        _, records = capture_repo
        records.append(
            FakeRecord(battery_voltage=3.52, temperature=85.25,
                       firmware_version="v7", device_code="29101",
                       alarm_at=NOW - timedelta(minutes=5))
        )

        row = rtl_alarms_30d_rows(device_scope=SCOPE, now=NOW)[0]

        assert row.battery_voltage == 3.52
        assert row.temperature == 85.25
        assert row.uid == "29101"
        assert row.firmware_version == "v7"
        assert row.alarm_at == NOW - timedelta(minutes=5)   # EVT-D9

    def test_rows_preserve_repository_order(self, capture_repo):
        """R3-D4: the service re-sorts nothing — whatever order the
        repository's ``event_ts DESC, event_id DESC`` produced is kept
        (the real SQL ordering is proven in the db suite)."""
        _, records = capture_repo
        older = FakeRecord(event_id=2, alarm_at=NOW - timedelta(days=2))
        newer = FakeRecord(event_id=3, alarm_at=NOW - timedelta(hours=1))
        records.extend([older, newer])

        rows = rtl_alarms_30d_rows(device_scope=SCOPE, now=NOW)

        assert [(r.alarm_at) for r in rows] == [older.alarm_at, newer.alarm_at]


# ---------------------------------------------------------------------------
# R3-D6 — strict transformer snapshot rule
# ---------------------------------------------------------------------------


class TestTransformerSnapshotRule:
    def test_event_snapshot_wins_when_present(self, capture_repo):
        """An explicit historical attribution is never rewritten by the
        device's later move."""
        _, records = capture_repo
        records.append(
            FakeRecord(
                event_transformer_id="t-hist",
                event_transformer_code="hist-code",
                current_transformer_code="current-code",
            )
        )

        row = rtl_alarms_30d_rows(device_scope=SCOPE, now=NOW)[0]

        assert row.transformer == "hist-code"

    def test_fallback_to_current_when_snapshot_absent(self, capture_repo):
        """UID-resolved events carry no snapshot: the device's CURRENT
        transformer is the explicit fallback."""
        _, records = capture_repo
        records.append(
            FakeRecord(
                event_transformer_id=None,
                event_transformer_code=None,
                current_transformer_code="current-code",
            )
        )

        row = rtl_alarms_30d_rows(device_scope=SCOPE, now=NOW)[0]

        assert row.transformer == "current-code"


class TestErrorWrapping:
    def test_database_failure_raises_safe_report_error(self, monkeypatch):
        def explode(**kwargs):
            raise RuntimeError("simulated outage")

        monkeypatch.setattr(repo, "rtl_alarms_30d_report_rows", explode)
        with pytest.raises(ReportError):
            rtl_alarms_30d_rows(device_scope=SCOPE, now=NOW)
