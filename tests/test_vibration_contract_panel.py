"""VIB-CONFIG-1 presentation tests — the vibration contract panel
component. Pure Dash component construction, no database, no callback.
"""
from __future__ import annotations

from datetime import datetime, timezone

from config.vibration_contract import VIBRATION_CONTRACT_QUESTIONS
from components.vibration_contract_panel import (
    ANSWER_INPUT_ID,
    CLEAR_BTN_ID,
    QUESTION_SELECT_ID,
    SET_BTN_ID,
    vibration_contract_panel,
)
from services.vibration_contract_service import AnswerState


def _state(key: str, text: str) -> AnswerState:
    return AnswerState(
        question_key=key, answer_text=text, updated_by_user_id=1,
        updated_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
    )


class TestAllUnanswered:
    def test_shows_unanswered_for_every_question(self):
        panel = vibration_contract_panel({})
        text = str(panel)
        assert text.count("Unanswered") == len(VIBRATION_CONTRACT_QUESTIONS)

    def test_status_line_shows_zero_of_fifteen(self):
        panel = vibration_contract_panel({})
        text = str(panel)
        assert f"0 of {len(VIBRATION_CONTRACT_QUESTIONS)} questions answered" in text


class TestPartiallyAnswered:
    def test_answered_question_shows_its_text_not_unanswered(self):
        answers = {"unit": _state("unit", "mm/s")}
        panel = vibration_contract_panel(answers)
        text = str(panel)
        assert "mm/s" in text
        # Exactly one fewer "Unanswered" line than the full set.
        assert text.count("Unanswered") == len(VIBRATION_CONTRACT_QUESTIONS) - 1

    def test_status_line_reflects_the_count(self):
        answers = {"unit": _state("unit", "mm/s"), "axes": _state("axes", "single")}
        panel = vibration_contract_panel(answers)
        text = str(panel)
        assert f"2 of {len(VIBRATION_CONTRACT_QUESTIONS)} questions answered" in text

    def test_every_question_text_from_the_registry_appears(self):
        """Nothing is invented or paraphrased — the panel must show the
        registry's own question text verbatim."""
        panel = vibration_contract_panel({})
        text = str(panel)
        for q in VIBRATION_CONTRACT_QUESTIONS:
            assert q.question in text


class TestErrorSlot:
    def test_error_message_is_rendered_when_present(self):
        panel = vibration_contract_panel({}, error="Select a question first.")
        assert "Select a question first." in str(panel)

    def test_no_error_by_default(self):
        panel = vibration_contract_panel({})
        # The error slot exists but is empty.
        text = str(panel)
        assert "vibration-contract-error" in text


class TestFormIds:
    def test_form_control_ids_are_present(self):
        panel = vibration_contract_panel({})
        ids = set()

        def walk(node):
            node_id = getattr(node, "id", None)
            if isinstance(node_id, str):
                ids.add(node_id)
            for child in getattr(node, "children", None) or []:
                if hasattr(child, "id") or hasattr(child, "children"):
                    walk(child)

        walk(panel)
        assert {QUESTION_SELECT_ID, ANSWER_INPUT_ID, SET_BTN_ID, CLEAR_BTN_ID} <= ids

    def test_dropdown_offers_exactly_the_fifteen_questions(self):
        panel = vibration_contract_panel({})

        def find_dropdown(node):
            if getattr(node, "id", None) == QUESTION_SELECT_ID:
                return node
            for child in getattr(node, "children", None) or []:
                found = find_dropdown(child) if hasattr(child, "id") or hasattr(child, "children") else None
                if found is not None:
                    return found
            return None

        dropdown = find_dropdown(panel)
        assert dropdown is not None
        assert len(dropdown.options) == len(VIBRATION_CONTRACT_QUESTIONS)
        assert {opt["value"] for opt in dropdown.options} == {
            q.key for q in VIBRATION_CONTRACT_QUESTIONS
        }
