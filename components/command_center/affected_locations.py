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

from dash import dcc, html

from components.command_center.primitives import cc_card
from routes import command_center_href

#: The full, unbounded view. Named here so the panel's link and the
#: route parser cannot drift apart.
LOCATIONS_PATH = "/command-center/locations"

#: Rows shown before the list becomes a scroll region. Real fleet data put
#: 30 affected plants in this panel, which pushed every card below it off
#: the screen. Bounding the HEIGHT is the fix; bounding the DATA is not -
#: a "+22 more" cap would hide affected plants, removing exactly the
#: concentration picture this panel exists to give. The CSS max-height is
#: set just under this many rows so the next one is visibly clipped, which
#: is what tells the operator there is more to see.
#: How many affected Plants the COCKPIT panel names. A deliberate decision,
#: not an accident of what Phase 7 happened to produce: thirty rows in a
#: fixed-height cell means comparing rank 3 against rank 27 by scrolling a
#: small pane, which is not comparing at all.
#:
#: Progressive disclosure, never truncation of the DATA. The service still
#: ranks every plant, `/command-center/locations` still shows all of them,
#: and the subtitle keeps stating the true total — so the population is
#: reported honestly even while the panel shows a working subset.
TOP_N = 8


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
                    # Selecting a plant is a link, not a click handler: the
                    # selection lives in the URL (?plant=), so it survives a
                    # refresh by construction and the selected view is
                    # bookmarkable. See routes.command_center_href.
                    dcc.Link(
                        location.plant_name,
                        href=command_center_href(location.plant_id),
                        className="command-center__rank-name command-center__rank-link",
                        title=f"Show transformer concentration for {location.plant_name}",
                    ),
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


def _scrollable(listing) -> html.Div:
    """Bound the list's height, keeping every row reachable.

    `tabIndex` and a named `region` role are not decoration: a scroll
    container that cannot take focus is unreachable by keyboard (WCAG
    2.1.1), so its lower rows would be visually present and functionally
    unavailable. Applied only past the row threshold - a focus stop that
    scrolls nothing is noise in the tab order.
    """
    return html.Div(
        className="command-center__ranking-scroll",
        # Dash types this prop as a STRING; passing int 0 renders but
        # logs "Invalid argument `tabIndex` passed into Div" on every
        # callback fire.
        tabIndex="0",
        role="region",
        **{"aria-label": "Affected locations, scrollable list"},
        children=[listing],
    )


def _subtitle(snapshot, ranked: list) -> str:
    """Names the scale up front.

    With the list bounded, "how big is this problem?" would otherwise be
    answerable only by scrolling to the bottom and counting.
    """
    total = len(snapshot.affected_locations)
    noun = "plant" if total == 1 else "plants"
    return f"{len(ranked)} of {total} {noun} affected"


def _selected_plant_id(snapshot) -> str | None:
    selected = getattr(snapshot, "selected_location", None)
    return getattr(selected, "plant_id", None) if selected else None


def visible_locations(ranked: list, selected_plant_id: str | None):
    """The rows the panel shows, and the selected row it had to keep.

    Returns `(shown, retained)`. `retained` is the selected plant when it
    ranks below the cut and had to be appended, else None — the caller needs
    to know, because a row that is present for a different reason than the
    others deserves to say so rather than looking like rank 9.

    The DATA is never truncated: `ranked` still holds every affected plant,
    the subtitle still counts them, and the full page still lists them.
    """
    if len(ranked) <= TOP_N:
        return list(ranked), None

    shown = list(ranked[:TOP_N])
    if selected_plant_id is None:
        return shown, None
    if any(row.plant_id == selected_plant_id for row in shown):
        return shown, None

    below = next(
        (row for row in ranked[TOP_N:] if row.plant_id == selected_plant_id),
        None,
    )
    if below is None:
        # Selected, but not affected at all — nothing to retain. It is a calm
        # plant, and this panel ranks exceptions.
        return shown, None
    return shown + [below], below



def affected_locations_card(snapshot) -> html.Section:
    """The Affected Locations card.

    Zero-affected plants are dropped here rather than in the service: the
    service keeps them so this choice stays a presentation one, and an
    exception-first ranking padded with bar-less calm plants would bury the
    plants that need someone.
    """
    ranked = [row for row in snapshot.affected_locations if row.affected_rtls]
    shown, retained = visible_locations(ranked, _selected_plant_id(snapshot))

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
        listing = ranked_locations_list(shown)
        # ALWAYS wrapped, not conditionally. The region is a HEIGHT bound,
        # not a row-count decision: inside the fixed cockpit its CSS flexes
        # it to whatever the cell allows, so even eight rows must live inside
        # it or the panel overflows its grid area on a short viewport. The
        # old row-count condition became unreachable the moment TOP_N capped
        # the list below it, which would have silently removed the bound.
        body = [_scrollable(listing)]
        if retained:
            # The selected plant ranks below the cut. It stays visible rather
            # than vanishing the moment it stops being one of the worst — a
            # selection that disappears reads as a bug, and the operator
            # chose this plant on purpose.
            body.append(
                html.P(
                    f"{retained.plant_name} is shown because it is selected "
                    f"(rank {ranked.index(retained) + 1} of {len(ranked)}).",
                    className="command-center__retained-note",
                )
            )
        # Only offered when there is something to open. A link over an empty
        # list promises content that is not there.
        if len(shown) < len(ranked):
            label = f"Show all {len(ranked)} affected plants →"
        else:
            label = "View all →"
        body.append(
            dcc.Link(
                label,
                href=LOCATIONS_PATH,
                className="command-center__view-all",
            )
        )

    return cc_card("Affected Locations", body, subtitle=_subtitle(snapshot, ranked))


def ranked_locations_list(ranked: list) -> html.Ol:
    """The ranked rows, unbounded.

    Shared by the bounded panel and the full-page view so one renderer
    serves both — a second copy is how the two would eventually disagree
    about the same plant. Bar widths are relative to the worst plant in the
    list it is given, so both surfaces scale identically.
    """
    worst = ranked[0].affected_rtls if ranked else 0
    return html.Ol(
        className="command-center__ranking",
        children=[_rank_row(location, worst) for location in ranked],
    )
