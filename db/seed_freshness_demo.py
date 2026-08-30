"""
Freshness demo seed — makes a few RTLs Stale and No Data, on purpose.

DEVELOPMENT / DEMO DATA. Nothing here comes from the client, and no RTL
actually stopped reporting. It exists because the local fleet seeds to
120/120 Fresh, which means the Command Center panels that exist to surface
exceptions have no exception to surface — Needs Attention, Affected
Locations, the transformer concentration and (from Phase 10) Priority
Investigation can all be *looked at* but not actually *seen working*.

THIS ONE DELETES READINGS. That makes it different in kind from its two
siblings, and the difference is not incidental:

    python -m db.seed_plant_monitoring --reset   writes equipment + readings
    python -m db.seed_admin_demo --reset         writes technicians
    python -m db.seed_events_demo                APPENDS events (ADR-007)
    python -m db.seed_freshness_demo --apply     REMOVES readings

Staleness and absence cannot be written. `Freshness` is `now - max(reading_ts)`
per (device, metric), and NO_DATA is the absence of any row at all
(services/monitoring_service.py:198-210). There is no value you can INSERT
that means "this feed stopped"; the only way to model a feed that stopped is
for the rows not to be there. So this seed subtracts, and says so loudly.

Consequences, stated rather than discovered:

- It is DRY-RUN BY DEFAULT. It prints the exact devices, metrics and row
  counts it would remove and changes nothing until `--apply`.
- THERE IS NO ONE-COMMAND UNDO, and pretending otherwise would be the same
  dishonesty these panels are built to avoid. Restoring the removed rows
  means a full `python -m db.seed_plant_monitoring --reset`, which rebuilds
  the hierarchy too — and its `_reset_data` deletes `devices`, which
  `device_events`, `user_device_assignments`, `rtl_active_state` and
  `rtl_programming_requests` all reference. Those must be cleared first.
  Treat applying this as a one-way local change.
- It is why this only ever touches READINGS — never a plant, transformer,
  device or event. Those are the rows that would be genuinely expensive to
  lose; synthetic telemetry for four RTLs is not.
- It is idempotent in effect, not in action: running it twice removes
  nothing new, because the rows it targets are already gone.

WHAT IT BUILDS, and why each one is here:

    1. FRESH      control — untouched, proves the others are not a global break
    2. STALE      every metric old — the plain case
    3. STALE      7 metrics fresh, 1 silent for hours — THE Phase 10 case
    4. NO_DATA    7 metrics fresh, 1 that never reported — the ADR-002 case

Target 3 is the one that matters most and the one a simpler fixture would
have missed. `device_last_updated` is a MAX across metrics, so on that RTL
it reads minutes old while the device is genuinely Stale; ranking or ageing
it on that field understates a real outage (ADR-009 D3). Without this target
the honest-minimum path exists only in tests.

Target 4 is ADR-002's rule made visible: an RTL is No Data when ANY ONE
metric has never reported, even while its other seven are fine — which is
also why no age may be shown beside it.

NEVER RUN THIS AGAINST PRODUCTION.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from config.metrics import METRIC_KEYS
from config.settings import monitoring
from db.engine import session_scope

#: How far past the staleness threshold the "plain stale" RTL is pushed.
#: Comfortably past it, so the fixture does not sit on the boundary and
#: flip state while someone is looking at the screen.
STALE_MARGIN = timedelta(hours=4)

#: The lagging metric on the mixed STALE target. Deliberately much older
#: than STALE_MARGIN so the two stale RTLs rank in a stated order and the
#: browser shows a legible "Xh Ym", not two rows that look identical.
LAGGING_AGE = timedelta(hours=9, minutes=17)


@dataclass(frozen=True)
class Target:
    """One RTL this seed shapes, and the shape it is given."""

    device_id: str
    outcome: str
    #: Metrics to touch. Empty means "every metric".
    metrics: tuple[str, ...]
    #: Delete rows NEWER than this age, leaving the older history intact.
    #: None means delete every row for the named metrics (-> NO_DATA).
    keep_older_than: timedelta | None
    why: str


#: Deliberately NOT `plant-01-t1-d1`. That id is the reserved identifier
#: (AGENTS.md scope: aa12/29017) used as a worked example throughout the
#: docs and tests, and quietly breaking its data would make every other
#: reference to it misleading.
TARGETS: tuple[Target, ...] = (
    Target(
        device_id="plant-02-t1-d1",
        outcome="FRESH (control)",
        metrics=(),
        keep_older_than=None,
        why="Untouched. If this RTL goes stale too, the cause is the clock "
            "or the simulator — not this seed.",
    ),
    Target(
        device_id="plant-03-t1-d1",
        outcome="STALE (every metric)",
        metrics=(),
        keep_older_than=STALE_MARGIN,
        why="The plain case: the whole RTL stopped delivering.",
    ),
    Target(
        device_id="plant-04-t1-d1",
        outcome="STALE (one lagging metric)",
        metrics=("voltage",),
        keep_older_than=LAGGING_AGE,
        why="ADR-009 D3: seven metrics stay fresh, so device_last_updated "
            "reads minutes old while the RTL is genuinely Stale.",
    ),
    Target(
        device_id="plant-05-t1-d1",
        outcome="NO_DATA (one metric never reported)",
        metrics=("frequency",),
        keep_older_than=None,
        why="ADR-002: any ONE metric with no reading makes the RTL No Data, "
            "even with seven healthy feeds beside it.",
    ),
)


def _validate_metrics() -> None:
    """Fail loudly if a target names a metric the registry does not have.

    A typo would otherwise delete nothing and report success, leaving a
    fixture that silently is not there.
    """
    for target in TARGETS:
        unknown = [m for m in target.metrics if m not in METRIC_KEYS]
        if unknown:
            raise SystemExit(
                f"Unknown metric(s) {unknown} on {target.device_id}. "
                f"Known metrics: {', '.join(METRIC_KEYS)}"
            )


def _plan(session, schema: str, now: datetime) -> list[tuple[Target, int]]:
    """How many rows each target would remove. Reads only."""
    plan = []
    for target in TARGETS:
        if target.keep_older_than is None and not target.metrics:
            plan.append((target, 0))  # the untouched control
            continue

        conditions = ["device_id = :device_id"]
        params: dict = {"device_id": target.device_id}
        if target.metrics:
            conditions.append("metric = ANY(:metrics)")
            params["metrics"] = list(target.metrics)
        if target.keep_older_than is not None:
            conditions.append("reading_ts > :cutoff")
            params["cutoff"] = now - target.keep_older_than

        count = session.execute(
            text(
                f"SELECT COUNT(*) FROM {schema}.readings "
                f"WHERE {' AND '.join(conditions)}"
            ),
            params,
        ).scalar_one()
        plan.append((target, int(count)))
    return plan


def _device_exists(session, schema: str, device_id: str) -> bool:
    return bool(
        session.execute(
            text(f"SELECT 1 FROM {schema}.devices WHERE device_id = :d"),
            {"d": device_id},
        ).first()
    )


def _apply(session, schema: str, now: datetime) -> int:
    removed = 0
    for target in TARGETS:
        if target.keep_older_than is None and not target.metrics:
            continue

        conditions = ["device_id = :device_id"]
        params: dict = {"device_id": target.device_id}
        if target.metrics:
            conditions.append("metric = ANY(:metrics)")
            params["metrics"] = list(target.metrics)
        if target.keep_older_than is not None:
            conditions.append("reading_ts > :cutoff")
            params["cutoff"] = now - target.keep_older_than

        result = session.execute(
            text(
                f"DELETE FROM {schema}.readings "
                f"WHERE {' AND '.join(conditions)}"
            ),
            params,
        )
        removed += result.rowcount or 0
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Make a few RTLs Stale / No Data so the exception panels have "
            "exceptions. DELETES readings. Dry-run unless --apply."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete. Without it, this only reports what it would do.",
    )
    args = parser.parse_args(argv)

    _validate_metrics()
    schema = monitoring.schema
    now = datetime.now(timezone.utc)

    with session_scope() as session:
        missing = [
            t.device_id for t in TARGETS
            if not _device_exists(session, schema, t.device_id)
        ]
        if missing:
            print(
                "Refused: these RTLs are not in the local hierarchy: "
                f"{', '.join(missing)}.\n"
                "Run `python -m db.seed_plant_monitoring --reset` first.",
                file=sys.stderr,
            )
            return 1

        plan = _plan(session, schema, now)

        print(f"Freshness demo seed · schema {schema}")
        print(f"Stale threshold is {monitoring.stale_after_minutes} minutes.\n")
        for target, count in plan:
            scope = ", ".join(target.metrics) if target.metrics else "all metrics"
            print(f"  {target.device_id}  ->  {target.outcome}")
            print(f"      {scope}: {count} reading(s) to remove")
            print(f"      {target.why}")
        total = sum(count for _, count in plan)

        if not args.apply:
            print(
                f"\nDry run. {total} reading(s) would be removed. "
                "Re-run with --apply to do it."
            )
            return 0

        if total == 0:
            print(
                "\nNothing to remove — the fixture is already in place. "
                "Re-run `python -m db.seed_plant_monitoring --reset` to undo it."
            )
            return 0

        removed = _apply(session, schema, now)

    print(f"\nRemoved {removed} reading(s).")
    print("Undo with: python -m db.seed_plant_monitoring --reset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
