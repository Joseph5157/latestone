"""
Seed script for local demo data.

Generates ~30 days of temperature readings at ~30-minute intervals for
trfr_temperature.aa12_29017, with realistic gradual/daily variation and a
few deliberately high values to demonstrate the warning state.

ASSUMPTION (flagged, not confirmed by client): timestamp string format is
interpreted as `YY/MM/DD,HH:MM` (17 chars), e.g. "26/08/01,00:00". This
matches the client's observed examples but must be confirmed before
production integration - see DATABASE.md.

Run:
    python -m db.seed            # seed if empty
    python -m db.seed --reset    # drop & recreate rows, then reseed
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timedelta

from sqlalchemy import text

from db.engine import session_scope

RANDOM_SEED = 42
DAYS_OF_HISTORY = 30
INTERVAL_MINUTES = 30
BASE_TEMP_C = 32.0
DAILY_SWING_C = 6.0        # day/night variation
NOISE_STD_C = 1.2
WARNING_SPIKE_COUNT = 6    # number of deliberately high readings
WARNING_SPIKE_MIN_C = 46.0
WARNING_SPIKE_MAX_C = 52.0

SCHEMA = "trfr_temperature"
TABLE = "aa12_29017"


def _format_timestamp(dt: datetime) -> str:
    """YY/MM/DD,HH:MM - 17 characters, matches VARCHAR(17) column."""
    return dt.strftime("%y/%m/%d,%H:%M")


def _generate_readings() -> list[tuple[str, str]]:
    rng = random.Random(RANDOM_SEED)

    now = datetime.now().replace(second=0, microsecond=0)
    # align to the nearest interval boundary
    now = now - timedelta(
        minutes=now.minute % INTERVAL_MINUTES, seconds=0, microseconds=0
    )
    start = now - timedelta(days=DAYS_OF_HISTORY)

    total_steps = int((now - start).total_seconds() // (INTERVAL_MINUTES * 60)) + 1
    timestamps = [start + timedelta(minutes=INTERVAL_MINUTES * i) for i in range(total_steps)]

    readings: list[tuple[str, str]] = []
    for ts in timestamps:
        hour_fraction = ts.hour + ts.minute / 60.0
        # smooth daily cycle, peak mid-afternoon
        daily_component = DAILY_SWING_C * math.sin(
            (hour_fraction - 6) / 24.0 * 2 * math.pi
        )
        noise = rng.gauss(0, NOISE_STD_C)
        temp = BASE_TEMP_C + daily_component + noise
        readings.append((ts, temp))

    # inject a small number of deliberate warning spikes, spread across history
    spike_indices = rng.sample(range(len(readings)), min(WARNING_SPIKE_COUNT, len(readings)))
    for idx in spike_indices:
        ts, _ = readings[idx]
        spike_temp = rng.uniform(WARNING_SPIKE_MIN_C, WARNING_SPIKE_MAX_C)
        readings[idx] = (ts, spike_temp)

    return [
        (_format_timestamp(ts), f"{temp:.1f}"[:4])
        for ts, temp in readings
    ]


def seed(reset: bool = False) -> int:
    """Seed the demo table. Returns number of rows inserted."""
    rows = _generate_readings()

    with session_scope() as session:
        if reset:
            session.execute(text(f'DELETE FROM {SCHEMA}."{TABLE}"'))

        existing_count = session.execute(
            text(f'SELECT COUNT(*) FROM {SCHEMA}."{TABLE}"')
        ).scalar_one()

        if existing_count > 0 and not reset:
            print(
                f"Table {SCHEMA}.{TABLE} already has {existing_count} rows; "
                "skipping seed. Use --reset to reseed."
            )
            return 0

        session.execute(
            text(
                f'INSERT INTO {SCHEMA}."{TABLE}" ("timestamp", temperature) '
                f'VALUES (:ts, :temp) ON CONFLICT ("timestamp") DO NOTHING'
            ),
            [{"ts": ts, "temp": temp} for ts, temp in rows],
        )

    print(f"Inserted {len(rows)} readings into {SCHEMA}.{TABLE}.")
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo temperature data.")
    parser.add_argument(
        "--reset", action="store_true", help="Delete existing rows before reseeding."
    )
    args = parser.parse_args()
    seed(reset=args.reset)
