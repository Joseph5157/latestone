"""Selected Location — which transformers are driving this plant's
attention? (CC-1 Phase 8)

One level below the Affected Locations ranking. Selecting a plant there
sets `?plant=` on the Command Center URL, and this panel answers the next
question with the same freshness truth.

Deep links go to the Plant / Transformer routes that already exist. That is
the point: flatten the investigation path without duplicating the
hierarchy — the operator lands on the real page for that asset, not on a
Command Center copy of it.

Renders what the service ranked (affected count descending, then code). It
does not re-sort, for the same reason the Affected Locations panel does
not: a second ordering rule is how two surfaces come to disagree about the
same transformer.
"""
from __future__ import annotations

from dash import dcc, html

from components.command_center.affected_locations import bar_width_percent
from components.command_center.primitives import cc_card

#: Existing routes, not new ones. Matches routes.parse_pathname's "plant"
#: and "transformer" rules.
PLANT_PATH = "/plants"


def _plant_href(plant_id: str) -> str:
    return f"{PLANT_PATH}/{plant_id}"


def _transformer_href(plant_id: str, transformer_id: str) -> str:
    return f"{PLANT_PATH}/{plant_id}/{transformer_id}"


def _transformer_row(location, transformer, worst: int) -> html.Li:
    composition = (
        f"{transformer.stale_rtls} stale · {transformer.no_data_rtls} no data "
        f"of {transformer.total_monitored_rtls}"
    )
    return html.Li(
        className="command-center__rank-row",
        children=[
            html.Div(
                className="command-center__rank-label",
                children=[
                    dcc.Link(
                        transformer.transformer_code,
                        href=_transformer_href(
                            location.plant_id, transformer.transformer_id
                        ),
                        className="command-center__rank-name command-center__rank-link",
                        title=f"Open {transformer.transformer_code}",
                    ),
                    html.Span(composition, className="command-center__rank-composition"),
                ],
            ),
            html.Div(
                className="command-center__rank-bar",
                children=[
                    html.Div(
                        className="command-center__rank-bar-fill",
                        style={
                            "width": f"{bar_width_percent(transformer.affected_rtls, worst):.4g}%"
                        },
                    )
                ],
                **{"aria-hidden": "true"},
            ),
            html.Span(
                str(transformer.affected_rtls),
                className="command-center__rank-value",
            ),
        ],
    )


def selected_location_card(snapshot) -> html.Section:
    """Transformer concentration for the selected plant.

    With nothing selected this prompts rather than rendering an empty
    panel: "no plant chosen" and "this plant is healthy" are different
    facts, and a blank card would say neither.
    """
    location = snapshot.selected_location

    if location is None:
        # A calm fleet, not a missing selection. Nothing is affected, so
        # there is no worst plant to open on — said plainly rather than
        # dressed as a prompt or an error.
        return cc_card(
            "Selected Location",
            [
                html.P(
                    "No RTLs currently require attention across the monitored "
                    "fleet.",
                    className="command-center__empty-note",
                )
            ],
            subtitle="Transformer concentration",
        )

    body: list = [
        html.P(
            [
                dcc.Link(
                    location.plant_name,
                    href=_plant_href(location.plant_id),
                    className="command-center__rank-link",
                    title=f"Open {location.plant_name}",
                ),
            ],
            className="command-center__selected-name",
        ),
    ]

    if not location.has_monitored_rtls:
        # Distinct from "nothing is wrong here": there is nothing to be
        # wrong. Reporting the former would invent a clean bill of health
        # for a plant that reports nothing at all.
        body.append(
            html.P(
                "No monitored RTLs in this Plant.",
                className="command-center__empty-note",
            )
        )
        return cc_card("Selected Location", body, subtitle="Transformer concentration")

    body.append(
        html.P(
            f"{location.affected_rtls} of {location.total_monitored_rtls} "
            "RTLs require attention",
            className="command-center__stat-share",
        )
    )

    # The Stale / No Data split. "18 affected" does not tell an operator
    # whether the plant stopped reporting or never started, and those need
    # different responses.
    body.append(
        html.Dl(
            className="command-center__composition",
            children=[
                html.Div(
                    className=f"command-center__composition-row command-center__tone--{tone}",
                    children=[
                        html.Dt(label, className="command-center__composition-label"),
                        html.Dd(str(count), className="command-center__composition-count"),
                    ],
                )
                for label, count, tone in (
                    ("Stale", location.stale_rtls, "stale"),
                    ("No Data", location.no_data_rtls, "none"),
                )
            ],
        )
    )

    ranked = [t for t in location.transformers if t.affected_rtls]
    if ranked:
        worst = ranked[0].affected_rtls
        body.append(
            html.Ol(
                className="command-center__ranking",
                children=[
                    _transformer_row(location, transformer, worst)
                    for transformer in ranked
                ],
            )
        )
    else:
        body.append(
            html.P(
                "No RTLs currently require attention in this Plant.",
                className="command-center__empty-note",
            )
        )

    return cc_card("Selected Location", body, subtitle="Transformer concentration")
