"""
Seed script for the multi-plant monitoring demo (monitoring.plants /
monitoring.readings).

Plant identities (name, country, lat/long, capacity, fuel) come from the
Kaggle "Global Power Plant Database" (WRI) - see db/seed_data/plants.json,
baked in as static data so the app has no runtime dependency on
kagglehub/pandas. Temperature readings are synthetic: same approach as
db/seed.py (daily cycle + noise + occasional warning spikes), but the
base temperature also varies with each plant's latitude so hotter/colder
climates look distinct on the chart.

This is demo data standing in for the client's real multi-plant readings
pending their DB consolidation - see PROJECT memory / conversation for
context, not to be confused with production data.

Run:
    python -m db.seed_multi_plant            # seed if empty
    python -m db.seed_multi_plant --reset     # drop & recreate rows, then reseed
"""
from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

from db.engine import session_scope

RANDOM_SEED = 42
DAYS_OF_HISTORY = 30
INTERVAL_MINUTES = 30
NOISE_STD_C = 1.2
WARNING_SPIKE_COUNT_PER_PLANT = 2
WARNING_SPIKE_MIN_C = 46.0
WARNING_SPIKE_MAX_C = 52.0
METRIC = "temperature"

SCHEMA = "monitoring"
PLANTS_TABLE = "plants"
READINGS_TABLE = "readings"

PLANTS_FILE = Path(__file__).parent / "seed_data" / "plants.json"


def _load_plants() -> list[dict]:
    with open(PLANTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _format_timestamp(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc)


def _base_temp_for_latitude(latitude: float) -> float:
    """Warmer near the equator, cooler at high latitudes - loose climate model."""
    return 34.0 - (abs(latitude) / 90.0) * 18.0


def _generate_readings_for_plant(plant: dict, rng: random.Random) -> list[tuple[datetime, float]]:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    now = now - timedelta(minutes=now.minute % INTERVAL_MINUTES, seconds=0, microseconds=0)
    start = now - timedelta(days=DAYS_OF_HISTORY)

    total_steps = int((now - start).total_seconds() // (INTERVAL_MINUTES * 60)) + 1
    timestamps = [start + timedelta(minutes=INTERVAL_MINUTES * i) for i in range(total_steps)]

    base_temp = _base_temp_for_latitude(plant["latitude"]) + rng.uniform(-2.0, 2.0)
    daily_swing = 5.0 + rng.uniform(-1.0, 1.0)

    readings: list[tuple[datetime, float]] = []
    for ts in timestamps:
        hour_fraction = ts.hour + ts.minute / 60.0
        daily_component = daily_swing * math.sin((hour_fraction - 6) / 24.0 * 2 * math.pi)
        noise = rng.gauss(0, NOISE_STD_C)
        temp = base_temp + daily_component + noise
        readings.append((ts, temp))

    spike_indices = rng.sample(
        range(len(readings)), min(WARNING_SPIKE_COUNT_PER_PLANT, len(readings))
    )
    for idx in spike_indices:
        ts, _ = readings[idx]
        spike_temp = rng.uniform(WARNING_SPIKE_MIN_C, WARNING_SPIKE_MAX_C)
        readings[idx] = (ts, spike_temp)

    return readings


def seed(reset: bool = False) -> int:
    """Seed plants + readings. Returns number of reading rows inserted."""
    plants = _load_plants()
    rng = random.Random(RANDOM_SEED)

    with session_scope() as session:
        if reset:
            session.execute(text(f"DELETE FROM {SCHEMA}.{READINGS_TABLE}"))
            session.execute(text(f"DELETE FROM {SCHEMA}.{PLANTS_TABLE}"))

        existing_count = session.execute(
            text(f"SELECT COUNT(*) FROM {SCHEMA}.{READINGS_TABLE}")
        ).scalar_one()

        if existing_count > 0 and not reset:
            print(
                f"Table {SCHEMA}.{READINGS_TABLE} already has {existing_count} rows; "
                "skipping seed. Use --reset to reseed."
            )
            return 0

        session.execute(
            text(
                f"""
                INSERT INTO {SCHEMA}.{PLANTS_TABLE}
                    (plant_id, name, country, latitude, longitude,
                     capacity_mw, primary_fuel, transformer, device)
                VALUES
                    (:plant_id, :name, :country, :latitude, :longitude,
                     :capacity_mw, :primary_fuel, :transformer, :device)
                ON CONFLICT (plant_id) DO NOTHING
                """
            ),
            plants,
        )

        total_rows = 0
        for plant in plants:
            plant_rng = random.Random(rng.random())
            readings = _generate_readings_for_plant(plant, plant_rng)
            rows = [
                {
                    "plant_id": plant["plant_id"],
                    "transformer": plant["transformer"],
                    "device": plant["device"],
                    "metric": METRIC,
                    "reading_ts": _format_timestamp(ts),
                    "value": round(temp, 2),
                }
                for ts, temp in readings
            ]
            session.execute(
                text(
                    f"""
                    INSERT INTO {SCHEMA}.{READINGS_TABLE}
                        (plant_id, transformer, device, metric, reading_ts, value)
                    VALUES
                        (:plant_id, :transformer, :device, :metric, :reading_ts, :value)
                    ON CONFLICT (plant_id, metric, reading_ts) DO NOTHING
                    """
                ),
                rows,
            )
            total_rows += len(rows)

    print(f"Inserted {len(plants)} plants and {total_rows} readings into {SCHEMA}.{READINGS_TABLE}.")
    return total_rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed multi-plant monitoring demo data.")
    parser.add_argument(
        "--reset", action="store_true", help="Delete existing rows before reseeding."
    )
    args = parser.parse_args()
    seed(reset=args.reset)
