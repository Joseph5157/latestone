"""Administrator audit-log viewer layout; data is supplied by its callback."""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table


AUDIT_LOG_TABLE_ID = "audit-log-table"
AUDIT_LOG_ERROR_ID = "audit-log-error"
AUDIT_LOG_SUMMARY_ID = "audit-log-summary"


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--audit-log",
        children=[
            app_header(breadcrumb_children=breadcrumb([("Audit Log", None)])),
            html.Header(
                className="admin-page-heading",
                children=[
                    html.Div("Administration", className="admin-page-heading__eyebrow"),
                    html.H1("Audit Log"),
                    html.P(
                        "A read-only record of application activity.",
                        className="admin-page-heading__description",
                    ),
                ],
            ),
            html.Div(
                className="admin-section-heading",
                children=[
                    html.Div(
                        children=[
                            html.Div("Activity", className="admin-section-heading__eyebrow"),
                            html.H2("Recorded actions"),
                        ],
                    ),
                    html.P("Newest activity appears first. Audit records cannot be changed here."),
                ],
            ),
            html.Div(id=AUDIT_LOG_ERROR_ID, className="listing-error"),
            html.P(id=AUDIT_LOG_SUMMARY_ID, className="page__meta"),
            entity_table(
                table_id=AUDIT_LOG_TABLE_ID,
                columns=[
                    {"name": "Timestamp", "id": "occurred_at"},
                    {"name": "Actor", "id": "actor"},
                    {"name": "Action", "id": "operation"},
                    {"name": "Entity type", "id": "entity_type"},
                    {"name": "Entity ID", "id": "entity_id"},
                ],
                rows=[],
                responsive=True,
                column_widths={
                    "occurred_at": "19%",
                    "actor": "20%",
                    "operation": "24%",
                    "entity_type": "18%",
                },
            ),
        ],
    )
