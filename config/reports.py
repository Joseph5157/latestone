"""
Report definitions — single source of truth.

Confirmed by the RTL Functional Specification (§11, doc ID 240-137264801).
Each definition specifies the exact output columns the client expects.

These are schema/layout definitions only. No data is populated here.
The backend report service, when available, must produce output matching
these column sets exactly.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    label: str
    columns: tuple[str, ...]
    date_range_fixed: str | None  # None = user-selectable, "30d" = locked to 30 days
    description: str


REPORTS: tuple[ReportDefinition, ...] = (
    ReportDefinition(
        key="rtl_alarms_30d",
        label="RTL Alarms (30 Days)",
        columns=(
            "OU",
            "Zone",
            "Sector",
            "CNC",
            "Feeder",
            "Transformer",
            "UID",
            "Battery(V)",
            "Alarm Date & Time",
            "Temperature (\u00b0C)",
            "Alarm",
            "Firmware",
        ),
        date_range_fixed="30d",
        description=(
            "Alarms triggered by RTL devices over a 30-day period. "
            "Includes temperature readings, battery voltage, and firmware version."
        ),
    ),
    ReportDefinition(
        key="installed_rtls",
        label="Installed RTLs",
        columns=(
            "OU",
            "Zone",
            "Sector",
            "CNC",
            "Feeder Name",
            "Transformer",
            "UID",
            "Timestamp of Last Recorded Data",
            "Last Recorded Temperature (\u00b0C)",
            "RTL Status",
        ),
        date_range_fixed=None,
        description=(
            "Current inventory of installed RTL devices. "
            "Asset/current-state report; date range is not mandatory."
        ),
    ),
    ReportDefinition(
        key="max_temperature",
        label="Maximum Temperature",
        columns=(
            "OU",
            "Zone",
            "Sector",
            "CNC",
            "Feeder Name",
            "Transformer",
            "Date Installed",
            "Date of Maximum Temperature",
            "Maximum Temperature (\u00b0C)",
        ),
        date_range_fixed=None,
        description=(
            "Peak temperature recorded per transformer. "
            "Reporting period defaults to a rolling 30 days, with a custom "
            "date range also available (development baseline C-15, "
            "pending client confirmation)."
        ),
    ),
)

_REPORTS_BY_KEY: dict[str, ReportDefinition] = {r.key: r for r in REPORTS}


def get_report(key: str) -> ReportDefinition | None:
    """Look up a report definition by key."""
    return _REPORTS_BY_KEY.get(key)


def report_options() -> list[dict]:
    """Dropdown options for the report-type selector."""
    return [{"label": r.label, "value": r.key} for r in REPORTS]


def all_report_keys() -> tuple[str, ...]:
    """Ordered tuple of all confirmed report keys."""
    return tuple(r.key for r in REPORTS)
