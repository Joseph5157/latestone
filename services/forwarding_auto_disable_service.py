"""BR016 daily auto-disable of message forwarding (C08-AUTO-DISABLE-1).

Development baseline (docs/context/ACTIVE_GATE.md, C08-BASELINE-1) — pending
client confirmation, not a confirmed Eskom/client answer:

- This application owns BR016's cutoff, not the RTL Master.
- Default cutoff 18:30 Africa/Johannesburg (config/forwarding_schedule.py).
- At the cutoff, EVERY user whose forwarding is currently enabled is
  disabled — no per-user or per-RTL scoping.
- An Administrator may set exactly ONE global, same-day-only override of the
  cutoff time, with a mandatory reason. It expires automatically: it only
  ever applies to the date it was set for, and the default resumes the next
  day with no action required.
- Every override change and every automatic-disable transition is audited.

Layering (matches message_forwarding_service.py / audit_service.py):

    scheduler entry point -> apply_auto_disable() -> session_scope()
                                 ├── repo.list_enabled_forwarding_user_ids()
                                 ├── repo.set_message_forwarding() per user
                                 └── audit_service.record(system_originated=True) per real transition
                              single COMMIT / ROLLBACK for the whole batch

    admin override control -> set_override()/clear_override() -> session_scope()
                                 ├── repo.set_/clear_auto_disable_override()
                                 └── audit_service.record() (human actor)
                              single COMMIT / ROLLBACK

IDEMPOTENCY (the scheduler architecture decision in ACTIVE_GATE.md): this
module keeps no "have I already run today" flag. ``apply_auto_disable`` may
be invoked on any cadence, any number of times:

- Before the cutoff, it does nothing.
- At or after the cutoff, it disables every currently-enabled user. A repeat
  call the same day finds them already disabled — ``set_message_forwarding``
  itself treats that as FWD-D3's same-state no-op, so nothing is written and
  nothing is re-audited.
- Once local calendar time rolls past midnight, "now" is before the cutoff
  again, so the function goes back to doing nothing until the next cutoff —
  no explicit day-rollover logic exists because none is needed.

This is why no timer must run inside a Dash/Gunicorn worker: any external
scheduler (cron, a Railway scheduled job, ...) calling this on any cadence
gets the same correct outcome.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from config import audit as audit_cfg
from config.forwarding_schedule import DEFAULT_CUTOFF_TIME, TIMEZONE
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import audit_service

logger = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class AutoDisableError(Exception):
    """An override change failed for a reason safe to show the user."""


@dataclass(frozen=True)
class OverrideState:
    """The admin-facing view of the current override, if any."""

    override_date: date
    cutoff_time: time
    reason: str
    set_by_user_id: int
    set_at: datetime


@dataclass(frozen=True)
class AutoDisableResult:
    """What one ``apply_auto_disable`` invocation did.

    ``ran`` is True whenever the cutoff had passed and the bulk-disable path
    executed — even if ``disabled_user_ids`` ends up empty because nobody
    was enabled, or everybody was already disabled by an earlier call today.
    """

    ran: bool
    disabled_user_ids: tuple[int, ...]
    effective_cutoff: time
    local_now: datetime


def parse_cutoff_time(raw: str) -> time:
    """Strict "HH:MM" (24-hour) parse, or ``AutoDisableError``.

    Deliberately narrower than ``datetime.strptime`` alone would enforce:
    that accepts "9:5" or "09:30:00" as well, and a cutoff time is exactly
    the kind of value where a slightly-malformed input silently doing
    something other than what an administrator typed would be a bad outage
    waiting to happen.
    """
    candidate = (raw or "").strip()
    match = _TIME_RE.match(candidate)
    if not match:
        raise AutoDisableError(
            'Cutoff time must be in 24-hour "HH:MM" format, e.g. "18:30".'
        )
    return time(int(match.group(1)), int(match.group(2)))


def _to_override_state(record: repo.AutoDisableOverrideRecord) -> OverrideState:
    return OverrideState(
        override_date=record.override_date,
        cutoff_time=record.cutoff_time,
        reason=record.reason,
        set_by_user_id=record.set_by_user_id,
        set_at=record.set_at,
    )


def _override_snapshot(record: repo.AutoDisableOverrideRecord | None) -> dict | None:
    if record is None:
        return None
    return {
        "override_date": record.override_date,
        "cutoff_time": record.cutoff_time.isoformat(),
        "reason": record.reason,
        "set_by_user_id": record.set_by_user_id,
    }


def _local_now(now: datetime | None) -> datetime:
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise AutoDisableError(
            "apply_auto_disable requires a timezone-aware `now`; a naive "
            "datetime cannot be safely converted to Africa/Johannesburg."
        )
    return now.astimezone(TIMEZONE)


def get_current_override() -> OverrideState | None:
    """The current override row, whether or not it still applies to today.

    Callers that care whether it is still IN EFFECT must compare
    ``override_date`` to today's Africa/Johannesburg date themselves (or use
    ``effective_cutoff_for``, which already does).
    """
    record = repo.get_auto_disable_override()
    return _to_override_state(record) if record else None


def effective_cutoff_for(local_date: date) -> time:
    """The cutoff that applies on ``local_date`` (Africa/Johannesburg).

    An override only ever applies to the exact date it was set for — this is
    the entire mechanism behind "expires automatically... normal 18:30
    resumes next day": there is no separate expiry step, just a date that no
    longer matches.
    """
    override = repo.get_auto_disable_override()
    if override is not None and override.override_date == local_date:
        return override.cutoff_time
    return DEFAULT_CUTOFF_TIME


def apply_auto_disable(now: datetime | None = None) -> AutoDisableResult:
    """Disable forwarding for every enabled user, if the cutoff has passed.

    Safe to call on any schedule, any number of times — see the module
    docstring's IDEMPOTENCY section. ``now`` defaults to the real current
    time; tests pass an explicit timezone-aware value instead of monkeypatch
    -ing the clock.
    """
    local_now = _local_now(now)
    cutoff = effective_cutoff_for(local_now.date())

    if local_now.time() < cutoff:
        return AutoDisableResult(
            ran=False, disabled_user_ids=(), effective_cutoff=cutoff, local_now=local_now
        )

    disabled: list[int] = []
    with session_scope() as session:
        user_ids = repo.list_enabled_forwarding_user_ids(session=session)
        for user_id in user_ids:
            change = repo.set_message_forwarding(user_id, False, session=session)
            if not change.changed:
                # Already disabled by an earlier invocation today (or a
                # concurrent one) — FWD-D3 no-op, nothing to audit.
                continue

            username = None
            user = repo.get_user_by_id(user_id)
            if user is not None:
                username = user.username

            old_snapshot = None
            if change.previous is not None:
                old_snapshot = {
                    "username": username,
                    "enabled": change.previous.enabled,
                    "enabled_at": change.previous.enabled_at,
                    "disabled_at": change.previous.disabled_at,
                }
            new_snapshot = {
                "username": username,
                "enabled": change.current.enabled,
                "enabled_at": change.current.enabled_at,
                "disabled_at": change.current.disabled_at,
            }
            audit_service.record(
                session,
                operation=audit_cfg.MESSAGE_FORWARDING_DISABLED,
                entity_type=audit_cfg.ENTITY_MESSAGE_FORWARDING,
                entity_id=str(user_id),
                old_values=old_snapshot,
                new_values=new_snapshot,
                actor_user_id=None,
                system_originated=True,
            )
            disabled.append(user_id)

    return AutoDisableResult(
        ran=True,
        disabled_user_ids=tuple(disabled),
        effective_cutoff=cutoff,
        local_now=local_now,
    )


def set_override(
    *, cutoff_time: time, reason: str, actor_user_id: int, today: date | None = None
) -> OverrideState:
    """Set today's global override.

    Same-state re-application (identical date/cutoff/reason as what is
    already set) is a genuine no-op — mirrors forwarding's FWD-D3 rule:
    nothing is written, nothing is audited, and ``set_by_user_id``/``set_at``
    stay whatever they already were. Changing the cutoff or the reason is
    always a real transition and is always audited, regardless of who makes
    the change.

    ``today`` is exposed for tests; callers otherwise get the real
    Africa/Johannesburg date, matching what ``apply_auto_disable`` will
    itself compute.
    """
    if not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise AutoDisableError(
            "Setting an override requires an authenticated administrator."
        )
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise AutoDisableError(
            "A reason is required to override the auto-disable cutoff."
        )
    if today is None:
        today = datetime.now(timezone.utc).astimezone(TIMEZONE).date()

    try:
        with session_scope() as session:
            change = repo.set_auto_disable_override(
                override_date=today,
                cutoff_time=cutoff_time,
                reason=clean_reason,
                set_by_user_id=actor_user_id,
                session=session,
            )
            if change.changed:
                audit_service.record(
                    session,
                    operation=audit_cfg.AUTO_DISABLE_OVERRIDE_SET,
                    entity_type=audit_cfg.ENTITY_AUTO_DISABLE_SCHEDULE,
                    entity_id=audit_cfg.AUTO_DISABLE_SCHEDULE_ENTITY_ID,
                    old_values=_override_snapshot(change.previous),
                    new_values=_override_snapshot(change.current),
                    actor_user_id=actor_user_id,
                )
            return _to_override_state(change.current)
    except AutoDisableError:
        raise
    except Exception as exc:
        logger.exception("Failed to set auto-disable override for actor %s", actor_user_id)
        raise AutoDisableError(
            "The override could not be saved. Please try again."
        ) from exc


def clear_override(*, actor_user_id: int) -> OverrideState | None:
    """Clear the current override before it naturally expires.

    Returns the override that was cleared, or None if nothing was set — a
    genuine no-op (mirrors FWD-D2): nothing is deleted, nothing is audited.
    """
    if not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise AutoDisableError(
            "Clearing an override requires an authenticated administrator."
        )

    try:
        with session_scope() as session:
            previous = repo.clear_auto_disable_override(session=session)
            if previous is None:
                return None
            audit_service.record(
                session,
                operation=audit_cfg.AUTO_DISABLE_OVERRIDE_CLEARED,
                entity_type=audit_cfg.ENTITY_AUTO_DISABLE_SCHEDULE,
                entity_id=audit_cfg.AUTO_DISABLE_SCHEDULE_ENTITY_ID,
                old_values=_override_snapshot(previous),
                new_values=None,
                actor_user_id=actor_user_id,
            )
            return _to_override_state(previous)
    except AutoDisableError:
        raise
    except Exception as exc:
        logger.exception("Failed to clear auto-disable override for actor %s", actor_user_id)
        raise AutoDisableError(
            "The override could not be cleared. Please try again."
        ) from exc
