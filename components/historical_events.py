"""Rendering for Historical Events (HISTORICAL-EVENTS-01).

Pure functions over ``services.rtl_events_service`` values. The wording states
that these are recorded events: no alarm state, no acknowledgement, no
severity, and the network columns are the RTL's *current* mapping.
"""
from __future__ import annotations

from dash import dcc, html

from components.rtl_fleet import source_time
from routes import rtl_detail_href
from services.rtl_events_service import PAGE_SIZE, EventsPage, EventType, HistoricalEvent
from services.rtl_fleet_service import HierarchyState
from services.rtl_network_service import MappingStatus

NO_MAPPING = "No current transformer mapping"
NO_HIERARCHY = "Hierarchy unavailable"
NOT_REGISTERED = "Not in the current RTL directory"

NOTE = (
    "Historical Events are records from the client event logs. They do not show whether "
    "a problem is still present, and no acknowledgement or resolution is recorded. "
    "Current Transformer and Current Network Context are the RTL's present mapping, not "
    "where it was at the time of the event. Times are as recorded by the RTL source (SAST)."
)
NO_EVENTS = "No events were recorded for this selection."
INVALID = ("Check the date range and RTL UID: the UID must be a whole number "
           "and the range must end after it starts.")


def value_text(event: HistoricalEvent) -> str:
    v = event.recorded_value
    if v is None:
        return "—"
    if event.value_kind == "temperature":
        return f"{float(v):.1f} °C"
    if event.value_kind == "battery_voltage":
        return f"{float(v):.2f} V"
    return f"{float(v):.1f}"  # Sensor Error: the number as recorded, not interpreted


def type_summary(page: EventsPage) -> html.Ul:
    """Counts per event class for the selected window (and UID), not lifetime."""
    return html.Ul(className="network-breakdown", children=[
        html.Li([t.label, html.Span(str(page.counts[t]), className="network-breakdown__count")])
        for t in EventType
    ])


def _uid_cell(event: HistoricalEvent):
    if event.registered:
        return dcc.Link(str(event.device_uid), href=rtl_detail_href(event.device_uid),
                        className="fleet-overview-link")
    return html.Span(f"Historical RTL UID {event.device_uid}", className="fleet-overview-empty")


def _transformer_cell(event: HistoricalEvent):
    row = event.current
    if row is None:
        return html.Span(NOT_REGISTERED, className="fleet-overview-empty")
    if row.mapping_status is MappingStatus.NOT_MAPPED:
        return html.Span(NO_MAPPING, className="fleet-overview-empty")
    return row.transformer_code or ", ".join(row.mapping_codes)


def _context_cell(event: HistoricalEvent):
    row = event.current
    if row is None or row.mapping_status is MappingStatus.NOT_MAPPED:
        return html.Span("—", className="fleet-overview-empty")
    if row.hierarchy_state is not HierarchyState.AVAILABLE or row.hierarchy is None:
        return html.Span(NO_HIERARCHY, className="fleet-overview-empty")
    h = row.hierarchy
    return " › ".join(p for p in (h.zone, h.sector, h.cnc, h.feeder) if p) or "—"


def _row(event: HistoricalEvent) -> html.Tr:
    return html.Tr([
        html.Td(source_time(event.recorded_at), **{"data-label": "Recorded At"}),
        html.Td(event.event_type.label, **{"data-label": "Event"}),
        html.Td(_uid_cell(event), className="fleet-overview-num", **{"data-label": "RTL UID"}),
        html.Td(value_text(event), className="fleet-overview-num", **{"data-label": "Recorded Value"}),
        html.Td(event.event_transformer_code or "—", **{"data-label": "Recorded Transformer"}),
        html.Td(_transformer_cell(event), **{"data-label": "Current Transformer"}),
        html.Td(_context_cell(event), **{"data-label": "Current Network Context"}),
    ])


def events_table(page: EventsPage):
    if not page.events:
        return html.P(NO_EVENTS, className="fleet-overview-empty")
    heads = ("Recorded At", "Event", "RTL UID", "Recorded Value", "Recorded Transformer",
             "Current Transformer", "Current Network Context")
    return html.Table(className="fleet-overview-table", children=[
        html.Thead(html.Tr([html.Th(h) for h in heads])),
        html.Tbody([_row(e) for e in page.events]),
    ])


def page_status(page: EventsPage) -> html.P:
    if not page.total:
        return html.P("0 events", className="fleet-overview-limits")
    first = page.page * PAGE_SIZE + 1
    last = first + len(page.events) - 1
    return html.P(f"Events {first}–{last} of {page.total} · page {page.page + 1} of {page.page_count} · "
                  "newest first", className="fleet-overview-limits")


def body(page: EventsPage) -> html.Div:
    return html.Div([
        html.P(f"Recorded {page.start:%d %b %Y} to {page.end:%d %b %Y}", className="fleet-overview-limits"),
        type_summary(page),
        page_status(page),
        events_table(page),
        html.P(NOTE, className="fleet-overview-limits"),
    ])


def message(text: str) -> html.Div:
    return html.Div(className="status-panel status-panel--empty", children=[html.P(text)])
