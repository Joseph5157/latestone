"""RTL command read API and lifecycle transitions (RTL-IF-1, RTL-IF-2).

Command *creation* is not here: it happens inside
`rtl_programming_service.record_request`, atomically with the programming
request and its audit row, because it is that call's responsibility, not a
standalone operation.

RTL-IF-2 adds the lifecycle transition functions
(`mark_sent`/`mark_acknowledged`/`mark_succeeded`/`mark_failed`/
`mark_timed_out`). This is the only layer allowed to write
`rtl_commands.state` — `repositories.plant_monitoring_repository.
update_command_state` is a low-level conditional UPDATE with no opinion on
which transitions are legal; that opinion lives here, checked against
`config.commands.ALLOWED_TRANSITIONS` before the repository is ever called.
Nothing outside this module (and the dispatcher that calls it,
`services/rtl_command_dispatch_service.py`) writes a state string directly.
"""
from __future__ import annotations

from config import commands as command_cfg
from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import CommandRecord

#: Which lifecycle timestamp column a transition INTO this state sets.
#: QUEUED has none — it is the row's insert-time state, set by
#: create_command(), never by a transition.
_TIMESTAMP_COLUMN_FOR_STATE = {
    command_cfg.STATE_SENT: "sent_at",
    command_cfg.STATE_ACKNOWLEDGED: "acknowledged_at",
    command_cfg.STATE_SUCCEEDED: "completed_at",
    command_cfg.STATE_FAILED: "completed_at",
    command_cfg.STATE_TIMED_OUT: "completed_at",
}


class CommandTransitionError(Exception):
    """A lifecycle transition was refused: unknown command, illegal move
    (including any move out of a terminal state), or lost a concurrent
    race for the expected current state."""


def get_command(command_id: int) -> CommandRecord | None:
    """Resolve one command by id, or None."""
    return repo.get_command(command_id)


def get_command_for_request(request_id: int) -> CommandRecord | None:
    """Resolve a programming request's single corresponding command, or None."""
    return repo.get_command_for_request(request_id)


def _transition(
    command_id: int,
    *,
    to_state: str,
    failure_code: str | None = None,
    failure_detail: str | None = None,
) -> CommandRecord:
    """Load the command, validate the move against ALLOWED_TRANSITIONS, and
    persist it via one conditional UPDATE (one DB transaction).

    The map check runs first so an illegal move (including any move out of
    a terminal state — every terminal state's ALLOWED_TRANSITIONS entry is
    empty) is refused before touching the database at all. The repository's
    ``WHERE state = :expected_state`` is the second, DB-level check: it
    closes the race between this read and that write, so a command that
    changed state in between (e.g. two callers dispatching the same command
    concurrently) fails loudly here instead of one silently overwriting the
    other.
    """
    command = repo.get_command(command_id)
    if command is None:
        raise CommandTransitionError(f"Unknown command_id: {command_id!r}")

    allowed = command_cfg.ALLOWED_TRANSITIONS.get(command.state, frozenset())
    if to_state not in allowed:
        raise CommandTransitionError(
            f"Command {command_id} cannot move from {command.state!r} to "
            f"{to_state!r}."
        )

    timestamp_column = _TIMESTAMP_COLUMN_FOR_STATE[to_state]

    try:
        return repo.update_command_state(
            command_id,
            expected_state=command.state,
            to_state=to_state,
            timestamp_column=timestamp_column,
            failure_code=failure_code,
            failure_detail=failure_detail,
        )
    except ValueError as exc:
        raise CommandTransitionError(str(exc)) from exc


def mark_sent(command_id: int) -> CommandRecord:
    """QUEUED -> SENT."""
    return _transition(command_id, to_state=command_cfg.STATE_SENT)


def mark_acknowledged(command_id: int) -> CommandRecord:
    """SENT -> ACKNOWLEDGED."""
    return _transition(command_id, to_state=command_cfg.STATE_ACKNOWLEDGED)


def mark_succeeded(command_id: int) -> CommandRecord:
    """ACKNOWLEDGED -> SUCCEEDED."""
    return _transition(command_id, to_state=command_cfg.STATE_SUCCEEDED)


def mark_failed(
    command_id: int, *, failure_code: str, failure_detail: str | None = None
) -> CommandRecord:
    """SENT -> FAILED."""
    return _transition(
        command_id,
        to_state=command_cfg.STATE_FAILED,
        failure_code=failure_code,
        failure_detail=failure_detail,
    )


def mark_timed_out(
    command_id: int, *, failure_code: str, failure_detail: str | None = None
) -> CommandRecord:
    """SENT -> TIMED_OUT."""
    return _transition(
        command_id,
        to_state=command_cfg.STATE_TIMED_OUT,
        failure_code=failure_code,
        failure_detail=failure_detail,
    )


__all__ = [
    "CommandRecord",
    "CommandTransitionError",
    "get_command",
    "get_command_for_request",
    "mark_acknowledged",
    "mark_failed",
    "mark_sent",
    "mark_succeeded",
    "mark_timed_out",
]
