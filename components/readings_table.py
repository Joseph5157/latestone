"""Recent readings table component.

Metric-driven: column header comes from MetricConfig, no status column
(implied thresholds we do not have).
"""
from __future__ import annotations

from dash import dash_table, html

from config.metrics import MetricConfig, format_value, get_metric, METRICS
from services.monitoring_service import Reading


def build_table_rows(metric: MetricConfig, readings: list[Reading]) -> list[dict]:
    """Format readings for the DataTable. Readings expected newest-first."""
    rows = []
    for r in readings:
        rows.append(
            {
                "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M"),
                "value": format_value(metric, r.value),
            }
        )
    return rows


def readings_table(table_id: str = "readings-table", metric: MetricConfig | None = None):
    """DataTable with metric-driven column header."""
    if metric is None:
        metric = METRICS[0]
    return html.Div(
        className="readings-table-container",
        children=[
            dash_table.DataTable(
                id=table_id,
                columns=[
                    {"name": "Timestamp (UTC)", "id": "timestamp"},
                    {"name": metric.label, "id": "value"},
                ],
                data=[],
                page_size=15,
                style_as_list_view=True,
                # ENT-6B: aligned with entity_table's shared cell treatment.
                # No font-family/font-size here — the vendor stylesheet sets
                # neither, so cells inherit the body's Inter at page size
                # exactly as entity tables do; declaring it inline was drift.
                style_cell={
                    "padding": "11px 12px",
                    "textAlign": "left",
                },
                # Same header and zebra values as entity_table so both table
                # families read as one system. Header rule colour uses the
                # border token rather than a second literal grey.
                style_header={
                    "backgroundColor": "#f9fafb",
                    "fontWeight": "600",
                    "borderBottom": "1px solid var(--color-border)",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#f9fafb"},
                ],
            )
        ],
    )
