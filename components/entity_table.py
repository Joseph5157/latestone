"""Generic sortable entity table."""
from __future__ import annotations

from dash import dash_table, html


def entity_table(
    table_id: str,
    columns: list[dict],
    rows: list[dict],
    sort_by: str | None = None,
) -> html.Div:
    """Render a sortable, filterable DataTable.

    columns: list of {"name": str, "id": str, ...} dicts.
    rows: list of row dicts.
    """
    return html.Div(
        className="entity-table-wrapper",
        children=[
            dash_table.DataTable(
                id=table_id,
                columns=columns,
                data=rows,
                sort_action="native",
                filter_action="native",
                page_size=30,
                style_as_list_view=True,
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "left", "padding": "8px 12px"},
                style_header={"fontWeight": "600", "backgroundColor": "#f9fafb"},
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#f9fafb"},
                ],
            )
        ],
    )
