"""Administrator control for the C-01 global temperature warning/critical
threshold configuration (THRESH-CONFIG-1, framework only).

Presentation only — every value comes from
`services.temperature_threshold_service`. Labels source the °C unit from
the existing temperature metric definition (`config/metrics.py`), so the
unit string is never duplicated here — if it ever changed there, this panel
would not silently disagree with it.

DISPLAY PRECISION IS NOT THE METRIC'S. `MetricConfig.precision` (1 decimal
place) is chart/table DISPLAY metadata for READINGS — an intentional
rounding choice for a measured value with no exact "true" figure. A
configured threshold is not a reading: it is the exact value an
Administrator entered and the exact value stored (NUMERIC(12,3) — see
migration 011 and services/temperature_threshold_service.STORAGE_EXPONENT).
Rendering it at the metric's 1-decimal display precision would silently
hide real configured precision (e.g. a stored 60.250 would show as "60.3",
implying a different, unconfirmed value). This panel therefore renders
the canonical `Decimal` faithfully via fixed-point formatting, never
`MetricConfig.precision`.
"""
from __future__ import annotations

from decimal import Decimal

from dash import dcc, html

from config.metrics import ATTRIBUTION_METRIC_KEY, get_metric
from services.temperature_threshold_service import ThresholdConfigState

PANEL_ID = "temperature-threshold-panel"
WARNING_INPUT_ID = "temperature-threshold-warning"
CRITICAL_INPUT_ID = "temperature-threshold-critical"
SET_BTN_ID = "temperature-threshold-set-btn"
CLEAR_BTN_ID = "temperature-threshold-clear-btn"
ERROR_ID = "temperature-threshold-error"

_TEMPERATURE_METRIC = get_metric(ATTRIBUTION_METRIC_KEY)
_UNIT = _TEMPERATURE_METRIC.unit


def _format_value(value: Decimal) -> str:
    """Fixed-point, exact — the canonical stored value, verbatim. Never
    `MetricConfig.precision`; see the module docstring."""
    return f"{value:f} {_UNIT}"


def _status_text(state: ThresholdConfigState | None) -> str:
    if state is None:
        return "Not configured."
    return (
        f"Warning: {_format_value(state.warning_c)} · "
        f"Critical: {_format_value(state.critical_c)}"
    )


def temperature_threshold_panel(
    state: ThresholdConfigState | None, *, error: str | None = None
) -> html.Div:
    """The full panel: status line, set/clear form, and an error slot.

    No device or user selector — C-01's baseline is exactly one global
    configuration, same reasoning as `auto_disable_override_panel`.
    """
    # No `id` here: this div is returned as the CHILDREN of the fixed-id
    # container the page layout declares (`PANEL_ID`) — see
    # auto_disable_override_panel.py's identical note.
    return html.Div(
        className="temperature-threshold-panel",
        children=[
            html.H3(
                f"{_TEMPERATURE_METRIC.label} Threshold (C-01, framework only)",
                className="temperature-threshold-panel__heading",
            ),
            html.P(
                _status_text(state),
                className="temperature-threshold-panel__status",
            ),
            html.Div(
                className="temperature-threshold-panel__form",
                children=[
                    html.Label(
                        f"Warning ({_UNIT})", htmlFor=WARNING_INPUT_ID,
                    ),
                    dcc.Input(
                        id=WARNING_INPUT_ID,
                        type="text",
                        placeholder=f"e.g. 60 {_UNIT}",
                        value="",
                        className="temperature-threshold-panel__warning-input",
                    ),
                    html.Label(
                        f"Critical ({_UNIT})", htmlFor=CRITICAL_INPUT_ID,
                    ),
                    dcc.Input(
                        id=CRITICAL_INPUT_ID,
                        type="text",
                        placeholder=f"e.g. 75 {_UNIT}",
                        value="",
                        className="temperature-threshold-panel__critical-input",
                    ),
                    html.Div(
                        className="temperature-threshold-panel__actions",
                        children=[
                            html.Button(
                                "Set threshold",
                                id=SET_BTN_ID,
                                n_clicks=0,
                                className="temperature-threshold-panel__set-btn",
                            ),
                            html.Button(
                                "Clear",
                                id=CLEAR_BTN_ID,
                                n_clicks=0,
                                disabled=state is None,
                                className="temperature-threshold-panel__clear-btn",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(error, id=ERROR_ID, className="listing-error") if error else html.Div(id=ERROR_ID, className="listing-error"),
        ],
    )
