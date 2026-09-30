"""Factual RTL dashboard (FACTUAL-DASHBOARD-01).

Aggregates two existing factual services and nothing else: ``rtl_fleet_service``
(registered directory, temperature facts) and ``rtl_network_service`` (current
mapping, hierarchy, supporting-source disagreement). No SQL here, no counting
rule of its own beyond ``max`` over reading times, and no communication or
alarm state - there is no approved rule for either.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from services import rtl_network_service as network
from services.rtl_fleet_service import FleetStatus, FleetSummary, RealFleet, get_real_fleet
from services.rtl_network_service import CurrentNetwork, NetworkStatus, NetworkSummary
from services.rtl_scope import RtlScope, UNRESTRICTED

__all__ = ["DashboardStatus", "RTLDashboard", "get_dashboard", "may_view_dashboard"]

may_view_dashboard = network.may_view_real_fleet


class DashboardStatus(str, Enum):
    DATA = "data"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class RTLDashboard:
    status: DashboardStatus
    fleet: FleetSummary | None = None
    network: NetworkSummary | None = None
    latest_reading: datetime | None = None
    by_zone: tuple[tuple[str, int], ...] = ()


def get_dashboard(*, fleet_fetch=get_real_fleet,
                  network_fetch=network.get_current_network,
                  scope: RtlScope = UNRESTRICTED) -> RTLDashboard:
    """One fleet snapshot and one network snapshot; either failing hides both.

    Showing half a dashboard would let two sets of counts disagree on screen.
    Both snapshots are built for the same ``scope`` (ADR-032), so a Technician's
    counts are over their assigned RTLs only.
    """
    fleet: RealFleet = fleet_fetch(scope=scope)
    if fleet.status is not FleetStatus.DATA or fleet.summary is None:
        return RTLDashboard(DashboardStatus.UNAVAILABLE)
    current: CurrentNetwork = network_fetch(scope=scope)
    if current.status is not NetworkStatus.DATA:
        return RTLDashboard(DashboardStatus.UNAVAILABLE)
    times = [r.last_reported for r in fleet.rows if r.last_reported is not None]
    return RTLDashboard(
        DashboardStatus.DATA,
        fleet=fleet.summary,
        network=network.summarise(current.rows),
        latest_reading=max(times) if times else None,
        by_zone=network.level_breakdown(current.rows, "zone"),
    )
