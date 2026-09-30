"""Rendering for Technician Assignments (ADR-032).

Pure functions over ``services.rtl_assignment_service`` values. Wording is the
client's: RTL, Technician, Unassigned RTLs. No SQL table names and no internal
enum values reach the screen - provenance is shown as a sentence.
"""
from __future__ import annotations

from datetime import datetime

from dash import dcc, html

from components.kpi_card import kpi_card
from pages import rtl_assignments as page
from routes import rtl_detail_href
from services.rtl_assignment_service import (
    PROVENANCE_LEGACY_IMPORT,
    AssignmentRow,
    RtlAssignmentRecord,
)

NO_MAPPING = "No current transformer mapping"
UNASSIGNED = "Unassigned"
LEGACY_TEXT = "Imported from legacy assignment data"
ROW_LIMIT = 200


def when(value: datetime | None) -> str:
    return value.strftime("%d %b %Y %H:%M UTC") if value else "—"


def stats(rows: tuple[AssignmentRow, ...]) -> html.Div:
    assigned = sum(r.is_assigned for r in rows)
    return html.Div(className="kpi-row fleet-overview-stats", children=[
        kpi_card("Registered RTLs", str(len(rows)), "In the client directory"),
        kpi_card("Assigned", str(assigned), "One Technician each"),
        kpi_card("Unassigned RTLs", str(len(rows) - assigned), "Administrator-only pool"),
    ])


def since_text(row: AssignmentRow) -> str:
    if not row.is_assigned:
        return "—"
    return LEGACY_TEXT if row.since_is_import else when(row.since)


def _pick(uid: int, mode: str, label: str, primary: bool = False) -> html.Button:
    return html.Button(
        label, type="button", n_clicks=0,
        id={"type": page.PICK_TYPE, "uid": uid, "mode": mode},
        className="btn btn--primary btn--sm" if primary else "btn btn--sm",
    )


def _row(row: AssignmentRow) -> html.Tr:
    transformer = ", ".join(row.transformer_codes) if row.transformer_codes else NO_MAPPING
    actions = [_pick(row.device_uid, "reassign" if row.is_assigned else "assign",
                     "Reassign" if row.is_assigned else "Assign", primary=not row.is_assigned),
               _pick(row.device_uid, "history", "History")]
    return html.Tr([
        html.Td(dcc.Link(str(row.device_uid), href=rtl_detail_href(row.device_uid),
                         className="fleet-overview-link"),
                className="fleet-overview-num", **{"data-label": "RTL UID"}),
        html.Td(row.technician_name or html.Span(UNASSIGNED, className="fleet-overview-empty"),
                **{"data-label": "Technician"}),
        html.Td(transformer, className="" if row.transformer_codes else "fleet-overview-empty",
                **{"data-label": "Transformer"}),
        html.Td(since_text(row), **{"data-label": "Assigned since"}),
        html.Td(html.Div(className="rtl-assign-actions", children=actions),
                **{"data-label": "Actions"}),
    ])


def assignment_table(rows: tuple[AssignmentRow, ...]):
    if not rows:
        return html.P("No RTLs match this selection.", className="fleet-overview-empty")
    shown = rows[:ROW_LIMIT]
    children = [html.Table(className="fleet-overview-table", children=[
        html.Thead(html.Tr([html.Th("RTL UID"), html.Th("Technician"), html.Th("Transformer"),
                            html.Th("Assigned since"), html.Th("Actions")])),
        html.Tbody([_row(r) for r in shown]),
    ])]
    if len(rows) > len(shown):
        children.append(html.P(
            f"Showing the first {len(shown)} of {len(rows)} RTLs. Search by UID or filter to narrow.",
            className="fleet-overview-limits"))
    return html.Div(children)


def technician_filter_options(rows: tuple[AssignmentRow, ...]) -> list[dict]:
    seen: dict[int, str] = {}
    for r in rows:
        if r.technician_user_id is not None:
            seen[r.technician_user_id] = r.technician_name or str(r.technician_user_id)
    return [{"label": name, "value": uid} for uid, name in sorted(seen.items(), key=lambda kv: kv[1])]


def history_table(records: list[RtlAssignmentRecord]):
    if not records:
        return html.P("This RTL has never been assigned.", className="fleet-overview-empty")
    body = []
    for r in records:
        legacy = r.provenance == PROVENANCE_LEGACY_IMPORT
        started = LEGACY_TEXT if legacy else when(r.assigned_at)
        by = "—" if legacy else (r.assigned_by_name or "—")
        body.append(html.Tr([
            html.Td(r.technician_name, **{"data-label": "Technician"}),
            html.Td(started, **{"data-label": "Started"}),
            html.Td("Current" if r.is_current else when(r.ended_at), **{"data-label": "Ended"}),
            html.Td(by, **{"data-label": "Assigned by"}),
            html.Td("Legacy assignment data" if legacy else "Administrator",
                    **{"data-label": "Source"}),
        ]))
    return html.Div([
        html.H3("Assignment history", className="rtl-detail-section__title"),
        html.Table(className="fleet-overview-table", children=[
            html.Thead(html.Tr([html.Th("Technician"), html.Th("Started"), html.Th("Ended"),
                                html.Th("Assigned by"), html.Th("Source")])),
            html.Tbody(body),
        ]),
    ])


def unavailable_panel() -> html.Div:
    return html.Div(className="status-panel status-panel--empty", children=[
        html.H3("Client RTL data is unavailable"),
        html.P("The registered RTL list could not be read, so no assignments are shown."),
    ])
