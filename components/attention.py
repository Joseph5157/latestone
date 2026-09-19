"""The redesigned Command Center's panels (CC-NEW-1).

Pure render functions over `services.attention_service` values. They decide
nothing: kinds, conditions and ranking arrive already decided, and every
visual tone comes from `components.status_colors` (ADR-026).
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Sequence

from dash import dcc, html

from components.command_center.primitives import cc_card
from components.status_colors import CONDITION_TONE, KIND_TONE, TONE_NAME, status_chip_class
from routes import device_href
from services.attention_service import (
    ACKNOWLEDGEABLE_KINDS,
    ActivityItem,
    AttentionSnapshot,
    KIND_LABELS,
    DailyAlarms,
    Problem,
    ProblemKind,
    format_limit,
    oldest_unacknowledged,
)
from services.temperature_condition_service import (
    CONDITION_LABELS,
    LIMIT_SOURCE_NOTE,
    DeviceTemperature,
    TemperatureCondition,
)

#: Status-bar counters (POLISH-1), in the order an operator reads them.
#: Grouped by the same tone the problem chips use, so a counter and the
#: chips it counts can never disagree about which colour a kind is.
SEVERITY_COUNTERS = (
    ("Critical", "critical"),
    ("Warning", "warning"),
    ("No data", "nodata"),
    ("Device fault", "info"),
)


#: Pattern-matching id type for the severity filter controls (CLICK-FILTER-1):
#: counters and strip segments carry their tone; "Show all" carries "all".
SEVERITY_BUTTON = "attention-severity"


def tone_of(p: Problem) -> str:
    return KIND_TONE[p.kind]


def severity_breakdown(problems: Sequence[Problem]) -> dict[str, str]:
    """Per tone, "Kind n · Kind n" in rank order ("" when none)."""
    per_kind: dict[ProblemKind, int] = {}
    for p in problems:
        per_kind[p.kind] = per_kind.get(p.kind, 0) + 1
    out = {tone: [] for _label, tone in SEVERITY_COUNTERS}
    for kind in ProblemKind:
        if per_kind.get(kind):
            out[KIND_TONE[kind]].append(f"{KIND_LABELS[kind]} {per_kind[kind]}")
    return {tone: " · ".join(parts) for tone, parts in out.items()}


def severity_counts(problems: Sequence[Problem]) -> dict[str, int]:
    counts = {tone: 0 for _label, tone in SEVERITY_COUNTERS}
    for p in problems:
        counts[KIND_TONE[p.kind]] += 1
    return counts


#: Pattern-matching id types for the per-problem actions (CC-ACTIONS-1).
ACK_BUTTON = "attention-ack"
MANAGE_BUTTON = "attention-manage"

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


def condition_chip(condition: TemperatureCondition) -> html.Span:
    return _chip(CONDITION_LABELS[condition], CONDITION_TONE[condition])


def _chip(label: str, tone: str) -> html.Span:
    return html.Span(label, className=f"attention-chip {status_chip_class(tone)}")


def _device_link(device_id: str, device_code: str) -> dcc.Link:
    return dcc.Link(device_code, href=device_href(device_id), className="attention-link")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def status_bar(snapshot: AttentionSnapshot, selected: str | None = None) -> html.Div:
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
    counts = severity_counts(snapshot.problems)
    # CLICK-FILTER-1: each counter filters the problem list; the active one
    # is pressed, and pressing it again clears the filter.
    # CC-SEVERITY-CARDS-1: stat cards, same shape as the Fleet Overview's.
    # Still the CLICK-FILTER-1 filter buttons: the active one is pressed, and
    # pressing it again clears the filter.
    breakdown = severity_breakdown(snapshot.problems)
    counters = html.Div(className="attention-severity-cards", children=[
        html.Button(
            type="button", n_clicks=0, disabled=not counts[tone],
            id={"type": SEVERITY_BUTTON, "tone": tone, "part": "counter"},
            className=f"attention-counter attention-severity-card attention-counter--{tone}"
                      + (" attention-counter--zero" if not counts[tone] else "")
                      + (" attention-counter--active" if selected == tone else ""),
            title=("Show all problems" if selected == tone else f"Show only {label}"),
            **{"aria-pressed": "true" if selected == tone else "false"},
            children=[
                html.Span(label, className="attention-counter__label"),
                html.Strong(str(counts[tone]), className="attention-counter__value"),
                html.Span(breakdown[tone] or "None right now",
                          className="attention-severity-card__detail"),
            ],
        )
        for label, tone in SEVERITY_COUNTERS
    ])
    # CC-VISUALS-1: the mix of problems before any number is read.
    strip = html.Div(
        className="attention-strip", **{"aria-hidden": "true"},
        children=(
            [html.Span(className="attention-strip__seg attention-strip__seg--normal",
                       style={"flexGrow": 1})]
            if clear else
            [html.Button(type="button", n_clicks=0, tabIndex="-1",
                         id={"type": SEVERITY_BUTTON, "tone": tone, "part": "strip"},
                         className=f"attention-strip__seg attention-strip__seg--{tone}"
                                   + (" attention-strip__seg--dim" if selected and selected != tone else ""),
                         style={"flexGrow": counts[tone]}, title=f"{label} {counts[tone]} — show only these")
             for label, tone in SEVERITY_COUNTERS if counts[tone]]
        ),
    )
    oldest = oldest_unacknowledged(snapshot.problems)
    backlog = html.Div(className="attention-status__backlog", children=[
        html.Span(
            f"Oldest unacknowledged: {oldest.label} · {ago(oldest.since, snapshot.generated_at)}"
            if oldest else "No unacknowledged alarms",
            className="attention-status__oldest",
        ),
        html.Span(f"{snapshot.acknowledged_24h} acknowledged in the last 24 h",
                  className="attention-status__acked"),
    ])
    status = html.Div(
        className="attention-status" + (" attention-status--clear" if clear else ""),
        children=[
            *headline,
            backlog,
            html.Span(
                f"{snapshot.reporting_rtls} of {snapshot.total_rtls} RTLs reporting",
                className="attention-status__reporting",
            ),
            limits,
            strip,
        ],
    )
    return html.Div(className="attention-overview", children=[status, counters])


def _actions(p: Problem, may_ack: frozenset[str], may_manage: frozenset[str]) -> list:
    """Buttons only where the policy said yes (visibility, not authority:
    the callbacks re-check with require_action)."""
    buttons = []
    if p.kind in ACKNOWLEDGEABLE_KINDS and p.device_id in may_ack:
        buttons.append(html.Button(
            "Acknowledge", type="button", n_clicks=0,
            id={"type": ACK_BUTTON, "device": p.device_id, "kind": p.kind.value},
            className="attention-action attention-action--primary",
            title=f"Acknowledge {p.count} open alarm(s) on {p.device_code}",
        ))
    if p.device_id in may_manage:
        buttons.append(html.Button(
            "Manage", type="button", n_clicks=0,
            id={"type": MANAGE_BUTTON, "device": p.device_id},
            className="attention-action",
            title=f"Program, forwarding or deactivate {p.device_code}",
        ))
    return buttons


def problem_list(
    problems: Sequence[Problem],
    now: datetime,
    *,
    may_ack: frozenset[str] = frozenset(),
    may_manage: frozenset[str] = frozenset(),
    selected: str | None = None,
) -> html.Section:
    filter_note = []
    if selected:
        label = dict((t, l) for l, t in SEVERITY_COUNTERS).get(selected, selected)
        problems = [p for p in problems if tone_of(p) == selected]
        filter_note = [html.Div(className="attention-filter-note", children=[
            html.Span(f"Showing {label} only · {_plural(len(problems), 'problem')}"),
            html.Button("Show all", type="button", n_clicks=0,
                        id={"type": SEVERITY_BUTTON, "tone": "all", "part": "clear"},
                        className="attention-action"),
        ])]
    if not problems:
        body = filter_note + [html.P("Nothing needs attention.", className="attention-empty")]
    else:
        # Column header on the same grid as the rows, so "since" and the
        # actions read as columns (POLISH-1). Hidden on phones.
        head = html.Div(className="attention-problem attention-problem--head",
                        **{"aria-hidden": "true"}, children=[
            html.Span("Problem", className="attention-problem__h-chip"),
            html.Span("RTL · where", className="attention-problem__main"),
            html.Span("Since", className="attention-problem__since"),
            html.Span("", className="attention-problem__actions"),
        ])
        body = filter_note + [head, html.Ul(className="attention-problems", children=[
            html.Li(
                className=f"attention-problem attention-problem--{KIND_TONE[p.kind]}",
                children=[
                    _chip(p.label, KIND_TONE[p.kind]),
                    html.Div(className="attention-problem__main", children=[
                        _device_link(p.device_id, p.device_code),
                        html.Span(f"{p.plant_name} · {p.transformer_code}",
                                  className="attention-problem__where"),
                    ]),
                    html.Span(p.detail, className="attention-problem__detail"),
                    html.Span(ago(p.since, now), className="attention-problem__since",
                              title=p.since.strftime("%Y-%m-%d %H:%M UTC") if p.since else None),
                    html.Div(_actions(p, may_ack, may_manage),
                             className="attention-problem__actions"),
                ],
            )
            for p in problems
        ])]
    return cc_card("Needs attention", body,
                   subtitle="Most urgent first · alarms stay until acknowledged")


def temperature_scale(temps: Sequence[DeviceTemperature], limits) -> tuple[float, float]:
    """(low, high) °C for the Hottest bars: wide enough for every value and
    both limit markers, with a little room either side."""
    values = [t.value for t in temps if t.value is not None]
    if limits is not None:
        values += [float(limits.warning_c), float(limits.critical_c)]
    if not values:
        return 0.0, 1.0
    low, high = math.floor(min(values) - 5), math.ceil(max(values) + 2)
    return float(low), float(max(high, low + 1))


def _pct(value: float, scale: tuple[float, float]) -> float:
    low, high = scale
    return round(max(0.0, min(100.0, 100 * (value - low) / (high - low))), 1)


def hottest_card(temps: Sequence[DeviceTemperature], limits=None) -> html.Section:
    if not temps:
        body = [html.P("No recent temperature readings.", className="attention-empty")]
    else:
        scale = temperature_scale(temps, limits)
        markers = [] if limits is None else [
            html.Span(className="attention-meter__mark attention-meter__mark--warning",
                      style={"left": f"{_pct(float(limits.warning_c), scale)}%"},
                      title=f"Warning {format_limit(limits.warning_c)} °C"),
            html.Span(className="attention-meter__mark attention-meter__mark--critical",
                      style={"left": f"{_pct(float(limits.critical_c), scale)}%"},
                      title=f"Critical {format_limit(limits.critical_c)} °C"),
        ]
        body = [html.Ol(className="attention-hottest", children=[
            html.Li(className="attention-hottest__row", children=[
                _device_link(t.device_id, t.device_code),
                html.Span(t.transformer_code, className="attention-hottest__where"),
                # CC-VISUALS-1: how close to the limits, not just the number.
                html.Div(className="attention-meter", **{"aria-hidden": "true"}, children=[
                    html.Div(className=f"attention-meter__fill attention-meter__fill--{CONDITION_TONE[t.condition]}",
                             style={"width": f"{_pct(t.value, scale)}%"}),
                    *markers,
                ]),
                html.Span(f"{t.value:.1f} °C", className="attention-hottest__value"),
                # Only a real finding earns a chip; "Limits not set" is said
                # once in the status bar, not repeated on every row.
                *([condition_chip(t.condition)]
                  if t.condition in _FLAGGED else []),
            ])
            for t in temps
        ])]
        if limits is not None:
            body.append(html.P(
                f"Markers: Warning {format_limit(limits.warning_c)} °C · "
                f"Critical {format_limit(limits.critical_c)} °C",
                className="attention-meter__legend",
            ))
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
                # CC-VISUALS-1: one stack per day, a segment per alarm kind.
                html.Div(
                    className="attention-trend__bar",
                    style={"height": f"{round(100 * d.count / peak)}%"},
                    title=", ".join(f"{KIND_LABELS[k]} {n}" for k, n in d.by_kind) or None,
                    children=[
                        html.Div(className=f"attention-trend__seg attention-trend__seg--{KIND_TONE[k]}",
                                 style={"flexGrow": n})
                        for k, n in d.by_kind
                    ],
                ),
            ]),
            html.Span(d.day.strftime("%a %d"), className="attention-trend__label"),
        ])
        for d in days
    ]
    seen = {k for d in days for k, _n in d.by_kind}
    legend = html.Div(className="attention-trend__legend", children=[
        # ADR-026: the level first, so red reads as "Critical", not as "Power Down".
        html.Span(f"{TONE_NAME[KIND_TONE[k]]} · {KIND_LABELS[k]}",
                  className=f"attention-legend attention-legend--{KIND_TONE[k]}")
        for k in ProblemKind if k in seen
    ])
    total = sum(d.count for d in days)
    return cc_card(
        "Alarms per day", [html.Div(className="attention-trend", children=bars), legend],
        subtitle=f"Battery, power-down and sensor alarms · last 7 days · {total} total",
    )
