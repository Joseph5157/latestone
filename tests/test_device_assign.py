"""Tests for device assignment drawer — layout, mock adapter, cascade logic.

All tests exercise pure logic (no Dash runtime, no database).
"""
from __future__ import annotations

import pytest

from callbacks.device_assign import (
    _plant_options,
    _transformer_options,
    get_mock_assignment,
    clear_mock_assignments,
    _mock_assignments,
)
from components.assign_device_drawer import assign_device_drawer


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

class TestAssignDrawerLayout:
    def test_layout_returns_div(self):
        drawer = assign_device_drawer()
        assert hasattr(drawer, "children")

    def test_layout_has_overlay(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-drawer-overlay" in ids

    def test_layout_has_panel(self):
        drawer = assign_device_drawer()
        assert "assign-drawer__panel" in str(drawer)

    def test_layout_has_device_info_section(self):
        drawer = assign_device_drawer()
        assert "assign-drawer-device-code" in str(drawer)
        assert "assign-drawer-current-transformer" in str(drawer)
        assert "assign-drawer-current-plant" in str(drawer)

    def test_layout_has_plant_dropdown(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-plant" in ids

    def test_layout_has_transformer_dropdown(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-transformer" in ids

    def test_layout_has_confirm_button(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-confirm-btn" in ids

    def test_layout_has_cancel_button(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-cancel-btn" in ids

    def test_layout_has_hidden_device_store(self):
        drawer = assign_device_drawer()
        ids = _collect_ids(drawer)
        assert "assign-device-hidden-id" in ids

    def test_layout_has_prototype_notice(self):
        drawer = assign_device_drawer()
        text = str(drawer)
        assert "Prototype" in text or "prototype" in text


# ---------------------------------------------------------------------------
# Mock adapter
# ---------------------------------------------------------------------------

class TestMockAssignment:
    def setup_method(self):
        clear_mock_assignments()

    def test_no_assignment_returns_none(self):
        assert get_mock_assignment("device-1") is None

    def test_set_and_get_assignment(self):
        _mock_assignments["device-1"] = "tx-new"
        assert get_mock_assignment("device-1") == "tx-new"

    def test_clear_assignments(self):
        _mock_assignments["device-1"] = "tx-new"
        clear_mock_assignments()
        assert get_mock_assignment("device-1") is None

    def test_multiple_devices(self):
        _mock_assignments["d1"] = "tx-1"
        _mock_assignments["d2"] = "tx-2"
        assert get_mock_assignment("d1") == "tx-1"
        assert get_mock_assignment("d2") == "tx-2"


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
