"""
Seed the plant_monitoring schema with synthetic development data.

SYNTHETIC DEVELOPMENT DATA. Plants are real (Kaggle/WRI), but transformers,
devices, and all 8 metric time series are generated. This script is NOT a
production data loader.

Usage:
    python -m db.seed_plant_monitoring [--reset]

--reset  Delete all existing data (readings, devices, transformers, plants)
         before seeding. Without --reset, seeding is skipped when readings
         already exist.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from sqlalchemy import text

from config.settings import database, monitoring
from db.engine import get_engine, session_scope
from db.generators import DAYS_OF_HISTORY, build_timestamps, generate_device_series
from db.hierarchy import build_hierarchy

SEED_DATA_DIR = Path(__file__).parent / "seed_data"
PLANTS_FILE = SEED_DATA_DIR / "plants.json"


def _load_plants() -> list[dict]:
    with open(PLANTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _reset_data(schema: str) -> None:
    """Delete data in FK-safe order."""
    with session_scope() as session:
        session.execute(text(f"DELETE FROM {schema}.readings"))
        session.execute(text(f"DELETE FROM {schema}.devices"))
        session.execute(text(f"DELETE FROM {schema}.transformers"))
        session.execute(text(f"DELETE FROM {schema}.plants"))
    print("  Reset complete — all data deleted.")


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


def _check_readings_exist(schema: str) -> bool:
    """Check if readings already exist."""
    with session_scope() as session:
        result = session.execute(
            text(f"SELECT EXISTS(SELECT 1 FROM {schema}.readings LIMIT 1)")
        )
        return result.scalar()


def seed(*, reset: bool = False) -> None:
    """Main seed orchestration."""
    schema = monitoring.schema
    engine = get_engine()

    print(f"Schema: {schema}")
    print(f"Database: {database.db}@{database.host}:{database.port}")

    # Check if data already exists
    if not reset and _check_readings_exist(schema):
        print("Readings already exist. Use --reset to reseed.")
        return

    if reset:
        print("Resetting existing data...")
        _reset_data(schema)

    # Load plants
    plants = _load_plants()
    plant_ids = [p["plant_id"] for p in plants]
    countries = {p["plant_id"]: p["country"] for p in plants}
    plant_latitudes = {p["plant_id"]: p["latitude"] for p in plants}

    # Build hierarchy
    transformers, devices = build_hierarchy(plant_ids, countries)
    device_ids = [d.device_id for d in devices]

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
    print("Seeding devices...")
    with session_scope() as session:
        for d in devices:
            session.execute(
                text(
                    f"INSERT INTO {schema}.devices "
                    "(device_id, transformer_id, device_code) "
                    "VALUES (:device_id, :transformer_id, :device_code) "
                    "ON CONFLICT (device_id) DO NOTHING"
                ),
                {
                    "device_id": d.device_id,
                    "transformer_id": d.transformer_id,
                    "device_code": d.device_code,
                },
            )

    # Generate timestamps
    anchor = datetime.now(timezone.utc)
    # Floor to previous 30-minute boundary
    minute_floor = (anchor.minute // 30) * 30
    anchor = anchor.replace(minute=minute_floor, second=0, microsecond=0)
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
    parser.add_argument("--reset", action="store_true", help="Delete existing data before seeding")
    args = parser.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
