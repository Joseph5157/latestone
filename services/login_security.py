"""Sign-in bookkeeping: throttling and audit (ADR-033).

The database side effects around a sign-in attempt, kept apart from
`auth_service.check_credentials` (a pure verdict) so the verdict stays testable
without a database and the side effects have one home.

THROTTLING is keyed on a hash of the normalised login name typed — not on the
account — so a name that does not exist is throttled exactly like one that
does and the lock reveals nothing about which names exist. After
`throttle_threshold` consecutive failures the key is refused for a bounded,
doubling back-off (capped at `throttle_max_seconds`); the count forgets itself
after `throttle_forget_minutes` and is cleared by a successful sign-in. There
is never a permanent lockout, so no recovery needs database surgery.

AUDIT never records the typed text (it may be a mistyped password), a hash or a
token. A failed attempt against a real account is recorded against that
account; against an unknown name it is recorded as ``unknown``.
"""
from __future__ import annotations

import logging

from config import audit as audit_cfg
from config.settings import auth_settings
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import audit_service
from services import credentials as credentials_mod

logger = logging.getLogger(__name__)

UNKNOWN_ENTITY_ID = "unknown"


def locked_seconds(username: str | None) -> int:
    """Seconds until this login name may try again; 0 = free to try."""
    return repo.get_throttle_lock_seconds(credentials_mod.throttle_key(username))


def register_failure(username: str | None, *, user_id: int | None, reason: str) -> None:
    """Count a failed attempt and audit it (plus one audit row when the lock
    engages). Never raises to the caller: a bookkeeping fault must not turn a
    refusal into an error page or, worse, a success."""
    try:
        count, newly_locked = repo.record_login_failure(
            credentials_mod.throttle_key(username),
            threshold=auth_settings.throttle_threshold,
            base_seconds=auth_settings.throttle_base_seconds,
            max_seconds=auth_settings.throttle_max_seconds,
            forget_seconds=auth_settings.throttle_forget_minutes * 60,
        )
        entity_id = str(user_id) if user_id is not None else UNKNOWN_ENTITY_ID
        with session_scope() as session:
            audit_service.record(
                session,
                operation=audit_cfg.LOGIN_FAILED,
                entity_type=audit_cfg.ENTITY_USER,
                entity_id=entity_id,
                new_values={"reason": reason, "consecutive_failures": count},
                actor_user_id=None,
                system_originated=True,
            )
            if newly_locked:
                audit_service.record(
                    session,
                    operation=audit_cfg.LOGIN_THROTTLED,
                    entity_type=audit_cfg.ENTITY_USER,
                    entity_id=entity_id,
                    new_values={"consecutive_failures": count},
                    actor_user_id=None,
                    system_originated=True,
                )
    except Exception:
        logger.exception("Could not record a failed sign-in")


def register_success(username: str | None, user_id: int) -> None:
    """Clear the throttle, stamp last login and audit the sign-in.

    Raises on failure: a sign-in that cannot be audited is refused (the
    caller treats any exception as a refusal), consistent with the AUD-1 rule
    that an unaudited privileged action does not proceed.
    """
    repo.clear_login_throttle(credentials_mod.throttle_key(username))
    with session_scope() as session:
        repo.touch_last_login(session, user_id)
        audit_service.record(
            session,
            operation=audit_cfg.LOGIN_SUCCEEDED,
            entity_type=audit_cfg.ENTITY_USER,
            entity_id=str(user_id),
            actor_user_id=user_id,
        )


def register_logout(user_id: int) -> None:
    """Audit a sign-out. Never raises: signing out must always complete."""
    try:
        with session_scope() as session:
            audit_service.record(
                session,
                operation=audit_cfg.LOGOUT,
                entity_type=audit_cfg.ENTITY_USER,
                entity_id=str(user_id),
                actor_user_id=user_id,
            )
    except Exception:
        logger.exception("Could not audit a sign-out")
