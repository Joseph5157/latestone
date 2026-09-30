"""Rendering for the real Fleet Overview (SATURDAY-REAL-FLEET-01).

Pure render functions over `services.rtl_fleet_service` values. Wording is
factual: 339-style counts are the *registered* directory, never "active" or
"online". Missing values are stated in words, never shown as raw nulls, and
there is no Online/Offline column and no electrical metric.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from dash import html

from components.kpi_card import kpi_card
from services.rtl_fleet_service import (
    FleetSummary,
    HierarchyState,
    RTLFleetRow,
    RealFleet,
    TemperatureState,
)

NO_TEMPERATURE = "No temperature data"
NO_MAPPING = "No current transformer mapping"
NO_HIERARCHY = "Hierarchy unavailable"
AMBIGUOUS = "Ambiguous latest temperature"

FILTER_ALL = "all"
FILTER_WITH_TEMPERATURE = "with_temperature"
FILTER_NO_TEMPERATURE = "no_temperature"
FILTER_NO_MAPPING = "no_mapping"

FILTER_LABELS = {
    FILTER_ALL: "All registered",
    FILTER_WITH_TEMPERATURE: "With temperature data",
    FILTER_NO_TEMPERATURE: NO_TEMPERATURE,
    FILTER_NO_MAPPING: NO_MAPPING,
}

_FILTERS = {
    FILTER_ALL: lambda r: True,
    FILTER_WITH_TEMPERATURE: lambda r: r.temperature_state is not TemperatureState.NO_DATA,
    FILTER_NO_TEMPERATURE: lambda r: r.temperature_state is TemperatureState.NO_DATA,
    FILTER_NO_MAPPING: lambda r: not r.has_transformer_mapping,
}

SCOPE_NOTE = (
    "Registered RTLs are every device in the client's RTL directory. This is not a "
    "count of active or online RTLs. Times are as recorded by the RTL source (SAST)."
)


def temperature_text(value: Decimal | None) -> str:
    return f"{float(value):.1f} °C"


def source_time(moment: datetime | None) -> str:
    """Naive source-clock value, labelled SAST (ADR-029); no conversion."""
    return moment.strftime("%d %b %Y %H:%M SAST") if moment else "—"


def filter_counts(rows) -> dict[str, int]:
    return {key: sum(1 for r in rows if test(r)) for key, test in _FILTERS.items()}


def filter_options(fleet: RealFleet) -> list[dict]:
    counts = filter_counts(fleet.rows)
    return [{"label": f"{FILTER_LABELS[k]} · {n}", "value": k} for k, n in counts.items()]


def filter_rows(fleet: RealFleet, filter_key: str) -> tuple[RTLFleetRow, ...]:
    """An unknown filter shows every registered RTL."""
    test = _FILTERS.get(filter_key, _FILTERS[FILTER_ALL])
    return tuple(r for r in fleet.rows if test(r))


def summary_cards(summary: FleetSummary) -> html.Div:
    with_note = f"{summary.ambiguous} with an ambiguous latest value" if summary.ambiguous else "Latest reading on record"
    return html.Div(className="kpi-row fleet-overview-stats", children=[
        kpi_card("Registered RTLs", str(summary.registered), "Client RTL directory"),
        kpi_card("Current transformer mappings", str(summary.mapped), "RTLs with a mapping"),
        kpi_card("With temperature data", str(summary.with_temperature), with_note),
        kpi_card("No temperature data", str(summary.no_temperature), "Registered, no reading on record"),
    ])


def _temperature_cell(row: RTLFleetRow):
    if row.temperature_state is TemperatureState.VALUE:
        return html.Span(temperature_text(row.temperature), className="fleet-overview-num")
    if row.temperature_state is TemperatureState.AMBIGUOUS:
        values = ", ".join(temperature_text(v) for v in row.ambiguous_values)
        return html.Span(f"{AMBIGUOUS} ({values})", title="Conflicting readings share the latest timestamp; none is chosen.")
    return html.Span(NO_TEMPERATURE, className="fleet-overview-empty")


def _location_cell(row: RTLFleetRow):
    if row.hierarchy_state is HierarchyState.NOT_MAPPED:
        return html.Span("—", className="fleet-overview-empty")
    if row.hierarchy_state is HierarchyState.UNAVAILABLE or row.hierarchy is None:
        return html.Span(NO_HIERARCHY, className="fleet-overview-empty")
    h = row.hierarchy
    path = " · ".join(part for part in (h.zone, h.sector, h.cnc) if part)
    return html.Span([path, html.Br(), h.feeder] if path and h.feeder else (path or h.feeder or NO_HIERARCHY))


def _row(row: RTLFleetRow) -> html.Tr:
    transformer = (
        ", ".join(row.transformer_codes) if row.has_transformer_mapping else NO_MAPPING
    )
    return html.Tr([
        html.Td(str(row.device_uid), className="fleet-overview-num", **{"data-label": "RTL UID"}),
        html.Td(_temperature_cell(row), **{"data-label": "Latest temperature"}),
        html.Td(source_time(row.last_reported), **{"data-label": "Last reading"}),
        html.Td(
            html.Span(transformer, className="" if row.has_transformer_mapping else "fleet-overview-empty"),
            **{"data-label": "Transformer"},
        ),
        html.Td(_location_cell(row), **{"data-label": "Zone · Sector · CNC / Feeder"}),
    ])


def fleet_table(rows: tuple[RTLFleetRow, ...]):
    if not rows:
        return html.P("No RTLs match this filter.", className="fleet-overview-empty")
    return html.Table(className="fleet-overview-table", children=[
        html.Thead(html.Tr([
            html.Th("RTL UID"), html.Th("Latest temperature"), html.Th("Last reading"),
            html.Th("Transformer"), html.Th("Zone · Sector · CNC / Feeder"),
        ])),
        html.Tbody([_row(r) for r in rows]),
    ])


def restricted_panel() -> html.Div:
    """Roles without an approved raw-RTL visibility rule (default deny)."""
    return html.Div(className="status-panel status-panel--empty", children=[
        html.H3("Client RTL fleet not available for your account"),
        html.P(
            "The client RTL directory is shown to Administrators and General Users. "
            "There is no approved link between client RTLs and technician assignments yet."
        ),
    ])
