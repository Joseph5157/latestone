"""RTL-IF-3 simulated incoming-event source tests.

Proves services/simulated_event_source.py is a thin, non-bypassing front
end onto the EXISTING device_event_service.ingest_event() boundary — no
persistence, projection, validation, or consumer logic of its own.
Database-backed suites run against the module-scoped isolated_schema
(tests/conftest.py), never the real plant_monitoring tables.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from config.events import (
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_CHECK_IN,
    EVENT_TYPE_INVALID_UID,
    EVENT_TYPE_STARTUP,
)
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import device_event_service as ingest
from services import simulated_event_source as sim
from services.device_scope import DeviceScope
from services.notification_service import current_notifications
from services.report_service import rtl_alarms_30d_rows

NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)

PLANT = "sim-p1"
T1 = "sim-p1-t1"
D1 = "sim-p1-t1-d1"   # code 39101


def _wipe() -> None:
    with session_scope() as session:
        for table in (
            "audit_log", "device_events", "rtl_active_state",
            "rtl_commands", "rtl_programming_requests", "message_forwarding",
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
                f"VALUES ('{PLANT}', 'Sim Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('{T1}', '{PLANT}', 't1')"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                "(device_id, transformer_id, device_code) "
                f"VALUES ('{D1}', '{T1}', '39101')"
            )
        )


def _event_count() -> int:
    with session_scope() as session:
        return session.execute(
            text(f"SELECT COUNT(*) FROM {repo._SCHEMA}.device_events")
        ).scalar_one()


def _state(device_id: str) -> dict | None:
    with session_scope() as session:
        row = session.execute(
            text(
                f"SELECT {repo._ACTIVE_STATE_COLUMNS} "
                f"FROM {repo._SCHEMA}.rtl_active_state WHERE device_id = :d"
            ),
            {"d": device_id},
        ).first()
    if row is None:
        return None
    return {"is_active": bool(row[1])}


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestSimulatedEventEntersCanonicalPipeline:
    def setup_method(self):
        _wipe()
        _seed()

    def test_a_valid_simulated_event_persists_through_ingest_event(self):
        """A. Reaches NormalizedEvent + ingest_event(); a device_events row
        exists afterward."""
        before = _event_count()
        result = sim.emit_startup(event_ts=NOW, device_id=D1)
        assert isinstance(result, ingest.IngestResult)
        assert _event_count() == before + 1

    def test_b_persisted_row_has_correct_device_and_event_identity(self):
        """B."""
        result = sim.emit_battery_low(
            event_ts=NOW, device_id=D1, battery_voltage=3.4
        )
        row = repo.get_device_event(result.event_id)
        assert row["device_id"] == D1
        assert row["event_type"] == EVENT_TYPE_BATTERY_LOW
        assert float(row["battery_voltage"]) == 3.4

    def test_c_startup_activates_an_inactive_resolved_rtl(self):
        """C. inactive RTL -> simulated startup -> existing activation
        projection -> active state becomes true."""
        assert _state(D1) is None  # no row yet: never activated

        result = sim.emit_startup(event_ts=NOW, device_id=D1)

        assert result.outcome == ingest.OUTCOME_ACTIVATED
        assert _state(D1)["is_active"] is True

    def test_c_startup_activation_preserves_existing_audit_behaviour(self):
        """C, continued: the system-originated RTL_ACTIVATED audit row
        still exists, unchanged from INGEST-1I."""
        from config import audit as audit_cfg

        sim.emit_startup(event_ts=NOW, device_id=D1)

        with session_scope() as session:
            rows = session.execute(
                text(
                    f"SELECT operation, user_id FROM {repo._SCHEMA}.audit_log"
                )
            ).all()
        assert len(rows) == 1
        assert rows[0][0] == audit_cfg.RTL_ACTIVATED
        assert rows[0][1] is None  # ACT-D5: system-originated, no human actor

    def test_d_repeated_startup_is_history_only_not_re_activated(self):
        """D. ACT-D3 idempotency, exercised through the simulator: a second
        startup on an already-active device persists a history row and
        churns nothing."""
        sim.emit_startup(event_ts=NOW, device_id=D1)
        frozen_state = _state(D1)

        second = sim.emit_startup(event_ts=NOW + timedelta(hours=1), device_id=D1)

        assert second.outcome == ingest.OUTCOME_ALREADY_ACTIVE
        assert _event_count() == 2       # both persisted (append-only)
        assert _state(D1) == frozen_state

    def test_e_check_in_persists_without_activation(self):
        """E. Check-in is a supported non-activation event: it persists,
        and does NOT invent activation behaviour."""
        assert _state(D1) is None

        result = sim.emit_check_in(event_ts=NOW, device_id=D1)

        assert result.outcome == ingest.OUTCOME_RECORDED
        assert _state(D1) is None  # never activated by a non-startup type
        row = repo.get_device_event(result.event_id)
        assert row["event_type"] == EVENT_TYPE_CHECK_IN

    def test_f_unregistered_uid_quarantines_exactly_as_before(self):
        """F. Existing invalid_uid behaviour preserved: no device is
        created, the row is stored unresolved."""
        result = sim.emit_startup(event_ts=NOW, reported_uid="unregistered-999")

        assert result.outcome == ingest.OUTCOME_UNRESOLVED_UID
        row = repo.get_device_event(result.event_id)
        assert row["event_type"] == EVENT_TYPE_INVALID_UID
        assert row["reported_uid"] == "unregistered-999"
        assert row["device_id"] is None
        assert _state(D1) is None
        # No device was silently created for the unknown UID.
        with session_scope() as session:
            count = session.execute(
                text(f"SELECT COUNT(*) FROM {repo._SCHEMA}.devices")
            ).scalar_one()
        assert count == 1  # only D1, seeded above


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestSimulatorRefusesUnsupportedOrMalformedInput:
    def setup_method(self):
        _wipe()
        _seed()

    def test_g_unsupported_event_type_is_refused_before_any_persistence(self):
        """G. The simulator's own allowlist refuses an event type outside
        SUPPORTED_EVENT_TYPES — no row is written."""
        with pytest.raises(sim.UnsupportedSimulatedEventType):
            sim.emit("high_temperature", event_ts=NOW, device_id=D1)

        assert _event_count() == 0

    def test_g_canonical_service_still_accepts_the_same_type_directly(self):
        """Confirms G is a simulator-only restriction, not a change to the
        canonical service's open-vocabulary policy (INGEST-D7) — the exact
        type refused above still persists via ingest_event() directly."""
        result = ingest.ingest_event(
            ingest.NormalizedEvent(
                event_type="high_temperature", event_ts=NOW, device_id=D1
            )
        )
        assert result.outcome == ingest.OUTCOME_RECORDED
        assert _event_count() == 1

    def test_h_naive_timestamp_is_rejected_safely(self):
        """H. Malformed input (a naive datetime) fails inside the
        canonical _validate(), not silently accepted by the simulator."""
        naive = datetime(2026, 9, 4, 12, 0, 0)  # no tzinfo
        with pytest.raises(ingest.IngestError):
            sim.emit_startup(event_ts=naive, device_id=D1)

        assert _event_count() == 0

    def test_h_non_string_device_id_is_rejected_safely(self):
        """H. A malformed device_id type fails the same canonical check
        any other caller would hit."""
        with pytest.raises(ingest.IngestError):
            sim.emit_startup(event_ts=NOW, device_id=12345)

        assert _event_count() == 0

    def test_h_event_with_no_attribution_at_all_is_rejected(self):
        """H. Mirrors ck_device_events_attribution: no device_id,
        transformer_id, or reported_uid at all is refused before any
        database access."""
        with pytest.raises(ingest.IngestError):
            sim.emit_check_in(event_ts=NOW)

        assert _event_count() == 0


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestExistingConsumersSeeSimulatedEventsUnchanged:
    """I. notification_service / event_semantics / report_service consume
    simulated events exactly as they consume any other persisted event —
    no rewrite of any consumer."""

    def setup_method(self):
        _wipe()
        _seed()

    def test_simulated_battery_low_reaches_the_notification_center(self):
        sim.emit_battery_low(event_ts=NOW, device_id=D1, battery_voltage=3.4)

        result = current_notifications(
            reading_rows=[], scope=DeviceScope(device_ids=None),
            now=NOW + timedelta(minutes=5),
        )

        assert [r.key for r in result] == [f"battery_alarm:{D1}"]

    def test_simulated_battery_low_reaches_the_rtl_alarms_report(self):
        sim.emit_battery_low(event_ts=NOW, device_id=D1, battery_voltage=3.4)

        rows = rtl_alarms_30d_rows(
            device_scope=DeviceScope(device_ids=None),
            now=NOW + timedelta(minutes=5),
        )

        assert len(rows) == 1
        assert rows[0].battery_voltage == 3.4
        assert rows[0].alarm_label

    def test_simulated_startup_reaches_the_notification_center(self):
        sim.emit_startup(event_ts=NOW, device_id=D1)

        result = current_notifications(
            reading_rows=[], scope=DeviceScope(device_ids=None),
            now=NOW + timedelta(minutes=5),
        )

        assert [r.key for r in result] == [f"startup_checkin:{D1}"]


class TestNoBrowserAuthorizationSurfaceIntroduced:
    """L. Nothing in callbacks/ or pages/ references the simulator modules
    — no callback wiring, no UI, no new authorization surface."""

    def test_simulated_event_source_is_not_imported_by_ui_layers(self):
        import pathlib

        project_root = pathlib.Path(__file__).resolve().parent.parent
        for package in ("callbacks", "pages", "components"):
            for path in (project_root / package).rglob("*.py"):
                text_content = path.read_text(encoding="utf-8")
                assert "simulated_event_source" not in text_content, path
                assert "simulator_transport" not in text_content, path
                assert "rtl_command_dispatch_service" not in text_content, path
