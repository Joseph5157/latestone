"""Rendering for the real Fleet Overview (SATURDAY-REAL-FLEET-01).

Pure render functions over `services.rtl_fleet_service` values. Wording is
factual: 339-style counts are the *registered* directory, never "active" or
"online". Missing values are stated in words, never shown as raw nulls, and
there is no Online/Offline column and no electrical metric.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from dash import dcc, html

from components.kpi_card import kpi_card
from routes import RTL_LIST_PATH, RTL_NETWORK_PATH, rtl_detail_href
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


def network_coverage_line(summary: FleetSummary) -> html.P:
    """One factual line of network coverage with the way into the Network view.

    Derived from the same fleet snapshot as the cards (the fleet rows apply the
    ADR-031 mapping/hierarchy rule), so it costs no further source read.
    """
    return html.P(className="fleet-overview-limits network-coverage", children=[
        f"Network coverage: {summary.mapped} of {summary.registered} registered RTLs have a "
        f"current transformer mapping · {summary.hierarchy_resolved} hierarchy resolved · "
        f"{summary.hierarchy_unavailable} hierarchy unavailable. ",
        dcc.Link("View Network", href=RTL_NETWORK_PATH, className="fleet-overview-link"),
    ])


def summary_block(summary: FleetSummary) -> html.Div:
    return html.Div([summary_cards(summary), network_coverage_line(summary)])


def rtl_summary_panel(summary: FleetSummary) -> html.Section:
    """Compact real-RTL summary for the Command Center (RTL-NETWORK-USE-01).

    Facts only: no communication or operating state, and no synthetic counts.
    """
    return html.Section(className="rtl-summary-panel", children=[
        html.H2("Registered RTLs (client directory)", className="rtl-detail-section__title"),
        html.Div(className="kpi-row fleet-overview-stats", children=[
            kpi_card("Registered RTLs", str(summary.registered), "Client RTL directory"),
            kpi_card("Mapped RTLs", str(summary.mapped), "With a current transformer mapping"),
            kpi_card("Unmapped RTLs", str(summary.unmapped), NO_MAPPING),
            kpi_card("Temperature data available", str(summary.with_temperature),
                     f"{summary.no_temperature} with no reading on record"),
        ]),
        network_coverage_line(summary),
        dcc.Link("View Registered RTLs", href=RTL_LIST_PATH, className="fleet-overview-link"),
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
        # RTL-UID-DETAIL-01: the UID is the link, because the UID is the
        # identity. It goes to the canonical `/rtls/<uid>` route built by the
        # shared helper — never through `/devices/...`, which addresses a
        # synthetic application device with no approved mapping to this RTL.
        # Every registered row links, whatever its telemetry or mapping state:
        # registration is what makes the detail page exist.
        html.Td(
            dcc.Link(str(row.device_uid), href=rtl_detail_href(row.device_uid),
                     className="fleet-overview-link"),
            className="fleet-overview-num", **{"data-label": "RTL UID"},
        ),
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
