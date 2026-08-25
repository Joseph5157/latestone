"""Device event ingestion — the canonical boundary crossed by INGEST-1I.

Layering contract (AUD-1 pattern, FWD-D5, INGEST-D5):

    [future transport adapter] → NormalizedEvent
                                    → device_event_service.ingest_event()
                                        → session_scope()
                                            ├── repo.insert_device_event(session=s)
                                            ├── repo.activate_device_active_state(session=s)   [startup only]
                                            └── audit_service.record(s, system_originated=True) [real transitions]
                                          single COMMIT / ROLLBACK ALL

What is REAL after INGEST-1I: the persisted normalized event row,
conservative identity resolution, the startup → rtl_active_state
projection (ACT-D1..D7), and its system-originated audit trail.

What is deliberately NOT here (INGEST-D8/D9): any transport (SMS/MQTT/
webhook/poller), deduplication (INGEST-D3), raw-message retention, and all
downstream consumers other than activation.

Identity resolution (INGEST-D2, frozen revision):

    1. trusted explicit device_id  -> exact registered device or reject
    2. reported_uid + transformer  -> composite identity (the schema's only
                                      uniqueness guarantee:
                                      UNIQUE (transformer_id, device_code))
    3. reported_uid alone          -> resolve ONLY on exactly one match;
                                      zero matches quarantine as invalid_uid;
                                      MULTIPLE matches never select a device
                                      and keep their declared type unresolved
    4. transformer_id alone        -> persist attributed to the transformer

An ambiguous UID must never select the first matching device: that protects
ACT-D2 even if duplicate device codes eventually appear under different
transformers. No new event vocabulary is invented for ambiguity — the row
keeps its declared type with reported_uid set and device_id NULL.
"""
from __future__ import annotations

import logging
import numbers
from dataclasses import dataclass
from datetime import datetime

from config import audit as audit_cfg
from config.events import EVENT_TYPE_INVALID_UID, EVENT_TYPE_STARTUP
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import audit_service

logger = logging.getLogger(__name__)


class IngestError(Exception):
    """The event could not be accepted — nothing was persisted.

    A future transport adapter must treat this as "unaccepted" so it can
    retry rather than assume storage (INGEST-D5)."""


#: Event persisted with no domain effect (non-startup types, transformer-
#: only attribution).
OUTCOME_RECORDED = "recorded"
#: Resolved startup caused an absent→active or inactive→active transition.
OUTCOME_ACTIVATED = "activated"
#: Resolved startup on an already-active device: history row only, zero
#: state churn and zero audit rows (ACT-D3).
OUTCOME_ALREADY_ACTIVE = "already_active"
#: Reported UID matched no registered device; stored as invalid_uid.
OUTCOME_UNRESOLVED_UID = "unresolved_uid"
#: Reported UID matched several registered devices; stored unresolved with
#: its declared type — never resolved by arbitrary choice (INGEST-D2).
OUTCOME_AMBIGUOUS_UID = "ambiguous_uid"

_MAX_EVENT_TYPE = 30      # device_events.event_type VARCHAR(30)
_MAX_SEVERITY = 20        # device_events.severity VARCHAR(20)
_MAX_SOURCE = 30          # device_events.source VARCHAR(30)
_MAX_ID = 30              # device_id / transformer_id / reported_uid


@dataclass(frozen=True)
class NormalizedEvent:
    """Canonical application-level input after raw transport parsing.

    Mirrors exactly what migration 006 can persist (INGEST-D1): no JSONB
    raw payload, correlation id or external message id exists in the
    schema, so none is fabricated here. ``event_ts`` MUST be timezone-
    aware (INGEST-D4): it is when the SOURCE says the event occurred;
    PostgreSQL records ingestion time itself in created_at.
    """

    event_type: str
    event_ts: datetime
    device_id: str | None = None
    transformer_id: str | None = None
    reported_uid: str | None = None
    severity: str | None = None
    temperature: float | None = None
    battery_voltage: float | None = None
    message: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class IngestResult:
    """The caller's view of one accepted event."""

    outcome: str
    event_id: int
    resolved_device_id: str | None
    activated_at: datetime | None


@dataclass(frozen=True)
class _Resolution:
    """Internal outcome of identity resolution for one validated event."""

    device_id: str | None
    reported_uid: str | None
    event_type: str          # possibly retyped to invalid_uid (zero matches)
    classification: str      # RESOLVED / UNRESOLVED / AMBIGUOUS / TRANSFORMER


_RESOLUTION_RESOLVED = "resolved"
_RESOLUTION_UNRESOLVED = "unresolved"
_RESOLUTION_AMBIGUOUS = "ambiguous"
_RESOLUTION_TRANSFORMER = "transformer"


def _clean_optional_str(value, *, field: str, max_len: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise IngestError(f"{field} must be a string.")
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > max_len:
        raise IngestError(f"{field} must be at most {max_len} characters.")
    return trimmed


def _clean_optional_number(value, *, field: str):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise IngestError(f"{field} must be a number.")
    return value


def _validate(event: NormalizedEvent) -> NormalizedEvent:
    """Validate the canonical shape before ANY database access."""
    if not isinstance(event, NormalizedEvent):
        raise IngestError("Expected a NormalizedEvent.")

    event_type = _clean_optional_str(
        event.event_type, field="event_type", max_len=_MAX_EVENT_TYPE
    )
    if event_type is None:
        raise IngestError("event_type is required.")

    if not isinstance(event.event_ts, datetime) or isinstance(
        event.event_ts, bool
    ):
        raise IngestError("event_ts must be a datetime.")
    if event.event_ts.tzinfo is None or (
        event.event_ts.utcoffset() is None
    ):
        raise IngestError(
            "event_ts must be timezone-aware (INGEST-D4); naive timestamps "
            "are rejected at the canonical boundary."
        )

    device_id = _clean_optional_str(
        event.device_id, field="device_id", max_len=_MAX_ID
    )
    transformer_id = _clean_optional_str(
        event.transformer_id, field="transformer_id", max_len=_MAX_ID
    )
    reported_uid = _clean_optional_str(
        event.reported_uid, field="reported_uid", max_len=_MAX_ID
    )

    # Mirror ck_device_events_attribution before touching the database.
    if device_id is None and transformer_id is None and reported_uid is None:
        raise IngestError(
            "The event needs at least one of device_id, transformer_id or "
            "reported_uid."
        )

    if event.message is not None and not isinstance(event.message, str):
        raise IngestError("message must be a string.")

    return NormalizedEvent(
        event_type=event_type,
        event_ts=event.event_ts,
        device_id=device_id,
        transformer_id=transformer_id,
        reported_uid=reported_uid,
        severity=_clean_optional_str(
            event.severity, field="severity", max_len=_MAX_SEVERITY
        ),
        temperature=_clean_optional_number(
            event.temperature, field="temperature"
        ),
        battery_voltage=_clean_optional_number(
            event.battery_voltage, field="battery_voltage"
        ),
        message=event.message,
        source=_clean_optional_str(
            event.source, field="source", max_len=_MAX_SOURCE
        ),
    )


def _resolve_identity(event: NormalizedEvent, session) -> _Resolution:
    """Conservative resolution sequence (INGEST-D2). Runs INSIDE the
    caller's transaction using that session, so resolution and persistence
    observe one consistent snapshot."""

    # 1. Trusted explicit device_id: exact registered device or reject.
    if event.device_id is not None:
        if not repo.device_id_registered(event.device_id, session=session):
            raise IngestError(
                f"device_id {event.device_id!r} is not a registered device."
            )
        return _Resolution(
            device_id=event.device_id,
            reported_uid=event.reported_uid,
            event_type=event.event_type,
            classification=_RESOLUTION_RESOLVED,
        )

    uid = event.reported_uid

    # 4. Transformer-only attribution: nothing to resolve.
    if uid is None:
        return _Resolution(
            device_id=None,
            reported_uid=None,
            event_type=event.event_type,
            classification=_RESOLUTION_TRANSFORMER,
        )

    # 2. Composite identity: UNIQUE (transformer_id, device_code) caps the
    # result at exactly one row.
    if event.transformer_id is not None:
        matches = repo.find_device_ids_by_code(
            uid, transformer_id=event.transformer_id, session=session
        )
    else:
        # 3. UID alone: resolve only on EXACTLY ONE match.
        matches = repo.find_device_ids_by_code(uid, session=session)

    if len(matches) == 1:
        return _Resolution(
            device_id=matches[0],
            reported_uid=uid,
            event_type=event.event_type,
            classification=_RESOLUTION_RESOLVED,
        )
    if len(matches) == 0:
        # Legacy invalid_uid_log semantics (migration 006): preserve the
        # reported UID, retype the row, never resolve.
        return _Resolution(
            device_id=None,
            reported_uid=uid,
            event_type=EVENT_TYPE_INVALID_UID,
            classification=_RESOLUTION_UNRESOLVED,
        )
    # Multiple matches: never choose arbitrarily, never activate, and do
    # NOT invent new vocabulary — declared type kept, device_id NULL.
    return _Resolution(
        device_id=None,
        reported_uid=uid,
        event_type=event.event_type,
        classification=_RESOLUTION_AMBIGUOUS,
    )


def ingest_event(event: NormalizedEvent) -> IngestResult:
    """Accept one normalized event: validate, resolve, persist, project.

    INGEST-D5 atomicity: the event INSERT, any startup activation and the
    RTL_ACTIVATED audit share ONE transaction — a failure anywhere rolls
    everything back, so callers can treat an exception as "not accepted".
    Append-only persistence (INGEST-D3): every accepted call inserts a row.
    """
    validated = _validate(event)

    try:
        with session_scope() as session:
            resolution = _resolve_identity(validated, session)

            event_id = repo.insert_device_event(
                event_type=resolution.event_type,
                event_ts=validated.event_ts,
                device_id=resolution.device_id,
                transformer_id=validated.transformer_id,
                reported_uid=resolution.reported_uid,
                severity=validated.severity,
                temperature=validated.temperature,
                battery_voltage=validated.battery_voltage,
                message=validated.message,
                source=validated.source,
                session=session,
            )

            if resolution.classification != _RESOLUTION_RESOLVED:
                return IngestResult(
                    outcome={
                        _RESOLUTION_UNRESOLVED: OUTCOME_UNRESOLVED_UID,
                        _RESOLUTION_AMBIGUOUS: OUTCOME_AMBIGUOUS_UID,
                        _RESOLUTION_TRANSFORMER: OUTCOME_RECORDED,
                    }[resolution.classification],
                    event_id=event_id,
                    resolved_device_id=None,
                    activated_at=None,
                )

            if resolution.event_type != EVENT_TYPE_STARTUP:
                # Persistable open-vocabulary type with a resolved device:
                # no behaviour attached yet (INGEST-D7).
                return IngestResult(
                    outcome=OUTCOME_RECORDED,
                    event_id=event_id,
                    resolved_device_id=resolution.device_id,
                    activated_at=None,
                )

            change = repo.activate_device_active_state(
                resolution.device_id, session=session
            )

            if change.changed:
                # ACT-D5: system-originated — NULL actor, allowlisted op.
                audit_service.record(
                    session,
                    operation=audit_cfg.RTL_ACTIVATED,
                    entity_type=audit_cfg.ENTITY_DEVICE,
                    entity_id=resolution.device_id,
                    old_values=(
                        {
                            "is_active": False,
                            "deactivated_at": (
                                change.previous.deactivated_at
                                if change.previous is not None
                                else None
                            ),
                        }
                        if change.previous is not None
                        else {"is_active": None}
                    ),
                    new_values={
                        "is_active": True,
                        "activated_at": change.current.activated_at,
                    },
                    actor_user_id=None,
                    system_originated=True,
                )

            return IngestResult(
                outcome=(
                    OUTCOME_ACTIVATED
                    if change.changed
                    else OUTCOME_ALREADY_ACTIVE
                ),
                event_id=event_id,
                resolved_device_id=resolution.device_id,
                activated_at=(
                    change.current.activated_at if change.changed else None
                ),
            )
    except IngestError:
        raise
    except Exception as exc:
        logger.exception("Failed to ingest %s event", validated.event_type)
        raise IngestError(
            "The event could not be recorded. Nothing was persisted."
        ) from exc


__all__ = [
    "IngestError",
    "IngestResult",
    "NormalizedEvent",
    "OUTCOME_ACTIVATED",
    "OUTCOME_ALREADY_ACTIVE",
    "OUTCOME_AMBIGUOUS_UID",
    "OUTCOME_RECORDED",
    "OUTCOME_UNRESOLVED_UID",
    "ingest_event",
]
