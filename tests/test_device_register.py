"""Tests for device registration form — layout, validation, review, prototype submit.

All tests exercise pure logic (no Dash runtime, no database).
"""
from __future__ import annotations

import pytest

from callbacks.device_register import (
    _plant_options,
    _transformer_options,
    _validate_form,
    _review_summary,
)
from pages.device_register import layout


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

class TestDeviceRegisterLayout:
    def test_layout_returns_component(self):
        lay = layout()
        assert hasattr(lay, "children")

    def test_layout_has_breadcrumb(self):
        lay = layout()
        assert "breadcrumb" in str(lay).lower() or "Devices" in str(lay)

    def test_layout_has_form(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "device-register-form" in ids

    def test_layout_has_review_section(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "device-register-review" in ids

    def test_layout_has_success_section(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "device-register-success" in ids

    def test_layout_has_prototype_notice(self):
        lay = layout()
        text = str(lay)
        assert "Prototype workflow" in text or "Prototype" in text

    def test_layout_has_required_fields(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "device-register-code" in ids
        assert "device-register-plant" in ids
        assert "device-register-transformer" in ids
        assert "device-register-status" in ids


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidateForm:
    def test_empty_code_fails(self):
        errors = _validate_form("", "plant-1", "tx-1")
        assert "code" in errors

    def test_whitespace_only_code_fails(self):
        errors = _validate_form("   ", "plant-1", "tx-1")
        assert "code" in errors

    def test_code_too_long_fails(self):
        errors = _validate_form("a" * 11, "plant-1", "tx-1")
        assert "code" in errors

    def test_code_exactly_10_chars_passes(self):
        errors = _validate_form("a" * 10, "plant-1", "tx-1")
        assert "code" not in errors

    def test_missing_plant_fails(self):
        errors = _validate_form("29017", "", "tx-1")
        assert "plant" in errors

    def test_missing_transformer_fails(self):
        errors = _validate_form("29017", "plant-1", "")
        assert "transformer" in errors

    def test_all_valid_returns_empty(self):
        errors = _validate_form("29017", "plant-1", "tx-1")
        assert errors == {}

    def test_valid_with_whitespace_code_passes(self):
        errors = _validate_form(" 29017 ", "plant-1", "tx-1")
        assert errors == {}


# ---------------------------------------------------------------------------
# Review summary
# ---------------------------------------------------------------------------

class TestReviewSummary:
    def test_returns_div(self):
        summary = _review_summary("29017", "Plant A", "T1", "active")
        assert hasattr(summary, "children")

    def test_shows_all_fields(self):
        summary = _review_summary("29017", "Plant A", "T1", "active")
        text = str(summary)
        assert "29017" in text
        assert "Plant A" in text
        assert "T1" in text
        assert "Active" in text


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
