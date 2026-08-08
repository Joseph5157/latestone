"""Recent readings table component."""
from __future__ import annotations

from dash import dash_table, html

from config.settings import demo_device
from services.temperature_service import Reading, Status, get_status


def _row_status(temp: float) -> str:
    return get_status(temp).value


def build_table_rows(readings: list[Reading]) -> list[dict]:
    """readings expected newest-first."""
    rows = []
    for r in readings:
        status = _row_status(r.temperature_c)
        rows.append(
            {
                "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M"),
                "temperature": f"{r.temperature_c:.1f} {demo_device.unit}",
                "status": status,
            }
        )
    return rows


def readings_table(id_prefix: str = ""):
    return html.Div(
        className="readings-table-container",
        children=[
            dash_table.DataTable(
                id=f"{id_prefix}readings-table",
                columns=[
                    {"name": "Timestamp", "id": "timestamp"},
                    {"name": "Temperature", "id": "temperature"},
                    {"name": "Status", "id": "status"},
                ],
                data=[],
                page_size=15,
                style_as_list_view=True,
                style_cell={
                    "fontFamily": "Inter, system-ui, sans-serif",
                    "fontSize": "13px",
                    "padding": "8px 12px",
                    "textAlign": "left",
                },
                style_header={
                    "backgroundColor": "#f3f4f6",
                    "fontWeight": "600",
                    "borderBottom": "1px solid #d1d5db",
                },
                style_data_conditional=[
                    {
                        "if": {"filter_query": '{status} = "Warning"'},
                        "backgroundColor": "#fef2f2",
                        "color": "#991b1b",
                    },
                ],
            )
        ],
    )
