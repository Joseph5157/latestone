"""Administrator control for capturing the C-02 vibration sensor contract
(VIB-CONFIG-1, framework only).

Presentation only — every value comes from
`services.vibration_contract_service`; the question text/order comes from
`config.vibration_contract` (transcribed from
`docs/VIBRATION_METRIC_CONTRACT_TBD.md`, never invented here). This panel
records ANSWERS to questions; it does not interpret them, and nothing
about vibration is activated by it — no unit, axis, threshold, or
aggregation assumption is made anywhere in this file.
"""
from __future__ import annotations

from dash import dcc, html

from config.vibration_contract import VIBRATION_CONTRACT_QUESTIONS
from services.vibration_contract_service import AnswerState

PANEL_ID = "vibration-contract-panel"
QUESTION_SELECT_ID = "vibration-contract-question-select"
ANSWER_INPUT_ID = "vibration-contract-answer-input"
SET_BTN_ID = "vibration-contract-set-btn"
CLEAR_BTN_ID = "vibration-contract-clear-btn"
ERROR_ID = "vibration-contract-error"


def _summary_rows(answers: dict[str, AnswerState]) -> list[html.Li]:
    """One line per question, in the TBD document's own order — clearly
    "Unanswered" vs the recorded text, never blank/ambiguous."""
    rows = []
    for question in VIBRATION_CONTRACT_QUESTIONS:
        state = answers.get(question.key)
        status = state.answer_text if state is not None else "Unanswered"
        rows.append(
            html.Li(
                [html.Strong(f"{question.question} "), status],
                className=(
                    "vibration-contract-panel__answered"
                    if state is not None
                    else "vibration-contract-panel__unanswered"
                ),
            )
        )
    return rows


def vibration_contract_panel(
    answers: dict[str, AnswerState], *, error: str | None = None
) -> html.Div:
    """The full panel: a status summary of all 15 questions, an edit form
    that operates on whichever question is selected, and an error slot.

    No device or user selector — this is a single, framework-wide
    contract, the same reasoning as `temperature_threshold_panel`.
    """
    answered_count = len(answers)
    total_count = len(VIBRATION_CONTRACT_QUESTIONS)

    # No `id` here: this div is returned as the CHILDREN of the fixed-id
    # container the page layout declares (`PANEL_ID`) — see
    # temperature_threshold_panel.py's identical note.
    return html.Div(
        className="vibration-contract-panel",
        children=[
            html.H3(
                "Vibration Contract",
                className="vibration-contract-panel__heading",
            ),
            html.P(
                f"{answered_count} of {total_count} questions answered.",
                className="vibration-contract-panel__status",
            ),
            # The heading used to carry an internal tracking id to say this.
            # The meaning is load-bearing and the id was not: this records
            # the sensor specification as it becomes known, and no vibration
            # data is monitored, charted or alarmed anywhere.
            html.P(
                "Records the vibration sensor specification as it is "
                "confirmed. Vibration is not yet measured, charted or "
                "alarmed anywhere in the application.",
                className="vibration-contract-panel__note",
            ),
            html.Ul(
                _summary_rows(answers),
                className="vibration-contract-panel__summary",
            ),
            html.Div(
                className="vibration-contract-panel__form",
                children=[
                    html.Label("Question", htmlFor=QUESTION_SELECT_ID),
                    dcc.Dropdown(
                        id=QUESTION_SELECT_ID,
                        options=[
                            {"label": q.question, "value": q.key}
                            for q in VIBRATION_CONTRACT_QUESTIONS
                        ],
                        value=None,
                        clearable=False,
                        placeholder="Select a question...",
                        className="vibration-contract-panel__question-select",
                    ),
                    html.Label("Answer", htmlFor=ANSWER_INPUT_ID),
                    dcc.Textarea(
                        id=ANSWER_INPUT_ID,
                        placeholder="Type the recorded answer for the selected question...",
                        value="",
                        className="vibration-contract-panel__answer-input",
                    ),
                    html.Div(
                        className="vibration-contract-panel__actions",
                        children=[
                            html.Button(
                                "Set answer",
                                id=SET_BTN_ID,
                                n_clicks=0,
                                className="vibration-contract-panel__set-btn",
                            ),
                            html.Button(
                                "Clear",
                                id=CLEAR_BTN_ID,
                                n_clicks=0,
                                className="vibration-contract-panel__clear-btn",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(error, id=ERROR_ID, className="listing-error") if error else html.Div(id=ERROR_ID, className="listing-error"),
        ],
    )
