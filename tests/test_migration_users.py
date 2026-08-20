"""
Migration tests — 003_users (DB-1).

Verifies the users table: PK, UNIQUE(username), the confirmed-role CHECK,
and that email_address/mobile_number are deliberately nullable and NOT
unique (no business rule confirms uniqueness for either yet).

All tests run Alembic in a SUBPROCESS against a temporary schema so the real
seeded development database is never modified.
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

TEST_SCHEMA = f"pm_db1_users_{uuid.uuid4().hex[:8]}"


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


@pytest.fixture(scope="module", autouse=True)
def _clean_test_schema():
    _drop_test_schema()
    _run_alembic("upgrade", "head")
    yield
    _drop_test_schema()


def _insert_user(username: str, role: str = "general", **overrides) -> None:
    fields = {
        "username": username,
        "full_name": overrides.get("full_name", "Test User"),
        "role": role,
    }
    if "email_address" in overrides:
        fields["email_address"] = overrides["email_address"]
    if "mobile_number" in overrides:
        fields["mobile_number"] = overrides["mobile_number"]
    columns = ", ".join(fields)
    placeholders = ", ".join(f":{k}" for k in fields)
    with session_scope() as session:
        session.execute(
            text(f"INSERT INTO {TEST_SCHEMA}.users ({columns}) VALUES ({placeholders})"),
            fields,
        )


class TestUsersSchema:
    def test_table_and_columns_present(self):
        with session_scope() as session:
            columns = set(
                session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = :schema AND table_name = 'users'"
                    ),
                    {"schema": TEST_SCHEMA},
                ).scalars().all()
            )
        assert columns == {
            "user_id", "username", "full_name", "email_address", "mobile_number",
            "role", "status", "created_at", "updated_at",
        }

    def test_default_status_is_active(self):
        _insert_user("default_status_user")
        with session_scope() as session:
            status = session.execute(
                text(f"SELECT status FROM {TEST_SCHEMA}.users WHERE username = 'default_status_user'")
            ).scalar_one()
        assert status == "active"


class TestUsernameUniqueness:
    def test_duplicate_username_rejected(self):
        _insert_user("dup_user")
        with pytest.raises(IntegrityError):
            _insert_user("dup_user")


class TestEmailAndMobileNotUnique:
    def test_duplicate_email_allowed(self):
        _insert_user("email_user_1", email_address="shared@example.com")
        # Must not raise: email uniqueness is not a confirmed business rule.
        _insert_user("email_user_2", email_address="shared@example.com")

    def test_duplicate_mobile_allowed(self):
        _insert_user("mobile_user_1", mobile_number="0000000000")
        _insert_user("mobile_user_2", mobile_number="0000000000")

    def test_null_email_and_mobile_allowed(self):
        _insert_user("bare_user")  # no email/mobile supplied


class TestRoleCheck:
    @pytest.mark.parametrize("role", ["administrator", "technician", "general"])
    def test_confirmed_roles_accepted(self, role):
        _insert_user(f"role_user_{role}", role=role)

    def test_unconfirmed_role_rejected(self):
        with pytest.raises(IntegrityError):
            _insert_user("bad_role_user", role="superadmin")
