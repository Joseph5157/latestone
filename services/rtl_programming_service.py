"""RTL programming requests — the persistence boundary crossed by OPS-PROG-1.

Layering contract (AUD-1 pattern, FWD-D5), extended by RTL-IF-1:

    callback → rtl_programming_service → session_scope()
                ├── repo.create_programming_request(session=s)
                ├── repo.create_command(session=s)
                └── audit_service.record(s, ...)
              single COMMIT / ROLLBACK BOTH

What is REAL after OPS-PROG-1: the persisted programming-request row, its
authorization (upstream, at the action guard), its audit trail, and
reload/read-back from PostgreSQL.

RTL-IF-1 adds one ``rtl_commands`` row per accepted request, in the same
transaction: the protocol-neutral seam a future transport will consume.
This does NOT change what the request row means — see PROG-D7 below, still
true.

PROG-D6 (superseded by RTL-PROG-EXEC-1): originally, every row this
service created stayed ``pending`` with NULL completion columns forever,
because no device-integration slice existed to own the lifecycle. That
slice now exists (`services/rtl_command_service.py`,
`services/rtl_command_dispatch_service.py`) and RTL-PROG-EXEC-1 wires this
call to it: the moment the command row above is created, the request is
projected from ``pending`` to ``queued`` in this same transaction
(``config.commands.REQUEST_STATUS_FOR_COMMAND_STATE``) — ``pending`` is
now the row's insert-time default only, never its observable rest state
once ``record_request`` has returned successfully. Every later command
transition projects further (`services/rtl_command_service.py`'s
``_transition``); this function still starts nothing beyond that first
QUEUED command — no transport, no retry, no scheduler, no automatic
dispatch. Recording a request is NOT evidence that a physical RTL was
programmed — the UI copy must say so (PROG-D7).

Frozen semantics:

- PROG-D1  The RTL Master MSISDN is operator-supplied and manually entered.
           No trustworthy source exists in the repository (devices.msisdn is
           the individual RTL Client's SIM number, NOT the Master's), so it
           must never be prefilled from there. Validation is limited to what
           the schema proves: non-empty after trimming, at most 20
           characters. No telephone-format invention.
- PROG-D2  request_method is always "dashboard" — nothing was sent anywhere.
- PROG-D3  Append-only history: every accepted call inserts a new row, even
           an identical repeat. There is no no-op path to classify.
- PROG-D4  Multiple pending rows per device are allowed; nothing here
           enforces single-pending semantics.
- PROG-D5  Audit entity is ("device", device_id); request-specific fields
           travel in new_values under the approved allowlist.
"""
from __future__ import annotations

import logging

from config import audit as audit_cfg
from config import commands as command_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import ProgrammingRequestRecord
from services import audit_service

logger = logging.getLogger(__name__)

#: PROG-D2 — the only request method this slice writes. The column's
#: vocabulary is open (no CHECK); naming the origin honestly leaves the
#: future transport paths free to use their own values.
REQUEST_METHOD_DASHBOARD = "dashboard"

#: The only MSISDN limit proven by the schema (varchar(20)). Anything
#: stricter would be invented policy (PROG-D1).
MAX_MASTER_MSISDN_LENGTH = 20


class ProgrammingError(Exception):
    """A programming request failed for a reason safe to show the user."""


def _validate_master_msisdn(master_msisdn) -> str:
    """Trim and bound-check the operator-supplied Master MSISDN."""
    if not isinstance(master_msisdn, str):
        raise ProgrammingError(
            "Enter the RTL Master MSISDN before recording the request."
        )
    trimmed = master_msisdn.strip()
    if not trimmed:
        raise ProgrammingError(
            "Enter the RTL Master MSISDN before recording the request."
        )
    if len(trimmed) > MAX_MASTER_MSISDN_LENGTH:
        raise ProgrammingError(
            f"The RTL Master MSISDN must be at most "
            f"{MAX_MASTER_MSISDN_LENGTH} characters."
        )
    return trimmed


def record_request(
    *, device_id: str, master_msisdn: str, actor_user_id: int
) -> ProgrammingRequestRecord:
    """Persist one pending programming request for ``device_id`` and audit it.

    Strict actor rule (AUD-1 review decision D2): ``actor_user_id`` must be
    the authenticated session's id — missing or malformed fails the whole
    operation before any database access. Authorization itself already
    happened upstream at the action guard; this check only guarantees that
    an authenticated identity exists to persist and audit with.
    """
    if not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise ProgrammingError(
            "Recording a programming request requires an authenticated account."
        )

    msisdn = _validate_master_msisdn(master_msisdn)

    try:
        with session_scope() as session:
            record = repo.create_programming_request(
                device_id,
                master_msisdn=msisdn,
                requested_by=actor_user_id,
                request_method=REQUEST_METHOD_DASHBOARD,
                session=session,
            )

            # Same transaction as the request insert (RTL-IF-1): a failed
            # command insert rolls the request row back with it too. No
            # separate audit event for this — see ADR-017.
            repo.create_command(
                request_id=record.request_id,
                command_type=command_cfg.COMMAND_TYPE_PROGRAM_RTL,
                state=command_cfg.STATE_QUEUED,
                session=session,
            )

            # RTL-PROG-EXEC-1: the request is now genuinely queued for
            # dispatch, not merely "pending" (the insert-time default) —
            # project it, in this same transaction, so a failed projection
            # rolls the whole request back with it too.
            record = repo.update_programming_request_status(
                record.request_id,
                status=command_cfg.REQUEST_STATUS_FOR_COMMAND_STATE[
                    command_cfg.STATE_QUEUED
                ],
                session=session,
            )

            # Same transaction as the insert: a failed audit write rolls
            # the request row back with it (FWD-D5 atomicity).
            audit_service.record(
                session,
                operation=audit_cfg.RTL_PROGRAM_REQUESTED,
                entity_type=audit_cfg.ENTITY_DEVICE,
                entity_id=device_id,
                old_values=None,
                new_values={
                    "request_id": record.request_id,
                    "transformer_id": record.transformer_id,
                    "master_msisdn": record.master_msisdn,
                    "request_method": record.request_method,
                },
                actor_user_id=actor_user_id,
            )
            return record
    except Exception as exc:
        logger.exception(
            "Failed to record programming request for device %s", device_id
        )
        raise ProgrammingError(
            "The programming request could not be recorded. Please try again."
        ) from exc


def recent_requests(device_id: str, *, limit: int = 5):
    """Read back a device's most recent requests straight from PostgreSQL."""
    return repo.list_recent_programming_requests(device_id, limit=limit)


__all__ = [
    "MAX_MASTER_MSISDN_LENGTH",
    "ProgrammingError",
    "REQUEST_METHOD_DASHBOARD",
    "recent_requests",
    "record_request",
]
