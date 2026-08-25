"""INGEST-1I canonical ingestion end-to-end tests — INGEST-D1..D10 frozen.

Covers the full service path: shape validation, conservative identity
resolution (including the composite/ambiguous UID cases), append-only
persistence, the startup activation projection, ACT-D3 no-op, and
INGEST-D5 transaction atomicity.

Database-backed suites run against the module-scoped isolated_schema
(tests/conftest.py), never the real plant_monitoring tables.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from config import audit as audit_cfg
from config.events import EVENT_TYPE_INVALID_UID, EVENT_TYPE_STARTUP
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import device_event_service as ingest


TS_A = datetime(2026, 8, 25, 6, 0, 0, tzinfo=timezone.utc)
TS_B = datetime(2026, 8, 25, 7, 30, 0, tzinfo=timezone.utc)

PLANT = "ing-p1"
T1 = "ing-p1-t1"
T2 = "ing-p1-t2"
D1 = f"d-{T1}"   # code 29101 under t1
D2 = f"d-{T2}"   # SAME code 29101 under t2 — legal by schema


def _wipe() -> None:
    with session_scope() as session:
        for table in (
            "audit_log", "device_events", "rtl_active_state",
            "rtl_programming_requests", "message_forwarding",
            "user_device_assignments", "readings",
            "devices", "transformers", "plants", "users",
        ):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


def _seed_hierarchy_with_duplicate_codes() -> None:
    """Two transformers each registering device_code 29101 — deliberately
    exercising that device_code is NOT globally unique in the schema."""
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                "(plant_id, name, country, latitude, longitude) "
                f"VALUES ('{PLANT}', 'Ingest Plant', 'Testland', 0, 0)"
            )
        )
        for transformer_id, tcode in ((T1, "t1"), (T2, "t2")):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.transformers "
                    "(transformer_id, plant_id, transformer_code) "
                    f"VALUES ('{transformer_id}', '{PLANT}', :code)"
                ),
                {"code": tcode},
            )
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    "(device_id, transformer_id, device_code) "
                    f"VALUES ('d-{transformer_id}', '{transformer_id}', '29101')"
                )
            )


def _event_row(event_id: int) -> dict | None:
    return repo.get_device_event(event_id)


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
    return {
        "is_active": bool(row[1]),
        "activated_at": row[2],
        "deactivated_at": row[3],
        "updated_at": row[4],
    }


def _event_count() -> int:
    with session_scope() as session:
        return session.execute(
            text(f"SELECT COUNT(*) FROM {repo._SCHEMA}.device_events")
        ).scalar_one()


def _audit_rows() -> list[dict]:
    with session_scope() as session:
        rows = session.execute(
            text(
                f"SELECT operation, user_id, entity_type, entity_id "
                f"FROM {repo._SCHEMA}.audit_log ORDER BY audit_id"
            )
        ).mappings().fetchall()
    return [dict(r) for r in rows]


def _startup(**overrides) -> ingest.NormalizedEvent:
    base = dict(
        event_type=EVENT_TYPE_STARTUP,
        event_ts=TS_A,
        reported_uid="29101",
        source="test-transport",
    )
    base.update(overrides)
    return ingest.NormalizedEvent(**base)


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestIdentityResolution:
    def setup_method(self):
        _wipe()
        _seed_hierarchy_with_duplicate_codes()

    def test_trusted_device_id_resolves_and_activates(self):
        result = ingest.ingest_event(_startup(device_id=D1))

        assert result.outcome == ingest.OUTCOME_ACTIVATED
        assert result.resolved_device_id == D1
        assert _state(D1)["is_active"] is True

    def test_unregistered_trusted_device_id_is_rejected(self):
        """INGEST-D2: an explicit id is honoured only when registered;
        nothing is persisted."""
        with pytest.raises(ingest.IngestError):
            ingest.ingest_event(_startup(device_id="not-registered"))

        assert _event_count() == 0
        assert _state(D1) is None

    def test_composite_uid_and_transformer_resolves(self):
        """UID + transformer → the composite identity, unique by schema."""
        result = ingest.ingest_event(
            _startup(transformer_id=T2, reported_uid="29101")
        )

        assert result.outcome == ingest.OUTCOME_ACTIVATED
        assert result.resolved_device_id == D2
        assert _state(D2)["is_active"] is True

    def test_ambiguous_uid_never_selects_a_device(self):
        """INGEST-D2 (frozen revision): UID alone matching MULTIPLE devices
        must never choose the first match and never activate."""
        result = ingest.ingest_event(_startup(reported_uid="29101"))

        assert result.outcome == ingest.OUTCOME_AMBIGUOUS_UID
        row = _event_row(result.event_id)
        assert row["event_type"] == EVENT_TYPE_STARTUP   # declared type kept
        assert row["reported_uid"] == "29101"
        assert row["device_id"] is None                  # unresolved
        assert _state(D1) is None and _state(D2) is None
        assert _audit_rows() == []

    def test_unknown_uid_quarantines_as_invalid_uid(self):
        """Zero matches → legacy invalid_uid semantics; UID preserved."""
        result = ingest.ingest_event(_startup(reported_uid="99999"))

        assert result.outcome == ingest.OUTCOME_UNRESOLVED_UID
        row = _event_row(result.event_id)
        assert row["event_type"] == EVENT_TYPE_INVALID_UID
        assert row["reported_uid"] == "99999"
        assert row["device_id"] is None
        assert _state(D1) is None
        assert _audit_rows() == []


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestStartupProjection:
    def setup_method(self):
        _wipe()
        _seed_hierarchy_with_duplicate_codes()

    def test_first_startup_activation_audits_once_with_null_actor(self):
        result = ingest.ingest_event(_startup(device_id=D1))

        rows = _audit_rows()
        assert len(rows) == 1
        assert rows[0]["operation"] == audit_cfg.RTL_ACTIVATED
        assert rows[0]["user_id"] is None               # ACT-D5
        assert rows[0]["entity_id"] == D1

        assert result.activated_at is not None
        assert _state(D1)["activated_at"] == result.activated_at

    def test_repeat_startup_on_active_device_is_history_only(self):
        """ACT-D3: second startup persists an event but churns nothing and
        audits nothing."""
        first = ingest.ingest_event(_startup(device_id=D1))
        frozen_state = _state(D1)
        audit_after_first = _audit_rows()

        second = ingest.ingest_event(_startup(device_id=D1, event_ts=TS_B))

        assert second.outcome == ingest.OUTCOME_ALREADY_ACTIVE
        assert _event_count() == 2                      # history kept
        assert _state(D1) == frozen_state               # zero churn
        assert _audit_rows() == audit_after_first       # no duplicate audit

    def test_non_startup_events_persist_without_side_effects(self):
        """INGEST-D7: open vocabulary persists; only startup has effects."""
        check_in = ingest.NormalizedEvent(
            event_type="check_in", event_ts=TS_B, reported_uid="29101"
        )
        result = ingest.ingest_event(check_in)

        assert result.outcome == ingest.OUTCOME_AMBIGUOUS_UID
        # Same event against a uniquely-resolvable attribution still has
        # no side effect unless it is a startup:
        reading = ingest.NormalizedEvent(
            event_type="check_in", event_ts=TS_B, device_id=D1
        )
        recorded = ingest.ingest_event(reading)
        assert recorded.outcome == ingest.OUTCOME_RECORDED
        assert recorded.resolved_device_id == D1
        assert _state(D1) is None                       # never activated
        assert _audit_rows() == []

    def test_transformer_only_event_persists_attributed_to_transformer(self):
        event = ingest.NormalizedEvent(
            event_type="comms_alarm", event_ts=TS_A, transformer_id=T1
        )
        result = ingest.ingest_event(event)

        assert result.outcome == ingest.OUTCOME_RECORDED
        row = _event_row(result.event_id)
        assert row["transformer_id"] == T1
        assert row["device_id"] is None


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestPersistenceSemantics:
    def setup_method(self):
        _wipe()
        _seed_hierarchy_with_duplicate_codes()

    def test_source_ts_and_db_created_at_are_distinct_clocks(self):
        """INGEST-D4: event_ts stored as given (source clock); created_at
        from the DB ingestion clock."""
        past = datetime(2020, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
        result = ingest.ingest_event(_startup(device_id=D1, event_ts=past))

        row = _event_row(result.event_id)
        assert row["event_ts"] == past                  # trusted as supplied
        assert row["created_at"] is not None
        assert row["created_at"] > past                 # DB clock is later

    def test_payload_scalars_message_and_source_persist(self):
        result = ingest.ingest_event(
            _startup(
                device_id=D1,
                temperature=21.5,
                battery_voltage=3.9,
                message="switch-on at feeder cabinet",
                source="test-transport",
                severity=None,
            )
        )

        row = _event_row(result.event_id)
        assert float(row["temperature"]) == 21.5
        assert float(row["battery_voltage"]) == 3.9
        assert row["message"] == "switch-on at feeder cabinet"
        assert row["source"] == "test-transport"

    def test_append_only_identical_repeats_all_persist(self):
        """INGEST-D3: no dedup — two identical accepted calls insert two
        rows even when every field matches."""
        first = ingest.ingest_event(_startup(device_id=D1))
        second = ingest.ingest_event(_startup(device_id=D1))

        assert first.event_id != second.event_id
        assert _event_count() == 2


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestTransactionAtomicity:
    def setup_method(self):
        _wipe()
        _seed_hierarchy_with_duplicate_codes()

    def test_audit_failure_rolls_back_event_and_activation(
        self, monkeypatch
    ):
        """INGEST-D5: INSERT + activation + audit share one transaction."""

        def explode(**kwargs):
            raise RuntimeError("simulated audit-store outage")

        monkeypatch.setattr(repo, "insert_audit_log", explode)

        with pytest.raises(ingest.IngestError):
            ingest.ingest_event(_startup(device_id=D1))

        # Nothing survived: not the event, not the activation, not the audit.
        assert _event_count() == 0
        assert _state(D1) is None
        assert _audit_rows() == []

    def test_ingest_error_leaves_no_partial_rows_for_unresolved_trusted_id(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            repo, "device_id_registered", lambda *a, **k: False
        )
        with pytest.raises(ingest.IngestError):
            ingest.ingest_event(_startup(device_id=D1))
        assert _event_count() == 0
