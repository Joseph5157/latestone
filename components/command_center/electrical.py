"""Electrical Conditions — the Critical/Warning visual system (CC-1 Phase 6).

Renders the two conditions the DEVICE classifies, and is explicit that the
current fleet count for each is not derivable.

The distinction this card exists to hold (ADR-001, EVT-D4):

    power_down  event → Critical presentation
    battery_low event → Warning  presentation

never

    battery_voltage < 3.61 → Critical
    battery_voltage < 3.75 → Warning

The voltage figures below are legend copy describing what the device
already decided before it emitted the event. Nothing here evaluates them —
a structural AST test
(tests/test_command_center_service.py::TestNoThresholdLogicInCommandCenter)
fails the build if any Command Center module ever compares against them.

This module receives already-decided values and never imports
`event_semantics`: the mapping is the facade's to state, not a component's
to assemble.
"""
from __future__ import annotations

from dash import html

from components.command_center.primitives import cc_card

#: Shown in place of a count. Deliberately a word, in its own element, never
#: a numeral: `0` would assert that no RTL is currently in this condition,
#: and that is exactly the claim the event model cannot support.
UNAVAILABLE_TEXT = "Unavailable"

#: The em-dash placeholder that sits where a number would be. Paired with
#: the word above so the absence reads as deliberate rather than as a
#: value that failed to load.
UNAVAILABLE_DASH = "—"


def _condition_block(condition) -> html.Div:
    """One classified condition: category, then what is and isn't known.

    The severity tone paints the CATEGORY MARKER and its label only. The
    unavailable value stays neutral — colouring it red would make "we do
    not know" look like "this is critical right now", which is the precise
    misreading this card is built to prevent.
    """
    return html.Div(
        className="command-center__condition",
        children=[
            html.Div(
                className=(
                    "command-center__condition-category "
                    f"command-center__tone--{condition.severity_key}"
                ),
                children=[
                    html.Span(
                        className="command-center__condition-marker",
                        **{"aria-hidden": "true"},
                    ),
                    html.Span(
                        condition.severity_label,
                        className="command-center__condition-severity",
                    ),
                ],
            ),
            html.P(
                condition.condition_label,
                className="command-center__condition-name",
            ),
            html.Dl(
                className="command-center__condition-facts",
                children=[
                    html.Div(
                        className="command-center__condition-fact",
                        children=[
                            html.Dt("Current state"),
                            html.Dd(
                                className="command-center__unavailable",
                                children=[
                                    html.Span(
                                        UNAVAILABLE_DASH,
                                        className="command-center__unavailable-dash",
                                        **{"aria-hidden": "true"},
                                    ),
                                    html.Span(UNAVAILABLE_TEXT),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="command-center__condition-fact",
                        children=[
                            html.Dt("Device definition"),
                            html.Dd(
                                condition.definition,
                                className="command-center__condition-definition",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def electrical_conditions_card(snapshot) -> html.Section:
    """The Electrical Conditions card.

    Renders exactly the conditions it is handed — it never adds a category
    because it happens to have styling for one. High temperature and
    vibration have no approved domain rule and are structurally absent from
    `services/event_semantics.py`; that absence must survive all the way to
    the screen.
    """
    return cc_card(
        "Electrical Conditions",
        [
            html.Div(
                className="command-center__conditions",
                children=[
                    _condition_block(condition)
                    for condition in snapshot.electrical_conditions
                ],
            ),
            html.P(
                "Event categories are classified by the device. Current fleet "
                "state requires an event closure contract that does not exist "
                "yet.",
                className="command-center__explanation",
            ),
        ],
        subtitle="Classified device event categories",
    )
