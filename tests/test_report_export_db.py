"""REPORT-4I database-backed export tests — end-to-end document builds and
scope isolation on the isolated schema (tests/conftest.py).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from config.events import EVENT_TYPE_BATTERY_LOW, EVENT_TYPE_POWER_DOWN
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services.action_guard import require_capability
from services.auth_service import AuthenticatedUser
from services.authorization import AuthorizationError, EXPORT_DATA
from services.device_scope import DeviceScope
from services.report_export import (
    format_csv,
    installed_rtls_document,
    rtl_alarms_document,
)
from services.report_service import installed_rtls_rows, rtl_alarms_30d_rows

NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

PLANT = "exp-p1"
T1 = "exp-p1-t1"
D1 = "exp-p1-t1-d1"
D2 = "exp-p1-t1-d2"


def _wipe() -> None:
    with session_scope() as session:
        for table in (
            "audit_log", "device_events", "rtl_active_state",
            "rtl_programming_requests", "message_forwarding",
            "user_device_assignments", "readings",
            "devices", "transformers", "plants", "users",
        ):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


def _seed() -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                "(plant_id, name, country, latitude, longitude) "
                f"VALUES ('{PLANT}', 'Export Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('{T1}', '{PLANT}', 'tc1')"
            )
        )
        for i, device_id in enumerate((D1, D2), start=1):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    "(device_id, transformer_id, device_code) "
                    f"VALUES ('{device_id}', '{T1}', '2960{i}')"
                )
            )


def _event(event_type, device_id):
    return repo.insert_device_event(
        event_type=event_type,
        event_ts=NOW - timedelta(hours=1),
        device_id=device_id,
        battery_voltage=3.5,
        source="test",
    )


def _parse(content: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(content, newline="")))


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestAlarmsExportEndToEnd:
    def setup_method(self):
        _wipe()
        _seed()

    def test_exported_rows_match_scoped_preview(self):
        """R4-D7: the exporter rebuilds through the same service call the
        preview uses — identical rows for identical inputs."""
        _event(EVENT_TYPE_BATTERY_LOW, D1)
        _event(EVENT_TYPE_POWER_DOWN, D2)

        rows = rtl_alarms_30d_rows(device_scope=DeviceScope(None), now=NOW)
        doc = rtl_alarms_document(rows, scope_label="fleet", now=NOW)
        parsed = _parse(format_csv(doc))

        assert len(parsed) == 1 + len(rows)          # header + one per event
        # BR009 (FS-ALARM-1): power_down exports as "Comms Alarm".
        assert {parsed[1][10], parsed[2][10]} == {"Battery Alarm", "Comms Alarm"}

    def test_empty_scope_exports_header_only(self):
        """An unassigned technician sees nothing — and exports exactly a
        header-only file, not an error."""
        _event(EVENT_TYPE_BATTERY_LOW, D1)

        rows = rtl_alarms_30d_rows(
            device_scope=DeviceScope(frozenset()), now=NOW
        )
        doc = rtl_alarms_document(rows, scope_label="assigned", now=NOW)
        parsed = _parse(format_csv(doc))

        assert len(parsed) == 1                       # header only (R4-D5)

    def test_scope_isolation_in_exported_bytes(self):
        """A scoped technician's file must never contain another device's
        alarm rows."""
        _event(EVENT_TYPE_BATTERY_LOW, D1)
        _event(EVENT_TYPE_BATTERY_LOW, D2)

        rows = rtl_alarms_30d_rows(
            device_scope=DeviceScope(frozenset({D1})), now=NOW
        )
        content = format_csv(rtl_alarms_document(rows, scope_label="assigned", now=NOW))

        assert "29601" in content                     # own device's UID
        assert "29602" not in content                 # never the other's


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestInstalledRtlsExportEndToEnd:
    def setup_method(self):
        _wipe()
        _seed()

    def test_zero_reading_devices_still_export_with_empty_cells(self):
        """R2-D4 preserved through export: no readings → row present,
        last-data/last-temp cells empty."""
        rows = installed_rtls_rows(device_scope=DeviceScope(None))
        doc = installed_rtls_document(rows, scope_label="fleet", now=NOW)
        parsed = _parse(format_csv(doc))

        assert len(parsed) == 3                       # header + both devices
        by_uid = {r[6]: r for r in parsed[1:]}
        assert by_uid["29601"][7] == ""               # Timestamp of Last Data
        assert by_uid["29601"][8] == ""               # Last Temperature


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestExportAuthorizationIntegration:
    def setup_method(self):
        _wipe()
        _seed()

    @staticmethod
    def _user(user_id: int, username: str, role: str) -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=user_id, username=username, full_name="Test User", role=role
        )

    def test_every_confirmed_role_passes_the_export_guard(self):
        """EXPORT_DATA grants all roles with no assignment condition.

        ADR-013 supersedes R4-D3's naming of `require_action` here: the claim
        is identical and the role set is identical, but export names no
        device, so it is asserted through the capability guard. The `device_id`
        this used to pass was inert — `require_action` short-circuits before
        the assignment read whenever the any-device set already allows the
        role, which for EXPORT_DATA was every role.
        """
        for role in ("administrator", "technician", "general"):
            user = self._user(1, "someone", role)
            require_capability(user, EXPORT_DATA)   # must not raise

    def test_absent_identity_is_refused_before_any_rows_are_fetched(self):
        with pytest.raises(AuthorizationError):
            require_capability(None, EXPORT_DATA)
