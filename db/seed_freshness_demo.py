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
- IT IS REVERSIBLE (ADR-010 D5). Before deleting anything it CAPTURES the
  exact rows it is about to remove, and `--restore` puts them back. The
  capture is written and read back before a single row is deleted, so a
  crash between the two leaves the database untouched.
- Restore inserts with `ON CONFLICT DO NOTHING`, which the
  `UNIQUE (device_id, metric, reading_ts)` constraint makes exactly
  idempotent: a half-finished apply and a repeated restore both converge on
  the original state rather than duplicating rows.
- `--apply` refuses while a capture exists, so the pristine copy can never
  be overwritten by a second run.
- It only ever touches READINGS - never a plant, transformer, device or
  event. Those are the rows that would be genuinely expensive to lose.
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
import json
import pathlib
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from config.metrics import METRIC_KEYS
from config.settings import monitoring
from db.engine import session_scope

#: Where the captured rows live while the demo is applied.
#:
#: A FILE, not a table. The capture is a developer-tool artifact with the
#: lifetime of one demo, and Alembic is the sole authority on this schema
#: (AGENTS.md rule 9) - adding a domain table so a demo script can undo
#: itself would put a dev convenience in the client's data model forever.
#: Gitignored: it holds a snapshot of local synthetic readings, and its
#: presence is what "the demo is currently applied" means.
CAPTURE_PATH = pathlib.Path(".freshness-demo-capture.json")

#: How far past the staleness threshold the "plain stale" RTL is pushed.
#: Comfortably past it, so the fixture does not sit on the boundary and
#: flip state while someone is looking at the screen.
STALE_MARGIN = timedelta(hours=28)

#: The lagging metric on the mixed STALE target. Deliberately much older
#: than STALE_MARGIN so the two stale RTLs rank in a stated order and the
#: browser shows a legible different age, not two rows that look identical.
LAGGING_AGE = timedelta(hours=33, minutes=17)


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


def _matching_rows(session, schema: str, target, now: datetime):
    """Every reading this target would remove. Reads only.

    One place builds the predicate for counting, capturing and deleting, so
    the three can never disagree about which rows are in scope - a capture
    that covered a different set than the delete would restore the wrong
    thing, silently.
    """
    conditions = ["device_id = :device_id"]
    params: dict = {"device_id": target.device_id}
    if target.metrics:
        conditions.append("metric = ANY(:metrics)")
        params["metrics"] = list(target.metrics)
    if target.keep_older_than is not None:
        conditions.append("reading_ts > :cutoff")
        params["cutoff"] = now - target.keep_older_than
    return " AND ".join(conditions), params


def _capture(session, schema: str, now: datetime) -> list[dict]:
    """The exact rows about to be deleted, as plain data.

    Values are strings: `NUMERIC` round-trips through `Decimal`, and a float
    would quietly re-insert a different number than it removed.
    """
    captured = []
    for target in TARGETS:
        if target.keep_older_than is None and not target.metrics:
            continue
        where, params = _matching_rows(session, schema, target, now)
        rows = session.execute(
            text(
                f"SELECT device_id, metric, reading_ts, value "
                f"FROM {schema}.readings WHERE {where}"
            ),
            params,
        ).fetchall()
        for row in rows:
            captured.append(
                {
                    "device_id": row.device_id,
                    "metric": row.metric,
                    "reading_ts": row.reading_ts.isoformat(),
                    "value": str(row.value),
                }
            )
    return captured


def _write_capture(rows: list[dict]) -> int:
    """Write, then read back, BEFORE anything is deleted.

    The read-back is the point: an unwritable disk or a truncated write must
    fail while the database is still intact, not after the rows are gone.
    """
    CAPTURE_PATH.write_text(json.dumps(rows), encoding="utf-8")
    verified = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
    if len(verified) != len(rows):
        raise SystemExit(
            f"Capture verification failed: wrote {len(rows)} rows, read back "
            f"{len(verified)}. Nothing has been deleted."
        )
    return len(verified)


def _restore(session, schema: str, rows: list[dict]) -> int:
    """Put the captured readings back, exactly.

    `ON CONFLICT DO NOTHING` against `UNIQUE (device_id, metric, reading_ts)`
    makes this idempotent, so restoring twice - or restoring after an apply
    that failed partway - converges on the original state instead of
    duplicating or erroring.
    """
    restored = 0
    for row in rows:
        result = session.execute(
            text(
                f"INSERT INTO {schema}.readings "
                "(device_id, metric, reading_ts, value) "
                "VALUES (:device_id, :metric, :reading_ts, :value) "
                "ON CONFLICT (device_id, metric, reading_ts) DO NOTHING"
            ),
            row,
        )
        restored += result.rowcount or 0
    return restored



def _plan(session, schema: str, now: datetime) -> list[tuple[Target, int]]:
    """How many rows each target would remove. Reads only."""
    plan = []
    for target in TARGETS:
        if target.keep_older_than is None and not target.metrics:
            plan.append((target, 0))  # the untouched control
            continue

        where, params = _matching_rows(session, schema, target, now)
        count = session.execute(
            text(f"SELECT COUNT(*) FROM {schema}.readings WHERE {where}"),
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

        where, params = _matching_rows(session, schema, target, now)
        result = session.execute(
            text(f"DELETE FROM {schema}.readings WHERE {where}"),
            params,
        )
        removed += result.rowcount or 0
    return removed


def _restore_command(schema: str) -> int:
    """Put the captured readings back and drop the capture.

    Runs before any of the target/plan machinery: restoring is about the
    capture file, not about what the targets would select now. Deriving the
    rows to restore from the CURRENT time would restore a different set than
    was removed, which is the whole failure mode capturing exists to avoid.
    """
    if not CAPTURE_PATH.exists():
        print(
            "Nothing to restore: no capture file. The demo is not applied.",
            file=sys.stderr,
        )
        return 1

    rows = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
    with session_scope() as session:
        restored = _restore(session, schema, rows)

    # Only after the database is confirmed updated. A capture removed before
    # the insert commits would leave the rows unrecoverable.
    CAPTURE_PATH.unlink()
    print(f"Restored {restored} of {len(rows)} captured reading(s).")
    if restored != len(rows):
        print(
            f"  {len(rows) - restored} were already present — expected when a "
            "previous restore was interrupted, since the insert is idempotent."
        )
    print("The database is back to its pre-demo state.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Make a few RTLs Stale / No Data so the exception panels have "
            "exceptions. Deletes readings, after capturing them. Dry-run "
            "unless --apply; reversible with --restore."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Capture the affected readings, then delete them.",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Put the captured readings back and remove the capture.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Report whether the demo is currently applied.",
    )
    args = parser.parse_args(argv)

    _validate_metrics()
    schema = monitoring.schema
    now = datetime.now(timezone.utc)

    if args.status:
        if CAPTURE_PATH.exists():
            rows = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
            print(f"APPLIED — {len(rows)} reading(s) captured in {CAPTURE_PATH}.")
            print("Undo with: python -m db.seed_freshness_demo --restore")
        else:
            print("NOT APPLIED — no capture file.")
        return 0

    if args.restore:
        return _restore_command(schema)

    with session_scope() as session:
        missing = [
            t.device_id for t in TARGETS
            if not _device_exists(session, schema, t.device_id)
        ]
        if missing:
            print(
                "Refused: these RTLs are not in the local hierarchy: "
                f"{', '.join(missing)}.\n"
                "Run `python -m db.seed_plant_monitoring` first.",
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
                "Re-run with --apply to capture and remove them."
            )
            return 0

        # Refused rather than merged: a second apply would overwrite the
        # pristine capture with one taken from an already-modified database,
        # and the original readings would be unrecoverable.
        if CAPTURE_PATH.exists():
            print(
                f"\nRefused: {CAPTURE_PATH} already exists, so the demo is "
                "already applied.\nRestore first: "
                "python -m db.seed_freshness_demo --restore",
                file=sys.stderr,
            )
            return 1

        if total == 0:
            print("\nNothing to remove — the fixture is already in place.")
            return 0

        # Capture and verify BEFORE deleting. A crash between the two leaves
        # the database untouched, which is the safe direction to fail in.
        captured = _capture(session, schema, now)
        written = _write_capture(captured)
        print(f"\nCaptured {written} reading(s) to {CAPTURE_PATH}.")

        removed = _apply(session, schema, now)

    print(f"Removed {removed} reading(s).")
    print("Undo with: python -m db.seed_freshness_demo --restore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
