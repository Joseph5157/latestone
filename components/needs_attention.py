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
    extra_groups: list[dict] | None = None,
    empty_message: str = (
        "No current data-freshness exceptions."
    ),
) -> html.Div:
    """Render the exception queue above the fleet inventory table.

    ``queue`` is the dict built by
    ``callbacks.listings.build_exception_queue``: ``groups`` (ordered,
    already capped on RTL leaves), plus the totals the disclosure line
    reports truthfully.

    ``extra_groups`` (``callbacks.listings.extra_groups_beyond_cap``) is the
    remainder beyond the cap, rendered hidden in place and revealed in-page
    by the "Show all" toggle — never a second page to navigate to for the
    same exceptions "View full fleet" already links elsewhere.
    """
    groups = (queue or {}).get("groups") or []
    if not groups:
        return _empty_panel(empty_message)

    children = [
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
    ]
    if extra_groups:
        children.append(
            html.Div(
                id="needs-attention-extra",
                className="needs-attention__list needs-attention__list--extra",
                children=[_plant_group(g) for g in extra_groups],
            )
        )
        children.append(
            html.Button(
                "Show all",
                id="needs-attention-toggle",
                n_clicks=0,
                className="needs-attention__toggle",
                **{"aria-expanded": "false", "aria-controls": "needs-attention-extra"},
            )
        )

    return html.Div(id="needs-attention-card", className="card needs-attention", children=children)


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
    """Full text chip. Plant rows only — the one loud signal per group."""
    state = Freshness(state_value)
    return html.Span(
        FRESHNESS_PRESENTATION[state].label,
        className=f"needs-attention__badge needs-attention__badge--{state.value}",
    )


def _dot(state_value: str) -> html.Span:
    """Quiet severity indicator for transformer/device rows. Repeating the
    plant row's full text badge at every nested depth — and, on leaves, an
    "issue" that was always the identical word to the badge next to it — was
    the redundancy that made the panel read as raw output rather than a
    designed hierarchy. Colour alone never carries the state: a
    visually-hidden label keeps it in the accessibility tree."""
    state = Freshness(state_value)
    return html.Span(
        html.Span(FRESHNESS_PRESENTATION[state].label, className="visually-hidden"),
        className=f"needs-attention__dot needs-attention__dot--{state.value}",
    )


def _age(row: dict, extra_class: str = "") -> html.Span:
    class_name = "needs-attention__age"
    if extra_class:
        class_name += f" {extra_class}"
    return html.Span(row["last_update"], className=class_name)


def _without_state_prefix(issue: str) -> str:
    """Drop a `FreshnessRollup.label()`-style "State · " prefix for a row
    using a dot instead of a text badge — the dot already carries severity,
    so repeating the word in the text next to it would recreate the same
    redundancy `_dot` exists to remove. Falls back to the original text if
    there is no such prefix, rather than guessing at a different shape."""
    _before, sep, rest = issue.partition(" · ")
    return rest if sep else issue


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
                    html.Div(
                        className="needs-attention__row-main",
                        children=[
                            html.Span(group["entity"], className="needs-attention__entity"),
                            html.Span(group["issue"], className="needs-attention__detail"),
                            _age(group, "needs-attention__age--group"),
                        ],
                    ),
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
                _dot(branch["_state"]),
                dcc.Link(
                    branch["entity"], href=branch["href"],
                    className="needs-attention__entity-link",
                ),
                html.Span(
                    _without_state_prefix(branch["issue"]),
                    className="needs-attention__detail",
                ),
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
    """The actionable row: direct drill-through to the RTL dashboard.

    No "issue" text — for a single device its state IS the leaf's whole
    story, already carried by the dot; restating "Stale" in words beside a
    stale-coloured dot next to a STALE-coloured branch next to a
    STALE-coloured plant badge was the exact repetition being removed here.
    """
    return html.Div(
        className=(
            f"needs-attention__row needs-attention__row--device "
            f"needs-attention__row--{leaf['_state']}"
        ),
        children=[
            _dot(leaf["_state"]),
            dcc.Link(
                leaf["entity"], href=leaf["href"],
                className="needs-attention__entity-link",
            ),
            _age(leaf),
            html.Span("›", className="needs-attention__chevron", **{"aria-hidden": "true"}),
        ],
    )
