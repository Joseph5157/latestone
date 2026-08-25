"""REPORT-4I pure tests — export document model, CSV formatter, filename
convention, and format-honesty contract. No database.

Database-backed scope-isolation and end-to-end proofs live in
test_report_export_db.py.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from config.reports import get_report
from services import report_export as ex


NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class FakeAlarmRow:
    ou = None
    zone = None
    sector = None
    cnc = None
    feeder_name = None
    transformer: str = "tc1"
    uid: str | None = "29101"
    battery_voltage: float | None = 3.52
    alarm_at: datetime = datetime(2026, 8, 20, 6, 30, tzinfo=timezone.utc)
    temperature: float | None = 85.25
    alarm_label: str = "Battery Alarm"
    firmware_version: str | None = "v7"


def _parse(content: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(content, newline="")))


# ---------------------------------------------------------------------------
# R4-D1 — the honesty contract
# ---------------------------------------------------------------------------


class TestFormatHonesty:
    def test_label_names_development_default_and_pending_approval(self):
        label = ex.EXPORT_FORMAT_LABEL.lower()
        assert "development" in label
        assert "csv" in label
        assert "pending" in label or "still" in label

    def test_label_never_claims_official_status(self):
        label = ex.EXPORT_FORMAT_LABEL.lower()
        for forbidden in ("required", "official", "client-approved production format is csv"):
            assert forbidden not in label

    def test_only_csv_is_registered(self):
        """R4-D1/D10: exactly one development formatter until the client
        answers; PDF/XLSX are absent, not stubbed."""
        assert list(ex.FORMATTERS) == ["csv"]


# ---------------------------------------------------------------------------
# R4-D9 — which reports are exportable
# ---------------------------------------------------------------------------


class TestExportableReports:
    def test_exactly_rep01_and_rep02(self):
        assert set(ex.EXPORTABLE_REPORTS) == {"installed_rtls", "rtl_alarms_30d"}

    def test_rep03_has_no_download_path(self):
        assert "max_temperature" not in ex.EXPORTABLE_REPORTS
        with pytest.raises(ValueError):
            ex.render_export(
                "max_temperature",
                ex.ExportDocument("max_temperature", "t", "fleet", NOW,
                                  ("A",), ()),
            )


# ---------------------------------------------------------------------------
# R4-D5 — column order and header fidelity
# ---------------------------------------------------------------------------


class TestHeaders:
    @pytest.mark.parametrize(
        "report_key,builder",
        [
            ("rtl_alarms_30d", ex.rtl_alarms_document),
            ("installed_rtls", ex.installed_rtls_document),
        ],
    )
    def test_headers_match_the_client_contract_exactly(self, report_key, builder):
        doc = builder([], scope_label="fleet", now=NOW)   # header-only document
        assert doc.headers == get_report(report_key).columns

    def test_header_only_document_for_zero_rows(self):
        """R4-D5: a valid zero-row report exports headers only."""
        content = ex.format_csv(ex.rtl_alarms_document([], scope_label="fleet", now=NOW))
        parsed = _parse(content)
        assert len(parsed) == 1
        assert parsed[0][0] == "OU"


# ---------------------------------------------------------------------------
# R4-D4 — domain-native cells, UTF-8, escaping
# ---------------------------------------------------------------------------


class TestCellSemantics:
    def _alarm_csv(self, row: FakeAlarmRow) -> list[list[str]]:
        return _parse(ex.format_csv(ex.rtl_alarms_document([row], scope_label="fleet", now=NOW)))

    def test_none_becomes_empty_never_the_ui_placeholder(self):
        """R2-D2/R3-D5/R4-D4: '—' must never leak into exported bytes."""
        row = FakeAlarmRow(battery_voltage=None, temperature=None,
                           firmware_version=None, uid=None)
        record = self._alarm_csv(row)[1]
        assert "—" not in ex.format_csv(ex.rtl_alarms_document([row], scope_label="fleet", now=NOW))
        assert [record[7], record[9], record[11], record[6]] == ["", "", "", ""]

    def test_timestamps_are_iso8601_utc(self):
        record = self._alarm_csv(FakeAlarmRow())[1]
        assert record[8] == "2026-08-20T06:30:00Z"

    def test_naive_datetime_is_interpreted_as_utc(self):
        naive = FakeAlarmRow(alarm_at=datetime(2026, 8, 20, 6, 30))
        record = self._alarm_csv(naive)[1]
        assert record[8] == "2026-08-20T06:30:00Z"

    def test_numerics_render_raw_not_decorated(self):
        record = self._alarm_csv(FakeAlarmRow())[1]
        assert record[7] == "3.52"
        assert record[9] == "85.25"

    def test_taxonomy_cells_are_empty(self):
        record = self._alarm_csv(FakeAlarmRow())[1]
        assert record[0:5] == ["", "", "", "", ""]

    def test_commas_quotes_newlines_and_unicode_round_trip(self):
        tricky = 'Alarm, with "quotes" and\nnewline — °C ünicode'
        doc = ex.ExportDocument(
            report_key="rtl_alarms_30d", title="t", period_label="fleet",
            generated_at_utc=NOW, headers=("Alarm",), rows=[(tricky,)],
        )
        parsed = _parse(ex.format_csv(doc))
        assert parsed[1][0] == tricky

    def test_output_is_plain_utf8_no_bom(self):
        """Review refinement: neutral UTF-8, no BOM, unless client/tooling
        evidence later demands utf-8-sig."""
        doc = ex.rtl_alarms_document([FakeAlarmRow()], scope_label="fleet", now=NOW)
        raw = ex.format_csv(doc).encode("utf-8")
        assert not raw.startswith(b"\xef\xbb\xbf")


# ---------------------------------------------------------------------------
# R4-D6 — deterministic development filename convention
# ---------------------------------------------------------------------------


class TestFilename:
    def test_shape_is_deterministic(self):
        name = ex.export_filename("rtl_alarms_30d", "fleet", NOW)
        assert name == "rtl_alarms_30d_fleet_20260825T120000Z.csv"

    def test_hostile_scope_characters_are_sanitized(self):
        name = ex.export_filename(
            "installed_rtls",
            'plant/"Koeberg",\n unit <1>',
            NOW,
        )
        assert set(name) <= set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        )
        assert name.endswith("_20260825T120000Z.csv")

    def test_long_scope_labels_are_bounded(self):
        name = ex.export_filename("installed_rtls", "x" * 500, NOW)
        assert len(name) <= 120

    def test_render_export_returns_mime_and_filename(self):
        doc = ex.rtl_alarms_document([FakeAlarmRow()], scope_label="fleet", now=NOW)
        content, mime, filename = ex.render_export("rtl_alarms_30d", doc)
        assert mime == "text/csv"
        assert filename == "rtl_alarms_30d_fleet_20260825T120000Z.csv"
        assert "Battery Alarm" in content
