"""Tests for prototype role-based access helpers.

All tests exercise pure logic (no Dash runtime, no database, no identity system).
"""
from __future__ import annotations

from services.prototype_access import (
    can_program_rtl,
    can_manage_assignment,
    can_toggle_message_forwarding,
    can_deactivate_rtl,
    can_view_device,
    can_export_data,
)


class TestCanProgramRtl:
    def test_administrator_can_always_program(self):
        assert can_program_rtl("administrator") is True

    def test_administrator_can_program_unassigned_rtl(self):
        assert can_program_rtl("administrator", is_assigned_to_user=False) is True

    def test_assigned_technician_can_program(self):
        assert can_program_rtl("technician", is_assigned_to_user=True) is True

    def test_unassigned_technician_cannot_program(self):
        assert can_program_rtl("technician", is_assigned_to_user=False) is False

    def test_technician_without_flag_cannot_program(self):
        assert can_program_rtl("technician") is False

    def test_general_user_cannot_program(self):
        assert can_program_rtl("general") is False

    def test_unknown_role_cannot_program(self):
        assert can_program_rtl("unknown") is False


class TestCanManageAssignment:
    def test_administrator_can_manage(self):
        assert can_manage_assignment("administrator") is True

    def test_technician_cannot_manage(self):
        assert can_manage_assignment("technician") is False

    def test_general_user_cannot_manage(self):
        assert can_manage_assignment("general") is False

    def test_unknown_role_cannot_manage(self):
        assert can_manage_assignment("unknown") is False


class TestCanToggleMessageForwarding:
    def test_administrator_can_always_toggle(self):
        assert can_toggle_message_forwarding("administrator") is True

    def test_administrator_can_toggle_unassigned(self):
        assert can_toggle_message_forwarding("administrator", is_assigned_to_user=False) is True

    def test_assigned_technician_can_toggle(self):
        assert can_toggle_message_forwarding("technician", is_assigned_to_user=True) is True

    def test_unassigned_technician_cannot_toggle(self):
        assert can_toggle_message_forwarding("technician", is_assigned_to_user=False) is False

    def test_technician_without_flag_cannot_toggle(self):
        assert can_toggle_message_forwarding("technician") is False

    def test_general_user_cannot_toggle(self):
        assert can_toggle_message_forwarding("general") is False


class TestCanDeactivateRtl:
    def test_administrator_can_always_deactivate(self):
        assert can_deactivate_rtl("administrator") is True

    def test_administrator_can_deactivate_unassigned(self):
        assert can_deactivate_rtl("administrator", is_assigned_to_user=False) is True

    def test_assigned_technician_can_deactivate(self):
        assert can_deactivate_rtl("technician", is_assigned_to_user=True) is True

    def test_unassigned_technician_cannot_deactivate(self):
        assert can_deactivate_rtl("technician", is_assigned_to_user=False) is False

    def test_technician_without_flag_cannot_deactivate(self):
        assert can_deactivate_rtl("technician") is False

    def test_general_user_cannot_deactivate(self):
        assert can_deactivate_rtl("general") is False


class TestCanViewDevice:
    def test_administrator_can_view(self):
        assert can_view_device("administrator") is True

    def test_technician_can_view(self):
        assert can_view_device("technician") is True

    def test_general_user_can_view(self):
        assert can_view_device("general") is True

    def test_unknown_role_cannot_view(self):
        assert can_view_device("unknown") is False


class TestCanExportData:
    def test_administrator_can_export(self):
        assert can_export_data("administrator") is True

    def test_technician_can_export(self):
        assert can_export_data("technician") is True

    def test_general_user_can_export(self):
        assert can_export_data("general") is True

    def test_unknown_role_cannot_export(self):
        assert can_export_data("unknown") is False
