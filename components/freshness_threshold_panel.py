"""Administrator control for the global freshness (Stale-after) threshold
(FRESHNESS-CONFIG-1). Presentation only; values come from
`services.freshness_threshold_service` via the callback.
"""
from __future__ import annotations

from dash import dcc, html

from components.fleet_condition import threshold_label
from services.freshness_threshold_service import (
    MAX_MINUTES,
    MIN_MINUTES,
    FreshnessThresholdState,
)

PANEL_ID = "freshness-threshold-panel"
MINUTES_INPUT_ID = "freshness-threshold-minutes"
SET_BTN_ID = "freshness-threshold-set-btn"
CLEAR_BTN_ID = "freshness-threshold-clear-btn"
ERROR_ID = "freshness-threshold-error"


def _describe(minutes: int) -> str:
    return f"{threshold_label(minutes)} ({minutes:,} minutes)"


def _status_text(state: FreshnessThresholdState | None, default_minutes: int) -> str:
    if state is None:
        return f"Using the default: Stale after {_describe(default_minutes)}."
    return f"Stale after {_describe(state.stale_after_minutes)}."


def freshness_threshold_panel(
    state: FreshnessThresholdState | None,
    *,
    default_minutes: int,
    error: str | None = None,
) -> html.Div:
    # No `id` on this div: it is the children of the page's fixed PANEL_ID slot.
    return html.Div(
        className="temperature-threshold-panel freshness-threshold-panel",
        children=[
            html.H3("Freshness Threshold", className="temperature-threshold-panel__heading"),
            html.P(
                _status_text(state, default_minutes),
                className="temperature-threshold-panel__status freshness-threshold-panel__status",
            ),
            html.P(
                "Applies to every RTL: an RTL is Stale when any monitored "
                "metric's latest reading is older than this. Changes show on "
                "the dashboard's next refresh. The formal >24h no-data "
                "notification is not affected.",
                className="temperature-threshold-panel__note",
            ),
            html.Div(
                className="temperature-threshold-panel__form",
                children=[
                    html.Label("Stale after (minutes)", htmlFor=MINUTES_INPUT_ID),
                    dcc.Input(
                        id=MINUTES_INPUT_ID,
                        type="text",
                        inputMode="numeric",
                        placeholder="e.g. 720 for 12 hours",
                        value="",
                        className="freshness-threshold-panel__minutes-input",
                    ),
                    html.Small(
                        f"Whole minutes, {MIN_MINUTES} to {MAX_MINUTES:,}. "
                        "60 = 1 hour, 1,440 = 24 hours.",
                        className="freshness-threshold-panel__hint",
                    ),
                    html.Div(
                        className="temperature-threshold-panel__actions",
                        children=[
                            html.Button(
                                "Save threshold",
                                id=SET_BTN_ID,
                                n_clicks=0,
                                className="temperature-threshold-panel__set-btn",
                            ),
                            html.Button(
                                "Reset to default",
                                id=CLEAR_BTN_ID,
                                n_clicks=0,
                                disabled=state is None,
                                className="temperature-threshold-panel__clear-btn",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(error, id=ERROR_ID, className="listing-error")
            if error
            else html.Div(id=ERROR_ID, className="listing-error"),
        ],
    )
