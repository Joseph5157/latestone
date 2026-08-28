"""Needs Attention panel — grouped exception queue for the Fleet Overview.

Presentation only. The grouped Plant -> Transformer -> RTL tree arrives
presentation-ready from the listing callback, derived from the shared
`FleetHealth` (never a second computation). Only NON-FRESH branches appear;
the panel never fabricates electrical "warning"/"critical" states and never
labels stale data as equipment failure.

The leaf cap is applied by the builder and counts ACTIONABLE RTL leaves only —
plant and transformer headings are hierarchy context and render automatically
beneath whichever leaves are shown.
"""
from __future__ import annotations

from dash import dcc, html

from components.card import card_header
from components.freshness_presentation import FRESHNESS_PRESENTATION
from services.monitoring_service import Freshness


def needs_attention(
    queue: dict,
    empty_message: str = (
        "No current data-freshness exceptions."
    ),
) -> html.Div:
    """Render the exception queue above the fleet inventory table.

    ``queue`` is the dict built by
    ``callbacks.listings.build_exception_queue``: ``groups`` (ordered,
    already capped on RTL leaves), plus the totals the disclosure line
    reports truthfully.
    """
    groups = (queue or {}).get("groups") or []
    if not groups:
        return _empty_panel(empty_message)

    return html.Div(
        className="card needs-attention",
        children=[
            # Title, disclosure and the fleet link are the card header's three
            # slots; they previously needed a bespoke summary row because no
            # card had an action slot to put the link in.
            card_header(
                "Needs attention",
                _disclosure(queue),
                # A plain anchor, not dcc.Link: Dash intercepts dcc.Link
                # clicks as route changes, so an in-page hash target must
                # stay a real anchor to scroll without rewriting the URL.
                action=html.A(
                    "View full fleet",
                    href="#fleet-plants",
                    className="needs-attention__all",
                ),
                heading=html.H2,
            ),
            html.Div(
                className="needs-attention__list",
                children=[_plant_group(g) for g in groups],
            ),
        ],
    )


def _plural(count: int, singular: str) -> str:
    return f"{count} {singular}" if count == 1 else f"{count} {singular}s"


def _disclosure(queue: dict) -> str:
    """Truthful counts: RTLs are the actionable unit; plants give scope."""
    total = queue.get("total_rtls", 0)
    shown = queue.get("shown_rtls", 0)
    plants = queue.get("plant_count", 0)
    if total == 0:
        return f"{_plural(plants, 'affected plant')}."
    scope = f"across {_plural(plants, 'plant')}"
    if shown < total:
        return f"Showing {shown} of {_plural(total, 'affected RTL')} {scope}."
    return f"{_plural(total, 'affected RTL')} {scope}."


def _empty_panel(message: str) -> html.Div:
    """Panel with a truthful empty state — never an absent panel, which would
    make 'nothing to show' and 'we failed to load' look identical."""
    return html.Div(
        className="card needs-attention",
        children=[
            card_header("Needs attention", heading=html.H2),
            html.P(message, className="needs-attention__empty"),
        ],
    )


def _badge(state_value: str) -> html.Span:
    state = Freshness(state_value)
    return html.Span(
        FRESHNESS_PRESENTATION[state].label,
        className=f"needs-attention__badge needs-attention__badge--{state.value}",
    )


def _age(row: dict) -> html.Span:
    return html.Span(row["last_update"], className="needs-attention__age")


def _plant_group(group: dict) -> html.Div:
    """Plant header row + its non-fresh subtree. Context level: roll-up state."""
    return html.Div(
        className=(
            f"needs-attention__group needs-attention__group--{group['_state']}"
        ),
        children=[
            html.Div(
                className=(
                    f"needs-attention__row needs-attention__row--group "
                    f"needs-attention__row--{group['_state']}"
                ),
                children=[
                    _badge(group["_state"]),
                    html.Span(group["entity"], className="needs-attention__entity"),
                    html.Span(group["issue"], className="needs-attention__detail"),
                    _age(group),
                    dcc.Link(
                        "Open", href=group["href"],
                        className="needs-attention__link",
                    ),
                ],
            ),
            html.Div(
                className="needs-attention__subtree",
                children=[_transformer_branch(t) for t in group["children"]],
            ),
        ],
    )


def _transformer_branch(branch: dict) -> html.Div:
    """Transformer context row + its non-fresh RTL leaves."""
    children: list = [
        html.Div(
            className=(
                f"needs-attention__row needs-attention__row--transformer "
                f"needs-attention__row--{branch['_state']}"
            ),
            children=[
                _badge(branch["_state"]),
                dcc.Link(
                    branch["entity"], href=branch["href"],
                    className="needs-attention__entity-link",
                ),
                html.Span(branch["issue"], className="needs-attention__detail"),
                _age(branch),
            ],
        ),
    ]
    if branch["children"]:
        children.append(
            html.Div(
                className=(
                    "needs-attention__subtree needs-attention__subtree--leaves"
                ),
                children=[_rtl_leaf(leaf) for leaf in branch["children"]],
            )
        )
    return html.Div(className="needs-attention__branch", children=children)


def _rtl_leaf(leaf: dict) -> html.Div:
    """The actionable row: direct drill-through to the RTL dashboard."""
    return html.Div(
        className=(
            f"needs-attention__row needs-attention__row--device "
            f"needs-attention__row--{leaf['_state']}"
        ),
        children=[
            _badge(leaf["_state"]),
            dcc.Link(
                leaf["entity"], href=leaf["href"],
                className="needs-attention__entity-link",
            ),
            html.Span(leaf["issue"], className="needs-attention__detail"),
            _age(leaf),
            html.Span("›", className="needs-attention__chevron", **{"aria-hidden": "true"}),
        ],
    )
