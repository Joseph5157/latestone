"""Administrator-configurable global freshness (Stale-after) threshold
(FRESHNESS-CONFIG-1).

Same shape as ``temperature_threshold_service`` — singleton row, UNCONFIGURED
IS ABSENCE, audited set/clear in one transaction — with one deliberate
difference: this value is read back LIVE. ``effective_stale_after_minutes()``
is what ``monitoring_service.evaluate_freshness`` uses, so a saved change
alters what counts as Stale across the whole dashboard.

With no configured row the environment-derived default applies
(``config.settings.monitoring.stale_after_minutes``, 24 hours unless
``FRESHNESS_STALE_AFTER_MINUTES`` says otherwise).

BR008's formal ">24h no data" notification rule is independent and does not
read this value (FS §17 rule 4).

Resolution cost: ``evaluate_freshness`` runs once per metric per device
(~960 times per fleet render), so the value is resolved at most once per
Flask request and kept on ``flask.g``. That is request-scoped, not process
state: the next request after a Save sees the new value on every worker.
Outside a request (scripts), each call reads the database directly.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from flask import g, has_request_context

from config import audit as audit_cfg
from config.settings import monitoring
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import audit_service

logger = logging.getLogger(__name__)

#: Typo guards, not client-confirmed business thresholds. Below 5 minutes
#: the whole fleet would read Stale between normal reports; above 365 days
#: freshness would effectively be switched off. Migration 015 repeats both
#: bounds as a CHECK constraint.
MIN_MINUTES = 5
MAX_MINUTES = 365 * 24 * 60

_G_KEY = "_effective_stale_after_minutes"


class FreshnessThresholdError(Exception):
    """A change failed for a reason safe to show the user."""


@dataclass(frozen=True)
class FreshnessThresholdState:
    stale_after_minutes: int
    configured_by_user_id: int
    configured_at: datetime


def default_stale_after_minutes() -> int:
    """The environment-derived fallback used when nothing is configured."""
    return monitoring.stale_after_minutes


def _to_state(record: repo.FreshnessThresholdConfigRecord) -> FreshnessThresholdState:
    return FreshnessThresholdState(
        stale_after_minutes=record.stale_after_minutes,
        configured_by_user_id=record.configured_by_user_id,
        configured_at=record.configured_at,
    )


def _snapshot(record: repo.FreshnessThresholdConfigRecord | None) -> dict | None:
    if record is None:
        return None
    return {
        "stale_after_minutes": record.stale_after_minutes,
        "configured_by_user_id": record.configured_by_user_id,
    }


def _validate(minutes) -> int:
    if isinstance(minutes, bool) or not isinstance(minutes, int):
        raise FreshnessThresholdError("The threshold must be a whole number of minutes.")
    if not MIN_MINUTES <= minutes <= MAX_MINUTES:
        raise FreshnessThresholdError(
            f"The threshold must be between {MIN_MINUTES} minutes and "
            f"{MAX_MINUTES:,} minutes (365 days)."
        )
    return minutes


def parse_minutes(raw) -> int:
    """Strict parse of the form value: digits only, no decimals or signs."""
    candidate = str(raw if raw is not None else "").strip()
    if not candidate:
        raise FreshnessThresholdError("Enter a threshold in minutes.")
    if not candidate.isdigit() or not candidate.isascii():
        raise FreshnessThresholdError("The threshold must be a whole number of minutes.")
    return _validate(int(candidate))


def _require_actor(actor_user_id, verb: str) -> None:
    if not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise FreshnessThresholdError(
            f"{verb} the freshness threshold requires an authenticated administrator."
        )


def _forget_request_value() -> None:
    if has_request_context():
        g.pop(_G_KEY, None)


def get_current_config() -> FreshnessThresholdState | None:
    """The configured value, or None when unconfigured."""
    record = repo.get_freshness_threshold_config()
    return _to_state(record) if record else None


def _read_override_minutes() -> int | None:
    record = repo.get_freshness_threshold_config()
    return record.stale_after_minutes if record else None


def _resolve() -> int:
    override = _read_override_minutes()
    return override if override is not None else default_stale_after_minutes()


def effective_stale_after_minutes() -> int:
    """The threshold freshness evaluation must use right now."""
    if not has_request_context():
        return _resolve()
    cached = g.get(_G_KEY)
    if cached is None:
        cached = _resolve()
        setattr(g, _G_KEY, cached)
    return cached


def set_config(*, stale_after_minutes, actor_user_id: int) -> FreshnessThresholdState:
    """Set or change the threshold. Re-applying the current value writes and
    audits nothing."""
    _require_actor(actor_user_id, "Setting")
    minutes = _validate(stale_after_minutes)
    try:
        with session_scope() as session:
            change = repo.set_freshness_threshold_config(
                stale_after_minutes=minutes,
                configured_by_user_id=actor_user_id,
                session=session,
            )
            if change.changed:
                audit_service.record(
                    session,
                    operation=audit_cfg.FRESHNESS_THRESHOLD_SET,
                    entity_type=audit_cfg.ENTITY_FRESHNESS_THRESHOLD,
                    entity_id=audit_cfg.FRESHNESS_THRESHOLD_ENTITY_ID,
                    old_values=_snapshot(change.previous),
                    new_values=_snapshot(change.current),
                    actor_user_id=actor_user_id,
                )
            state = _to_state(change.current)
    except FreshnessThresholdError:
        raise
    except Exception as exc:
        logger.exception("Failed to set freshness threshold for actor %s", actor_user_id)
        raise FreshnessThresholdError(
            "The freshness threshold could not be saved. Please try again."
        ) from exc
    _forget_request_value()
    return state


def clear_config(*, actor_user_id: int) -> FreshnessThresholdState | None:
    """Return to the environment default. Returns what was cleared, or None
    when nothing was configured (a no-op, not audited)."""
    _require_actor(actor_user_id, "Clearing")
    try:
        with session_scope() as session:
            previous = repo.clear_freshness_threshold_config(session=session)
            if previous is not None:
                audit_service.record(
                    session,
                    operation=audit_cfg.FRESHNESS_THRESHOLD_CLEARED,
                    entity_type=audit_cfg.ENTITY_FRESHNESS_THRESHOLD,
                    entity_id=audit_cfg.FRESHNESS_THRESHOLD_ENTITY_ID,
                    old_values=_snapshot(previous),
                    new_values=None,
                    actor_user_id=actor_user_id,
                )
    except FreshnessThresholdError:
        raise
    except Exception as exc:
        logger.exception("Failed to clear freshness threshold for actor %s", actor_user_id)
        raise FreshnessThresholdError(
            "The freshness threshold could not be cleared. Please try again."
        ) from exc
    _forget_request_value()
    return _to_state(previous) if previous is not None else None
