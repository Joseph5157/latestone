"""Report export — format-neutral document model + CSV formatter (REPORT-4).

Frozen decisions:

- R4-D1  CSV is an explicitly DEVELOPMENT-DEFAULT export format. The
         client-approved production report format/delivery remains
         unresolved (REQ-1A §16). Never call CSV "required", "official"
         or "production" — EXPORT_FORMAT_LABEL is the honesty contract.
- R4-D2  Pipeline: domain rows → ExportDocument → formatter. Report data
         services stay format-ignorant; a future client-approved format
         is a new formatter plus a registry entry, nothing more.
- R4-D3  SUPERSEDED by ADR-013, in the part that named the guard.
         Authorization still lives in the CALLBACK and still runs before
         any rows are fetched, and this module still performs none — that
         much stands. But it is `require_capability(EXPORT_DATA)`, not
         `require_action(EXPORT_DATA)`: export names no device, so the
         device-dimensioned guard never applied. As written, R4-D3
         described a two-argument `require_action` that had already
         stopped existing, and the download path it specified raised
         TypeError in every commit that contained it.
- R4-D4  Domain-native export: values come from report-service domain
         rows, never rendered HTML. None → empty cell (never the UI "—");
         timestamps → ISO 8601 UTC; numerics keep raw textual precision;
         encoding is plain UTF-8 (no BOM) unless future client/tooling
         evidence says otherwise.
- R4-D5  A zero-row report exports as a header-only file — "no alarms in
         the period" is report data, not an error.
- R4-D6  Filenames follow a DEVELOPMENT convention:
         {report_key}_{scope}_{UTC timestamp}.csv, sanitized to safe
         characters. No client naming requirement exists.
- R4-D7  Callers rebuild the report through the same service functions
         and parameters used for the preview; this module never queries.
- R4-D9  Only Installed RTLs and RTL Alarms (30 Days) are exportable;
         Maximum Temperature has no builder until its period is resolved.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config.reports import get_report

#: R4-D1 honesty contract. Rendered verbatim near the download control and
#: asserted by tests so the distinction can never silently disappear.
EXPORT_FORMAT_LABEL = (
    "CSV is the current development export format; the client-approved "
    "production format is still pending."
)

#: R4-D9 — reports with real download capability. REP-03 stays out until
#: its reporting period is client-confirmed.
EXPORTABLE_REPORTS = ("installed_rtls", "rtl_alarms_30d")

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class ExportDocument:
    """A format-neutral report document ready for any tabular formatter."""

    report_key: str
    title: str
    period_label: str
    generated_at_utc: datetime
    headers: tuple[str, ...]
    rows: tuple[tuple[str | None, ...], ...] = field(default_factory=tuple)


def _utc(value: datetime) -> str:
    """ISO 8601 UTC rendering for export cells (R4-D4)."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _cell(value) -> str:
    """One domain value → one CSV cell.

    None becomes an empty field — deliberately NOT the UI placeholder
    "—", which would corrupt machine readability (R2-D2/R3-D5/R4-D4).
    Everything else renders through str() with float formatting left to
    Python's shortest-roundtrip repr (raw numeric text, no decoration).
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return _utc(value)
    return str(value)


def build_document(
    *,
    report_key: str,
    scope_label: str,
    now: datetime,
    rows,
    cell_extractors: tuple,
) -> ExportDocument:
    """Assemble an ExportDocument from report-service domain rows.

    ``headers`` come from config.reports (single column-order truth);
    ``cell_extractors`` map each domain row to header-aligned values.
    """
    report = get_report(report_key)
    if report is None:
        raise ValueError(f"Unknown report key {report_key!r}")
    headers = tuple(report.columns)
    if len(cell_extractors) != len(headers):
        raise ValueError(
            f"{report_key}: {len(cell_extractors)} extractors cannot "
            f"populate {len(headers)} columns."
        )
    exported = tuple(
        tuple(extractor(row) for extractor in cell_extractors) for row in rows
    )
    return ExportDocument(
        report_key=report_key,
        title=report.label,
        period_label=scope_label,
        generated_at_utc=now,
        headers=headers,
        rows=exported,
    )


def installed_rtls_document(rows, *, scope_label: str, now: datetime) -> ExportDocument:
    """ExportDocument for the Installed RTLs report (REPORT-2 rows)."""
    return build_document(
        report_key="installed_rtls",
        scope_label=scope_label,
        now=now,
        rows=rows,
        cell_extractors=(
            lambda r: r.ou,
            lambda r: r.zone,
            lambda r: r.sector,
            lambda r: r.cnc,
            lambda r: r.feeder_name,
            lambda r: r.transformer,
            lambda r: r.uid,
            lambda r: r.last_recorded_at,
            lambda r: r.last_temperature,
            lambda r: r.rtl_status,
        ),
    )


def rtl_alarms_document(rows, *, scope_label: str, now: datetime) -> ExportDocument:
    """ExportDocument for the RTL Alarms (30 Days) report (REPORT-3 rows).

    Alarm Date & Time is the source occurrence time rendered ISO-8601 UTC
    (EVT-D9); battery/temperature are empty when absent (EVT-D4).
    """
    return build_document(
        report_key="rtl_alarms_30d",
        scope_label=scope_label,
        now=now,
        rows=rows,
        cell_extractors=(
            lambda r: r.ou,
            lambda r: r.zone,
            lambda r: r.sector,
            lambda r: r.cnc,
            lambda r: r.feeder_name,
            lambda r: r.transformer,
            lambda r: r.uid,
            lambda r: r.battery_voltage,
            lambda r: r.alarm_at,
            lambda r: r.temperature,
            lambda r: r.alarm_label,
            lambda r: r.firmware_version,
        ),
    )


def format_csv(document: ExportDocument) -> str:
    """Render an ExportDocument as CSV text (the development formatter).

    stdlib csv handles quoting/escaping (QUOTE_MINIMAL covers embedded
    commas, quotes and newlines). Plain UTF-8 — no BOM — per R4-D4;
    utf-8-sig would be a tooling-specific change requiring evidence.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(document.headers)
    for row in document.rows:
        writer.writerow([_cell(value) for value in row])
    return buffer.getvalue()


#: R4-D2 registry: the only place a format name meets a renderer.
FORMATTERS = {"csv": format_csv}

_CSV_MIME = "text/csv"


def export_filename(report_key: str, scope_label: str, now: datetime) -> str:
    """Deterministic filename per the development convention (R4-D6).

    {report_key}_{scope}_{UTC timestamp}.csv with everything outside
    [A-Za-z0-9._-] collapsed to underscores. No client naming requirement
    exists — this convention is development-owned and revisitable.
    """
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw = f"{report_key}_{scope_label}_{stamp}.csv"
    sanitized = _SAFE_FILENAME.sub("_", raw)
    return sanitized[:120]


def render_export(
    report_key: str, document: ExportDocument
) -> tuple[str, str, str]:
    """(content, mime_type, filename) for an approved exportable report.

    Raises ValueError for reports outside EXPORTABLE_REPORTS — REP-03 must
    never gain a download path merely by passing a different key.
    """
    if report_key not in EXPORTABLE_REPORTS:
        raise ValueError(f"{report_key!r} is not an exportable report.")
    formatter = FORMATTERS["csv"]  # R4-D1: single registered dev format
    content = formatter(document)
    filename = export_filename(report_key, document.period_label, document.generated_at_utc)
    return content, _CSV_MIME, filename


__all__ = [
    "EXPORT_FORMAT_LABEL",
    "EXPORTABLE_REPORTS",
    "ExportDocument",
    "export_filename",
    "format_csv",
    "installed_rtls_document",
    "render_export",
    "rtl_alarms_document",
]
