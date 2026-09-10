"""My RTLs panel — a Technician's own assignment work list on the Fleet Overview.

Presentation only. Rows arrive already built by
`callbacks.listings.build_my_rtls_rows` from the ONE shared `FleetHealth` the
page's render already fetched (ADR-002) — this module issues no query and no
second freshness computation.

Renders ABOVE Fleet Condition for a restricted scope only (`not
scope.is_unrestricted`, ADR-004); Administrator/General never see this panel
at all — not an empty one, since "unrestricted" and "assigned nothing" are
different facts and this component must not blur them. See
`callbacks.listings.my_rtls_section` for the rendering condition itself.

No action controls (ADR-016): each row is a one-click link to the existing,
shared device dashboard — the sole authorized entry point to Program RTL /
Message Forwarding / Deactivate — never a second one.
"""
from __future__ import annotations

from dash import html

from components.card import card_header
from components.entity_table import entity_table

MY_RTLS_TABLE_ID = "my-rtls-table"

#: Same column id the existing devices table uses for its identity column.
#: Safe to reuse: `entity_table`'s row-click navigation is wired per table id
#: (each table's own `active_cell` Input), so two tables sharing a column id
#: never collide.
DEVICE_LINK_COLUMN = "device"

MY_RTLS_COLUMNS = [
    {"name": "RTL", "id": DEVICE_LINK_COLUMN},
    {"name": "Plant", "id": "plant"},
    {"name": "Transformer", "id": "transformer"},
    # Data-delivery freshness only, never an electrical condition (§21) —
    # same rule and same column id as every other listing on this page.
    {"name": "Data", "id": "freshness"},
]


def _plural(n: int) -> str:
    return "RTL" if n == 1 else "RTLs"


def my_rtls_panel(rows: list[dict]) -> html.Div:
    """The Technician's uncapped (D3) work list, or a truthful empty state.

    Empty is not "no panel": a restricted caller with zero active
    assignments (EMPTY scope) still gets this card, saying so explicitly —
    the same distinction `needs_attention`'s own empty state makes between
    "nothing to show" and "not rendered at all".
    """
    if not rows:
        return html.Div(
            className="card my-rtls",
            children=[
                card_header("My RTLs", heading=html.H2),
                html.P(
                    "No RTLs are currently assigned to you.",
                    className="my-rtls__empty",
                ),
            ],
        )
    return html.Div(
        className="card my-rtls",
        children=[
            card_header(
                "My RTLs",
                f"{len(rows)} assigned {_plural(len(rows))}.",
                heading=html.H2,
            ),
            entity_table(
                table_id=MY_RTLS_TABLE_ID,
                columns=MY_RTLS_COLUMNS,
                rows=rows,
                link_column_id=DEVICE_LINK_COLUMN,
                state_column_id="freshness",
                responsive=True,
            ),
        ],
    )
