"""
Administration summary — the operational counterpart to fleet monitoring.

Answers "how is the fleet *administered*": how many RTLs have a technician,
how many do not, how many technicians are available, and what was registered
recently. Deliberately separate from `monitoring_service`, which answers "how
is the fleet *reporting*". The two axes must not be merged — an unassigned
RTL is not an unhealthy one, and a stale RTL is not an unassigned one.

This service therefore computes no freshness and holds no `FleetHealth`. The
Fleet Overview already builds that once per render from a single query; a
callback wanting both puts them side by side rather than asking this module
to recompute a second opinion.

POPULATION. Every figure here counts **Managed RTLs** — administratively
active devices, regardless of their transformer's status. The Fleet
Overview's own device count is **Monitoring Devices** — active devices under
active transformers. The difference is deliberate: administration answers
"what do we manage", monitoring answers "what reports", and an RTL under a
decommissioned transformer belongs to the first but not the second.

A screen showing both must therefore label them, not reconcile them. Two
numbers that differ are not a bug here, and making them match by quietly
swapping a population would be. Today they happen to be equal (nothing in
the development data is deactivated), which is exactly when the mistake is
easiest to make.

ADMIN-1 scope: data/service contracts only. Nothing here renders, and no
page consumes it yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import AdminDeviceRow

#: How far back "recently registered" reaches, as a duration rather than a
#: number of days, so the window is exact: 7 x 24 hours before the reference
#: instant, never "the last seven calendar days" (which would depend on a
#: timezone this service does not have).
#:
#: DEVELOPMENT VALUE. No client rule defines a registration-recency window;
#: seven days matches the reporting cadence the Functional Specification uses
#: elsewhere and is a placeholder until confirmed.
RECENT_REGISTRATION_WINDOW: timedelta = timedelta(days=7)

#: How many unassigned RTLs the summary carries. The overview shows an
#: exception sample, not an inventory — the full list belongs on Device
#: Management, which already renders every device.
DEFAULT_UNASSIGNED_ROW_LIMIT: int = 5


@dataclass(frozen=True)
class AdminOverviewSummary:
    """One render's administration figures, over the Managed RTL population.

    `total_devices` is the count of Managed RTLs. It is NOT interchangeable
    with the Fleet Overview's device count, which covers Monitoring Devices —
    see this module's docstring.

    `unassigned_rows` is a tuple, not a list: the whole point of this
    contract is that a caller reads it and cannot quietly reshape what a
    later component will render.

    Every row in `unassigned_rows` is by definition unassigned — there is no
    technician field, because on this list it would always be None.
    `unassigned_rows` is a capped sample of `unassigned_devices`, so the two
    are equal only when the count fits under the limit.
    """

    total_devices: int
    assigned_devices: int
    unassigned_devices: int
    active_technicians: int
    recently_registered_devices: int
    unassigned_rows: tuple[AdminDeviceRow, ...]


def _now() -> datetime:
    """Indirection so tests can pin the clock — same convention as
    `monitoring_service._now`."""
    return datetime.now(timezone.utc)


def registration_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """The closed `[start, end]` interval "recently registered" covers.

    Split out from `get_admin_overview` so the policy is testable without a
    database, and so one reference instant produces both bounds. Reading the
    clock twice — once per bound — would let a window drift mid-computation.
    """
    reference = now or _now()
    return reference - RECENT_REGISTRATION_WINDOW, reference


def get_admin_overview(
    now: datetime | None = None,
    unassigned_limit: int | None = DEFAULT_UNASSIGNED_ROW_LIMIT,
    include_inactive: bool = False,
) -> AdminOverviewSummary:
    """Build the administration summary from four aggregate queries.

    `now` is threaded through so one render evaluates the registration window
    against a single instant, the same discipline `get_fleet_health` applies
    to freshness.

    `include_inactive` follows `hierarchy_service`'s convention: active-only
    by default, so these figures describe exactly the Managed RTL population
    the Device Management table lists. Setting it True widens to every device
    on record, which is a third population again — useful for an audit view,
    never for a headline figure.

    Four queries, never one per device: the counts are aggregates and the
    exception list is a single limited anti-join.

    Returns whatever is true. A fleet with no technicians and no assignments
    reports zero assigned and every device unassigned rather than anything
    more flattering.
    """
    start, end = registration_window(now)

    counts = repo.count_device_assignments(include_inactive=include_inactive)
    active_technicians = repo.count_active_technicians()
    recently_registered = repo.count_devices_registered_between(
        start, end, include_inactive=include_inactive
    )
    unassigned_rows = repo.list_unassigned_devices(
        limit=unassigned_limit, include_inactive=include_inactive
    )

    return AdminOverviewSummary(
        total_devices=counts.total_devices,
        assigned_devices=counts.assigned_devices,
        unassigned_devices=counts.unassigned_devices,
        active_technicians=active_technicians,
        recently_registered_devices=recently_registered,
        unassigned_rows=tuple(unassigned_rows),
    )
