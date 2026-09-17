"""INGEST-1I pure-logic tests — canonical event shape, vocabulary, and the
system-originated audit API. No database required.

Database-backed behaviour (persistence, activation projection, atomicity)
lives in test_device_event_ingestion_db.py / test_rtl_activation.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from config import audit as audit_cfg
from config.events import EVENT_TYPE_INVALID_UID, EVENT_TYPE_STARTUP
from services import audit_service
from services.device_event_service import (
    IngestError,
    NormalizedEvent,
    _validate,
)

TS = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


def _event(**overrides) -> NormalizedEvent:
    base = dict(
        event_type="startup",
        event_ts=TS,
        reported_uid="29017",
        source="test",
    )
    base.update(overrides)
    return NormalizedEvent(**base)


# ---------------------------------------------------------------------------
# Event vocabulary module (config/events.py — deliberately NOT config.audit)
# ---------------------------------------------------------------------------


class TestEventVocabulary:
    def test_startup_is_the_activation_trigger(self):
        assert EVENT_TYPE_STARTUP == "startup"

    def test_invalid_uid_matches_legacy_name(self):
        """Legacy invalid_uid_log replacement; migration 006 vocabulary."""
        assert EVENT_TYPE_INVALID_UID == "invalid_uid"

    def test_values_fit_the_column_limit(self):
        for value in (EVENT_TYPE_STARTUP, EVENT_TYPE_INVALID_UID):
            assert len(value) <= 30  # device_events.event_type VARCHAR(30)

    def test_event_names_do_not_leak_into_audit_vocabulary(self):
        """config/audit.py is exclusively the audit operation/entity
        vocabulary (review refinement): event constants live elsewhere."""
        assert not hasattr(audit_cfg, "EVENT_TYPE_STARTUP")
        assert not hasattr(audit_cfg, "EVENT_TYPE_INVALID_UID")


# ---------------------------------------------------------------------------
# Canonical normalized-event shape (INGEST-D1/D4)
# ---------------------------------------------------------------------------


class TestNormalizedEventValidation:
    def test_minimal_valid_event_passes(self):
        validated = _validate(_event())
        assert validated.event_type == "startup"
        assert validated.reported_uid == "29017"

    def test_non_datetime_timestamp_rejected(self):
        with pytest.raises(IngestError):
            _validate(_event(event_ts="2026-08-25T12:00:00+00:00"))

    def test_naive_timestamp_rejected(self):
        """INGEST-D4: timezone-aware source time required at the boundary;
        no clock-skew correction is invented instead."""
        naive = datetime(2026, 8, 25, 12, 0, 0)
        with pytest.raises(IngestError):
            _validate(_event(event_ts=naive))

    def test_empty_event_type_rejected(self):
        with pytest.raises(IngestError):
            _validate(_event(event_type="   "))

    def test_overlong_event_type_rejected(self):
        with pytest.raises(IngestError):
            _validate(_event(event_type="x" * 31))

    def test_whitespace_event_type_is_trimmed(self):
        assert _validate(_event(event_type="  startup ")).event_type == "startup"

    @pytest.mark.parametrize(
        "field", ["device_id", "transformer_id", "reported_uid"]
    )
    def test_attribution_fields_bounded_at_thirty(self, field):
        with pytest.raises(IngestError):
            _validate(_event(**{field: "x" * 31}))

    def test_total_absence_of_attribution_rejected_before_database(self):
        """Mirrors ck_device_events_attribution without touching PostgreSQL."""
        with pytest.raises(IngestError):
            _validate(_event(reported_uid=None))

    def test_severity_bounded_at_twenty(self):
        with pytest.raises(IngestError):
            _validate(_event(severity="x" * 21))

    def test_source_bounded_at_thirty(self):
        with pytest.raises(IngestError):
            _validate(_event(source="x" * 31))

    def test_message_must_be_a_string(self):
        with pytest.raises(IngestError):
            _validate(_event(message=123))

    @pytest.mark.parametrize("field", ["temperature", "battery_voltage"])
    def test_measurements_reject_non_numbers(self, field):
        with pytest.raises(IngestError):
            _validate(_event(**{field: "21.5"}))

    @pytest.mark.parametrize("field", ["temperature", "battery_voltage"])
    def test_measurements_reject_bools(self, field):
        """bool is an int subclass; it is never a measurement."""
        with pytest.raises(IngestError):
            _validate(_event(**{field: True}))


# ---------------------------------------------------------------------------
# System-originated audit API (INGEST-D6 / ACT-D5)
# ---------------------------------------------------------------------------


class TestSystemOriginatedAudit:
    def test_allowlist_contains_exactly_the_implemented_system_features(self):
        # RTL_ACTIVATED (INGEST-1) is the only system-originated app feature.
        # BR016 is RTL Master-owned and deliberately not in this allowlist.
        assert audit_cfg.SYSTEM_OPERATIONS == frozenset({audit_cfg.RTL_ACTIVATED})

    def test_rtl_activated_operation_fits_column_limit(self):
        assert len(audit_cfg.RTL_ACTIVATED) <= 50
        assert audit_cfg.RTL_ACTIVATED == "RTL_ACTIVATED"

    def test_system_originated_rejects_a_human_actor(self):
        """ACT-D5: a system action must never be attributed to a user."""
        with pytest.raises(audit_service.AuditError):
            audit_service.record(
                None,  # validation fails before any DB access
                operation=audit_cfg.RTL_ACTIVATED,
                entity_type=audit_cfg.ENTITY_DEVICE,
                entity_id="d1",
                actor_user_id=42,
                system_originated=True,
            )

    def test_system_originated_rejects_unallowlisted_operations(self):
        with pytest.raises(audit_service.AuditError):
            audit_service.record(
                None,
                operation=audit_cfg.DEVICE_REGISTERED,
                entity_type=audit_cfg.ENTITY_DEVICE,
                entity_id="d1",
                actor_user_id=None,
                system_originated=True,
            )


class TestHumanActorInvariantUnchanged:
    """The default path keeps strict D2 exactly as AUD-1 shipped it."""

    @pytest.mark.parametrize("bad_actor", [None, "1", True, 4.0])
    def test_default_record_still_requires_an_integer_actor(self, bad_actor):
        with pytest.raises(audit_service.AuditError):
            audit_service.record(
                None,
                operation=audit_cfg.DEVICE_REGISTERED,
                entity_type=audit_cfg.ENTITY_DEVICE,
                entity_id="d1",
                actor_user_id=bad_actor,
            )
