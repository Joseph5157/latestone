"""C-02 vibration contract answer capture (VIB-CONFIG-1) — framework only.

Development baseline (docs/context/ACTIVE_GATE.md, C08-BASELINE-1), pending
client confirmation: vibration must be a configurable framework, never
hardcoded. `docs/VIBRATION_METRIC_CONTRACT_TBD.md` lists 15 unanswered
questions about the real sensor contract. This module gives an
Administrator an audited place to record an answer to EACH question
individually — it invents no answer, no unit, no axis model, no threshold,
no aggregation, no cadence, and no sensor range for any of them.

VIBRATION REMAINS FULLY INACTIVE. Nothing here is read by
`config/metrics.py`, `services/event_semantics.py`, the metric registry,
any repository metric/reading query, or `MonitoringCondition`. This module
only persists text an Administrator typed against a known question key —
it does not interpret that text, and no other part of the application
reads it back for any runtime purpose. See
`docs/VIBRATION_METRIC_CONTRACT_TBD.md`'s "Implementation Rule" section,
which this gate does not touch.

Layering (matches temperature_threshold_service.py / audit_service.py):

    admin panel control -> set_answer()/clear_answer() -> session_scope()
                               ├── repo.set_/clear_vibration_contract_answer()
                               └── audit_service.record() (human actor)
                            single COMMIT / ROLLBACK

UNANSWERED IS ABSENCE, per question, independently — mirrors
`temperature_threshold_service`'s "unconfigured is absence" exactly, just
at per-key granularity instead of one global fact. Answering question A
never requires inventing an answer for question B; each of the 15 keys
lives or is absent on its own.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from config import audit as audit_cfg
from config.vibration_contract import is_known_question_key
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import audit_service

logger = logging.getLogger(__name__)


class VibrationContractError(Exception):
    """A vibration contract answer change failed for a reason safe to show
    the user."""


@dataclass(frozen=True)
class AnswerState:
    """The admin-facing view of one question's current answer."""

    question_key: str
    answer_text: str
    updated_by_user_id: int
    updated_at: datetime


def _to_state(record: repo.VibrationContractAnswerRecord) -> AnswerState:
    return AnswerState(
        question_key=record.question_key,
        answer_text=record.answer_text,
        updated_by_user_id=record.updated_by_user_id,
        updated_at=record.updated_at,
    )


def _snapshot(record: repo.VibrationContractAnswerRecord | None) -> dict | None:
    if record is None:
        return None
    return {
        "answer_text": record.answer_text,
        "updated_by_user_id": record.updated_by_user_id,
    }


def _require_known_key(question_key: str) -> None:
    if not is_known_question_key(question_key):
        raise VibrationContractError(
            f"{question_key!r} is not one of the recorded vibration "
            "contract questions."
        )


def get_all_answers() -> dict[str, AnswerState]:
    """Every ANSWERED question, keyed by question_key. A key absent from
    this dict is unanswered — the caller (the panel/callback) reconciles
    this against `config.vibration_contract.VIBRATION_CONTRACT_QUESTIONS`
    to know the full set of 15 and which are still open."""
    return {
        record.question_key: _to_state(record)
        for record in repo.list_vibration_contract_answers()
    }


def get_answer(question_key: str) -> AnswerState | None:
    """One question's current answer, or None when unanswered."""
    record = repo.get_vibration_contract_answer(question_key)
    return _to_state(record) if record else None


def set_answer(
    *, question_key: str, answer_text: str, actor_user_id: int
) -> AnswerState:
    """Record (or change) one question's answer.

    Same-state re-application (identical answer_text for this key) is a
    genuine no-op — mirrors THRESH-CONFIG-1's rule: nothing is written,
    nothing is audited. Changing the text is always a real transition and
    is always audited, regardless of who makes the change. An empty/
    whitespace-only answer is refused (use `clear_answer` to remove one) —
    this function never silently treats "blank" as "clear".
    """
    if not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise VibrationContractError(
            "Recording a vibration contract answer requires an "
            "authenticated administrator."
        )
    _require_known_key(question_key)
    clean_answer = (answer_text or "").strip()
    if not clean_answer:
        raise VibrationContractError(
            "An answer is required. Use Clear to remove an existing answer."
        )

    try:
        with session_scope() as session:
            change = repo.set_vibration_contract_answer(
                question_key=question_key,
                answer_text=clean_answer,
                updated_by_user_id=actor_user_id,
                session=session,
            )
            if change.changed:
                audit_service.record(
                    session,
                    operation=audit_cfg.VIBRATION_CONTRACT_ANSWER_SET,
                    entity_type=audit_cfg.ENTITY_VIBRATION_CONTRACT,
                    entity_id=question_key,
                    old_values=_snapshot(change.previous),
                    new_values=_snapshot(change.current),
                    actor_user_id=actor_user_id,
                )
            return _to_state(change.current)
    except VibrationContractError:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to set vibration contract answer %r for actor %s",
            question_key, actor_user_id,
        )
        raise VibrationContractError(
            "The answer could not be saved. Please try again."
        ) from exc


def clear_answer(*, question_key: str, actor_user_id: int) -> AnswerState | None:
    """Clear one question's answer, returning to "unanswered".

    Returns the answer that was cleared, or None if it was already
    unanswered — a genuine no-op: nothing is deleted, nothing is audited.
    """
    if not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise VibrationContractError(
            "Clearing a vibration contract answer requires an "
            "authenticated administrator."
        )
    _require_known_key(question_key)

    try:
        with session_scope() as session:
            previous = repo.clear_vibration_contract_answer(
                question_key, session=session,
            )
            if previous is None:
                return None
            audit_service.record(
                session,
                operation=audit_cfg.VIBRATION_CONTRACT_ANSWER_CLEARED,
                entity_type=audit_cfg.ENTITY_VIBRATION_CONTRACT,
                entity_id=question_key,
                old_values=_snapshot(previous),
                new_values=None,
                actor_user_id=actor_user_id,
            )
            return _to_state(previous)
    except VibrationContractError:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to clear vibration contract answer %r for actor %s",
            question_key, actor_user_id,
        )
        raise VibrationContractError(
            "The answer could not be cleared. Please try again."
        ) from exc
