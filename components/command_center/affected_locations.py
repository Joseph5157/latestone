"""Affected Locations — where is attention concentrated? (CC-1 Phase 7)

A ranked horizontal bar view of freshness exceptions per Plant.
Location = Plant (ADR-003): no Zone, Feeder, GIS or map, because the schema
has no such level to hang one on.

This module renders a ranking the service already decided. It does not
re-sort: `services/command_center_service.py` owns the rule (affected count
descending, then plant name ascending), and a component sorting again would
be a second definition of "worst", free to drift from the first.

Affected is `Stale + No Data` (ADR-002). No event data reaches this panel —
events answer "did something happen", this answers "is the data current
now", and mixing the two time semantics is exactly what ADR-002 forbids.
"""
from __future__ import annotations

from dash import html

from components.command_center.primitives import cc_card


def bar_width_percent(affected: int, worst: int) -> float:
    """Bar width relative to the WORST plant, not to the fleet.

    The panel's question is comparative — "where is this concentrated?" —
    so the longest bar is the worst plant and everything else reads against
    it. Scaling by each plant's own affected-percent instead would flatten
    exactly the contrast the ranking exists to show: a plant with 18 of 24
    affected and one with 2 of 3 would draw nearly identical bars while
    representing very different amounts of work.

    Returns 0.0 when nothing is affected, so an all-healthy fleet draws no
    bars rather than dividing by zero.
    """
    return (100 * affected / worst) if worst else 0.0


def _rank_row(location, worst: int) -> html.Li:
    """One plant: name, bar, count. Composition rides along as a subtitle
    so the affected total stays the dominant figure."""
    composition = f"{location.stale_rtls} stale · {location.no_data_rtls} no data"
    return html.Li(
        className="command-center__rank-row",
        children=[
            html.Div(
                className="command-center__rank-label",
                children=[
                    html.Span(location.plant_name, className="command-center__rank-name"),
                    html.Span(composition, className="command-center__rank-composition"),
                ],
            ),
            html.Div(
                className="command-center__rank-bar",
                children=[
                    html.Div(
                        className="command-center__rank-bar-fill",
                        style={"width": f"{bar_width_percent(location.affected_rtls, worst):.4g}%"},
                    )
                ],
                # The bar is decoration over a number that is already in the
                # DOM beside it, so it is hidden from assistive tech rather
                # than announced as an unlabelled graphic.
                **{"aria-hidden": "true"},
            ),
            html.Span(
                str(location.affected_rtls),
                className="command-center__rank-value",
            ),
        ],
    )


def affected_locations_card(snapshot) -> html.Section:
    """The Affected Locations card.

    Zero-affected plants are dropped here rather than in the service: the
    service keeps them so this choice stays a presentation one, and an
    exception-first ranking padded with bar-less calm plants would bury the
    plants that need someone.
    """
    ranked = [row for row in snapshot.affected_locations if row.affected_rtls]

    if not ranked:
        # Two different facts, kept apart. "Nothing is wrong" is a measured
        # result; "there is nothing here" is the absence of anything to
        # measure, and reporting the first when the second is true would
        # invent a clean bill of health.
        message = (
            "No RTLs require attention in your current access scope."
            if snapshot.affected_locations
            else "No monitored RTLs in your current access scope."
        )
        body = [html.P(message, className="command-center__empty-note")]
    else:
        worst = ranked[0].affected_rtls
        body = [
            html.Ol(
                className="command-center__ranking",
                children=[_rank_row(location, worst) for location in ranked],
            )
        ]

    return cc_card(
        "Affected Locations",
        body,
        subtitle="RTLs requiring attention, by plant",
    )
