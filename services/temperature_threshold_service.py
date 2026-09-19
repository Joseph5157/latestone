"""C-01 global temperature warning/critical threshold configuration
(THRESH-CONFIG-1) — framework only.

Development baseline (docs/context/ACTIVE_GATE.md, C08-BASELINE-1), pending
client confirmation: warning/critical temperature thresholds must be
administrator-configurable, never permanently hardcoded, with every change
audited. Actual Eskom threshold values remain unconfirmed — this module
persists whatever an Administrator configures; it invents no default and
activates no alarm/event logic. Readings are evaluated against this
configuration only by `services/temperature_condition_service.py`
(TEMP-CONDITION-1, ADR-023); this module never evaluates a reading itself.

Layering (matches forwarding_auto_disable_service.py / audit_service.py):

    admin panel control -> set_threshold_config()/clear_threshold_config()
                               -> session_scope()
                                    ├── repo.set_/clear_temperature_threshold_config()
                                    └── audit_service.record() (human actor)
                                 single COMMIT / ROLLBACK

UNCONFIGURED IS ABSENCE, not a row with placeholder values — mirrors
``forwarding_auto_disable_service``'s override exactly. No reason field: the
audit trail already carries the actor and the old/new values; the C-01
baseline does not require a stated reason the way C08's override does, and
neither ``audit_service.record`` nor the repository layer for this feature
requires one, so none is invented here.

CANONICAL DECIMAL SEMANTICS (correctness fix, before this migration's first
commit). Migration 011 stores both values as ``NUMERIC(12, 3)``. Validating
them as Python ``float`` and only THEN persisting is unsound: two distinct
floats can satisfy ``warning_c < critical_c`` in binary64 and still collapse
to the SAME three-decimal value once stored (or land in the opposite
order) — the comparison the service "guaranteed" would no longer describe
what the database actually holds. Every value entering this module is
therefore canonicalized to a ``decimal.Decimal`` at EXACTLY this column's
scale (`_canonicalize`) before any comparison, any no-op check, or any
write — the same representation the database will store, not an
approximation of it. A value with more than three decimal places is
REJECTED, never silently rounded: the client is not entitled to precision
this column cannot hold, and rounding on its behalf could turn a value it
typed into a different one it never confirmed. This is a technical
representability check, not an invented Eskom min/max range — no bound on
the VALUE itself is enforced anywhere in this module.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import audit_service

logger = logging.getLogger(__name__)

#: Matches migration 011's `NUMERIC(12, 3)` column scale exactly — the one
#: and only precision every threshold value is validated, compared, and
#: persisted at. Deliberately NOT `config.metrics.get_metric("temperature")
#: .precision` (1 decimal place): that is chart/table DISPLAY precision, a
#: presentation concern, and must never be allowed to influence what this
#: module accepts or stores.
STORAGE_EXPONENT = Decimal("0.001")


class ThresholdConfigError(Exception):
    """A threshold configuration change failed for a reason safe to show
    the user."""


@dataclass(frozen=True)
class ThresholdConfigState:
    """The admin-facing view of the current threshold configuration, if
    any. ``warning_c``/``critical_c`` are the exact canonical ``Decimal``
    values on record — never rounded for display."""

    warning_c: Decimal
    critical_c: Decimal
    configured_by_user_id: int
    configured_at: datetime


def _to_state(record: repo.TemperatureThresholdConfigRecord) -> ThresholdConfigState:
    return ThresholdConfigState(
        warning_c=record.warning_c,
        critical_c=record.critical_c,
        configured_by_user_id=record.configured_by_user_id,
        configured_at=record.configured_at,
    )


def _snapshot(record: repo.TemperatureThresholdConfigRecord | None) -> dict | None:
    if record is None:
        return None
    return {
        # str(), not the raw Decimal: audit_log's old/new_values are JSONB
        # written through plain `json.dumps` (repo.insert_audit_log), which
        # has no native Decimal support. str() preserves the exact
        # canonical value in the audit trail; float() would reintroduce
        # the same binary imprecision this fix removes everywhere else.
        "warning_c": str(record.warning_c),
        "critical_c": str(record.critical_c),
        "configured_by_user_id": record.configured_by_user_id,
    }


def _canonicalize(value, *, field_label: str) -> Decimal:
    """Convert ``value`` to the exact ``Decimal`` that would be persisted,
    or raise ``ThresholdConfigError`` — never round away precision this
    column cannot hold.

    Accepts a ``str`` (from the form), a ``Decimal``, or (defensively, for
    a caller that skipped `parse_temperature`) an ``int``/``float``. A
    ``float`` is converted via its own `str()` — Python's shortest
    round-tripping decimal text — so a user-typed "20.0004" is read back
    as exactly `Decimal("20.0004")`, never the binary64 approximation
    `Decimal(20.0004)` would give (20.00039999999999999148...).
    """
    if isinstance(value, bool):
        raise ThresholdConfigError(f"{field_label} must be a number.")
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, float):
        candidate = Decimal(str(value))
    elif isinstance(value, int):
        candidate = Decimal(value)
    elif isinstance(value, str):
        try:
            candidate = Decimal(value.strip())
        except InvalidOperation as exc:
            raise ThresholdConfigError(f"{field_label} must be a number.") from exc
    else:
        raise ThresholdConfigError(f"{field_label} must be a number.")

    exponent = candidate.as_tuple().exponent
    if not isinstance(exponent, int):
        # Decimal's own NaN/Infinity vocabulary ('n', 'N', 'F') — reachable
        # both from a float (`str(float("inf"))` -> "inf") and directly
        # from a string like "Infinity"/"NaN", which `Decimal()` parses
        # without raising. Exactly the malformed-input class a temperature
        # threshold must never silently accept.
        raise ThresholdConfigError(f"{field_label} must be a finite number.")
    if exponent < -3:
        raise ThresholdConfigError(
            f"{field_label} supports at most 3 decimal places "
            f"({value!s} would not be stored as entered)."
        )
    # exponent >= -3 here, so this can only pad zeros to reach the column's
    # scale — never actually round anything away.
    return candidate.quantize(STORAGE_EXPONENT, rounding=ROUND_HALF_UP)


def parse_temperature(raw: str | None, *, field_label: str) -> Decimal:
    """Strict numeric parse for one threshold field, or ``ThresholdConfigError``."""
    candidate = (raw or "").strip()
    if not candidate:
        raise ThresholdConfigError(f"{field_label} is required.")
    return _canonicalize(candidate, field_label=field_label)


def get_current_threshold_config() -> ThresholdConfigState | None:
    """The current configuration, or None when never configured (or the
    last one was explicitly cleared) — absence IS "unconfigured"."""
    record = repo.get_temperature_threshold_config()
    return _to_state(record) if record else None


def set_threshold_config(
    *, warning_c, critical_c, actor_user_id: int
) -> ThresholdConfigState:
    """Set (or change) the global threshold configuration.

    Canonicalizes both values to the exact `Decimal` NUMERIC(12,3) will
    store — independently of any caller's own parsing, because this is the
    single trusted entry point for a value ever reaching storage, not
    `parse_temperature` (which a caller may skip by passing a float or
    Decimal directly). `warning_c < critical_c` is then checked on THAT
    canonical representation, so it can never disagree with what actually
    gets persisted (see this module's docstring). No arbitrary min/max
    range is enforced: C-01 gives no numeric bounds to encode, and
    inventing one would itself be a hardcoded threshold.

    Same-state re-application (identical canonical warning_c/critical_c as
    what is already set) is a genuine no-op — mirrors C08's override rule:
    nothing is written, nothing is audited. Changing either value is
    always a real transition and is always audited, regardless of who
    makes the change.
    """
    if not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise ThresholdConfigError(
            "Setting the temperature threshold requires an authenticated administrator."
        )
    warning_c = _canonicalize(warning_c, field_label="Warning")
    critical_c = _canonicalize(critical_c, field_label="Critical")
    if not warning_c < critical_c:
        raise ThresholdConfigError(
            "The warning threshold must be lower than the critical threshold."
        )

    try:
        with session_scope() as session:
            change = repo.set_temperature_threshold_config(
                warning_c=warning_c,
                critical_c=critical_c,
                configured_by_user_id=actor_user_id,
                session=session,
            )
            if change.changed:
                audit_service.record(
                    session,
                    operation=audit_cfg.TEMPERATURE_THRESHOLD_SET,
                    entity_type=audit_cfg.ENTITY_TEMPERATURE_THRESHOLD,
                    entity_id=audit_cfg.TEMPERATURE_THRESHOLD_ENTITY_ID,
                    old_values=_snapshot(change.previous),
                    new_values=_snapshot(change.current),
                    actor_user_id=actor_user_id,
                )
            return _to_state(change.current)
    except ThresholdConfigError:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to set temperature threshold config for actor %s", actor_user_id
        )
        raise ThresholdConfigError(
            "The temperature threshold could not be saved. Please try again."
        ) from exc


def clear_threshold_config(*, actor_user_id: int) -> ThresholdConfigState | None:
    """Clear the current configuration, returning to "unconfigured".

    Returns the configuration that was cleared, or None if nothing was set
    — a genuine no-op: nothing is deleted, nothing is audited.
    """
    if not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise ThresholdConfigError(
            "Clearing the temperature threshold requires an authenticated administrator."
        )

    try:
        with session_scope() as session:
            previous = repo.clear_temperature_threshold_config(session=session)
            if previous is None:
                return None
            audit_service.record(
                session,
                operation=audit_cfg.TEMPERATURE_THRESHOLD_CLEARED,
                entity_type=audit_cfg.ENTITY_TEMPERATURE_THRESHOLD,
                entity_id=audit_cfg.TEMPERATURE_THRESHOLD_ENTITY_ID,
                old_values=_snapshot(previous),
                new_values=None,
                actor_user_id=actor_user_id,
            )
            return _to_state(previous)
    except ThresholdConfigError:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to clear temperature threshold config for actor %s", actor_user_id
        )
        raise ThresholdConfigError(
            "The temperature threshold could not be cleared. Please try again."
        ) from exc
