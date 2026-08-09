"""Generic sortable entity table."""
from __future__ import annotations

from dash import dash_table, html


def entity_table(
    table_id: str,
    columns: list[dict],
    rows: list[dict],
    sort_by: str | None = None,
    link_column_id: str | None = None,
) -> html.Div:
    """Render a sortable, filterable DataTable.

    columns: list of {"name": str, "id": str, ...} dicts.
    rows: list of row dicts. Rows may carry extra keys not listed in
        `columns` (e.g. an internal id) for a click callback to read via
        `active_cell` without rendering them as a column.
    link_column_id: column id styled to look clickable; a same-tab
        navigation callback (keyed off `active_cell`) is wired separately.
        Plain cell click-to-navigate is used instead of markdown links
        because dash_table hardcodes markdown-rendered links to
        target="_blank", which would break in-app navigation.
    """
    style_cell_conditional = (
        [
            {
                "if": {"column_id": link_column_id},
                "color": "#2563eb",
                "textDecoration": "underline",
                "cursor": "pointer",
                # The identity column wraps instead of truncating. Every other
                # column gets an ellipsis (see app.css), but half of "Itaipu
                # Binacional Dam (Paraguay part)" is not an identity, and this
                # is the cell the operator clicks to navigate.
                "whiteSpace": "normal",
                "overflowWrap": "anywhere",
            }
        ]
        if link_column_id
        else []
    )
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
                # OBS-2: dash_table's stylesheet sets `text-overflow: inherit`
                # on the inner .dash-cell-value with a 4-class selector, so the
                # value must be set on the `td` here — an app.css rule targeting
                # the inner div loses the cascade and silently does nothing.
                # Verified against computed style, not the stylesheet source.
                style_cell={
                    "textAlign": "left",
                    "padding": "8px 12px",
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                },
                style_header={"fontWeight": "600", "backgroundColor": "#f9fafb"},
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#f9fafb"},
                ],
                style_cell_conditional=style_cell_conditional,
            )
        ],
    )
