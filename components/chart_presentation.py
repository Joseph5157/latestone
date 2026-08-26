"""Shared Plotly presentation building blocks for the Powerplant chart family.

Full-size charts (metric_chart.py) and metric workspace cells
(metric_workspace.py) speak
the same visual language — one template, one gridline colour, one muted
"no data" colour, one hover-value format — but a full chart and an
eight-per-row sparkline earn different margins, axis titles and
interactivity. Only the pieces genuinely identical across both families live
here; anything that differs on purpose (margins, height, titles, uirevision,
dragmode) stays local to its own chart builder.
"""
from __future__ import annotations

from config.metrics import MetricConfig

TEMPLATE = "plotly_white"
GRIDLINE_COLOR = "#eef0f3"
MUTED_TEXT_COLOR = "#6b7280"


def grid_axis(**overrides) -> dict:
    """A visible-gridline axis in the shared colour.

    `overrides` adds axis-specific keys (`nticks`, `title`) without repeating
    `showgrid`/`gridcolor` at every call site. A hidden axis (Quick Trend's
    x-axis) sets its own `showgrid=False` directly instead of calling this —
    that difference is deliberate, not something this helper should paper over.
    """
    return {"showgrid": True, "gridcolor": GRIDLINE_COLOR, **overrides}


def no_data_annotation(text: str, size: int = 14) -> dict:
    """kwargs for `fig.add_annotation(**no_data_annotation(...))`.

    Full charts and Quick Trend cells show different text at different sizes
    — a full sentence at 14px vs. a compact "No readings" at 11px — but
    always in the same muted colour, never the warning palette: absent data
    is a data-quality condition, not an alarm.
    """
    return dict(text=text, showarrow=False, font=dict(size=size, color=MUTED_TEXT_COLOR))


def hover_template(metric: MetricConfig) -> str:
    """`2026-08-09 05:43 UTC · 21.4 °C` — one definition for every trace that
    plots a Reading against this metric's value.

    Previously written out three times; two of the three copies stated UTC in
    the tooltip and one (the primary line chart) did not, even though its own
    axis title already says "Time (UTC)". One definition closes that gap.
    """
    return (
        "%{x|%Y-%m-%d %H:%M} UTC<br>%{y:."
        + str(metric.precision) + "f} " + metric.unit
        + "<extra></extra>"
    )
