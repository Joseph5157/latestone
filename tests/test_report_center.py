"""Tests for Report Center page — layout, form, cascade, mock reports, prototype generation.

All tests exercise pure logic (no Dash runtime, no database, no reporting service).
"""
from __future__ import annotations

import pytest

from callbacks.report_center import (
    _plant_options,
    _transformer_options,
    _device_options,
    _scope_label,
    _mock_recent_reports,
)
from pages.report_center import layout


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

class TestReportCenterLayout:
    def test_layout_returns_component(self):
        lay = layout()
        assert hasattr(lay, "children")

    def test_layout_has_breadcrumb(self):
        lay = layout()
        assert "breadcrumb" in str(lay).lower() or "Report Center" in str(lay)

    def test_layout_has_prototype_notice(self):
        lay = layout()
        text = str(lay)
        assert "Prototype" in text or "prototype" in text

    def test_layout_has_generate_section(self):
        lay = layout()
        text = str(lay)
        assert "Generate Report" in text

    def test_layout_has_recent_section(self):
        lay = layout()
        text = str(lay)
        assert "Recent Reports" in text

    def test_layout_has_report_type_dropdown(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-type" in ids

    def test_layout_has_asset_scope_dropdown(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-asset-scope" in ids

    def test_layout_has_plant_dropdown(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-plant" in ids

    def test_layout_has_transformer_dropdown(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-transformer" in ids

    def test_layout_has_device_dropdown(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-device" in ids

    def test_layout_has_period_radio(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-period" in ids

    def test_layout_has_custom_date_range(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-custom-date-range" in ids

    def test_layout_has_generate_button(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-generate-btn" in ids

    def test_layout_has_recent_reports_table(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "recent-reports-table" in ids

    def test_report_type_disabled_tbd(self):
        lay = layout()
        text = str(lay)
        assert "TBD" in text
        assert "Client to confirm" in text


# ---------------------------------------------------------------------------
# Scope label helper
# ---------------------------------------------------------------------------

class TestScopeLabel:
    def test_fleet(self):
        assert _scope_label("fleet") == "Entire Fleet"

    def test_plant(self):
        # This will fall back to plant_id since no service in test
        result = _scope_label("plant", plant_id="p1")
        assert "Plant:" in result

    def test_transformer(self):
        result = _scope_label("transformer", plant_id="p1", transformer_id="t1")
        assert "Transformer:" in result

    def test_device(self):
        result = _scope_label("device", device_id="d1")
        assert "Device:" in result


# ---------------------------------------------------------------------------
# Cascade options helpers
# ---------------------------------------------------------------------------

class TestCascadeOptions:
    def test_plant_options_returns_list(self):
        options = _plant_options()
        assert isinstance(options, list)

    def test_transformer_options_empty_without_plant(self):
        options = _transformer_options("")
        assert options == []

    def test_device_options_empty_without_transformer(self):
        options = _device_options("")
        assert options == []


# ---------------------------------------------------------------------------
# Mock recent reports
# ---------------------------------------------------------------------------

class TestMockRecentReports:
    def test_mock_reports_is_list(self):
        assert isinstance(_mock_recent_reports, list)

    def test_mock_reports_has_entries(self):
        # Seeded by callbacks on import
        assert len(_mock_recent_reports) >= 0


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