"""Rendering for the current Network view (LATEST-NETWORK-CONTEXT-01).

Pure render functions over ``services.rtl_network_service`` values. Wording is
factual: counts are *registered* RTLs, missing values are stated in words
("No current transformer mapping", "Hierarchy unavailable"), never a raw null,
and there is no communication-state column and no electrical metric.
"""
from __future__ import annotations

from dash import dcc, html

from components.kpi_card import kpi_card
from routes import rtl_detail_href
from services.rtl_fleet_service import HierarchyState
from services.rtl_network_service import (
    LEVELS,
    SCOPE_ALL,
    SCOPE_HIERARCHY_UNAVAILABLE,
    SCOPE_MAPPED,
    SCOPE_NEEDS_REVIEW,
    SCOPE_UNMAPPED,
    CurrentNetworkRow,
    MappingStatus,
    NetworkSummary,
    level_breakdown,
    scope_counts,
)

NO_MAPPING = "No current transformer mapping"
NO_HIERARCHY = "Hierarchy unavailable"
AMBIGUOUS_MAPPING = "Several current transformer mappings"

LEVEL_LABELS = {"zone": "Zone", "sector": "Sector", "cnc": "CNC", "feeder": "Feeder",
                "transformer": "Transformer"}
LEVEL_PLURALS = {"zone": "zones", "sector": "sectors", "cnc": "CNCs", "feeder": "feeders",
                 "transformer": "transformers"}

SCOPE_LABELS = {
    SCOPE_ALL: "All registered",
    SCOPE_MAPPED: "With a current mapping",
    SCOPE_UNMAPPED: NO_MAPPING,
    SCOPE_HIERARCHY_UNAVAILABLE: NO_HIERARCHY,
    SCOPE_NEEDS_REVIEW: "Needs review",
}

SCOPE_NOTE = (
    "Registered RTLs are every device in the client's RTL directory. The current transformer "
    "is the RTL's present mapping; earlier transformers are history and are not shown here. "
    "RTLs are not classified by communication or operating state."
)

SOURCE_LABELS = {
    "settings": "latest settings record",
    "startup": "latest check-in",
    "telemetry": "latest temperature reading",
}


def scope_options(rows) -> list[dict]:
    counts = scope_counts(rows)
    return [{"label": f"{SCOPE_LABELS[k]} · {n}", "value": k} for k, n in counts.items()]


def level_dropdown_options(values) -> list[dict]:
    return [{"label": v, "value": v} for v in values]


def summary_cards(summary: NetworkSummary, registered_total: int) -> html.Div:
    """Counts over the RTLs in the current view (``summary`` is of the view)."""
    return html.Div(className="kpi-row fleet-overview-stats", children=[
        kpi_card("Registered RTLs in view", str(summary.registered), f"of {registered_total} registered"),
        kpi_card("Mapped RTLs", str(summary.mapped), "With a current transformer mapping"),
        kpi_card("Unmapped RTLs", str(summary.unmapped), NO_MAPPING),
        kpi_card("Hierarchy resolved", str(summary.hierarchy_resolved), "Mapped, full path found"),
        kpi_card("Hierarchy unavailable", str(summary.hierarchy_unavailable),
                 "Mapped, no hierarchy path"),
    ])


def breakdown(rows: tuple[CurrentNetworkRow, ...], level: str | None):
    """RTL counts for the next level down, over the rows in view."""
    if level is None:
        return None
    items = level_breakdown(rows, level)
    if not items:
        return None
    return html.Div([
        html.H2(f"RTLs by {LEVEL_LABELS[level]}", className="rtl-detail-section__title"),
        html.Ul(className="network-breakdown", children=[
            html.Li([v, html.Span(str(n), className="network-breakdown__count")])
            for v, n in items
        ]),
    ])


def _path_cell(row: CurrentNetworkRow, level: str):
    if row.hierarchy_state is HierarchyState.AVAILABLE and row.hierarchy is not None:
        return getattr(row.hierarchy, level) or "—"
    return html.Span("—", className="fleet-overview-empty")


def _transformer_cell(row: CurrentNetworkRow):
    if row.mapping_status is MappingStatus.NOT_MAPPED:
        return html.Span(NO_MAPPING, className="fleet-overview-empty")
    if row.mapping_status is MappingStatus.AMBIGUOUS:
        return html.Span(f"{AMBIGUOUS_MAPPING}: {', '.join(row.mapping_codes)}")
    parts: list = [row.transformer_code]
    if row.hierarchy_state is not HierarchyState.AVAILABLE:
        parts.append(html.Span(NO_HIERARCHY, className="fleet-overview-empty network-review"))
    for d in row.disagreements:
        parts.append(html.Span(
            f"Needs review: {SOURCE_LABELS[d.source.value]} names {', '.join(d.codes)}",
            className="network-review",
            title="Sources disagree about this RTL's transformer; none is chosen over the mapping.",
        ))
    return html.Span(parts)


def _sort_key(row: CurrentNetworkRow):
    path = tuple(
        (getattr(row.hierarchy, lvl) or "").casefold() if row.hierarchy else ""
        for lvl in ("zone", "sector", "cnc", "feeder")
    )
    return (row.hierarchy is None, *path, (row.transformer_code or "").casefold(), row.device_uid)


def _row(row: CurrentNetworkRow) -> html.Tr:
    return html.Tr([
        html.Td(_path_cell(row, "zone"), **{"data-label": "Zone"}),
        html.Td(_path_cell(row, "sector"), **{"data-label": "Sector"}),
        html.Td(_path_cell(row, "cnc"), **{"data-label": "CNC"}),
        html.Td(_path_cell(row, "feeder"), **{"data-label": "Feeder"}),
        html.Td(_transformer_cell(row), **{"data-label": "Transformer"}),
        # The UID links to the canonical detail route, never through /devices.
        html.Td(dcc.Link(str(row.device_uid), href=rtl_detail_href(row.device_uid),
                         className="fleet-overview-link"),
                className="fleet-overview-num", **{"data-label": "RTL"}),
    ])


def network_table(rows: tuple[CurrentNetworkRow, ...]):
    if not rows:
        return html.P("No RTLs match this selection.", className="fleet-overview-empty")
    return html.Table(className="fleet-overview-table", children=[
        html.Thead(html.Tr([html.Th(LEVEL_LABELS[lvl]) for lvl in LEVELS] + [html.Th("RTL")])),
        html.Tbody([_row(r) for r in sorted(rows, key=_sort_key)]),
    ])


def restricted_panel() -> html.Div:
    """Roles without an approved raw-RTL visibility rule (default deny)."""
    return html.Div(className="status-panel status-panel--empty", children=[
        html.H3("Client RTL network not available for your account"),
        html.P(
            "The client RTL network is shown to Administrators and General Users. "
            "There is no approved link between client RTLs and technician assignments yet."
        ),
    ])
