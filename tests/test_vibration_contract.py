"""VIB-CONFIG-1 tests — C-02 vibration contract answer capture (framework
only).

Development baseline (docs/context/ACTIVE_GATE.md, C08-BASELINE-1), pending
client confirmation. Pure classes cover validation without a database.
Database-backed suites run against the module-scoped isolated_schema
(tests/conftest.py), never the real plant_monitoring tables — mirrors
tests/test_temperature_threshold.py.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from config import audit as audit_cfg
from config.vibration_contract import VIBRATION_CONTRACT_QUESTIONS, question_keys
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import vibration_contract_service as service


# ---------------------------------------------------------------------------
# Pure — the question registry itself
# ---------------------------------------------------------------------------


class TestQuestionRegistry:
    def test_exactly_fifteen_questions(self):
        """Direct count of docs/VIBRATION_METRIC_CONTRACT_TBD.md's table —
        corrected 2026-09-07; a prior tracked-context claim of 14 was a
        miscount."""
        assert len(VIBRATION_CONTRACT_QUESTIONS) == 15

    def test_all_keys_are_unique(self):
        keys = question_keys()
        assert len(keys) == len(set(keys))

    def test_no_question_invents_a_unit_axis_or_threshold_value(self):
        """This registry names SLOTS, never fills them. None of the
        transcribed question/why-it-matters text may itself assert a
        concrete unit, axis count, or threshold — that would be inventing
        the very answer this gate exists to leave open."""
        forbidden = ("mm/s2", "3-axis", "single-axis")
        for q in VIBRATION_CONTRACT_QUESTIONS:
            for token in forbidden:
                assert token not in q.question.lower()
                assert token not in q.why_it_matters.lower()


# ---------------------------------------------------------------------------
# Pure — validation, no database
# ---------------------------------------------------------------------------


class TestSetAnswerValidation:
    def test_requires_authenticated_actor(self):
        with pytest.raises(service.VibrationContractError):
            service.set_answer(question_key="unit", answer_text="mm/s", actor_user_id=None)
        with pytest.raises(service.VibrationContractError):
            service.set_answer(question_key="unit", answer_text="mm/s", actor_user_id=True)

    def test_unknown_question_key_rejected(self):
        with pytest.raises(service.VibrationContractError):
            service.set_answer(
                question_key="not_a_real_question", answer_text="whatever",
                actor_user_id=1,
            )

    @pytest.mark.parametrize("blank", ["", "   ", None])
    def test_blank_answer_rejected_not_treated_as_clear(self, blank):
        with pytest.raises(service.VibrationContractError):
            service.set_answer(question_key="unit", answer_text=blank, actor_user_id=1)


class TestClearAnswerValidation:
    def test_requires_authenticated_actor(self):
        with pytest.raises(service.VibrationContractError):
            service.clear_answer(question_key="unit", actor_user_id=None)

    def test_unknown_question_key_rejected(self):
        with pytest.raises(service.VibrationContractError):
            service.clear_answer(question_key="not_a_real_question", actor_user_id=1)


class TestVocabulary:
    def test_operations_fit_column_limit(self):
        assert len(audit_cfg.VIBRATION_CONTRACT_ANSWER_SET) <= 50
        assert len(audit_cfg.VIBRATION_CONTRACT_ANSWER_CLEARED) <= 50

    def test_not_a_system_operation(self):
        """No scheduler, no automatic evaluation exists for this feature —
        every change is human-originated."""
        assert audit_cfg.VIBRATION_CONTRACT_ANSWER_SET not in audit_cfg.SYSTEM_OPERATIONS
        assert audit_cfg.VIBRATION_CONTRACT_ANSWER_CLEARED not in audit_cfg.SYSTEM_OPERATIONS


# ---------------------------------------------------------------------------
# Database-backed — persistence, no-op semantics, audit, rollback
# ---------------------------------------------------------------------------


def _wipe() -> None:
    with session_scope() as session:
        for table in (
            "audit_log", "vibration_contract_answers",
            "user_device_assignments", "readings", "devices", "transformers",
            "plants", "users",
        ):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


def _audit_rows() -> list[dict]:
    with session_scope() as session:
        rows = session.execute(
            text(
                f"SELECT operation, entity_type, entity_id, old_values, "
                f"new_values, user_id FROM {repo._SCHEMA}.audit_log "
                f"ORDER BY audit_id"
            )
        ).mappings().fetchall()
    return [dict(r) for r in rows]


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestAnswerPersistence:
    def setup_method(self):
        _wipe()
        self.admin = repo.create_or_update_user(
            username="vib-admin", full_name="Admin",
            role="administrator", status="active",
        ).user_id

    def test_all_fifteen_questions_start_unanswered(self):
        answers = service.get_all_answers()
        assert answers == {}
        for key in question_keys():
            assert service.get_answer(key) is None

    def test_answering_one_question_leaves_the_other_fourteen_unanswered(self):
        service.set_answer(question_key="unit", answer_text="mm/s", actor_user_id=self.admin)

        answers = service.get_all_answers()
        assert set(answers) == {"unit"}
        for key in question_keys():
            if key != "unit":
                assert service.get_answer(key) is None

    def test_set_persists_and_audits_human_actor(self):
        state = service.set_answer(
            question_key="unit", answer_text="mm/s", actor_user_id=self.admin,
        )
        assert state.question_key == "unit"
        assert state.answer_text == "mm/s"
        assert state.updated_by_user_id == self.admin
        assert service.get_answer("unit").answer_text == "mm/s"

        rows = _audit_rows()
        assert len(rows) == 1
        assert rows[0]["operation"] == audit_cfg.VIBRATION_CONTRACT_ANSWER_SET
        assert rows[0]["entity_type"] == audit_cfg.ENTITY_VIBRATION_CONTRACT
        assert rows[0]["entity_id"] == "unit"
        assert rows[0]["user_id"] == self.admin
        assert rows[0]["old_values"] is None
        assert rows[0]["new_values"]["answer_text"] == "mm/s"

    def test_answer_text_is_stripped(self):
        service.set_answer(
            question_key="unit", answer_text="  mm/s  ", actor_user_id=self.admin,
        )
        assert service.get_answer("unit").answer_text == "mm/s"

    def test_identical_re_save_is_a_silent_noop(self):
        first = service.set_answer(
            question_key="unit", answer_text="mm/s", actor_user_id=self.admin,
        )
        again = service.set_answer(
            question_key="unit", answer_text="mm/s", actor_user_id=self.admin,
        )
        assert again.updated_at == first.updated_at  # no churn
        assert [r["operation"] for r in _audit_rows()] == [
            audit_cfg.VIBRATION_CONTRACT_ANSWER_SET,
        ]

    def test_changing_the_answer_is_a_real_change_and_is_audited(self):
        service.set_answer(question_key="unit", answer_text="mm/s", actor_user_id=self.admin)
        service.set_answer(question_key="unit", answer_text="g", actor_user_id=self.admin)

        ops = [r["operation"] for r in _audit_rows()]
        assert ops == [
            audit_cfg.VIBRATION_CONTRACT_ANSWER_SET,
            audit_cfg.VIBRATION_CONTRACT_ANSWER_SET,
        ]
        assert service.get_answer("unit").answer_text == "g"
        last_row = _audit_rows()[1]
        assert last_row["old_values"]["answer_text"] == "mm/s"
        assert last_row["new_values"]["answer_text"] == "g"

    def test_answering_a_different_question_is_independent_and_audited_separately(self):
        service.set_answer(question_key="unit", answer_text="mm/s", actor_user_id=self.admin)
        service.set_answer(question_key="axes", answer_text="single", actor_user_id=self.admin)

        ops_and_entities = [(r["operation"], r["entity_id"]) for r in _audit_rows()]
        assert ops_and_entities == [
            (audit_cfg.VIBRATION_CONTRACT_ANSWER_SET, "unit"),
            (audit_cfg.VIBRATION_CONTRACT_ANSWER_SET, "axes"),
        ]
        assert service.get_answer("unit").answer_text == "mm/s"
        assert service.get_answer("axes").answer_text == "single"

    def test_clear_is_a_noop_when_already_unanswered(self):
        result = service.clear_answer(question_key="unit", actor_user_id=self.admin)
        assert result is None
        assert _audit_rows() == []

    def test_clear_removes_row_and_audits(self):
        service.set_answer(question_key="unit", answer_text="mm/s", actor_user_id=self.admin)
        cleared = service.clear_answer(question_key="unit", actor_user_id=self.admin)

        assert cleared.answer_text == "mm/s"
        assert service.get_answer("unit") is None

        ops = [r["operation"] for r in _audit_rows()]
        assert ops == [
            audit_cfg.VIBRATION_CONTRACT_ANSWER_SET,
            audit_cfg.VIBRATION_CONTRACT_ANSWER_CLEARED,
        ]
        cleared_row = _audit_rows()[1]
        assert cleared_row["new_values"] is None
        assert cleared_row["old_values"]["answer_text"] == "mm/s"

    def test_clearing_one_question_leaves_others_untouched(self):
        service.set_answer(question_key="unit", answer_text="mm/s", actor_user_id=self.admin)
        service.set_answer(question_key="axes", answer_text="single", actor_user_id=self.admin)
        service.clear_answer(question_key="unit", actor_user_id=self.admin)

        assert service.get_answer("unit") is None
        assert service.get_answer("axes").answer_text == "single"

    def test_failed_audit_rolls_back_the_set(self, monkeypatch):
        def explode(**_kwargs):
            raise RuntimeError("simulated audit-store outage")

        monkeypatch.setattr(repo, "insert_audit_log", explode)
        with pytest.raises(service.VibrationContractError):
            service.set_answer(
                question_key="unit", answer_text="mm/s", actor_user_id=self.admin,
            )
        assert repo.get_vibration_contract_answer("unit") is None

    def test_failed_audit_rolls_back_the_clear(self, monkeypatch):
        service.set_answer(question_key="unit", answer_text="mm/s", actor_user_id=self.admin)

        def explode(**_kwargs):
            raise RuntimeError("simulated audit-store outage")

        monkeypatch.setattr(repo, "insert_audit_log", explode)
        with pytest.raises(service.VibrationContractError):
            service.clear_answer(question_key="unit", actor_user_id=self.admin)

        # The delete must not have survived without its audit row.
        assert repo.get_vibration_contract_answer("unit") is not None
