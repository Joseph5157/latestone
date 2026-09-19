"""The redesigned Command Center's panels (CC-NEW-1).

Pure render functions over `services.attention_service` values. They decide
nothing: kinds, conditions and ranking arrive already decided, and the only
mapping here is kind/condition -> visual tone.
"""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

from dash import dcc, html

from components.command_center.primitives import cc_card
from routes import device_href
from services.attention_service import (
    ActivityItem,
    AttentionSnapshot,
    DailyAlarms,
    Problem,
    ProblemKind,
    format_limit,
)
from services.temperature_condition_service import (
    CONDITION_LABELS,
    LIMIT_SOURCE_NOTE,
    DeviceTemperature,
    TemperatureCondition,
)

_KIND_TONE = {
    ProblemKind.TEMP_CRITICAL: "critical",
    ProblemKind.POWER_DOWN: "critical",
    ProblemKind.NO_DATA_24H: "nodata",
    ProblemKind.TEMP_WARNING: "warning",
    ProblemKind.BATTERY_LOW: "warning",
    ProblemKind.SENSOR_ERROR: "info",
}

_CONDITION_TONE = {
    TemperatureCondition.CRITICAL: "critical",
    TemperatureCondition.WARNING: "warning",
    TemperatureCondition.NORMAL: "normal",
    TemperatureCondition.LIMITS_NOT_SET: "info",
    TemperatureCondition.NO_RECENT_DATA: "nodata",
}


_FLAGGED = frozenset({TemperatureCondition.WARNING, TemperatureCondition.CRITICAL})


def ago(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return "—"
    seconds = (now - moment).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    return f"{int(seconds // 86400)} d ago"


def _chip(label: str, tone: str) -> html.Span:
    return html.Span(label, className=f"attention-chip attention-chip--{tone}")


def _device_link(device_id: str, device_code: str) -> dcc.Link:
    return dcc.Link(device_code, href=device_href(device_id), className="attention-link")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def status_bar(snapshot: AttentionSnapshot) -> html.Div:
    """One line that answers "is everything OK?" before anything else."""
    clear = not snapshot.problems
    headline = (
        [html.Strong("All clear", className="attention-status__headline")]
        if clear
        else [html.Strong(_plural(len(snapshot.problems), "problem"),
                          className="attention-status__headline")]
    )
    if snapshot.limits is None:
        limits = html.Span(
            "Temperature limits not set — high temperature cannot be flagged "
            "until an administrator sets them (Administration → Settings).",
            className="attention-status__limits attention-status__limits--unset",
        )
    else:
        limits = html.Span(
            f"Warning {format_limit(snapshot.limits.warning_c)} °C · "
            f"Critical {format_limit(snapshot.limits.critical_c)} °C · "
            f"{LIMIT_SOURCE_NOTE}",
            className="attention-status__limits",
        )
    return html.Div(
        className="attention-status" + (" attention-status--clear" if clear else ""),
        children=[
            *headline,
            html.Span(
                f"{snapshot.reporting_rtls} of {snapshot.total_rtls} RTLs reporting",
                className="attention-status__reporting",
            ),
            limits,
        ],
    )


def problem_list(problems: Sequence[Problem], now: datetime) -> html.Section:
    if not problems:
        body = [html.P("Nothing needs attention.", className="attention-empty")]
    else:
        body = [html.Ul(className="attention-problems", children=[
            html.Li(
                className=f"attention-problem attention-problem--{_KIND_TONE[p.kind]}",
                children=[
                    _chip(p.label, _KIND_TONE[p.kind]),
                    html.Div(className="attention-problem__main", children=[
                        _device_link(p.device_id, p.device_code),
                        html.Span(f"{p.plant_name} · {p.transformer_code}",
                                  className="attention-problem__where"),
                    ]),
                    html.Span(p.detail, className="attention-problem__detail"),
                    html.Span(ago(p.since, now), className="attention-problem__since",
                              title=p.since.strftime("%Y-%m-%d %H:%M UTC") if p.since else None),
                ],
            )
            for p in problems
        ])]
    return cc_card("Needs attention", body,
                   subtitle="Most urgent first · alarms stay until acknowledged")


def hottest_card(temps: Sequence[DeviceTemperature]) -> html.Section:
    if not temps:
        body = [html.P("No recent temperature readings.", className="attention-empty")]
    else:
        body = [html.Ol(className="attention-hottest", children=[
            html.Li(className="attention-hottest__row", children=[
                _device_link(t.device_id, t.device_code),
                html.Span(t.transformer_code, className="attention-hottest__where"),
                html.Span(f"{t.value:.1f} °C", className="attention-hottest__value"),
                # Only a real finding earns a chip; "Limits not set" is said
                # once in the status bar, not repeated on every row.
                *([_chip(CONDITION_LABELS[t.condition], _CONDITION_TONE[t.condition])]
                  if t.condition in _FLAGGED else []),
            ])
            for t in temps
        ])]
    return cc_card("Hottest now", body, subtitle="Latest reading per RTL")


def activity_card(items: Sequence[ActivityItem], now: datetime) -> html.Section:
    if not items:
        body = [html.P("No activity in the last 24 hours.", className="attention-empty")]
    else:
        body = [html.Ul(className="attention-activity", children=[
            html.Li(className="attention-activity__row", children=[
                html.Span(i.label, className="attention-activity__label"),
                _device_link(i.device_id, i.device_code),
                html.Span(i.plant_name, className="attention-activity__where"),
                html.Span(ago(i.at, now), className="attention-activity__when"),
            ])
            for i in items
        ])]
    return cc_card("Recent activity", body,
                   subtitle="Switch-ons, programming requests, acknowledgements · last 24 h")


def alarm_trend_card(days: Sequence[DailyAlarms]) -> html.Section:
    peak = max((d.count for d in days), default=0) or 1
    bars = [
        html.Div(className="attention-trend__day", children=[
            html.Span(str(d.count), className="attention-trend__count"),
            html.Div(className="attention-trend__track", children=[
                html.Div(className="attention-trend__bar",
                         style={"height": f"{round(100 * d.count / peak)}%"}),
            ]),
            html.Span(d.day.strftime("%a %d"), className="attention-trend__label"),
        ])
        for d in days
    ]
    total = sum(d.count for d in days)
    return cc_card(
        "Alarms per day", [html.Div(className="attention-trend", children=bars)],
        subtitle=f"Battery, power-down and sensor alarms · last 7 days · {total} total",
    )
