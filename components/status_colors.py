"""The dashboard's one colour key (ADR-026).

Colour says how urgent something is; the label says what it is. Every page
takes its status tone from here, so a colour means the same thing wherever an
operator meets it. Blue (`--color-accent`) is for links and the current
selection only and never appears in this key.
"""
from __future__ import annotations

from dash import html

from services.attention_service import ProblemKind
from services.temperature_condition_service import TemperatureCondition

#: (tone, name, meaning, what it covers), most urgent first.
COLOUR_KEY: tuple[tuple[str, str, str, str], ...] = (
    ("critical", "Critical", "act now",
     "Temperature at or above the critical limit · Power Down"),
    ("warning", "Warning", "check soon",
     "Temperature at or above the warning limit · Battery Low"),
    ("nodata", "No data", "the RTL is not reporting",
     "No recent reading · none for over 24 hours"),
    ("info", "Device fault", "the RTL itself needs a look", "Sensor Error"),
    ("normal", "Normal", "nothing to do", "Temperature below the warning limit"),
    ("none", "Not rated", "cannot be judged yet", "Temperature limits not set"),
)

TONE_NAME = {tone: name for tone, name, _m, _c in COLOUR_KEY}

#: The CSS token that carries each tone, in light and dark.
TONE_TOKEN = {
    "critical": "--sev-critical",
    "warning": "--sev-warning",
    "nodata": "--sev-nodata",
    "info": "--sev-info",
    "normal": "--sev-normal",
    "none": "--sev-none",
}

CONDITION_TONE: dict[TemperatureCondition, str] = {
    TemperatureCondition.CRITICAL: "critical",
    TemperatureCondition.WARNING: "warning",
    TemperatureCondition.NO_RECENT_DATA: "nodata",
    TemperatureCondition.NORMAL: "normal",
    TemperatureCondition.LIMITS_NOT_SET: "none",
}

KIND_TONE: dict[ProblemKind, str] = {
    ProblemKind.TEMP_CRITICAL: "critical",
    ProblemKind.POWER_DOWN: "critical",
    ProblemKind.TEMP_WARNING: "warning",
    ProblemKind.BATTERY_LOW: "warning",
    ProblemKind.NO_DATA_24H: "nodata",
    ProblemKind.SENSOR_ERROR: "info",
}


def status_chip_class(tone: str) -> str:
    return f"status-chip status-chip--{tone}"


def status_dot(tone: str) -> html.Span:
    """A small coloured dot before a status that is the row's own text
    (ADR-026: badges are for a status beside a value)."""
    return html.Span(className=f"status-dot status-dot--{tone}", **{"aria-hidden": "true"})


def colour_key() -> html.Details:
    """A small disclosure listing the key; closed by default."""
    return html.Details(className="colour-key", children=[
        html.Summary("Colour key", className="colour-key__summary"),
        html.Ul(className="colour-key__list", children=[
            html.Li(className="colour-key__item", children=[
                html.Span(name, className=status_chip_class(tone)),
                html.Span(f"{meaning} — {covers}", className="colour-key__covers"),
            ])
            for tone, name, meaning, covers in COLOUR_KEY
        ]),
        html.P("Blue marks links and your current selection; it is never a status.",
               className="colour-key__note"),
    ])
