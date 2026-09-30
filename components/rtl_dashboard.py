"""Rendering for the factual RTL dashboard (FACTUAL-DASHBOARD-01).

Pure functions over ``services.rtl_dashboard_service`` values. Counts are
registered RTLs; there is no communication state, alarm state or electrical
metric, and no synthetic count.
"""
from __future__ import annotations

from dash import dcc, html

from components.kpi_card import kpi_card
from components.rtl_fleet import source_time
from routes import RTL_LIST_PATH, RTL_NETWORK_PATH
from services.rtl_dashboard_service import RTLDashboard

NO_MAPPING = "No current transformer mapping"
NOTE = (
    "Registered RTLs are every device in the client's RTL directory. RTLs are not "
    "classified by communication or operating state, and no alarm state is shown. "
    "Times are as recorded by the RTL source (SAST)."
)


def _link(label: str, href: str):
    return dcc.Link(label, href=href, className="fleet-overview-link")


def summary_cards(d: RTLDashboard) -> html.Div:
    f, n = d.fleet, d.network
    return html.Div(className="kpi-row fleet-overview-stats", children=[
        kpi_card("Registered RTLs", str(f.registered), "Client RTL directory"),
        kpi_card("Mapped RTLs", str(n.mapped), "With a current transformer mapping"),
        kpi_card("Unmapped RTLs", str(n.unmapped), NO_MAPPING),
        kpi_card("Temperature data available", str(f.with_temperature), "A reading is on record"),
        kpi_card("No temperature data", str(f.no_temperature), "No reading on record"),
    ])


def network_section(d: RTLDashboard) -> html.Section:
    n = d.network
    items = [
        html.Li(["Hierarchy resolved", html.Span(str(n.hierarchy_resolved), className="network-breakdown__count")]),
        html.Li(["Hierarchy unavailable", html.Span(str(n.hierarchy_unavailable), className="network-breakdown__count")]),
        html.Li(["Mapping review", html.Span(str(n.needs_review), className="network-breakdown__count")]),
    ]
    children = [
        html.H2("Network", className="rtl-detail-section__title"),
        html.Ul(className="network-breakdown", children=items),
    ]
    if d.by_zone:
        children += [
            html.H3("RTLs by zone", className="rtl-detail-section__title"),
            html.Ul(className="network-breakdown", children=[
                html.Li([z, html.Span(str(c), className="network-breakdown__count")])
                for z, c in d.by_zone
            ]),
        ]
    children.append(_link("View Network", RTL_NETWORK_PATH))
    return html.Section(className="rtl-summary-panel dashboard-network", children=children)


def temperature_section(d: RTLDashboard) -> html.Section:
    f = d.fleet
    return html.Section(className="rtl-summary-panel dashboard-temperature", children=[
        html.H2("Temperature data", className="rtl-detail-section__title"),
        html.Ul(className="network-breakdown", children=[
            html.Li(["RTLs with temperature data",
                     html.Span(str(f.with_temperature), className="network-breakdown__count")]),
            html.Li(["RTLs with no temperature data",
                     html.Span(str(f.no_temperature), className="network-breakdown__count")]),
        ]),
        html.P(f"Most recent reading on record: {source_time(d.latest_reading)}",
               className="fleet-overview-limits"),
        _link("View Registered RTLs", RTL_LIST_PATH),
    ])


def dashboard_body(d: RTLDashboard) -> html.Div:
    return html.Div([
        summary_cards(d),
        html.Div(className="dashboard-sections", children=[network_section(d), temperature_section(d)]),
        html.P(NOTE, className="fleet-overview-limits"),
    ])


def unavailable_panel() -> html.Div:
    return html.Div(className="status-panel status-panel--empty", children=[
        html.H3("Client RTL data is unavailable"),
        html.P("The client RTL source could not be read. Nothing is shown rather than a partial count."),
    ])
