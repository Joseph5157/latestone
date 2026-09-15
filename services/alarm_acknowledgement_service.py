"""Internal acknowledgement lifecycle for persisted reportable alarm events.

This service intentionally has no clearance, resolution, delivery, or device
transport behaviour.  An acknowledgement only records who responded to the
existing event and when, in the same transaction as the audit row.
"""
from __future__ import annotations

from dataclasses import dataclass

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import audit_service
from services.device_scope import DeviceScope
from services.event_semantics import semantics_for
from config import audit as audit_cfg


class AlarmAcknowledgementError(Exception):
    """Safe failure for an acknowledgement that cannot be applied."""


@dataclass(frozen=True)
class AlarmAcknowledgementResult:
    """Outcome for the latest alarm event selected from Notification Center."""

    event: repo.DeviceEventRecord
    changed: bool


def acknowledge_alarm(
    *,
    event_id: int,
    actor_user_id: int,
    scope: DeviceScope,
) -> AlarmAcknowledgementResult:
    """Acknowledge one currently visible reportable alarm event.

    The event is read and updated using the same trusted scope.  The explicit
    service check keeps acknowledgement limited to the existing reportable
    alarm semantics rather than turning check-ins, unknown events, or
    freshness-derived notifications into acknowledgements.
    """
    if not isinstance(event_id, int) or isinstance(event_id, bool) or event_id <= 0:
        raise AlarmAcknowledgementError("The selected alarm is not valid.")
    if not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise AlarmAcknowledgementError("An authenticated operator is required.")

    with session_scope() as session:
        event_data = repo.get_device_event(
            event_id,
            session=session,
            allowed_device_ids=scope.device_ids,
        )
        if event_data is None or event_data.get("device_id") is None:
            raise AlarmAcknowledgementError("The selected alarm is not available.")
        if not semantics_for(event_data["event_type"]).is_reportable_alarm:
            raise AlarmAcknowledgementError("The selected event is not an acknowledgeable alarm.")

        if event_data["acknowledged_at"] is not None:
            return AlarmAcknowledgementResult(
                event=repo.DeviceEventRecord(**event_data),
                changed=False,
            )

        changed = repo.acknowledge_device_event(
            event_id,
            actor_user_id=actor_user_id,
            allowed_device_ids=scope.device_ids,
            session=session,
        )
        if changed is None:
            # A concurrent acknowledgement is safe and idempotent. Re-read
            # through the same scope so it never becomes a scope bypass.
            current_data = repo.get_device_event(
                event_id,
                session=session,
                allowed_device_ids=scope.device_ids,
            )
            if current_data is None or current_data["acknowledged_at"] is None:
                raise AlarmAcknowledgementError("The selected alarm is not available.")
            return AlarmAcknowledgementResult(
                event=repo.DeviceEventRecord(**current_data),
                changed=False,
            )

        audit_service.record(
            session,
            operation=audit_cfg.ALARM_ACKNOWLEDGED,
            entity_type=audit_cfg.ENTITY_DEVICE,
            entity_id=changed.device_id,
            old_values={"event_id": event_id, "acknowledged_at": None},
            new_values={
                "event_id": event_id,
                "acknowledged_at": changed.acknowledged_at,
                "acknowledged_by_user_id": actor_user_id,
            },
            actor_user_id=actor_user_id,
        )
        return AlarmAcknowledgementResult(event=changed, changed=True)


__all__ = [
    "AlarmAcknowledgementError",
    "AlarmAcknowledgementResult",
    "acknowledge_alarm",
]
