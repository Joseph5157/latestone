"""
Seed the plant_monitoring schema with synthetic development data.

SYNTHETIC DEVELOPMENT DATA. Plants are real (Kaggle/WRI), but transformers,
devices, and all 8 metric time series are generated. This script is NOT a
production data loader.

Usage:
    python -m db.seed_plant_monitoring [--reset]
    python -m db.seed_plant_monitoring --purge --yes-destroy-operational-history

--reset  Replace the synthetic READINGS and nothing else. The hierarchy is
         reconciled in place (every insert below is ON CONFLICT DO NOTHING and
         build_hierarchy is deterministic), and events, assignments, active
         state, programming requests, the audit log and users are all
         preserved. Without --reset, seeding is skipped when readings already
         exist. See ADR-010.

--purge  The destructive teardown, deliberately NOT part of --reset. Deletes
         the hierarchy and every dependent domain in FK-safe order, after
         reporting what it will destroy, and refuses without a second
         acknowledgement. It used to be what --reset did, which is the defect
         SEED-RESET-1 records: a command named "reset" attempting a
         demolition, and failing on a foreign key while doing it.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import psycopg2
from sqlalchemy import text

from config.metrics import ordered_metrics
from config.settings import database, monitoring
from db.engine import get_engine, session_scope
from db.generators import (
    DAYS_OF_HISTORY,
    build_timestamps,
    generate_device_series,
    registration_timestamp,
)
from db.hierarchy import build_hierarchy

SEED_DATA_DIR = Path(__file__).parent / "seed_data"
PLANTS_FILE = SEED_DATA_DIR / "plants.json"


def _load_plants() -> list[dict]:
    with open(PLANTS_FILE, encoding="utf-8") as f:
        return json.load(f)


#: What a RESET replaces. Exactly one table, and that is the whole decision
#: (ADR-010 D1). The monitoring seed owns MEASUREMENTS; it does not own the
#: record of what people and devices did.
RESET_REPLACES = ("readings",)

#: What a reset PRESERVES, named individually rather than as "everything
#: else" — a contract that lists nothing cannot be checked (ADR-010 D2).
#: A test asserts this covers every table in the schema.
RESET_PRESERVES = (
    "plants",
    "transformers",
    "devices",
    "device_events",
    "user_device_assignments",
    "rtl_active_state",
    "rtl_programming_requests",
    "rtl_commands",
    "audit_log",
    "message_forwarding",
    "users",
    # Administrator-set configuration (migrations 010/011/012). A reseed of
    # synthetic telemetry is not a reason to forget a configured cutoff
    # override, temperature threshold, or recorded vibration contract
    # answer — and none of them is measurement data this seed owns. They
    # were added by three consecutive migrations without being classified
    # here; the reset never touched them (RESET_REPLACES is readings only),
    # so behaviour was always correct, but this contract did not say so.
    "forwarding_auto_disable_override",
    "temperature_threshold_config",
    "vibration_contract_answers",
)

#: FK-safe deletion order for the DESTRUCTIVE teardown only (ADR-010 D3).
#: Children before parents, derived from the live `information_schema`
#: inventory in ADR-010 — every constraint in this schema is NO ACTION, so
#: nothing is removed implicitly and this order is the whole safety story.
#: A test walks the real schema and fails if a new table lands outside it.
PURGE_ORDER = (
    "readings",
    "device_events",
    "rtl_active_state",
    "user_device_assignments",
    "rtl_commands",
    "rtl_programming_requests",
    "devices",
    "transformers",
    "plants",
)

#: Domains --purge destroys that NOTHING can rebuild. Named so the operator
#: reads them before the prompt, not after the deletion.
PURGE_DESTROYS_IRRECOVERABLY = (
    "device_events",
    "user_device_assignments",
    "rtl_active_state",
    "rtl_programming_requests",
    "rtl_commands",
)


def _reset_measurements(schema: str) -> int:
    """Replace the synthetic measurements. Nothing else is touched.

    Deleting the hierarchy here is what used to break: four tables added by
    later work reference `devices`, every constraint is NO ACTION, and none
    of them was cleared first — so `--reset` failed outright on any database
    that had registered an RTL or run the event seed (SEED-RESET-1).

    Removing those deletes loses nothing, which is the part worth stating.
    All three hierarchy inserts below are already `ON CONFLICT DO NOTHING`
    and `build_hierarchy` is stable regardless of input ordering, so the same
    30/71/120 rows with the same ids are produced on every run. Re-inserting
    over an existing hierarchy was already a no-op; deleting it first was
    only ever a way to make that no-op look like work.
    """
    with session_scope() as session:
        result = session.execute(text(f"DELETE FROM {schema}.readings"))
        removed = result.rowcount or 0
    print(f"  Reset: {removed} reading(s) replaced. Hierarchy and operational")
    print("  history (events, assignments, active state, requests) preserved.")
    return removed


def _table_counts(schema: str, tables) -> dict:
    with session_scope() as session:
        return {
            table: int(
                session.execute(
                    text(f"SELECT COUNT(*) FROM {schema}.{table}")
                ).scalar_one()
            )
            for table in tables
        }


def purge(schema: str, *, acknowledged: bool = False) -> bool:
    """The destructive teardown, separate from `--reset` on purpose.

    Hiding this inside `--reset` is what produced SEED-RESET-1: a command
    whose name promised a refresh quietly attempted a demolition. It now
    states what it is about to destroy, with counts, and refuses without a
    second explicit acknowledgement.

    No CASCADE, here or on the constraints (ADR-010 D4). Cascading would make
    the delete succeed while silently taking audit and assignment history
    with it — the same defect wearing the fix's clothes, and harder to spot
    because the error message disappears.
    """
    counts = _table_counts(schema, PURGE_ORDER)
    print("PURGE will permanently delete:")
    for table in PURGE_ORDER:
        note = (
            "  <- cannot be rebuilt by any seed"
            if table in PURGE_DESTROYS_IRRECOVERABLY
            else ""
        )
        print(f"  {counts[table]:>9,} rows  {schema}.{table}{note}")

    if not acknowledged:
        print(
            "\nRefused. Re-run with --purge --yes-destroy-operational-history "
            "if that is genuinely what you want.\n"
            "To refresh measurements instead, use --reset."
        )
        return False

    with session_scope() as session:
        for table in PURGE_ORDER:
            session.execute(text(f"DELETE FROM {schema}.{table}"))
    print("\n  Purge complete.")
    return True


def _seed_readings_bulk(
    device_ids: list[str],
    plant_latitudes: dict[str, float],
    timestamps: list[datetime],
    schema: str,
    engine,
) -> int:
    """Bulk-load readings via psycopg2 COPY. Returns total row count."""
    total_rows = 0
    interval_minutes = 30  # matches generators.INTERVAL_MINUTES

    # Get the raw psycopg2 connection from SQLAlchemy
    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()

        for device_id in device_ids:
            # Extract plant_id from device_id (format: plant-XX-tY-dZ)
            plant_id = device_id.split("-t")[0]
            latitude = plant_latitudes[plant_id]

            series = generate_device_series(device_id, latitude, timestamps)

            # Build CSV rows: device_id, metric, reading_ts, value
            rows = []
            for metric_key, values in series.items():
                for ts, val in zip(timestamps, values):
                    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S%z")
                    rows.append(f"{device_id},{metric_key},{ts_str},{val}")

            # Use COPY for bulk insert
            copy_sql = f"""
                COPY {schema}.readings (device_id, metric, reading_ts, value)
                FROM STDIN WITH (FORMAT csv)
            """
            cursor.copy_expert(copy_sql, __import__("io").StringIO("\n".join(rows)))
            total_rows += len(rows)

            if total_rows % 100000 == 0:
                print(f"  ... {total_rows:,} rows loaded")

        raw_conn.commit()
    finally:
        raw_conn.close()

    return total_rows


class SeedState(str, Enum):
    EMPTY = "empty"
    PARTIAL = "partial"
    COMPLETE = "complete"


def evaluate_seed_state(pairs_with_readings: int, expected_pairs: int) -> SeedState:
    """Classify the dataset from its (device, metric) coverage.

    "Any reading exists" was the previous test, which reported a seed that died
    partway through the device loop as finished — so every later run skipped,
    preserving the incomplete data.

    `expected_pairs == 0` means there are no devices to cover, which is an empty
    database rather than a completed seed of nothing.
    """
    if pairs_with_readings <= 0 or expected_pairs <= 0:
        return SeedState.EMPTY
    if pairs_with_readings != expected_pairs:
        return SeedState.PARTIAL
    return SeedState.COMPLETE


def _measure_seed_state(schema: str) -> tuple[SeedState, int, int]:
    """(state, pairs_with_readings, expected_pairs) read from the database."""
    metric_count = len(ordered_metrics())
    with session_scope() as session:
        device_count = session.execute(
            text(f"SELECT COUNT(*) FROM {schema}.devices")
        ).scalar() or 0
        pairs = session.execute(
            text(f"SELECT COUNT(*) FROM (SELECT DISTINCT device_id, metric FROM {schema}.readings) p")
        ).scalar() or 0

    expected = device_count * metric_count
    return evaluate_seed_state(pairs, expected), pairs, expected


def seed(*, reset: bool = False) -> None:
    """Main seed orchestration."""
    schema = monitoring.schema
    engine = get_engine()

    print(f"Schema: {schema}")
    print(f"Database: {database.db}@{database.host}:{database.port}")

    # Check what is already there. A partial dataset must not be mistaken for a
    # finished one — that is how an interrupted seed used to survive every
    # subsequent run.
    if not reset:
        state, pairs, expected = _measure_seed_state(schema)
        if state is SeedState.COMPLETE:
            print(f"Readings already exist ({pairs}/{expected} device-metric pairs).")
            print("Use --reset to reseed.")
            return
        if state is SeedState.PARTIAL:
            print(
                f"Incomplete dataset: {pairs}/{expected} device-metric pairs have "
                "readings.\nA previous seed did not finish. Re-run with --reset "
                "to rebuild it."
            )
            sys.exit(1)

    if reset:
        print("Resetting measurements...")
        _reset_measurements(schema)

    # Load plants
    plants = _load_plants()
    plant_ids = [p["plant_id"] for p in plants]
    countries = {p["plant_id"]: p["country"] for p in plants}
    plant_latitudes = {p["plant_id"]: p["latitude"] for p in plants}

    # Build hierarchy
    transformers, devices = build_hierarchy(plant_ids, countries)
    device_ids = [d.device_id for d in devices]

    # One anchor for the whole seed, floored to the previous 30-minute
    # boundary. Taken here rather than beside the reading loop because device
    # registration dates are derived from it too: two `now()` calls would let
    # the registration history and the reading window disagree about when
    # "now" was, and a device could be registered after its own last reading.
    anchor = datetime.now(timezone.utc)
    minute_floor = (anchor.minute // 30) * 30
    anchor = anchor.replace(minute=minute_floor, second=0, microsecond=0)

    print(f"\nPlants: {len(plants)}")
    print(f"Transformers: {len(transformers)}")
    print(f"Devices: {len(devices)}")

    # Insert plants
    print("\nSeeding plants...")
    with session_scope() as session:
        for p in plants:
            session.execute(
                text(
                    f"INSERT INTO {schema}.plants "
                    "(plant_id, name, country, latitude, longitude, capacity_mw, primary_fuel) "
                    "VALUES (:plant_id, :name, :country, :latitude, :longitude, :capacity_mw, :primary_fuel) "
                    "ON CONFLICT (plant_id) DO NOTHING"
                ),
                {
                    "plant_id": p["plant_id"],
                    "name": p["name"],
                    "country": p["country"],
                    "latitude": p["latitude"],
                    "longitude": p["longitude"],
                    "capacity_mw": p.get("capacity_mw"),
                    "primary_fuel": p.get("primary_fuel"),
                },
            )

    # Insert transformers
    print("Seeding transformers...")
    with session_scope() as session:
        for t in transformers:
            session.execute(
                text(
                    f"INSERT INTO {schema}.transformers "
                    "(transformer_id, plant_id, transformer_code) "
                    "VALUES (:transformer_id, :plant_id, :transformer_code) "
                    "ON CONFLICT (transformer_id) DO NOTHING"
                ),
                {
                    "transformer_id": t.transformer_id,
                    "plant_id": t.plant_id,
                    "transformer_code": t.transformer_code,
                },
            )

    # Insert devices
    #
    # `created_at` is set EXPLICITLY. Left to migration 002's `now()` server
    # default it made every seeded device share one registration instant, which
    # turned any registration-recency figure into the whole fleet. The dates are
    # SYNTHETIC DEVELOPMENT SEED HISTORY (see db.generators.registration_timestamp)
    # and are not client-derived registration records.
    #
    # `updated_at` is set to the same instant: a freshly seeded device has never
    # been edited, so defaulting it to `now()` would show all 120 as just-modified.
    #
    # ON CONFLICT stays DO NOTHING. Re-running the seed over an existing database
    # therefore will NOT correct rows already carrying the backfilled default —
    # that needs `--reset`. Deliberate: DO UPDATE here would also overwrite the
    # genuine registration timestamp of any device registered through the app.
    print("Seeding devices...")
    with session_scope() as session:
        for d in devices:
            registered_at = registration_timestamp(d.device_id, anchor)
            session.execute(
                text(
                    f"INSERT INTO {schema}.devices "
                    "(device_id, transformer_id, device_code, created_at, updated_at) "
                    "VALUES (:device_id, :transformer_id, :device_code, :created_at, :updated_at) "
                    "ON CONFLICT (device_id) DO NOTHING"
                ),
                {
                    "device_id": d.device_id,
                    "transformer_id": d.transformer_id,
                    "device_code": d.device_code,
                    "created_at": registered_at,
                    "updated_at": registered_at,
                },
            )

    timestamps = build_timestamps(anchor)
    print(f"\nTimestamps: {len(timestamps)} (30 days, 30-min intervals)")
    print(f"Range: {timestamps[0].isoformat()} to {timestamps[-1].isoformat()}")

    # Bulk seed readings
    print(f"\nSeeding readings ({len(device_ids)} devices × {len(timestamps)} timestamps × 8 metrics)...")
    start_time = time.time()
    total_rows = _seed_readings_bulk(device_ids, plant_latitudes, timestamps, schema, engine)
    elapsed = time.time() - start_time

    print(f"\nDone! {total_rows:,} rows loaded in {elapsed:.1f}s")
    print(f"\nSummary:")
    print(f"  Plants:       {len(plants)}")
    print(f"  Transformers: {len(transformers)}")
    print(f"  Devices:      {len(devices)}")
    print(f"  Readings:     {total_rows:,}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed plant_monitoring schema")
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Replace the synthetic readings. Hierarchy and operational "
            "history (events, assignments, active state, programming "
            "requests) are preserved."
        ),
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help=(
            "DESTRUCTIVE. Delete the hierarchy and every dependent domain. "
            "Reports what it would destroy and refuses without "
            "--yes-destroy-operational-history."
        ),
    )
    parser.add_argument(
        "--yes-destroy-operational-history",
        action="store_true",
        dest="acknowledged",
        help="Second acknowledgement required by --purge.",
    )
    args = parser.parse_args()

    if args.purge:
        # Deliberately does not fall through into a seed: a purge and a
        # rebuild are two decisions, and running them as one is how the old
        # --reset came to hide a demolition behind a refresh.
        if not purge(monitoring.schema, acknowledged=args.acknowledged):
            sys.exit(1)
        return

    seed(reset=args.reset)


if __name__ == "__main__":
    main()
