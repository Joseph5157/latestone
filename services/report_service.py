"""Installed RTLs report — the first data-backed report (REPORT-2).

Thin service boundary between callbacks/report_center.py and
repositories/plant_monitoring_repository.py. The callback must not call the
repository directly.

Frozen REPORT-2 decisions (see REPORT-2_PLANNING_PROMPT.md and the reviewer
adjustments R2-D1..D7):

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
from datetime import datetime

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
