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
