"""The Device page's alarm history list (ADR-027): read-only, newest first.

Acknowledging stays on the Command Center (ADR-016); this list only says
what happened to the RTL and when, under its chart.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Sequence

from dash import html

from components.status_colors import KIND_TONE, status_text_class
from services.device_timeline_service import DeviceAlarm


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _span(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "under a minute"
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 48 * 60:
        return f"{minutes // 60} h"
    return f"{minutes // (24 * 60)} d"


def _status(alarm: DeviceAlarm) -> html.Span:
    if alarm.is_open:
        return html.Span("Unacknowledged",
                         className="device-alarms__ack device-alarms__ack--open")
    return html.Span(f"Acknowledged {_span(alarm.acknowledged_after)} later",
                     className="device-alarms__ack")


def alarm_history(alarms: Sequence[DeviceAlarm] | None, period_label: str) -> html.Section | None:
    """None when the viewer's role does not see alarms (General User)."""
    if alarms is None:
        return None
    open_count = sum(a.is_open for a in alarms)
    summary = (f"{_plural(len(alarms), 'alarm')} · {open_count} unacknowledged"
               if alarms else "")
    head = html.Div(className="device-alarms__head", children=[
        html.H3(f"Alarm history · {period_label}", className="device-alarms__title"),
        html.Span(summary, className="device-alarms__summary"),
    ])
    if not alarms:
        return html.Section(className="device-alarms", children=[
            head, html.P("No alarms in this period.", className="device-alarms__empty"),
        ])
    rows = [
        html.Li(className="device-alarms__row", children=[
            html.Time(a.at.strftime("%d %b %H:%M UTC"), className="device-alarms__time",
                      dateTime=a.at.isoformat()),
            html.Span(a.label, className="device-alarms__kind "
                      + status_text_class(KIND_TONE[a.kind])),
            _status(a),
        ])
        for a in alarms
    ]
    return html.Section(className="device-alarms", children=[
        head, html.Ul(rows, className="device-alarms__list"),
    ])
