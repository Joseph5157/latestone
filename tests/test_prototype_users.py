"""Tests for the persistent user store (DB-2).

Storage moved from an in-memory dict to plant_monitoring.users in DB-2, so
these now require a real database connection. They run against the
`isolated_schema` fixture (tests/conftest.py) â€” a disposable
`pm_test_<uuid>` schema, never the developer's real plant_monitoring.users
table.
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys

import pytest
from sqlalchemy import text

from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services.prototype_users import (
    get_all_users,
    get_user,
    upsert_user,
    remove_user,
    clear_all_users,
    get_technicians,
    get_technician_options,
    seed_demo_user,
    CONFIRMED_ROLES,
)

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]


def _auditor() -> int:
    """AUD-1: audited upserts need an authenticated actor. Created at
    repository level (no audit row) and idempotent across classes that
    share this module-scoped schema."""
    return repo.create_or_update_user(
        username="users-admin",
        full_name="users-admin",
        role="administrator",
        status="active",
    ).user_id


class TestPrototypeUsers:
    def setup_method(self):
        # AUD-1 audit rows FK-reference users; clear them before the users
        # table so each test starts from an empty store.
        with session_scope() as session:
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.audit_log"))
        clear_all_users()
        _auditor()

    def test_get_all_users_returns_list(self):
        users = get_all_users()
        assert isinstance(users, list)

    def test_upsert_user_adds_new_user(self):
        upsert_user("alice", "alice@example.com", "administrator", "active", actor_user_id=_auditor())
        user = get_user("alice")
        assert user is not None
        assert user["username"] == "alice"
        assert user["role"] == "administrator"

    def test_upsert_user_updates_existing_user(self):
        upsert_user("alice", "alice@example.com", "general", "active", actor_user_id=_auditor())
        upsert_user("alice", "alice@new.com", "technician", "active", actor_user_id=_auditor())
        user = get_user("alice")
        assert user["identifier"] == "alice@new.com"
        assert user["role"] == "technician"

    def test_upsert_user_validates_role(self):
        upsert_user("alice", "", "invalid_role", "active", actor_user_id=_auditor())
        user = get_user("alice")
        assert user["role"] == "general"  # defaults to general

    def test_get_user_returns_none_for_missing(self):
        assert get_user("nonexistent") is None

    def test_remove_user(self):
        upsert_user("alice", "", "general", "active", actor_user_id=_auditor())
        remove_user("alice")
        assert get_user("alice") is None

    def test_remove_user_noop_for_missing(self):
        remove_user("nonexistent")  # should not raise

    def test_clear_all_users_removes_all(self):
        upsert_user("alice", "", "general", "active", actor_user_id=_auditor())
        upsert_user("bob", "", "technician", "active", actor_user_id=_auditor())
        clear_all_users()
        # Note: get_all_users() calls seed_demo_user() which may re-add demo user
        # This test verifies clear_all_users clears the store
        # The demo user may be re-seeded depending on config
        users = get_all_users()
        # After clear, only demo user (if configured) should exist
        assert all(u["username"] == "admin" for u in users) or len(users) == 0


class TestGetTechnicians:
    def setup_method(self):
        clear_all_users()

    def test_returns_only_technicians(self):
        upsert_user("alice", "", "administrator", "active", actor_user_id=_auditor())
        upsert_user("bob", "", "technician", "active", actor_user_id=_auditor())
        upsert_user("charlie", "", "general", "active", actor_user_id=_auditor())
        techs = get_technicians()
        assert len(techs) == 1
        assert techs[0]["username"] == "bob"

    def test_excludes_inactive_technicians(self):
        upsert_user("bob", "", "technician", "inactive", actor_user_id=_auditor())
        techs = get_technicians()
        assert len(techs) == 0

    def test_returns_empty_when_no_technicians(self):
        techs = get_technicians()
        assert techs == []


class TestGetTechnicianOptions:
    def setup_method(self):
        clear_all_users()

    def test_returns_dropdown_options(self):
        upsert_user("bob", "", "technician", "active", actor_user_id=_auditor())
        options = get_technician_options()
        assert options == [{"label": "bob", "value": "bob"}]

    def test_returns_empty_list_when_no_technicians(self):
        options = get_technician_options()
        assert options == []

    def test_excludes_non_technicians(self):
        upsert_user("alice", "", "administrator", "active", actor_user_id=_auditor())
        upsert_user("bob", "", "technician", "active", actor_user_id=_auditor())
        options = get_technician_options()
        assert len(options) == 1
        assert options[0]["value"] == "bob"


class TestConfirmedRoles:
    def test_three_roles_defined(self):
        assert len(CONFIRMED_ROLES) == 3

    def test_administrator_role(self):
        assert "administrator" in CONFIRMED_ROLES

    def test_technician_role(self):
        assert "technician" in CONFIRMED_ROLES

    def test_general_role(self):
        assert "general" in CONFIRMED_ROLES


class TestSeedDemoUser:
    def setup_method(self):
        clear_all_users()

    def test_seeds_demo_user_when_configured(self):
        # seed_demo_user depends on demo_auth config
        # At minimum it should not raise
        seed_demo_user()
        users = get_all_users()
        assert isinstance(users, list)

    def test_seeding_twice_does_not_duplicate(self):
        from config.settings import demo_auth
        if not demo_auth.is_configured:
            pytest.skip("DEMO_USERNAME/DEMO_PASSWORD not configured")
        seed_demo_user()
        seed_demo_user()
        seed_demo_user()
        matches = [u for u in get_all_users() if u["username"] == demo_auth.username]
        assert len(matches) == 1

    def test_seeding_does_not_overwrite_admin_edits(self):
        """Idempotent means "ensure exists", not "reset to defaults"."""
        from config.settings import demo_auth
        if not demo_auth.is_configured:
            pytest.skip("DEMO_USERNAME/DEMO_PASSWORD not configured")
        seed_demo_user()
        upsert_user(demo_auth.username, "changed@example.com", "administrator", "active", actor_user_id=_auditor())
        seed_demo_user()  # must not revert the edit
        user = get_user(demo_auth.username)
        assert user["role"] == "administrator"
        assert user["identifier"] == "changed@example.com"


class TestPersistenceIsReal:
    """DB-2's actual goal: storage must not depend on module-level memory."""

    def setup_method(self):
        clear_all_users()

    def test_duplicate_username_upsert_does_not_create_duplicate_row(self):
        upsert_user("dora", "dora1@example.com", "general", "active", actor_user_id=_auditor())
        upsert_user("dora", "dora2@example.com", "technician", "active", actor_user_id=_auditor())
        rows = [u for u in repo.list_users() if u.username == "dora"]
        assert len(rows) == 1
        assert rows[0].role == "technician"
        assert rows[0].email_address == "dora2@example.com"

    def test_created_user_is_a_real_database_row(self):
        upsert_user("erin", "erin@example.com", "general", "active", actor_user_id=_auditor())
        row = repo.get_user_by_username("erin")
        assert row is not None
        assert row.full_name == "erin"  # defaulted, no source field for it
        assert row.email_address == "erin@example.com"
        assert row.mobile_number is None

    def test_removed_user_is_gone_from_the_database(self):
        upsert_user("frank", "", "general", "active", actor_user_id=_auditor())
        remove_user("frank")
        assert repo.get_user_by_username("frank") is None

    def test_clear_all_users_deletes_database_rows(self):
        upsert_user("gina", "", "general", "active", actor_user_id=_auditor())
        clear_all_users()
        assert repo.list_users() == []

    def test_survives_a_fresh_module_reload(self):
        """Reload the service module in-process and confirm the user is
        still visible, proving nothing lives in the module's own memory.
        """
        import services.prototype_users as prototype_users_module

        upsert_user("harold", "harold@example.com", "technician", "active", actor_user_id=_auditor())

        reloaded = importlib.reload(prototype_users_module)
        user = reloaded.get_user("harold")
        assert user is not None
        assert user["role"] == "technician"

        # Restore the normal module object for subsequent tests/imports.
        importlib.reload(prototype_users_module)

    def test_survives_a_separate_process(self, isolated_schema):
        """Stronger than the reload test: a genuinely separate OS process,
        pointed at the same isolated schema via PLANT_MONITORING_SCHEMA, must
        see the row â€” proof of real cross-process DB persistence rather than
        any in-process cache, without touching the real users table.
        """
        upsert_user("ivan", "ivan@example.com", "technician", "active", actor_user_id=_auditor())

        env = dict(os.environ)
        env["PLANT_MONITORING_SCHEMA"] = isolated_schema
        result = subprocess.run(
            [
                sys.executable, "-c",
                "from services.prototype_users import get_user; "
                "u = get_user('ivan'); "
                "print(u['role'] if u else 'MISSING')",
            ],
            cwd=os.getcwd(),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "technician"
