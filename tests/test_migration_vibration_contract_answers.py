"""
Migration tests — 012_vibration_contract_answers (VIB-CONFIG-1).

Covers the multi-row key-value shape (deliberately NOT a singleton like
migrations 010/011), the FK to users, the NOT NULL answer_text column, the
absence of any CHECK on question_key (the valid key set lives in
config/vibration_contract.py, not the schema — see the migration's own
docstring), and a genuine downgrade-then-reupgrade round trip. All tests
run Alembic in a SUBPROCESS against a temporary schema so the real seeded
development database is never modified — same pattern as
tests/test_migration_temperature_threshold_config.py.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from db.engine import session_scope

pytestmark = pytest.mark.db

TEST_SCHEMA = f"pm_vib_contract_{uuid.uuid4().hex[:8]}"


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PLANT_MONITORING_SCHEMA"] = TEST_SCHEMA
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
    )


def _drop_test_schema() -> None:
    with session_scope() as session:
        session.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))


def _seed_user() -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {TEST_SCHEMA}.users (username, full_name, role) "
                "VALUES ('admin_a', 'Admin A', 'administrator')"
            )
        )


def _user_id(username: str) -> int:
    with session_scope() as session:
        return session.execute(
            text(f"SELECT user_id FROM {TEST_SCHEMA}.users WHERE username = :u"),
            {"u": username},
        ).scalar_one()


@pytest.fixture(scope="module", autouse=True)
def _clean_test_schema():
    _drop_test_schema()
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, result.stderr
    _seed_user()
    yield
    _drop_test_schema()


class TestVibrationContractAnswers:
    def setup_method(self):
        # Each test starts with an empty answers table — the module-scoped
        # schema fixture is shared across tests in this class.
        with session_scope() as session:
            session.execute(
                text(f"DELETE FROM {TEST_SCHEMA}.vibration_contract_answers")
            )

    def test_one_row_accepted(self):
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.vibration_contract_answers "
                    "(question_key, answer_text, updated_by_user_id) "
                    "VALUES ('unit', 'mm/s', :uid)"
                ),
                {"uid": admin_a},
            )

    def test_multiple_rows_accepted_not_a_singleton(self):
        """Deliberately NOT the id=1 singleton shape migrations 010/011
        use — up to 15 independent question rows may coexist."""
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            for key, answer in [("unit", "mm/s"), ("axes", "single"), ("chart_type", "line")]:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.vibration_contract_answers "
                        "(question_key, answer_text, updated_by_user_id) "
                        "VALUES (:key, :answer, :uid)"
                    ),
                    {"key": key, "answer": answer, "uid": admin_a},
                )
            count = session.execute(
                text(f"SELECT COUNT(*) FROM {TEST_SCHEMA}.vibration_contract_answers")
            ).scalar_one()
        assert count == 3

    def test_duplicate_question_key_rejected_by_primary_key(self):
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.vibration_contract_answers "
                    "(question_key, answer_text, updated_by_user_id) "
                    "VALUES ('unit', 'mm/s', :uid)"
                ),
                {"uid": admin_a},
            )
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.vibration_contract_answers "
                        "(question_key, answer_text, updated_by_user_id) "
                        "VALUES ('unit', 'g', :uid)"
                    ),
                    {"uid": admin_a},
                )

    def test_missing_answer_text_rejected(self):
        admin_a = _user_id("admin_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.vibration_contract_answers "
                        "(question_key, updated_by_user_id) "
                        "VALUES ('unit', :uid)"
                    ),
                    {"uid": admin_a},
                )

    def test_unknown_user_rejected(self):
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.vibration_contract_answers "
                        "(question_key, answer_text, updated_by_user_id) "
                        "VALUES ('unit', 'mm/s', 999999)"
                    )
                )

    def test_schema_has_no_check_on_question_key(self):
        """Deliberate decision (migration's own docstring): the valid key
        set lives in config/vibration_contract.py, not a database CHECK —
        mirrors config/audit.py's operation-vocabulary precedent. The
        schema must accept an arbitrary key; the SERVICE (tested
        separately) is what refuses an unknown one."""
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.vibration_contract_answers "
                    "(question_key, answer_text, updated_by_user_id) "
                    "VALUES ('not_a_real_question', 'whatever', :uid)"
                ),
                {"uid": admin_a},
            )

    def test_row_can_be_replaced_after_delete(self):
        # The application layer upserts/deletes per question_key rather
        # than ever inserting a duplicate row (repositories.
        # plant_monitoring_repository.set_/clear_vibration_contract_answer)
        # — this just confirms the schema itself permits that lifecycle.
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.vibration_contract_answers "
                    "(question_key, answer_text, updated_by_user_id) "
                    "VALUES ('unit', 'mm/s', :uid)"
                ),
                {"uid": admin_a},
            )
            session.execute(
                text(
                    f"DELETE FROM {TEST_SCHEMA}.vibration_contract_answers "
                    "WHERE question_key = 'unit'"
                )
            )
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.vibration_contract_answers "
                    "(question_key, answer_text, updated_by_user_id) "
                    "VALUES ('unit', 'g', :uid)"
                ),
                {"uid": admin_a},
            )


class TestUpgradeDowngradeUpgrade:
    def test_upgrade_downgrade_upgrade_round_trips(self):
        """012's table survives a downgrade-then-reupgrade without
        residue, same shape as test_migration_temperature_threshold_config.py's
        equivalent check."""
        down = _run_alembic("downgrade", "011_temperature_threshold_config")
        assert down.returncode == 0, down.stderr

        with session_scope() as session:
            tables = set(
                session.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = :schema"
                    ),
                    {"schema": TEST_SCHEMA},
                ).scalars().all()
            )
        assert "vibration_contract_answers" not in tables
        # The prior migration's table must survive the downgrade — this
        # step only rolls back ONE revision.
        assert "temperature_threshold_config" in tables

        up = _run_alembic("upgrade", "head")
        assert up.returncode == 0, up.stderr

        with session_scope() as session:
            columns = set(
                session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = :schema AND table_name = 'vibration_contract_answers'"
                    ),
                    {"schema": TEST_SCHEMA},
                ).scalars().all()
            )
        assert {
            "question_key", "answer_text", "updated_by_user_id", "updated_at",
        } <= columns
        # No re-seed needed: the downgrade/upgrade cycle never touched
        # `users`, and this class runs last in file order.
