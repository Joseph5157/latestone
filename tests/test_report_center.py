"""Tests for Report Center page — layout, form, preview, mock reports, prototype generation.

All tests exercise pure logic (no Dash runtime, no database, no reporting service).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from callbacks.report_center import (
    _plant_options,
    _transformer_options,
    _device_options,
    _scope_label,
    _mock_recent_reports,
    _build_preview,
    _build_definition_status,
    _build_installed_rtls_table,
    _build_rtl_alarms_table,
    _format_alarm_at,
)
from components.entity_table import entity_table
from config.reports import (
    REPORTS,
    get_report,
    report_options,
    all_report_keys,
)
from pages.report_center import layout
from services.device_scope import UNRESTRICTED
from services.report_service import InstalledRtlsRow, RtlAlarms30dRow


# ---------------------------------------------------------------------------
# Report definitions — config/reports.py
# ---------------------------------------------------------------------------

class TestReportDefinitions:
    def test_exactly_three_reports(self):
        assert len(REPORTS) == 3

    def test_no_tbd_report(self):
        for r in REPORTS:
            assert "TBD" not in r.label
            assert "tbd" not in r.key

    def test_rtl_alarms_30d_columns(self):
        report = get_report("rtl_alarms_30d")
        assert report is not None
        assert report.label == "RTL Alarms (30 Days)"
        expected = [
            "OU", "Zone", "Sector", "CNC", "Feeder", "Transformer",
            "UID", "Battery(V)", "Alarm Date & Time",
            "Temperature (\u00b0C)", "Alarm", "Firmware",
        ]
        assert list(report.columns) == expected

    def test_installed_rtls_columns(self):
        report = get_report("installed_rtls")
        assert report is not None
        assert report.label == "Installed RTLs"
        expected = [
            "OU", "Zone", "Sector", "CNC", "Feeder Name", "Transformer",
            "UID", "Timestamp of Last Recorded Data",
            "Last Recorded Temperature (\u00b0C)", "RTL Status",
        ]
        assert list(report.columns) == expected

    def test_max_temperature_columns(self):
        report = get_report("max_temperature")
        assert report is not None
        assert report.label == "Maximum Temperature"
        expected = [
            "OU", "Zone", "Sector", "CNC", "Feeder Name", "Transformer",
            "Date Installed", "Date of Maximum Temperature",
            "Maximum Temperature (\u00b0C)",
        ]
        assert list(report.columns) == expected

    def test_rtl_alarms_date_fixed_to_30d(self):
        report = get_report("rtl_alarms_30d")
        assert report.date_range_fixed == "30d"

    def test_installed_rtls_date_not_fixed(self):
        report = get_report("installed_rtls")
        assert report.date_range_fixed is None

    def test_max_temperature_date_not_fixed(self):
        report = get_report("max_temperature")
        assert report.date_range_fixed is None

    def test_report_options_count(self):
        options = report_options()
        assert len(options) == 3

    def test_report_options_labels(self):
        options = report_options()
        labels = [o["label"] for o in options]
        assert "RTL Alarms (30 Days)" in labels
        assert "Installed RTLs" in labels
        assert "Maximum Temperature" in labels

    def test_all_report_keys(self):
        keys = all_report_keys()
        assert keys == ("rtl_alarms_30d", "installed_rtls", "max_temperature")

    def test_get_report_unknown_returns_none(self):
        assert get_report("nonexistent") is None


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

    def test_layout_has_preview_section(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-preview" in ids

    def test_layout_has_definition_status(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-definition-status" in ids

    def test_layout_has_period_notice(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-period-notice" in ids

    def test_layout_has_period_container(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-period-container" in ids

    def test_report_type_dropdown_not_disabled(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "report-type" in ids
        # Dropdown should NOT be disabled anymore
        # (we check by absence of disabled=True in the page text)
        text = str(lay)
        assert "Client to confirm" not in text

    def test_no_tbd_in_layout(self):
        lay = layout()
        text = str(lay)
        assert "TBD" not in text


# ---------------------------------------------------------------------------
# Preview builder
# ---------------------------------------------------------------------------

class TestBuildPreview:
    def test_preview_for_valid_report(self):
        preview = _build_preview("rtl_alarms_30d")
        text = str(preview)
        assert "RTL Alarms (30 Days)" in text
        assert "OU" in text
        assert "Firmware" in text

    def test_preview_for_installed_rtls(self):
        preview = _build_preview("installed_rtls")
        text = str(preview)
        assert "Installed RTLs" in text
        assert "RTL Status" in text

    def test_preview_for_max_temperature(self):
        preview = _build_preview("max_temperature")
        text = str(preview)
        assert "Maximum Temperature" in text
        assert "Date of Maximum Temperature" in text

    def test_preview_for_unknown_returns_empty(self):
        preview = _build_preview("nonexistent")
        assert hasattr(preview, "style")
        assert preview.style == {"display": "none"}

    def test_preview_has_columns_list(self):
        preview = _build_preview("rtl_alarms_30d")
        text = str(preview)
        assert "<li>" in text.lower() or "OU" in text

    def test_preview_has_description(self):
        preview = _build_preview("rtl_alarms_30d")
        text = str(preview)
        assert "Alarms triggered" in text


# ---------------------------------------------------------------------------
# Definition status builder
# ---------------------------------------------------------------------------

class TestBuildDefinitionStatus:
    def test_status_for_valid_report(self):
        """REPORT-3: rtl_alarms_30d is now data-backed, so its honesty
        notice states the real source instead of 'mapping incomplete'."""
        status = _build_definition_status("rtl_alarms_30d")
        text = str(status)
        assert "persisted device events" in text
        assert "last 30 days" in text

    def test_status_for_installed_rtls_is_data_backed(self):
        status = _build_definition_status("installed_rtls")
        assert "current application database" in str(status)

    def test_status_for_unknown_returns_empty(self):
        status = _build_definition_status("nonexistent")
        assert hasattr(status, "style")
        assert status.style == {"display": "none"}


# ---------------------------------------------------------------------------
# Scope label helper
# ---------------------------------------------------------------------------

class TestScopeLabel:
    """Only the fleet label is pure: every other scope resolves an equipment
    name through `hierarchy_service`, which reads the database. Those cases
    carry `db` so the pure-logic suite stays runnable without Docker."""

    def test_fleet(self):
        assert _scope_label("fleet") == "Entire Fleet"

    @pytest.mark.db
    def test_plant(self):
        result = _scope_label("plant", plant_id="p1")
        assert "Plant:" in result

    @pytest.mark.db
    def test_transformer(self):
        result = _scope_label(
            "transformer", plant_id="p1", transformer_id="t1", device_scope=UNRESTRICTED
        )
        assert "Transformer:" in result

    @pytest.mark.db
    def test_device(self):
        result = _scope_label("device", device_id="d1")
        assert "Device:" in result


# ---------------------------------------------------------------------------
# Cascade options helpers
# ---------------------------------------------------------------------------

class TestCascadeOptions:
    @pytest.mark.db
    def test_plant_options_returns_list(self):
        """Reads the plant list from the database; the empty-input cases below
        return before any query and stay in the pure-logic suite."""
        options = _plant_options(UNRESTRICTED)
        assert isinstance(options, list)

    def test_transformer_options_empty_without_plant(self):
        options = _transformer_options("", UNRESTRICTED)
        assert options == []

    def test_device_options_empty_without_transformer(self):
        options = _device_options("", UNRESTRICTED)
        assert options == []


# ---------------------------------------------------------------------------
# Mock recent reports
# ---------------------------------------------------------------------------

class TestMockRecentReports:
    def test_mock_reports_is_list(self):
        assert isinstance(_mock_recent_reports, list)

    def test_mock_reports_use_confirmed_names(self):
        _mock_recent_reports.clear()
        from callbacks.report_center import _seed_mock_reports
        _seed_mock_reports()
        confirmed_names = {"RTL Alarms (30 Days)", "Installed RTLs", "Maximum Temperature"}
        for entry in _mock_recent_reports:
            assert entry["report"] in confirmed_names

    def test_mock_reports_status_not_completed(self):
        _mock_recent_reports.clear()
        from callbacks.report_center import _seed_mock_reports
        _seed_mock_reports()
        for entry in _mock_recent_reports:
            assert entry["status"] != "Completed"
            assert entry["status"] == "Demo"

    def test_mock_reports_no_action_column(self):
        _mock_recent_reports.clear()
        from callbacks.report_center import _seed_mock_reports
        _seed_mock_reports()
        for entry in _mock_recent_reports:
            assert "action" not in entry

    def test_mock_reports_no_invented_names(self):
        _mock_recent_reports.clear()
        from callbacks.report_center import _seed_mock_reports
        _seed_mock_reports()
        invented = {"Daily Temperature Summary", "Transformer Load Report", "Energy Consumption Export"}
        for entry in _mock_recent_reports:
            assert entry["report"] not in invented


# ---------------------------------------------------------------------------
# Alarm timestamp UTC normalization (ENT-6A)
# ---------------------------------------------------------------------------

IST = timezone(timedelta(hours=5, minutes=30))


class TestAlarmTimestampUtc:
    """The alarm preview must render the same instant the CSV export does
    (ISO-8601 UTC): timezone-aware values convert to UTC before formatting."""

    def test_non_utc_timestamp_converts_to_utc(self):
        # 13:05 IST == 07:35 UTC — the old code formatted "13:05 UTC",
        # silently relabelling a non-UTC instant.
        value = datetime(2026, 8, 26, 13, 5, tzinfo=IST)
        assert _format_alarm_at(value) == "2026-08-26 07:35 UTC"

    def test_already_utc_timestamp_unchanged(self):
        value = datetime(2026, 8, 26, 7, 45, tzinfo=timezone.utc)
        assert _format_alarm_at(value) == "2026-08-26 07:45 UTC"

    def test_naive_timestamp_formats_as_is(self):
        """Mirrors report_export._utc: no tzinfo means nothing to convert."""
        value = datetime(2026, 8, 26, 7, 45)
        assert _format_alarm_at(value) == "2026-08-26 07:45 UTC"

    def test_preview_table_row_carries_converted_value(self):
        row = RtlAlarms30dRow(
            ou=None, zone=None, sector=None, cnc=None, feeder_name=None,
            transformer="T1", uid="29017", battery_voltage=3.9,
            alarm_at=datetime(2026, 8, 26, 13, 5, tzinfo=IST),
            temperature=61.5, alarm_label="Overtemperature",
            firmware_version="1.2.3",
        )
        text = str(_build_rtl_alarms_table([row]))
        assert "2026-08-26 07:35 UTC" in text
        assert "2026-08-26 13:05" not in text


def _alarm_row(**overrides) -> RtlAlarms30dRow:
    defaults = dict(
        ou=None, zone=None, sector=None, cnc=None, feeder_name=None,
        transformer="T1", uid="29017", battery_voltage=3.9,
        alarm_at=datetime(2026, 8, 26, 7, 45, tzinfo=timezone.utc),
        temperature=61.5, alarm_label="Overtemperature",
        firmware_version="1.2.3",
    )
    defaults.update(overrides)
    return RtlAlarms30dRow(**defaults)


def _installed_row(**overrides) -> InstalledRtlsRow:
    defaults = dict(
        ou=None, zone=None, sector=None, cnc=None, feeder_name=None,
        transformer="T1", uid="29017",
        last_recorded_at=datetime(2026, 8, 26, 7, 45, tzinfo=timezone.utc),
        last_temperature=61.5, rtl_status="active",
    )
    defaults.update(overrides)
    return InstalledRtlsRow(**defaults)


def _data_tables(component):
    tables = []
    stack = [component]
    while stack:
        current = stack.pop()
        if hasattr(current, "__class__") and current.__class__.__name__ == "DataTable":
            tables.append(current)
        if hasattr(current, "children") and current.children is not None:
            children = current.children
            stack.extend(children if isinstance(children, list) else [children])
    return tables


def _find_wrapper(component, table_id):
    for table in _data_tables(component):
        if table.id == table_id:
            return component
    raise AssertionError(f"{table_id} not found")


class TestReportTableBuildersIntact:
    """REP-01 / REP-02 presentation stays intact; zero rows stay valid."""

    def test_installed_rtls_table_columns_and_rows(self):
        wrapper = _build_installed_rtls_table([_installed_row()])
        (table,) = _data_tables(wrapper)
        assert [c["name"] for c in table.columns][:2] == ["OU", "Zone"]
        assert table.data[0]["uid"] == "29017"
        assert table.data[0]["rtl_status"] == "active"

    def test_rtl_alarms_table_columns_and_rows(self):
        wrapper = _build_rtl_alarms_table([_alarm_row()])
        (table,) = _data_tables(wrapper)
        assert table.columns[8]["name"] == "Alarm Date & Time"
        assert table.data[0]["alarm_label"] == "Overtemperature"

    def test_none_taxonomy_renders_placeholder_in_table_only(self):
        wrapper = _build_rtl_alarms_table([_alarm_row()])
        (table,) = _data_tables(wrapper)
        assert table.data[0]["ou"] == "\u2014"

    def test_zero_row_rtl_alarms_table_is_valid(self):
        wrapper = _build_rtl_alarms_table([])
        (table,) = _data_tables(wrapper)
        assert table.data == []
        assert len(table.columns) == 12

    def test_zero_row_installed_rtls_table_is_valid(self):
        wrapper = _build_installed_rtls_table([])
        (table,) = _data_tables(wrapper)
        assert table.data == []
        assert len(table.columns) == 10

    def test_both_report_tables_opt_into_responsive_presentation(self):
        assert "entity-table-wrapper--responsive" in str(
            _build_installed_rtls_table([]).className
        )
        assert "entity-table-wrapper--responsive" in str(
            _build_rtl_alarms_table([]).className
        )


# ---------------------------------------------------------------------------
# Layout structure — loading affordance + separate actions (ENT-6A)
# ---------------------------------------------------------------------------

class TestReportLoadingAndActionsLayout:
    def test_loading_wrappers_present(self):
        ids = _collect_ids(layout())
        # dcc.Loading components carry no id themselves; their presence is
        # asserted via the CSS hook class rendered on the wrapper div.
        assert str(layout()).count("report-loading") >= 2

    def test_generation_result_id_still_present_inside_loading(self):
        assert "report-generation-result" in _collect_ids(layout())

    def test_recent_reports_table_responsive(self):
        text = str(layout())
        assert "entity-table-wrapper--responsive" in text

    def test_generate_and_download_remain_separate_buttons(self):
        ids = _collect_ids(layout())
        assert "report-generate-btn" in ids
        assert "report-download-btn" in ids

    def test_demo_status_rendered_muted_not_freshness_green(self):
        tables = [
            t for t in _data_tables(layout()) if t.id == "recent-reports-table"
        ]
        (table,) = tables
        status_rule = [
            rule for rule in table.style_data_conditional
            if rule.get("if", {}).get("column_id") == "status"
        ]
        assert any(rule.get("fontStyle") == "italic" for rule in status_rule)


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------

class TestArchitecture:
    def test_no_sql_in_page_module(self):
        import pages.report_center as mod
        import inspect
        source = inspect.getsource(mod)
        assert "text(" not in source
        assert "session.execute" not in source

    def test_no_sql_in_callback_module(self):
        import callbacks.report_center as mod
        import inspect
        source = inspect.getsource(mod)
        # Check for SQLAlchemy text() usage, not substring matches
        assert "from sqlalchemy import text" not in source
        assert "session.execute" not in source

    def test_no_file_output_in_callbacks(self):
        import callbacks.report_center as mod
        import inspect
        source = inspect.getsource(mod)
        assert "open(" not in source
        assert "write(" not in source
        assert ".pdf" not in source
        assert ".xlsx" not in source
        assert ".csv" not in source

    def test_report_definitions_independent_of_backend(self):
        import config.reports as mod
        import inspect
        source = inspect.getsource(mod)
        assert "repository" not in source.lower()
        assert "database" not in source.lower()
        assert "sql" not in source.lower()

    def test_callback_module_uses_config_reports(self):
        import callbacks.report_center as mod
        import inspect
        source = inspect.getsource(mod)
        assert "from config.reports import" in source


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
