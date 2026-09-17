"""Message forwarding state — the persistence boundary crossed by OPS-FWD-1.

Layering contract (AUD-1 pattern, FWD-D5):

    callback → message_forwarding_service → session_scope()
                ├── repo.set_message_forwarding(session=s)
                └── audit_service.record(s, ...)
              single COMMIT / ROLLBACK BOTH

What is REAL after OPS-FWD-1: the per-user forwarding preference, its
authorization, its audit trail, and reload/read-back from PostgreSQL.

What is deliberately NOT here (FWD-D9): SMS/message transport, actual
startup/check-in forwarding delivery, and BR016's 18:30 automatic disable.
The Functional Specification assigns that cutoff to the RTL Master; this
dashboard has no scheduler, override, or substitute implementation for it.
Persisting the preference does not mean messages flow yet.

Frozen semantics (review decisions):

- FWD-D1  State is PER USER. The device drawer is only where the action is
  authorized; no device dimension exists in message_forwarding.
- FWD-D2  No row presents as disabled, and "disable" on a rowless account
  is a genuine no-op — no insert, no audit.
- FWD-D3  Same-state re-application is a no-op — no timestamp churn, no
  audit event.
- FWD-D6  Audit entity is ("message_forwarding", str(actor_user_id)); the
  payload allowlist is {username, enabled, enabled_at, disabled_at}.
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


class ForwardingError(Exception):
    """A forwarding change failed for a reason safe to show the user."""


@dataclass(frozen=True)
class ForwardingState:
    """The user-facing view of one account's forwarding state.

    Absence of a database row IS the disabled state (FWD-D2): this type
    collapses that distinction so callbacks never reason about rows.
    """

    user_id: int
    enabled: bool
    enabled_at: datetime | None
    disabled_at: datetime | None


def get_state(user_id: int) -> ForwardingState:
    """Read one account's state for display (drawer prefill, read-back)."""
    record = repo.get_message_forwarding(user_id)
    if record is None:
        return ForwardingState(
            user_id=user_id, enabled=False, enabled_at=None, disabled_at=None
        )
    return ForwardingState(
        user_id=record.user_id,
        enabled=record.enabled,
        enabled_at=record.enabled_at,
        disabled_at=record.disabled_at,
    )


def _snapshot(state: ForwardingState | None, username: str | None) -> dict | None:
    if state is None:
        return None
    return {
        "username": username,
        "enabled": state.enabled,
        "enabled_at": state.enabled_at,
        "disabled_at": state.disabled_at,
    }


def _state_of(record) -> ForwardingState:
    return ForwardingState(
        user_id=record.user_id,
        enabled=record.enabled,
        enabled_at=record.enabled_at,
        disabled_at=record.disabled_at,
    )


def set_forwarding(*, enabled: bool, actor_user_id: int) -> ForwardingState:
    """Apply one forwarding transition for the ACTING USER and audit it.

    Strict D2: ``actor_user_id`` must be the authenticated session's id —
    a missing or malformed actor fails the whole operation before any
    database access. The device context played its part in authorization
    upstream; it has no place in the stored state or the audit entity.
    """
    if not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise ForwardingError(
            "Message forwarding requires an authenticated account."
        )

    try:
        with session_scope() as session:
            change = repo.set_message_forwarding(
                actor_user_id, enabled, session=session
            )

            if change.changed:
                username = None
                user = repo.get_user_by_id(actor_user_id)
                if user is not None:
                    username = user.username

                previous_state = (
                    _state_of(change.previous)
                    if change.previous is not None
                    else None
                )
                current_state = _state_of(change.current)
                audit_service.record(
                    session,
                    operation=(
                        audit_cfg.MESSAGE_FORWARDING_ENABLED
                        if enabled
                        else audit_cfg.MESSAGE_FORWARDING_DISABLED
                    ),
                    entity_type=audit_cfg.ENTITY_MESSAGE_FORWARDING,
                    entity_id=str(actor_user_id),
                    old_values=_snapshot(previous_state, username),
                    new_values=_snapshot(current_state, username),
                    actor_user_id=actor_user_id,
                )
            else:
                # Genuine no-op (FWD-D2/D3): report truthfully from what
                # exists — absence of a row IS the disabled state.
                if change.current is not None:
                    current_state = _state_of(change.current)
                else:
                    current_state = ForwardingState(
                        user_id=actor_user_id,
                        enabled=False,
                        enabled_at=None,
                        disabled_at=None,
                    )

            return current_state
    except Exception as exc:
        logger.exception(
            "Failed to set message forwarding for %s", actor_user_id
        )
        raise ForwardingError(
            "The message forwarding preference could not be saved. "
            "Please try again."
        ) from exc
