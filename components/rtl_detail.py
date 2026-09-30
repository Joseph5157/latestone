"""Rendering for one registered client RTL (RTL-UID-DETAIL-01).

Pure render functions over ``services.rtl_detail_service`` values. The missing
state vocabulary is imported from ``components.rtl_fleet`` rather than restated
— one screen calling it "No temperature data" while the other says "No
readings" is how two views of the same fact start disagreeing.

There is no status colour, no health tone and no Online/Offline badge: this
source proves no communication or lifecycle state. There is no metric
selector: temperature is the only confirmed continuous telemetry.
"""
from __future__ import annotations

from dash import dcc, html
import plotly.graph_objects as go

from components.chart_presentation import TEMPLATE, grid_axis, no_data_annotation
from components.kpi_card import kpi_card
from components.rtl_fleet import (
    AMBIGUOUS,
    NO_HIERARCHY,
    NO_MAPPING,
    NO_TEMPERATURE,
    source_time,
    temperature_text,
)
from services.rtl_detail_service import HistoryStatus, RTLDetail, RTLHistory
from services.rtl_fleet_service import HierarchyState, TemperatureState

CHART_HEIGHT = 320
LINE_COLOR = "#3b82f6"

NO_READINGS = "No temperature readings in this period."
SOURCE_UNAVAILABLE = "The client RTL data source is unavailable. No RTL data is shown."

#: Shown instead of a value the source does not carry. A dash, never an empty
#: cell and never the string "None".
ABSENT = "—"


def _temperature_value(rtl: RTLDetail) -> str:
    if rtl.temperature_state is TemperatureState.VALUE:
        return temperature_text(rtl.temperature)
    if rtl.temperature_state is TemperatureState.AMBIGUOUS:
        return AMBIGUOUS
    return NO_TEMPERATURE


def _temperature_note(rtl: RTLDetail) -> str:
    """The one line under the value. Conflicting source values are shown, in
    full, without one being chosen."""
    if rtl.temperature_state is TemperatureState.AMBIGUOUS:
        values = ", ".join(temperature_text(v) for v in rtl.ambiguous_values)
        return f"Conflicting values at the latest timestamp: {values}"
    if rtl.temperature_state is TemperatureState.NO_DATA:
        return "No reading on record"
    return "Latest reading on record"


def _transformer_text(rtl: RTLDetail) -> str:
    return ", ".join(rtl.transformer_codes) if rtl.has_transformer_mapping else NO_MAPPING


def summary(rtl: RTLDetail) -> html.Div:
    """The three facts this source proves about one RTL, and nothing else."""
    return html.Div(className="kpi-row rtl-detail-summary", children=[
        kpi_card("Latest temperature", _temperature_value(rtl), _temperature_note(rtl)),
        kpi_card(
            "Last reading",
            source_time(rtl.last_reported) if rtl.last_reported else NO_TEMPERATURE,
            "As recorded by the RTL source (SAST)" if rtl.last_reported else "No reading on record",
        ),
        kpi_card(
            "Transformer",
            _transformer_text(rtl),
            "Current mapping" if rtl.has_transformer_mapping else "Not currently mapped",
        ),
    ])


def _context_row(label: str, value: str) -> html.Div:
    return html.Div(className="rtl-detail-context__item", children=[
        html.Span(label, className="rtl-detail-context__label"),
        html.Span(value, className="rtl-detail-context__value"),
    ])


def network_context(rtl: RTLDetail) -> html.Section:
    """Zone / Sector / CNC / Feeder for a mapped RTL, on an exact code match.

    Not a Network browser: five labelled facts about this one RTL. An unmapped
    RTL, or a mapped one whose hierarchy row is missing, says which of the two
    it is instead of showing blanks.
    """
    children = [html.H2("Network context", className="rtl-detail-section__title")]

    if rtl.hierarchy_state is HierarchyState.NOT_MAPPED:
        children.append(html.P(NO_MAPPING, className="rtl-detail-empty"))
        children.append(html.P(
            "This RTL has no current transformer mapping in the client source, "
            "so it has no network context.",
            className="rtl-detail-note",
        ))
        return html.Section(className="rtl-detail-context", children=children)

    children.append(_context_row("Transformer", _transformer_text(rtl)))

    if rtl.hierarchy_state is HierarchyState.UNAVAILABLE or rtl.hierarchy is None:
        children.append(html.P(NO_HIERARCHY, className="rtl-detail-empty"))
        children.append(html.P(
            "The client hierarchy reference has no entry for this transformer code. "
            "No hierarchy is inferred.",
            className="rtl-detail-note",
        ))
        return html.Section(className="rtl-detail-context", children=children)

    h = rtl.hierarchy
    for label, value in (
        ("Operating Unit", h.operating_unit),
        ("Zone", h.zone),
        ("Sector", h.sector),
        ("CNC", h.cnc),
        ("Feeder", h.feeder),
    ):
        children.append(_context_row(label, value or ABSENT))
    return html.Section(className="rtl-detail-context", children=children)


def window_range_text(history: RTLHistory) -> str:
    """The exact period on screen (ADR-030: it ends at the last reading)."""
    if history.window_start is None or history.window_end is None:
        return ""
    return f"{source_time(history.window_start)} to {source_time(history.window_end)}"


def history_figure(history: RTLHistory) -> go.Figure:
    """One temperature trace. No second axis, no other metric, no thresholds."""
    figure = go.Figure()
    if history.status is HistoryStatus.DATA and history.readings:
        figure.add_trace(go.Scatter(
            x=[r.reading_time for r in history.readings],
            y=[r.temperature for r in history.readings],
            mode="lines+markers",
            name="Temperature",
            line=dict(color=LINE_COLOR, width=2),
            marker=dict(size=4),
            hovertemplate="%{x|%d %b %Y %H:%M} SAST<br>%{y} °C<extra></extra>",
        ))
    else:
        message = (
            SOURCE_UNAVAILABLE if history.status is HistoryStatus.UNAVAILABLE else NO_READINGS
        )
        figure.add_annotation(**no_data_annotation(message))

    figure.update_layout(
        template=TEMPLATE,
        margin=dict(l=56, r=20, t=16, b=48),
        height=CHART_HEIGHT,
        showlegend=False,
        hovermode="x unified",
        xaxis=grid_axis(title="Source time (SAST)"),
        yaxis=grid_axis(title="°C"),
    )
    return figure


def history_panel(history: RTLHistory) -> html.Div:
    """The chart plus a plain statement of which period it covers."""
    if history.status is HistoryStatus.UNAVAILABLE:
        note = SOURCE_UNAVAILABLE
    elif history.status is HistoryStatus.NOT_REGISTERED:
        note = "This RTL is not in the client's registered directory."
    elif history.status is HistoryStatus.NO_DATA:
        note = NO_READINGS
    else:
        count = len(history.readings)
        note = f"{count} reading" if count == 1 else f"{count} readings"

    range_text = window_range_text(history)
    return html.Div(className="rtl-detail-history", children=[
        html.P(range_text or "No period to show", className="rtl-detail-history__range"),
        html.P(note, className="rtl-detail-history__note"),
        dcc.Graph(
            figure=history_figure(history),
            config={"displayModeBar": False},
            className="rtl-detail-history__chart",
        ),
    ])


def not_registered_panel(device_uid: int | None) -> html.Div:
    """A numeric UID that is not in ``device_list``.

    Deliberately states only that it is not registered. It does NOT say
    whether the UID appears in any other source table — 81 telemetry UIDs and
    88 historical-only UIDs exist, and confirming one from this page would
    turn the route into the existence oracle it must not be.
    """
    return html.Div(className="status-panel status-panel--not-found", children=[
        html.H3("RTL not found"),
        html.P(
            "This UID is not in the client's registered RTL directory, "
            "so there is no RTL to show."
        ),
        dcc.Link("Back to Registered RTLs", href="/plants"),
    ])
