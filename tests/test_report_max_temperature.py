"""REPORT-MAXTEMP-1 pure tests — Maximum Temperature service/presentation
logic and period resolution (C-15). Database-backed proofs of the
per-transformer query itself live in test_report_max_temperature_db.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from repositories import plant_monitoring_repository as repo
from services.device_scope import DeviceScope
from services import report_service
from services.report_service import (
    MAX_TEMPERATURE_DEFAULT_WINDOW,
    MaxTemperatureRow,
    ReportError,
    max_temperature_rows,
    resolve_max_temperature_period,
)

NOW = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
SCOPE = DeviceScope(device_ids=None)


@dataclass(frozen=True)
class FakeRecord:
    plant_id: str = "p1"
    transformer_id: str = "p1-t1"
    transformer_code: str = "t1code"
    device_id: str | None = "p1-t1-d1"
    max_temperature: float | None = 91.4
    max_reading_at: datetime | None = NOW - timedelta(days=2)
    installed_at: datetime | None = datetime(2025, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def capture_repo(monkeypatch):
    captured = {}
    records: list = []

    def fake(**kwargs):
        captured.update(kwargs)
        return list(records)

    monkeypatch.setattr(repo, "max_temperature_report_rows", fake)
    return captured, records


# ---------------------------------------------------------------------------
# RMT-D3 — period resolution (C-15 default + custom)
# ---------------------------------------------------------------------------


class TestPeriodResolution:
    def test_default_is_rolling_thirty_days_ending_at_reference(self):
        since, until = resolve_max_temperature_period(None, None, now=NOW)
        assert until == NOW
        assert since == NOW - MAX_TEMPERATURE_DEFAULT_WINDOW
        assert MAX_TEMPERATURE_DEFAULT_WINDOW == timedelta(days=30)

    def test_explicit_bounds_pass_through_verbatim(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 15, tzinfo=timezone.utc)
        since, until = resolve_max_temperature_period(start, end, now=NOW)
        assert (since, until) == (start, end)

    def test_only_one_bound_supplied_falls_back_to_default(self):
        """A malformed half-custom state (should not occur from the UI, but
        must not crash) resolves to the same default as no bounds at all."""
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        since, until = resolve_max_temperature_period(start, None, now=NOW)
        assert (since, until) == (NOW - MAX_TEMPERATURE_DEFAULT_WINDOW, NOW)

    def test_default_reference_time_does_not_raise(self):
        since, until = resolve_max_temperature_period(None, None)
        assert since < until <= datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Service delegation
# ---------------------------------------------------------------------------


class TestReportServiceDelegation:
    def test_service_passes_scope_metric_and_window_to_repository(self, capture_repo):
        captured, _ = capture_repo
        since, until = resolve_max_temperature_period(None, None, now=NOW)
        scope = DeviceScope(device_ids=frozenset({"d1"}))

        max_temperature_rows(
            plant_id="p1", device_scope=scope, since=since, until=until,
        )

        assert captured["allowed_device_ids"] == frozenset({"d1"})
        assert captured["temperature_metric"] == "temperature"
        assert captured["plant_id"] == "p1"
        assert captured["transformer_id"] is None
        assert captured["device_id"] is None
        assert captured["since"] == since
        assert captured["until"] == until

    def test_domain_row_taxonomy_is_actual_none_and_values_pass_through(self, capture_repo):
        _, records = capture_repo
        records.append(FakeRecord())

        rows = max_temperature_rows(
            device_scope=SCOPE, since=NOW - timedelta(days=30), until=NOW,
        )

        assert len(rows) == 1
        row = rows[0]
        assert row.ou is None and row.zone is None and row.sector is None
        assert row.cnc is None and row.feeder_name is None
        assert row.transformer == "t1code"
        assert row.max_temperature == 91.4
        assert row.max_temperature_at == NOW - timedelta(days=2)
        assert row.date_installed == datetime(2025, 1, 1, tzinfo=timezone.utc)

    def test_transformer_with_no_reading_in_window_is_a_real_row_with_nulls(self, capture_repo):
        _, records = capture_repo
        records.append(
            FakeRecord(device_id=None, max_temperature=None,
                       max_reading_at=None, installed_at=None)
        )

        rows = max_temperature_rows(
            device_scope=SCOPE, since=NOW - timedelta(days=30), until=NOW,
        )

        assert len(rows) == 1
        assert rows[0].max_temperature is None
        assert rows[0].max_temperature_at is None
        assert rows[0].date_installed is None

    def test_zero_rows_is_a_legitimate_empty_report(self, capture_repo):
        rows = max_temperature_rows(
            device_scope=SCOPE, since=NOW - timedelta(days=30), until=NOW,
        )
        assert rows == []

    def test_repository_failure_raises_friendly_report_error(self, monkeypatch):
        def explode(**kwargs):
            raise RuntimeError("simulated store outage")

        monkeypatch.setattr(repo, "max_temperature_report_rows", explode)
        with pytest.raises(ReportError):
            max_temperature_rows(
                device_scope=SCOPE, since=NOW - timedelta(days=30), until=NOW,
            )


# ---------------------------------------------------------------------------
# Presentation (callbacks/report_center.py helpers)
# ---------------------------------------------------------------------------


def _row(**overrides) -> MaxTemperatureRow:
    defaults = dict(
        ou=None, zone=None, sector=None, cnc=None, feeder_name=None,
        transformer="t1code",
        date_installed=datetime(2025, 1, 1, tzinfo=timezone.utc),
        max_temperature_at=datetime(2026, 9, 5, 8, 30, tzinfo=timezone.utc),
        max_temperature=91.4,
    )
    defaults.update(overrides)
    return MaxTemperatureRow(**defaults)


class TestMaxTemperaturePresentation:
    def test_column_headers_match_client_contract(self):
        from callbacks.report_center import _build_max_temperature_table

        names = [c["name"] for c in _build_max_temperature_table([_row()]).children[0].columns]
        assert names == [
            "OU", "Zone", "Sector", "CNC", "Feeder Name",
            "Transformer", "Date Installed", "Date of Maximum Temperature",
            "Maximum Temperature (°C)",
        ]

    def test_none_taxonomy_renders_as_placeholder_r2d2(self):
        from callbacks.report_center import _build_max_temperature_table

        data = _build_max_temperature_table([_row()]).children[0].data
        assert data[0]["ou"] == "—"
        assert data[0]["feeder_name"] == "—"

    def test_dates_render_date_only_not_datetime(self):
        from callbacks.report_center import _build_max_temperature_table

        data = _build_max_temperature_table([_row()]).children[0].data
        assert data[0]["date_installed"] == "2025-01-01"
        assert data[0]["max_temperature_at"] == "2026-09-05"
        assert data[0]["max_temperature"] == "91.4"

    def test_missing_date_installed_renders_as_placeholder_not_invented(self):
        """RMT-D2: no installed_at on the winning device -> blank, never a
        guessed date."""
        from callbacks.report_center import _build_max_temperature_table

        data = _build_max_temperature_table(
            [_row(date_installed=None)]
        ).children[0].data
        assert data[0]["date_installed"] == "—"

    def test_empty_transformer_row_renders_placeholders_not_zeros(self):
        from callbacks.report_center import _build_max_temperature_table

        data = _build_max_temperature_table(
            [_row(max_temperature=None, max_temperature_at=None, date_installed=None)]
        ).children[0].data
        assert data[0]["max_temperature"] == "—"
        assert data[0]["max_temperature_at"] == "—"

    def test_period_is_rendered_with_both_bounds_and_utc_label(self):
        from callbacks.report_center import _format_report_period

        text = _format_report_period(
            datetime(2026, 8, 8, tzinfo=timezone.utc),
            datetime(2026, 9, 7, tzinfo=timezone.utc),
        )
        assert text == "2026-08-08 to 2026-09-07 UTC"
