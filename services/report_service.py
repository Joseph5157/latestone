"""Installed RTLs report — the first data-backed report (REPORT-2).

Thin service boundary between callbacks/report_center.py and
repositories/plant_monitoring_repository.py. The callback must not call the
repository directly.

Frozen REPORT-2 decisions (see docs/archive/REPORT-2_PLANNING_PROMPT.md and
the reviewer adjustments R2-D1..D7):

- R2-D1 "Timestamp of Last Recorded Data" is the newest reading of ANY
  metric — a development interpretation of general device communication
  freshness, pending client confirmation.
- R2-D2 The client's OU/Zone/Sector/CNC/Feeder taxonomy has no confirmed
  mapping yet, so these fields stay None in the domain row. Turning them
  into display placeholders is presentation-layer work ONLY: an exporter
  added later must be able to distinguish "unmapped" from real report data.
- R2-D3 No administrative status filtering happens here. Registered devices
  appear with their `devices.status` exposed honestly; if the client later
  confirms installed means active, that rule is applied explicitly in one
  place (the repository query).
- R2-D4 Devices with zero readings remain in the report with NULLs.

Rows are ordered transformer then UID by the repository; this service
preserves that order and adds nothing to it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config.metrics import ATTRIBUTION_METRIC_KEY
from repositories import plant_monitoring_repository as repo
from services.device_scope import DeviceScope

logger = logging.getLogger(__name__)


class ReportError(Exception):
    """Report generation failed for a reason safe to show the user."""


@dataclass(frozen=True)
class InstalledRtlsRow:
    """Domain row for Installed RTLs, matching the client-confirmed column
    contract in config/reports.py. Raw typed values only — timestamp and
    temperature formatting is a presentation decision."""

    ou: str | None
    zone: str | None
    sector: str | None
    cnc: str | None
    feeder_name: str | None
    transformer: str
    uid: str
    last_recorded_at: datetime | None
    last_temperature: float | None
    rtl_status: str


def installed_rtls_rows(
    *,
    plant_id: str | None = None,
    transformer_id: str | None = None,
    device_id: str | None = None,
    device_scope: DeviceScope,
) -> list[InstalledRtlsRow]:
    """Build Installed RTLs rows for the asset scope ∩ ROLE-3 session scope.

    Scope intersection is delegated entirely to the repository's ANDed
    filters — no second visibility predicate lives here.
    """
    try:
        records = repo.installed_rtls_report_rows(
            temperature_metric=ATTRIBUTION_METRIC_KEY,
            plant_id=plant_id,
            transformer_id=transformer_id,
            device_id=device_id,
            allowed_device_ids=device_scope.device_ids,
        )
    except Exception as exc:
        logger.exception("Failed to build Installed RTLs report rows")
        raise ReportError(
            "The Installed RTLs report could not be loaded. "
            "Please try again."
        ) from exc

    return [
        # R2-D2: taxonomy columns are None until the client mapping lands.
        InstalledRtlsRow(
            ou=None,
            zone=None,
            sector=None,
            cnc=None,
            feeder_name=None,
            transformer=r.transformer_code,
            uid=r.device_code,
            last_recorded_at=r.last_recorded_at,
            last_temperature=r.last_temperature,
            rtl_status=r.status,
        )
        for r in records
    ]


@dataclass(frozen=True)
class RtlAlarms30dRow:
    """Domain row for RTL Alarms (30 Days), matching the client-confirmed
    column contract in config/reports.py (REPORT-3).

    Taxonomy fields stay None per R2-D2. ``alarm_at`` is the source
    occurrence time (EVT-D9); battery/temperature are display payload that
    is None when the device did not send it (EVT-D4). Raw typed values
    only — formatting is a presentation decision.
    """

    ou: None
    zone: None
    sector: None
    cnc: None
    feeder_name: None
    transformer: str
    uid: str | None
    battery_voltage: float | None
    alarm_at: datetime
    temperature: float | None
    alarm_label: str
    firmware_version: str | None


def _alarm_transformer_cell(record) -> tuple[str, str]:
    """Resolve the Transformer cell per the refined R3-D6 rule.

    Event snapshot present  -> the EVENT's transformer (historical fact;
    never silently rewritten because the device later moved).
    Event snapshot absent   -> the device's CURRENT transformer, as an
    explicit fallback for UID-resolved events that carry no snapshot.
    Returns (transformer_id, code).
    """
    if record.event_transformer_id is not None:
        return record.event_transformer_id, record.event_transformer_code
    return None, record.current_transformer_code


def rtl_alarms_30d_rows(
    *,
    plant_id: str | None = None,
    transformer_id: str | None = None,
    device_id: str | None = None,
    device_scope: DeviceScope,
    now: datetime | None = None,
) -> list[RtlAlarms30dRow]:
    """Build RTL Alarms (30 Days) rows for asset scope ∩ ROLE-3 scope.

    REPORT-3 frozen decisions:
    - R3-D1  alarm inclusion comes ONLY from
      ``event_semantics.is_reportable_alarm`` — this service never lists
      event-type literals.
    - R3-D4  ordering is the repository's ``event_ts DESC, event_id DESC``;
      preserved, not re-sorted.
    - R3-D5  alarm labels resolve through the shared semantics/category
      mapping; taxonomy columns are actual None.
    - R3-D6  transformer cell follows the strict snapshot rule (see
      ``_alarm_transformer_cell``).
    - R3-D7  fixed ALARM_REPORT_WINDOW (30 days), computed from an
      injectable reference time.
    """
    # Deferred import keeps report_service importable without events.
    from services.event_semantics import (
        ALARM_REPORT_WINDOW,
        alarm_label_for_event_type,
        reportable_alarm_event_types,
    )

    reference = now or datetime.now(timezone.utc)

    try:
        records = repo.rtl_alarms_30d_report_rows(
            event_types=list(reportable_alarm_event_types()),
            since=reference - ALARM_REPORT_WINDOW,
            plant_id=plant_id,
            transformer_id=transformer_id,
            device_id=device_id,
            allowed_device_ids=device_scope.device_ids,
        )
    except Exception as exc:
        logger.exception("Failed to build RTL Alarms (30 Days) report rows")
        raise ReportError(
            "The RTL Alarms report could not be loaded. Please try again."
        ) from exc

    return [
        RtlAlarms30dRow(
            ou=None,
            zone=None,
            sector=None,
            cnc=None,
            feeder_name=None,
            transformer=_alarm_transformer_cell(r)[1] or "",
            uid=r.device_code,
            battery_voltage=r.battery_voltage,
            alarm_at=r.alarm_at,
            temperature=r.temperature,
            alarm_label=alarm_label_for_event_type(r.event_type),
            firmware_version=r.firmware_version,
        )
        for r in records
    ]


# RMT-D3: the C-15 development baseline default (docs/context/ACTIVE_GATE.md)
# — rolling 30 days, pending client confirmation. Mirrors ALARM_REPORT_WINDOW's
# shape (event_semantics.py): a fixed timedelta resolved against an injectable
# reference time, never a bare "30 days ago" computed inline more than once.
MAX_TEMPERATURE_DEFAULT_WINDOW: timedelta = timedelta(days=30)


def resolve_max_temperature_period(
    since: datetime | None,
    until: datetime | None,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Resolve the Maximum Temperature report's period (C-15).

    Both bounds explicitly supplied -> that custom range, verbatim (the
    caller — the callback's date-picker parsing — already decided what
    "custom" means; this function does not re-interpret it). Otherwise the
    default: a rolling 30-day window ending at ``now`` (or the real current
    time if ``now`` is omitted). A single caller-visible entry point so the
    preview and the period text shown to the user can never compute two
    different windows for the same request — the same failure class R4-D7
    already guards against for CSV export vs preview.
    """
    if since is not None and until is not None:
        return since, until
    reference = now or datetime.now(timezone.utc)
    return reference - MAX_TEMPERATURE_DEFAULT_WINDOW, reference


@dataclass(frozen=True)
class MaxTemperatureRow:
    """Domain row for Maximum Temperature, matching the client-confirmed
    column contract in config/reports.py (REPORT-MAXTEMP-1).

    Taxonomy fields stay None per R2-D2. ``date_installed`` is the specific
    device's ``installed_at`` (RMT-D2 in the repository docstring) — not a
    transformer-level fact, since none exists. Raw typed values only;
    formatting is a presentation decision.
    """

    ou: None
    zone: None
    sector: None
    cnc: None
    feeder_name: None
    transformer: str
    date_installed: datetime | None
    max_temperature_at: datetime | None
    max_temperature: float | None


def max_temperature_rows(
    *,
    plant_id: str | None = None,
    transformer_id: str | None = None,
    device_id: str | None = None,
    device_scope: DeviceScope,
    since: datetime,
    until: datetime,
) -> list[MaxTemperatureRow]:
    """Build Maximum Temperature rows for asset scope ∩ ROLE-3 scope.

    ``since``/``until`` are the already-resolved window — call
    ``resolve_max_temperature_period`` first (both the preview and the
    (future) export path must resolve the same way; this function does not
    default them a second time). ``since > until`` is a malformed range,
    not this layer's business rule to police — it simply cannot match any
    reading, so PostgreSQL correctly returns zero rows; a valid empty
    report, not an exception.

    REPORT-MAXTEMP-1 frozen decisions:
    - RMT-D1  tie-break for a shared maximum is deterministic (repository).
    - RMT-D2  "Date Installed" is the winning device's own installed_at;
      None when that device never had one set — never invented.
    - Scope intersection is delegated entirely to the repository's ANDed
      filters, identical to installed_rtls_rows/rtl_alarms_30d_rows.
    """
    try:
        records = repo.max_temperature_report_rows(
            temperature_metric=ATTRIBUTION_METRIC_KEY,
            since=since,
            until=until,
            plant_id=plant_id,
            transformer_id=transformer_id,
            device_id=device_id,
            allowed_device_ids=device_scope.device_ids,
        )
    except Exception as exc:
        logger.exception("Failed to build Maximum Temperature report rows")
        raise ReportError(
            "The Maximum Temperature report could not be loaded. "
            "Please try again."
        ) from exc

    return [
        MaxTemperatureRow(
            ou=None,
            zone=None,
            sector=None,
            cnc=None,
            feeder_name=None,
            transformer=r.transformer_code,
            date_installed=r.installed_at,
            max_temperature_at=r.max_reading_at,
            max_temperature=r.max_temperature,
        )
        for r in records
    ]
