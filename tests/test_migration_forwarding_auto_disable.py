"""
Migration tests — 010_forwarding_auto_disable (C08-AUTO-DISABLE-1).

Covers the singleton constraint (id=1 only), the FK to users, and the
NOT NULL reason column. All tests run Alembic in a SUBPROCESS against a
temporary schema so the real seeded development database is never modified
— same pattern as tests/test_migration_rtl_operational_state.py.
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

TEST_SCHEMA = f"pm_c08_autodis_{uuid.uuid4().hex[:8]}"


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


class TestForwardingAutoDisableOverride:
    def setup_method(self):
        # Each test starts with an empty override table — the module-scoped
        # schema fixture is shared across tests in this class, and the
        # singleton constraint under test means leftover state from one test
        # would change what the next test is actually exercising.
        with session_scope() as session:
            session.execute(
                text(f"DELETE FROM {TEST_SCHEMA}.forwarding_auto_disable_override")
            )

    def test_singleton_row_accepted(self):
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.forwarding_auto_disable_override "
                    "(id, override_date, cutoff_time, reason, set_by_user_id) "
                    "VALUES (1, CURRENT_DATE, '20:00', 'late window', :uid)"
                ),
                {"uid": admin_a},
            )

    def test_non_singleton_id_rejected_by_check_constraint(self):
        admin_a = _user_id("admin_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.forwarding_auto_disable_override "
                        "(id, override_date, cutoff_time, reason, set_by_user_id) "
                        "VALUES (2, CURRENT_DATE, '20:00', 'late window', :uid)"
                    ),
                    {"uid": admin_a},
                )

    def test_second_row_at_id_one_rejected_by_primary_key(self):
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.forwarding_auto_disable_override "
                    "(id, override_date, cutoff_time, reason, set_by_user_id) "
                    "VALUES (1, CURRENT_DATE, '20:00', 'first', :uid)"
                ),
                {"uid": admin_a},
            )
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.forwarding_auto_disable_override "
                        "(id, override_date, cutoff_time, reason, set_by_user_id) "
                        "VALUES (1, CURRENT_DATE, '21:00', 'second', :uid)"
                    ),
                    {"uid": admin_a},
                )

    def test_missing_reason_rejected(self):
        admin_a = _user_id("admin_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.forwarding_auto_disable_override "
                        "(id, override_date, cutoff_time, set_by_user_id) "
                        "VALUES (1, CURRENT_DATE, '20:00', :uid)"
                    ),
                    {"uid": admin_a},
                )

    def test_unknown_user_rejected(self):
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.forwarding_auto_disable_override "
                        "(id, override_date, cutoff_time, reason, set_by_user_id) "
                        "VALUES (1, CURRENT_DATE, '20:00', 'late window', 999999)"
                    )
                )

    def test_row_can_be_replaced_after_delete(self):
        # The application layer upserts/deletes id=1 rather than ever
        # inserting a second row (repositories.plant_monitoring_repository.
        # set_auto_disable_override/clear_auto_disable_override) — this just
        # confirms the schema itself permits that lifecycle.
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"DELETE FROM {TEST_SCHEMA}.forwarding_auto_disable_override WHERE id = 1"
                )
            )
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.forwarding_auto_disable_override "
                    "(id, override_date, cutoff_time, reason, set_by_user_id) "
                    "VALUES (1, CURRENT_DATE, '21:15', 'second override', :uid)"
                ),
                {"uid": admin_a},
            )
