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

_COMMAND_STATUS_LABELS = {
    command_cfg.STATE_QUEUED: "Queued",
    command_cfg.STATE_SENT: "Sent in simulation",
    command_cfg.STATE_ACKNOWLEDGED: "Acknowledged in simulation",
    command_cfg.STATE_SUCCEEDED: "Succeeded in simulation",
    command_cfg.STATE_FAILED: "Failed in simulation",
    command_cfg.STATE_TIMED_OUT: "Timed out in simulation",
}


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


def _command_status(record: ProgrammingActivityView) -> str:
    if record.command_state is None:
        return "No command record"
    return _COMMAND_STATUS_LABELS.get(record.command_state, record.command_state)


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
                            className="programming-activity__details",
                            children=[
                                _detail("Requested by", record.requested_by_name),
                                _detail("Command type", _command_type(record)),
                                _detail("Master MSISDN", record.master_msisdn),
                                _detail("Command status", _command_status(record)),
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
