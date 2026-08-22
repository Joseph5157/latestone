"""Needs Attention panel — compact exception list for the Fleet Overview.

Presentation only. Rows arrive presentation-ready from the listing callback,
which derives them from the shared `FleetHealth` (never a second computation).
The panel is deliberately limited to data-freshness exceptions the current
model already knows — ``NO_DATA`` and ``STALE``. It never fabricates electrical
"warning" / "critical" states and never labels stale data as equipment failure.
"""
from __future__ import annotations

from dash import dcc, html

from components.freshness_presentation import FRESHNESS_PRESENTATION
from services.monitoring_service import Freshness

DEFAULT_VISIBLE_ITEMS = 5


def needs_attention(
    rows: list[dict],
    empty_message: str = (
        "No current data-freshness exceptions."
    ),
    max_items: int = DEFAULT_VISIBLE_ITEMS,
) -> html.Div:
    """Render a compact exception panel above the plants table.

    Each row is a dict with presentation-ready values:

    * ``entity`` — display name (plant name)
    * ``entity_id`` — stable identifier (for the link)
    * ``type`` — entity type label ("Plant")
    * ``issue`` — rollup label (e.g. "Stale · 2 of 3 devices")
    * ``last_update`` — pre-formatted string (e.g. "2h 17m ago · ...")
    * ``href`` — stable route to the entity page
    * ``_state`` — ``Freshness`` value for styling (``no_data`` / ``stale``)
    * ``_severity`` — ``severity_rank`` int for internal ordering

    Rows must arrive in exception-first order; this function does not re-sort.
    """
    if not rows:
        return _empty_panel(empty_message)

    visible_rows = rows[:max_items]
    total = len(rows)
    disclosure = (
        f"Showing {len(visible_rows)} of {total} affected plants."
        if total > len(visible_rows)
        else f"{total} affected {'plant' if total == 1 else 'plants'}."
    )

    return html.Div(
        className="needs-attention",
        children=[
            html.H2("Needs attention", className="needs-attention__title"),
            html.Div(
                className="needs-attention__summary-row",
                children=[
                    html.P(disclosure, className="needs-attention__summary"),
                    dcc.Link(
                        "View full fleet",
                        href="#fleet-plants",
                        className="needs-attention__all",
                    ),
                ],
            ),
            html.Div(
                className="needs-attention__list",
                children=[_row(r) for r in visible_rows],
            ),
        ],
    )


def _empty_panel(message: str) -> html.Div:
    """Panel with a truthful empty state — never an absent panel, which would
    make 'nothing to show' and 'we failed to load' look identical."""
    return html.Div(
        className="needs-attention",
        children=[
            html.H2("Needs attention", className="needs-attention__title"),
            html.P(message, className="needs-attention__empty"),
        ],
    )


def _row(row: dict) -> html.Div:
    """A single exception row: state badge · entity · type · detail · age · link."""
    state = Freshness(row["_state"])
    return html.Div(
        className=f"needs-attention__row needs-attention__row--{state.value}",
        children=[
            html.Span(
                FRESHNESS_PRESENTATION[state].label,
                className=f"needs-attention__badge needs-attention__badge--{state.value}",
            ),
            html.Span(row["entity"], className="needs-attention__entity"),
            html.Span(row["type"], className="needs-attention__type"),
            html.Span(row["issue"], className="needs-attention__detail"),
            html.Span(row["last_update"], className="needs-attention__age"),
            dcc.Link(
                "Open",
                href=row["href"],
                className="needs-attention__link",
            ),
        ],
    )
