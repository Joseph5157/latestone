"""Compact, truthful programming activity for a single RTL.

The component receives the repository read model; it never queries PostgreSQL
and never decides role or assignment policy.  Its copy makes the current
boundary explicit: persisted request and simulator lifecycle are application
facts, not evidence of physical device execution.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence

from dash import html

from config import commands as command_cfg

PROGRAMMING_ACTIVITY_ID = "programming-activity"

_REQUEST_STATUS_LABELS = {
    command_cfg.REQUEST_STATUS_PENDING: "Request recorded",
    command_cfg.REQUEST_STATUS_QUEUED: "Queued",
    command_cfg.REQUEST_STATUS_SENT: "In progress",
    command_cfg.REQUEST_STATUS_SUCCESSFUL: "Completed in simulation",
    command_cfg.REQUEST_STATUS_FAILED: "Simulation did not complete",
}

#: Ordered happy-path lifecycle a command can move through
#: (`config.commands.ALLOWED_TRANSITIONS`): QUEUED -> SENT -> ACKNOWLEDGED ->
#: SUCCEEDED. FAILED/TIMED_OUT are alternate terminal outcomes that only
#: branch off SENT — they are deliberately not part of this tuple, since the
#: rail must stop at the point a command actually diverged, never show a
#: state it can no longer reach (see `_lifecycle_steps`).
_LIFECYCLE_HAPPY_PATH = (
    command_cfg.STATE_QUEUED,
    command_cfg.STATE_SENT,
    command_cfg.STATE_ACKNOWLEDGED,
    command_cfg.STATE_SUCCEEDED,
)

_LIFECYCLE_STATE_NAMES = {
    command_cfg.STATE_QUEUED: "Queued",
    command_cfg.STATE_SENT: "Sent",
    command_cfg.STATE_ACKNOWLEDGED: "Acknowledged",
    command_cfg.STATE_SUCCEEDED: "Succeeded",
    command_cfg.STATE_FAILED: "Failed",
    command_cfg.STATE_TIMED_OUT: "Timed out",
}

#: Decorative-only markers (paired with explicit status wording in every
#: step's text, so meaning never depends on the marker or on colour alone).
_LIFECYCLE_MARKERS = {
    "done": "✓",
    "current": "→",
    "pending": "·",
    "final": "✓",
    "terminal": "✗",
}


def _lifecycle_steps(command_state: str | None) -> list[tuple[str, str]]:
    """Return ordered (state, status) pairs truthful to the real transition map.

    status is one of "done", "current", "pending", "final" (the resolved
    SUCCEEDED step) or "terminal" (a resolved FAILED/TIMED_OUT step). A
    FAILED/TIMED_OUT outcome truncates the rail immediately after SENT —
    ACKNOWLEDGED/SUCCEEDED are never rendered as still-pending for a command
    that can no longer reach them (`config.commands.ALLOWED_TRANSITIONS`).
    """
    if command_state is None:
        return []
    if command_state in (command_cfg.STATE_FAILED, command_cfg.STATE_TIMED_OUT):
        return [
            (command_cfg.STATE_QUEUED, "done"),
            (command_cfg.STATE_SENT, "done"),
            (command_state, "terminal"),
        ]
    steps: list[tuple[str, str]] = []
    reached_current = False
    for state in _LIFECYCLE_HAPPY_PATH:
        if state == command_state:
            status = "final" if state == command_cfg.STATE_SUCCEEDED else "current"
            steps.append((state, status))
            reached_current = True
        elif reached_current:
            steps.append((state, "pending"))
        else:
            steps.append((state, "done"))
    return steps


def _lifecycle_step_text(state: str, status: str) -> str:
    name = _LIFECYCLE_STATE_NAMES[state]
    if status == "done":
        return f"{name} (done)"
    if status == "current":
        return f"{name} (current)"
    if status == "pending":
        if state == command_cfg.STATE_SENT:
            return f"{name} (awaiting device integration)"
        return f"{name} (not yet reached)"
    if status == "final":
        return f"{name} (completed)"
    return f"{name} (command did not complete)"  # terminal FAILED/TIMED_OUT


def _lifecycle_rail(record: ProgrammingActivityView) -> html.Div:
    """Compact ordered lifecycle display — no percentage, no animation.

    Named states in sequence only; a state is shown only if the command's
    real transition history could still reach or has already reached it.
    """
    steps = _lifecycle_steps(record.command_state)
    if not steps:
        return html.Div(
            "No command record",
            className="programming-activity__lifecycle programming-activity__lifecycle--empty",
        )
    return html.Ol(
        className="programming-activity__lifecycle",
        children=[
            html.Li(
                className=(
                    "programming-activity__lifecycle-step "
                    f"programming-activity__lifecycle-step--{status}"
                ),
                children=[
                    html.Span(
                        _LIFECYCLE_MARKERS[status],
                        className="programming-activity__lifecycle-marker",
                        **{"aria-hidden": "true"},
                    ),
                    html.Span(
                        _lifecycle_step_text(state, status),
                        className="programming-activity__lifecycle-text",
                    ),
                ],
            )
            for state, status in steps
        ],
    )


class ProgrammingActivityView(Protocol):
    """Presentation shape supplied by the read-oriented service.

    Components must not import repositories: the protocol keeps this module
    structurally presentation-only while documenting the fields it renders.
    """

    request_id: int
    requested_by_name: str
    master_msisdn: str
    requested_at: datetime
    request_status: str
    request_completed_at: datetime | None
    error_message: str | None
    command_type: str | None
    command_state: str | None


class DeviceAuditHistoryView(Protocol):
    """Safe, device-scoped audit shape supplied by the read service."""

    occurred_at: datetime
    operation: str
    requester_name: str


def _timestamp(value: datetime | None) -> str:
    if value is None:
        return "Not recorded"
    return value.strftime("%d %b %Y %H:%M UTC")


def _request_status(record: ProgrammingActivityView) -> str:
    return _REQUEST_STATUS_LABELS.get(record.request_status, record.request_status)


def _command_type(record: ProgrammingActivityView) -> str:
    if record.command_type is None:
        return "No command type recorded"
    return record.command_type.replace("_", " ").title()


def _audit_action(record: DeviceAuditHistoryView) -> str:
    return record.operation.replace("_", " ").title()


def _execution_mode(record: ProgrammingActivityView) -> str:
    if record.command_state in (None, command_cfg.STATE_QUEUED):
        return "Awaiting device integration"
    # SimulatorTransport is currently the only application path that can
    # advance a command past QUEUED.  This label must be revisited alongside
    # any future real transport, rather than letting historic wording imply one.
    return "Simulation (development only)"


def _result(record: ProgrammingActivityView) -> str:
    if record.error_message:
        return record.error_message
    if record.command_state is None:
        return "Request recorded; no command lifecycle is available."
    if record.command_state == command_cfg.STATE_QUEUED:
        return "Request recorded; command is queued."
    if record.command_state == command_cfg.STATE_TIMED_OUT:
        return "Simulation timed out before completion."
    if record.command_state == command_cfg.STATE_FAILED:
        return "Simulation reported a failure."
    if record.command_state == command_cfg.STATE_SUCCEEDED:
        return "Simulation completed; no physical RTL delivery occurred."
    return "Simulation lifecycle is in progress."


def _detail(label: str, value: str) -> html.Div:
    return html.Div(
        className="programming-activity__detail",
        children=[
            html.Span(label, className="programming-activity__label"),
            html.Span(value, className="programming-activity__value"),
        ],
    )


def programming_activity_panel(
    records: Sequence[ProgrammingActivityView],
    audit_records: Sequence[DeviceAuditHistoryView] = (),
) -> html.Section:
    """Render scoped command and audit history without a physical claim."""
    command_body = (
        html.Div(
            className="programming-activity__empty",
            children="No programming activity recorded for this RTL.",
        )
        if not records
        else html.Ol(
            className="programming-activity__list",
            children=[
                html.Li(
                    className="programming-activity__item",
                    children=[
                        html.Div(
                            className="programming-activity__item-head",
                            children=[
                                html.Strong(
                                    _request_status(record),
                                    className="programming-activity__status",
                                ),
                                html.Span(
                                    f"Requested {_timestamp(record.requested_at)}",
                                    className="programming-activity__time",
                                ),
                            ],
                        ),
                        html.Div(
                            "Command lifecycle",
                            className="programming-activity__lifecycle-heading",
                        ),
                        _lifecycle_rail(record),
                        html.Div(
                            className="programming-activity__details",
                            children=[
                                _detail("Requested by", record.requested_by_name),
                                _detail("Command type", _command_type(record)),
                                _detail("Master MSISDN", record.master_msisdn),
                                _detail("Execution", _execution_mode(record)),
                                _detail("Completed", _timestamp(record.request_completed_at)),
                                _detail("Result", _result(record)),
                            ],
                        ),
                    ],
                )
                for record in records
            ],
        )
    )
    audit_body = (
        html.Div(
            className="programming-activity__empty",
            children="No audit activity recorded for this RTL.",
        )
        if not audit_records
        else html.Ol(
            className="programming-activity__list",
            children=[
                html.Li(
                    className="programming-activity__item",
                    children=[
                        html.Div(
                            className="programming-activity__item-head",
                            children=[
                                html.Strong(
                                    _audit_action(record),
                                    className="programming-activity__status",
                                ),
                                html.Span(
                                    _timestamp(record.occurred_at),
                                    className="programming-activity__time",
                                ),
                            ],
                        ),
                        html.Div(
                            className="programming-activity__details",
                            children=[
                                _detail("Requester", record.requester_name),
                                _detail("Lifecycle", "Audit record"),
                                _detail("Execution", "Not applicable"),
                                _detail("Result", "Recorded in this application"),
                            ],
                        ),
                    ],
                )
                for record in audit_records
            ],
        )
    )
    return html.Section(
        className="device-section programming-activity",
        children=[
            html.Div(
                className="device-section__heading device-section__heading--inline",
                children=[
                    html.Div(
                        children=[
                            html.Div("Operations", className="device-section__eyebrow"),
                            html.H2("Command & audit history"),
                        ]
                    ),
                    html.P("Recorded requests, command lifecycle, and device audit entries."),
                ],
            ),
            html.P(
                "Physical RTL delivery is not connected in this environment.",
                className="programming-activity__notice",
            ),
            html.H3("Command history", className="programming-activity__subheading"),
            command_body,
            html.H3("Audit history", className="programming-activity__subheading"),
            audit_body,
        ],
    )


def programming_activity_error() -> html.Section:
    """A read failure is distinct from a legitimate empty history."""
    return html.Section(
        className="device-section programming-activity",
        children=[
            html.Div(
                className="status-panel status-panel--error",
                children=[
                    html.H3("Command and audit history unavailable"),
                    html.P("Command and audit history could not be loaded. Please try again."),
                ],
            )
        ],
    )


__all__ = [
    "PROGRAMMING_ACTIVITY_ID",
    "programming_activity_error",
    "programming_activity_panel",
]
