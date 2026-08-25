"""RTL deactivation — the persistence boundary crossed by OPS-DEACT-1.

Layering contract (AUD-1 pattern, FWD-D5):

    callback → rtl_deactivation_service → session_scope()
                ├── repo.deactivate_device_active_state(session=s)
                └── audit_service.record(s, ...)   [only on a real change]
              single COMMIT / ROLLBACK BOTH

What is REAL after OPS-DEACT-1: the persisted active-list transition
(is_active true→false), its authorization (upstream, at the action guard),
its audit trail, and reload/read-back from PostgreSQL.

What is deliberately NOT here (DEACT-D4): any activation path, startup-
message ingestion, or RTL Master communication. Deactivating updates THIS
application's active-list record only — no command leaves the system, and
devices.status/assignments/monitoring are untouched (DEACT-D6).

Frozen semantics:

- DEACT-D1  An absent rtl_active_state row means off-list; deactivation of
            an absent row inserts nothing, audits nothing.
- DEACT-D2  Already-inactive rows are an idempotent no-op — no timestamp
            churn, no audit event.
- DEACT-D3  The only mutation is true→false with DB-clock deactivated_at/
            updated_at and preserved activated_at.
- DEACT-D5  Audit entity ("device", device_id); old/new payloads carry the
            previous/new is_active + deactivated_at. Audits exist only for
            genuine transitions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import audit_service

logger = logging.getLogger(__name__)


class DeactivationError(Exception):
    """A deactivation failed for a reason safe to show the user."""


#: Outcome vocabulary for the callback's three truthful panels.
OUTCOME_DEACTIVATED = "deactivated"
OUTCOME_NOT_ON_ACTIVE_LIST = "not_on_active_list"
OUTCOME_ALREADY_INACTIVE = "already_inactive"


@dataclass(frozen=True)
class DeactivationResult:
    """The user-facing view of one deactivation attempt."""

    outcome: str
    deactivated_at: datetime | None


def deactivate_rtl(*, device_id: str, actor_user_id: int) -> DeactivationResult:
    """Apply one active-list deactivation for ``device_id`` and audit it.

    Strict D2: ``actor_user_id`` must be the authenticated session's id —
    a missing or malformed actor fails the whole operation before any
    database access. Authorization already happened upstream at the guard;
    this check only guarantees an authenticated identity to persist with.
    """
    if not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise DeactivationError(
            "Deactivating an RTL requires an authenticated account."
        )

    try:
        with session_scope() as session:
            change = repo.deactivate_device_active_state(
                device_id, session=session
            )

            if change.changed:
                # Same transaction as the update: a failed audit write
                # rolls the state change back with it (FWD-D5 atomicity).
                audit_service.record(
                    session,
                    operation=audit_cfg.RTL_DEACTIVATED,
                    entity_type=audit_cfg.ENTITY_DEVICE,
                    entity_id=device_id,
                    old_values={
                        "is_active": True,
                        "deactivated_at": (
                            change.previous.deactivated_at
                            if change.previous is not None
                            else None
                        ),
                    },
                    new_values={
                        "is_active": False,
                        "deactivated_at": change.current.deactivated_at,
                    },
                    actor_user_id=actor_user_id,
                )
                outcome = OUTCOME_DEACTIVATED
            elif change.previous is None:
                # DEACT-D1: absence IS the off-list state; nothing changed.
                outcome = OUTCOME_NOT_ON_ACTIVE_LIST
            else:
                # DEACT-D2: idempotent re-application; nothing changed.
                outcome = OUTCOME_ALREADY_INACTIVE

            return DeactivationResult(
                outcome=outcome,
                deactivated_at=(
                    change.current.deactivated_at if change.current else None
                ),
            )
    except Exception as exc:
        logger.exception("Failed to deactivate RTL %s", device_id)
        raise DeactivationError(
            "The deactivation could not be recorded. Please try again."
        ) from exc


__all__ = [
    "DeactivationError",
    "DeactivationResult",
    "OUTCOME_ALREADY_INACTIVE",
    "OUTCOME_DEACTIVATED",
    "OUTCOME_NOT_ON_ACTIVE_LIST",
    "deactivate_rtl",
]
