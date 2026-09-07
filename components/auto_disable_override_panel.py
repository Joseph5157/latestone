"""Administrator control for the C08-AUTO-DISABLE-1 same-day cutoff override.

Presentation only — every value comes from
`services.forwarding_auto_disable_service`. This is intentionally the ONLY
UI this gate adds: the auto-disable action itself is system-driven (see the
scheduler entry point) and has no control surface of its own; only the
override needs one, since an Administrator has to be able to set it.

Development baseline (docs/context/ACTIVE_GATE.md, C08-BASELINE-1), pending
client confirmation: exactly one global override, never per-user/per-RTL —
this panel has no device or user selector because none exists to select.
"""
from __future__ import annotations

from dash import dcc, html

from config.forwarding_schedule import DEFAULT_CUTOFF_TIME, TIMEZONE_NAME
from services.forwarding_auto_disable_service import OverrideState

PANEL_ID = "auto-disable-override-panel"
TIME_INPUT_ID = "auto-disable-override-time"
REASON_INPUT_ID = "auto-disable-override-reason"
SET_BTN_ID = "auto-disable-override-set-btn"
CLEAR_BTN_ID = "auto-disable-override-clear-btn"
ERROR_ID = "auto-disable-override-error"


def _status_text(override: OverrideState | None, *, effective_today: bool) -> str:
    default_str = DEFAULT_CUTOFF_TIME.strftime("%H:%M")
    if override is not None and effective_today:
        return (
            f"Override active for today only: cutoff moved to "
            f"{override.cutoff_time.strftime('%H:%M')} {TIMEZONE_NAME} "
            f"(reason: {override.reason}). Normal {default_str} resumes "
            f"automatically tomorrow."
        )
    return f"Default cutoff: {default_str} {TIMEZONE_NAME}. No override active today."


def auto_disable_override_panel(
    override: OverrideState | None,
    *,
    effective_today: bool,
    error: str | None = None,
) -> html.Div:
    """The full panel: status line, set/clear form, and an error slot.

    `effective_today` is passed in rather than recomputed here — the caller
    already knows today's date and already read the override, so asking this
    presentation function to also know "today" would be a second place that
    date logic could drift from `effective_cutoff_for`.
    """
    # No `id` here: this div is returned as the CHILDREN of the fixed-id
    # container the page layout declares (`PANEL_ID`) — giving it the same
    # id itself would create a duplicate-id element every time the
    # containing callback fires.
    return html.Div(
        className="auto-disable-panel",
        children=[
            html.H3("Message Forwarding Auto-Disable (BR016)", className="auto-disable-panel__heading"),
            html.P(
                _status_text(override, effective_today=effective_today),
                className="auto-disable-panel__status",
            ),
            html.Div(
                className="auto-disable-panel__form",
                children=[
                    html.Label("Temporary cutoff (HH:MM, today only)", htmlFor=TIME_INPUT_ID),
                    dcc.Input(
                        id=TIME_INPUT_ID,
                        type="text",
                        placeholder="18:30",
                        value="",
                        className="auto-disable-panel__time-input",
                    ),
                    html.Label("Reason (required)", htmlFor=REASON_INPUT_ID),
                    dcc.Textarea(
                        id=REASON_INPUT_ID,
                        placeholder="Why is today's cutoff being moved?",
                        value="",
                        className="auto-disable-panel__reason-input",
                    ),
                    html.Div(
                        className="auto-disable-panel__actions",
                        children=[
                            html.Button(
                                "Set override",
                                id=SET_BTN_ID,
                                n_clicks=0,
                                className="auto-disable-panel__set-btn",
                            ),
                            html.Button(
                                "Clear override",
                                id=CLEAR_BTN_ID,
                                n_clicks=0,
                                disabled=not (override is not None and effective_today),
                                className="auto-disable-panel__clear-btn",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(error, id=ERROR_ID, className="listing-error") if error else html.Div(id=ERROR_ID, className="listing-error"),
        ],
    )
