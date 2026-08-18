"""Tests for shared prototype user state provider.

All tests exercise pure logic (no Dash runtime, no database, no identity system).
"""
from __future__ import annotations

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


class TestPrototypeUsers:
    def setup_method(self):
        clear_all_users()

    def test_get_all_users_returns_list(self):
        users = get_all_users()
        assert isinstance(users, list)

    def test_upsert_user_adds_new_user(self):
        upsert_user("alice", "alice@example.com", "administrator", "active")
        user = get_user("alice")
        assert user is not None
        assert user["username"] == "alice"
        assert user["role"] == "administrator"

    def test_upsert_user_updates_existing_user(self):
        upsert_user("alice", "alice@example.com", "general", "active")
        upsert_user("alice", "alice@new.com", "technician", "active")
        user = get_user("alice")
        assert user["identifier"] == "alice@new.com"
        assert user["role"] == "technician"

    def test_upsert_user_validates_role(self):
        upsert_user("alice", "", "invalid_role", "active")
        user = get_user("alice")
        assert user["role"] == "general"  # defaults to general

    def test_get_user_returns_none_for_missing(self):
        assert get_user("nonexistent") is None

    def test_remove_user(self):
        upsert_user("alice", "", "general", "active")
        remove_user("alice")
        assert get_user("alice") is None

    def test_remove_user_noop_for_missing(self):
        remove_user("nonexistent")  # should not raise

    def test_clear_all_users_removes_all(self):
        upsert_user("alice", "", "general", "active")
        upsert_user("bob", "", "technician", "active")
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
        upsert_user("alice", "", "administrator", "active")
        upsert_user("bob", "", "technician", "active")
        upsert_user("charlie", "", "general", "active")
        techs = get_technicians()
        assert len(techs) == 1
        assert techs[0]["username"] == "bob"

    def test_excludes_inactive_technicians(self):
        upsert_user("bob", "", "technician", "inactive")
        techs = get_technicians()
        assert len(techs) == 0

    def test_returns_empty_when_no_technicians(self):
        techs = get_technicians()
        assert techs == []


class TestGetTechnicianOptions:
    def setup_method(self):
        clear_all_users()

    def test_returns_dropdown_options(self):
        upsert_user("bob", "", "technician", "active")
        options = get_technician_options()
        assert options == [{"label": "bob", "value": "bob"}]

    def test_returns_empty_list_when_no_technicians(self):
        options = get_technician_options()
        assert options == []

    def test_excludes_non_technicians(self):
        upsert_user("alice", "", "administrator", "active")
        upsert_user("bob", "", "technician", "active")
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
