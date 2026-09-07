"""Report export — format-neutral document model + CSV/PDF formatters
(REPORT-4, extended by REPORT-EXPORT-1).

Frozen decisions:

- R4-D1  Both CSV and PDF are explicitly DEVELOPMENT-DEFAULT export
         formats (C-04 baseline: PDF + CSV, no native XLSX). The
         client-approved production delivery mechanism remains unresolved
         (REQ-1A §16). Never call either format "required", "official" or
         "production" — EXPORT_FORMAT_LABEL is the honesty contract.
- R4-D2  Pipeline: domain rows → ExportDocument → formatter. Report data
         services stay format-ignorant; a future client-approved format
         is a new formatter plus a registry entry, nothing more.
- R4-D3  SUPERSEDED by ADR-013, in the part that named the guard.
         Authorization still lives in the CALLBACK and still runs before
         any rows are fetched, and this module still performs none — that
         much stands. But it is `require_capability(EXPORT_DATA)`, not
         `require_action(EXPORT_DATA)`: export names no device, so the
         device-dimensioned guard never applied.
- R4-D4  Domain-native export: values come from report-service domain
         rows, never rendered HTML. None → empty cell (never the UI "—");
         timestamps → ISO 8601 UTC; numerics keep raw textual precision.
         `_cell()` is the ONE place this happens, shared by every
         formatter — CSV and PDF can never disagree about how a None or a
         datetime renders.
- R4-D5  A zero-row report exports as a header-only file — "no alarms in
         the period" is report data, not an error.
- R4-D6  Filenames follow a DEVELOPMENT convention:
         {report_key}_{scope}_{UTC timestamp}.{ext}, sanitized to safe
         characters. No client naming requirement exists.
- R4-D7  Callers rebuild the report through the same service functions
         and parameters used for the preview; this module never queries.
- R4-D9  SUPERSEDED by REPORT-EXPORT-1: all three real reports (Installed
         RTLs, RTL Alarms 30 Days, Maximum Temperature) are now
         exportable. Maximum Temperature's export rebuilds through the
         same `max_temperature_rows`/`resolve_max_temperature_period`
         functions the preview uses (R4-D7's principle, applied to a
         report whose window varies per request).
- R4-D10 PDF is a second registered formatter (`format_pdf`), built on
         fpdf2's high-level `Table` — which repeats column headers across
         pages on its own (`repeat_headings`, its default). No custom
         pagination logic is written here. Both formatters read the same
         `ExportDocument`; neither one is more "authoritative" than the
         other about what a None or a date means (R4-D4).
- R4-D11 Period identification is deliberately asymmetric across formats,
         never across CSV rows:
           - CSV stays a plain rectangular table for EVERY report, no
             exceptions: the first row is always exactly
             `get_report(key).columns`, with no preamble, no extra
             column, and no other decoration — for ANY of the three
             reports, not only the two that predate this gate. A period
             is never represented as CSV data at all.
           - `period_text` is still set on ALL three ExportDocuments and
             rendered as a PDF header line ("Period: ..."), because PDF is
             a brand-new format for every report here — there is no prior
             PDF behavior to preserve, and the PDF format itself calls for
             a title/scope/period/generated block.
           - Maximum Temperature's resolved period is instead identified
             deterministically in its CSV's FILENAME (`export_filename`'s
             `period_text` argument, gated to `report_key ==
             "max_temperature"` — Installed RTLs' and RTL Alarms' filenames
             are unaffected, matching R4-D6 exactly as before). The
             callback's export-status panel may additionally echo the
             resolved period in the UI; neither of those is a change to
             the CSV bytes themselves.
- R4-D12 `format_pdf` uses fpdf2's normal (compressed) output — no
         `pdf.compress = False`. This is production-shaped PDF behavior,
         not a development shortcut. Because FlateDecode-compressed
         content streams cannot be substring-matched as raw text, tests
         verify formatter BEHAVIOR (valid `%PDF-`/`%%EOF` framing, real
         pagination via the still-uncompressed `/Type /Page` object
         markers, and the exact header/row values actually handed to
         fpdf2's `Table.row`) rather than grepping decompressed bytes.
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
    "CSV and PDF are the current development export formats "
    "(C-04 baseline); the client-approved production delivery "
    "mechanism is still pending."
)

#: R4-D9 — all three real reports now have a download path.
EXPORTABLE_REPORTS = ("installed_rtls", "rtl_alarms_30d", "max_temperature")

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class ExportDocument:
    """A format-neutral report document ready for any tabular formatter."""

    report_key: str
    title: str
    scope_label: str
    generated_at_utc: datetime
    headers: tuple[str, ...]
    rows: tuple[tuple[str | None, ...], ...] = field(default_factory=tuple)
    #: R4-D11 — the resolved reporting period as display text, or None for
    #: a report with no period concept. Never a new DATA column.
    period_text: str | None = None


def _utc(value: datetime) -> str:
    """ISO 8601 UTC rendering for export cells (R4-D4)."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _cell(value) -> str:
    """One domain value → one exported cell, shared by every formatter.

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
    period_text: str | None = None,
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
        scope_label=scope_label,
        generated_at_utc=now,
        headers=headers,
        rows=exported,
        period_text=period_text,
    )


def installed_rtls_document(rows, *, scope_label: str, now: datetime) -> ExportDocument:
    """ExportDocument for the Installed RTLs report (REPORT-2 rows).

    R4-D11: `period_text` is a static label (current-state report, no
    period concept) — used only by the PDF header line, never the CSV
    preamble or filename (those stay gated to Maximum Temperature).
    """
    return build_document(
        report_key="installed_rtls",
        scope_label=scope_label,
        now=now,
        rows=rows,
        period_text="Not applicable (current-state report)",
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

    R4-D11: `period_text` is a static label — the 30-day window is fixed
    and already stated in the UI notice, not a resolved value that varies
    per request. Used only by the PDF header line (see module docstring).
    """
    return build_document(
        report_key="rtl_alarms_30d",
        scope_label=scope_label,
        now=now,
        rows=rows,
        period_text="Last 30 days (fixed by report definition)",
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


def max_temperature_document(
    rows, *, scope_label: str, period_text: str, now: datetime
) -> ExportDocument:
    """ExportDocument for the Maximum Temperature report (REPORT-MAXTEMP-1
    rows, exportable as of REPORT-EXPORT-1).

    ``period_text`` must be the SAME resolved-period text the preview
    showed (``_format_report_period`` in callbacks/report_center.py, fed
    by the same ``resolve_max_temperature_period`` the preview calls) —
    this function does not resolve or reformat it itself (R4-D7).
    """
    return build_document(
        report_key="max_temperature",
        scope_label=scope_label,
        now=now,
        rows=rows,
        period_text=period_text,
        cell_extractors=(
            lambda r: r.ou,
            lambda r: r.zone,
            lambda r: r.sector,
            lambda r: r.cnc,
            lambda r: r.feeder_name,
            lambda r: r.transformer,
            lambda r: r.date_installed,
            lambda r: r.max_temperature_at,
            lambda r: r.max_temperature,
        ),
    )


def format_csv(document: ExportDocument) -> str:
    """Render an ExportDocument as CSV text (a development formatter).

    stdlib csv handles quoting/escaping (QUOTE_MINIMAL covers embedded
    commas, quotes and newlines). Plain UTF-8 — no BOM — per R4-D4;
    utf-8-sig would be a tooling-specific change requiring evidence.

    R4-D11: always a plain rectangular table, for every report — the
    first row is exactly `document.headers`, with no metadata preamble
    and no period row, ever. Maximum Temperature's resolved period is
    identified in its filename (`export_filename`) and in its PDF header
    line, never inside the CSV body.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(document.headers)
    for row in document.rows:
        writer.writerow([_cell(value) for value in row])
    return buffer.getvalue()


def format_pdf(document: ExportDocument) -> bytes:
    """Render an ExportDocument as a real, paginated PDF (R4-D10).

    Landscape A4 so wider reports (RTL Alarms' 12 columns) have room.
    fpdf2's `Table` repeats the heading row on every page it spans
    (`repeat_headings`, on by default) — this function does not implement
    its own page-break/header-repeat logic. A zero-row document still
    produces a valid one-page PDF (header block + column headers, no data
    rows) — the same "legitimate empty report" convention as CSV (R4-D5).
    """
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", style="B", size=14)
    pdf.cell(0, 8, document.title, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 5, f"Scope: {document.scope_label}", new_x="LMARGIN", new_y="NEXT")
    if document.period_text is not None:
        pdf.cell(0, 5, f"Period: {document.period_text}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Generated: {_utc(document.generated_at_utc)}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", size=8)
    with pdf.table(headings_style=FontFace(emphasis="BOLD")) as table:
        table.row(list(document.headers))
        for row in document.rows:
            table.row([_cell(value) for value in row])

    return bytes(pdf.output())


#: R4-D2/R4-D10 registry: the only place a format name meets a renderer.
FORMATTERS = {"csv": format_csv, "pdf": format_pdf}

_MIME_TYPES = {"csv": "text/csv", "pdf": "application/pdf"}


def export_filename(
    report_key: str,
    scope_label: str,
    now: datetime,
    *,
    period_text: str | None = None,
    extension: str = "csv",
) -> str:
    """Deterministic filename per the development convention (R4-D6).

    {report_key}_{scope}[_{period}]_{UTC timestamp}.{extension}, sanitized
    to safe characters. ``period_text`` is omitted entirely unless the
    caller passes it (R4-D11 gates that to Maximum Temperature only, so
    Installed RTLs'/RTL Alarms' filenames are unchanged). No client naming
    requirement exists — this convention is development-owned and
    revisitable.
    """
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parts = [report_key, scope_label]
    if period_text is not None:
        parts.append(period_text)
    parts.append(stamp)
    raw = "_".join(parts) + f".{extension}"
    sanitized = _SAFE_FILENAME.sub("_", raw)
    return sanitized[:120]


def render_export(
    report_key: str, document: ExportDocument, export_format: str = "csv"
) -> tuple[str | bytes, str, str]:
    """(content, mime_type, filename) for an approved exportable report.

    Raises ValueError for a report outside EXPORTABLE_REPORTS, or a format
    outside FORMATTERS — neither gains a download path merely by passing a
    different key/format string.
    """
    if report_key not in EXPORTABLE_REPORTS:
        raise ValueError(f"{report_key!r} is not an exportable report.")
    if export_format not in FORMATTERS:
        raise ValueError(f"{export_format!r} is not a supported export format.")
    formatter = FORMATTERS[export_format]
    content = formatter(document)
    # R4-D11: the filename's period segment is Maximum Temperature-only.
    filename_period = document.period_text if report_key == "max_temperature" else None
    filename = export_filename(
        report_key, document.scope_label, document.generated_at_utc,
        period_text=filename_period, extension=export_format,
    )
    return content, _MIME_TYPES[export_format], filename


__all__ = [
    "EXPORT_FORMAT_LABEL",
    "EXPORTABLE_REPORTS",
    "ExportDocument",
    "export_filename",
    "format_csv",
    "format_pdf",
    "installed_rtls_document",
    "max_temperature_document",
    "render_export",
    "rtl_alarms_document",
]
