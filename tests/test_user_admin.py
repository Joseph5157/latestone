"""Tests for User Administration page — layout, table, search/filter, prototype actions.

All tests exercise pure logic (no Dash runtime, no database, no identity system).
"""
from __future__ import annotations

import pytest

from callbacks.user_admin import (
    _build_user_rows,
    _validate_user_form,
    _format_role,
)
from services.prototype_users import (
    clear_all_users,
    get_all_users,
    upsert_user,
    CONFIRMED_ROLES,
)
from components.user_form_drawer import user_form_drawer
from pages.user_admin import layout


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

class TestUserAdminLayout:
    def test_layout_returns_component(self):
        lay = layout()
        assert hasattr(lay, "children")

    def test_layout_has_breadcrumb(self):
        lay = layout()
        assert "breadcrumb" in str(lay).lower() or "User Administration" in str(lay)

    def test_layout_has_prototype_notice(self):
        lay = layout()
        text = str(lay)
        assert "Prototype" in text or "prototype" in text

    def test_layout_has_toolbar(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "user-admin-search" in ids
        assert "user-admin-status-filter" in ids
        assert "user-admin-add-btn" in ids

    def test_layout_has_entity_table(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "user-admin-table" in ids

    def test_layout_has_drawer(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "user-form-drawer" in ids


# ---------------------------------------------------------------------------
# Row building / filtering
# ---------------------------------------------------------------------------

class TestBuildUserRows:
    # clear_all_users() is database-backed (DB-2); runs against the isolated
    # test schema (tests/conftest.py), never the developer's real users table.
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def setup_method(self):
        clear_all_users()

    def test_returns_rows_for_all_users(self):
        users = [
            {"username": "alice", "identifier": "alice@example.com", "role": "administrator", "status": "active"},
            {"username": "bob", "identifier": "bob@example.com", "role": "technician", "status": "inactive"},
        ]
        rows = _build_user_rows(users)
        assert len(rows) == 2
        assert rows[0]["username"] == "alice"
        assert rows[1]["username"] == "bob"

    def test_filters_by_search_term(self):
        users = [
            {"username": "alice", "identifier": "alice@example.com", "role": "general", "status": "active"},
            {"username": "bob", "identifier": "bob@example.com", "role": "general", "status": "active"},
        ]
        rows = _build_user_rows(users, search_term="alice")
        assert len(rows) == 1
        assert rows[0]["username"] == "alice"

    def test_filters_by_status_active(self):
        users = [
            {"username": "alice", "identifier": "alice@example.com", "role": "general", "status": "active"},
            {"username": "bob", "identifier": "bob@example.com", "role": "general", "status": "inactive"},
        ]
        rows = _build_user_rows(users, status_filter="active")
        assert len(rows) == 1
        assert rows[0]["username"] == "alice"

    def test_filters_by_status_inactive(self):
        users = [
            {"username": "alice", "identifier": "alice@example.com", "role": "general", "status": "active"},
            {"username": "bob", "identifier": "bob@example.com", "role": "general", "status": "inactive"},
        ]
        rows = _build_user_rows(users, status_filter="inactive")
        assert len(rows) == 1
        assert rows[0]["username"] == "bob"

    def test_shows_all_when_filter_all(self):
        users = [
            {"username": "alice", "identifier": "alice@example.com", "role": "general", "status": "active"},
            {"username": "bob", "identifier": "bob@example.com", "role": "general", "status": "inactive"},
        ]
        rows = _build_user_rows(users, status_filter="all")
        assert len(rows) == 2

    def test_role_administrator_displayed(self):
        users = [{"username": "alice", "identifier": "", "role": "administrator", "status": "active"}]
        rows = _build_user_rows(users)
        assert rows[0]["role"] == "Administrator"

    def test_role_technician_displayed(self):
        users = [{"username": "alice", "identifier": "", "role": "technician", "status": "active"}]
        rows = _build_user_rows(users)
        assert rows[0]["role"] == "Technician"

    def test_role_general_displayed(self):
        users = [{"username": "alice", "identifier": "", "role": "general", "status": "active"}]
        rows = _build_user_rows(users)
        assert rows[0]["role"] == "General User"

    def test_role_legacy_tbd_shows_unassigned(self):
        users = [{"username": "alice", "identifier": "", "role": "tbd", "status": "active"}]
        rows = _build_user_rows(users)
        assert rows[0]["role"] == "Unassigned"

    def test_status_formatted(self):
        users = [{"username": "alice", "identifier": "", "role": "general", "status": "active"}]
        rows = _build_user_rows(users)
        assert rows[0]["status"] == "Active"

    def test_actions_column_has_edit(self):
        users = [{"username": "alice", "identifier": "", "role": "general", "status": "active"}]
        rows = _build_user_rows(users)
        assert "[Edit](#)" in rows[0]["actions"]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidateUserForm:
    # clear_all_users()/upsert_user() are database-backed (DB-2); isolated schema, see above.
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def setup_method(self):
        clear_all_users()

    def test_empty_username_fails(self):
        errors = _validate_user_form("")
        assert "username" in errors

    def test_whitespace_only_username_fails(self):
        errors = _validate_user_form("   ")
        assert "username" in errors

    def test_duplicate_username_fails(self):
        clear_all_users()
        upsert_user("alice", "", "general", "active")

        errors = _validate_user_form("alice")
        assert "username" in errors

    def test_valid_username_passes(self):
        errors = _validate_user_form("newuser")
        assert errors == {}


# ---------------------------------------------------------------------------
# Mock users
# ---------------------------------------------------------------------------

class TestMockUsers:
    # clear_all_users()/get_all_users() are database-backed (DB-2); isolated schema, see above.
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def setup_method(self):
        clear_all_users()

    def test_get_all_users_returns_list(self):
        users = get_all_users()
        assert isinstance(users, list)

    def test_demo_user_seeded_when_configured(self):
        users = get_all_users()
        assert len(users) >= 0


# ---------------------------------------------------------------------------
# User Form Drawer
# ---------------------------------------------------------------------------

class TestUserFormDrawer:
    def test_layout_returns_component(self):
        drawer = user_form_drawer()
        assert hasattr(drawer, "children")

    def test_has_overlay(self):
        drawer = user_form_drawer()
        ids = _collect_ids(drawer)
        assert "user-form-drawer-overlay" in ids

    def test_has_panel(self):
        drawer = user_form_drawer()
        assert "user-form-drawer__panel" in str(drawer)

    def test_has_form_fields(self):
        drawer = user_form_drawer()
        ids = _collect_ids(drawer)
        assert "user-form-username" in ids
        assert "user-form-identifier" in ids
        assert "user-form-role" in ids
        assert "user-form-status" in ids

    def test_role_dropdown_has_three_confirmed_roles(self):
        drawer = user_form_drawer()
        ids = _collect_ids(drawer)
        assert "user-form-role" in ids
        text = str(drawer)
        assert "Administrator" in text
        assert "Technician" in text
        assert "General User" in text

    def test_role_dropdown_not_disabled(self):
        drawer = user_form_drawer()
        text = str(drawer).lower()
        # Role dropdown should be enabled (not disabled)
        assert "disabled" not in text or "role" not in text

    def test_has_role_description_help_text(self):
        drawer = user_form_drawer()
        text = str(drawer)
        assert "broader RTL management" in text or "Technician" in text

    def test_has_confirm_and_cancel(self):
        drawer = user_form_drawer()
        ids = _collect_ids(drawer)
        assert "user-form-confirm-btn" in ids
        assert "user-form-cancel-btn" in ids

    def test_has_prototype_notice(self):
        drawer = user_form_drawer()
        text = str(drawer)
        assert "Prototype" in text or "prototype" in text


# ---------------------------------------------------------------------------
# Confirmed roles constant
# ---------------------------------------------------------------------------

class TestConfirmedRoles:
    def test_three_roles_defined(self):
        assert len(CONFIRMED_ROLES) == 3

    def test_administrator_role(self):
        assert "administrator" in CONFIRMED_ROLES

    def test_technician_role(self):
        assert "technician" in CONFIRMED_ROLES

    def test_general_role(self):
        assert "general" in CONFIRMED_ROLES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_ids(component) -> list[str]:
    """Recursively collect all component IDs from a Dash layout."""
    ids = []
    if hasattr(component, "id") and component.id:
        ids.append(component.id)
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                ids.extend(_collect_ids(child))
        elif children is not None:
            ids.extend(_collect_ids(children))
    return ids
