"""A labelled filter dropdown for an admin table's filter row.

Shared by Device Management (DEVICE-FILTERS-1) and Assignments
(ASSIGN-TOOLBAR-1), which filter the same device rows the same way.
"""
from __future__ import annotations

from dash import dcc, html

#: Values are `Freshness` states, matched against each row's `_state`.
DATA_FILTER_OPTIONS = [
    {"label": "All", "value": "all"},
    {"label": "Fresh", "value": "fresh"},
    {"label": "Stale", "value": "stale"},
    {"label": "No data", "value": "no_data"},
]


def column_filter(label: str, dropdown: dcc.Dropdown) -> html.Div:
    """One labelled column filter.

    dcc.Dropdown renders a div, which a <label for> cannot reach, so the
    label names a role="group" around it, as the Status filter does.
    """
    label_id = f"{dropdown.id}-label"
    return html.Div(
        className="device-admin-filters__item",
        children=[
            html.Label(label, id=label_id, className="device-admin-filters__label"),
            html.Div(
                role="group",
                **{"aria-labelledby": label_id},
                children=[dropdown],
            ),
        ],
    )
