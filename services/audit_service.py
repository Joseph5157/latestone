"""Audit service (AUD-1) — the single composition point for audit writes.

Layering contract:

    callback → domain service → session_scope()
                                   ├── repo mutation(session=s)
                                   └── audit_service.record(s, ...)
                                single COMMIT / ROLLBACK BOTH

``record`` NEVER opens or commits a transaction of its own: it exists to
participate in the caller's transaction, so a failed audit write rolls the
primary mutation back with it (approved AUD-1 architecture). Raw audit SQL
lives only in repositories.plant_monitoring_repository.insert_audit_log.

Strict actor rule (review decision D2): UI mutations must pass the
authenticated session's ``user_id`` — never a username for re-resolution,
never None. A missing/invalid actor fails the whole operation; NULL user_id
in audit_log stays reserved for explicitly system-originated operations
(ACT-D5, INGEST-D6): ``record(..., system_originated=True)`` requires
``actor_user_id=None`` AND an operation in ``config.audit.SYSTEM_OPERATIONS``
— a deliberately minimal allowlist, so the human strict-actor invariant is
untouched by default and no synthetic system user exists.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from repositories import plant_monitoring_repository as repo
from config import audit as audit_cfg


class AuditError(Exception):
    """Audit recording failed; the surrounding operation must not proceed."""


def _jsonable(value):
    """Coerce the few non-JSON-native primitives we allow into payloads."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _sanitize(payload: dict | None) -> dict | None:
    if payload is None:
        return None
    return {key: _jsonable(val) for key, val in payload.items()}


def record(
    session: Session,
    *,
    operation: str,
    entity_type: str,
    entity_id: str,
    old_values: dict | None = None,
    new_values: dict | None = None,
    actor_user_id: int | None,
    system_originated: bool = False,
) -> None:
    """Write one audit row inside ``session``'s open transaction.

    Human-originated path (the default): raises AuditError when the actor
    is missing/malformed (strict D2) so the caller's service can fail the
    operation before anything commits.

    System-originated path (``system_originated=True``, ACT-D5): the actor
    must be exactly ``None`` — passing a real user id is rejected so a
    system action can never be misattributed to a human — and the
    operation must be in ``config.audit.SYSTEM_OPERATIONS``. There is no
    synthetic system user; user_id simply stays NULL.

    Database-level failures (unknown FK, serialization) propagate from the
    INSERT and roll back the enclosing transaction the same way.
    """
    if system_originated:
        if actor_user_id is not None:
            raise AuditError(
                f"{operation} is system-originated and must not carry a "
                "human actor_user_id."
            )
        if operation not in audit_cfg.SYSTEM_OPERATIONS:
            raise AuditError(
                f"{operation} is not an approved system-originated "
                "operation; extend config.audit.SYSTEM_OPERATIONS "
                "deliberately, never by accident."
            )
    elif not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise AuditError(
            f"{operation} requires an authenticated actor_user_id "
            "(audit trail cannot record this action without one)."
        )
    if not isinstance(entity_id, str) or not entity_id:
        raise AuditError(f"{operation} requires a stable string entity_id.")
    try:
        repo.insert_audit_log(
            operation=operation,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=_sanitize(old_values),
            new_values=_sanitize(new_values),
            actor_user_id=actor_user_id,
            session=session,
        )
    except AuditError:
        raise
    except Exception as exc:
        raise AuditError(
            f"Failed to record audit entry for {operation}; "
            "the operation was not applied."
        ) from exc


__all__ = ["AuditError", "record"]
