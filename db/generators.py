"""
Deterministic development measurement generation.

SYNTHETIC DEVELOPMENT DATA standing in for client measurements, which are
not yet available. These are NOT client-provided readings and the metric
set is NOT a client-confirmed measurement definition.

All values are expressed in DEVELOPMENT DISPLAY UNITS (see config/metrics.py).
Real client units and metric definitions must be mapped when the client
database/schema is available.

energy is modelled as a CUMULATIVE METER that increases monotonically -
period semantics are last minus first, not average. A negative delta would
indicate a counter reset or data-quality condition; no counter-reset
handling is implemented at this stage.

Pure functions: seeded per device, so output is reproducible.
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime, timedelta

from config.metrics import METRIC_KEYS

INTERVAL_MINUTES = 30
DAYS_OF_HISTORY = 30

NOMINAL_VOLTAGE_KV = 11.0
NOMINAL_FREQUENCY_HZ = 50.0
SQRT3 = math.sqrt(3.0)


def build_timestamps(anchor: datetime) -> list[datetime]:
    """1,441 inclusive timestamps: 30 days back to the anchor, 30 min apart."""
    steps = (DAYS_OF_HISTORY * 24 * 60) // INTERVAL_MINUTES
    start = anchor - timedelta(days=DAYS_OF_HISTORY)
    return [start + timedelta(minutes=INTERVAL_MINUTES * i) for i in range(steps + 1)]


def _seed_for(device_id: str) -> int:
    return int(hashlib.sha256(device_id.encode("utf-8")).hexdigest()[:12], 16)


def _base_temp_for_latitude(latitude: float) -> float:
    """Warmer near the equator, cooler at high latitudes - loose climate model."""
    return 34.0 - (abs(latitude) / 90.0) * 18.0


def _daily_fraction(ts: datetime) -> float:
    return (ts.hour + ts.minute / 60.0) / 24.0


def generate_device_series(
    device_id: str, latitude: float, timestamps: list[datetime]
) -> dict[str, list[float]]:
    """Generate all 8 development metric series for one device.

    Electrical metrics are kept mutually coherent rather than independently
    random: active_power is derived from voltage/current/power_factor, and
    reactive_power from active_power and power_factor, so the dashboard's
    numbers look plausible together.
    """
    rng = random.Random(_seed_for(device_id))

    base_temp = _base_temp_for_latitude(latitude) + rng.uniform(-2.0, 2.0)
    daily_swing = 5.0 + rng.uniform(-1.0, 1.0)
    base_current = 150.0 + rng.uniform(-30.0, 60.0)
    load_swing = 0.18 + rng.uniform(-0.05, 0.05)

    temperature: list[float] = []
    voltage: list[float] = []
    current: list[float] = []
    active_power: list[float] = []
    reactive_power: list[float] = []
    power_factor: list[float] = []
    frequency: list[float] = []
    energy: list[float] = []

    meter = 5000.0 + rng.uniform(0.0, 4000.0)  # arbitrary starting meter value
    interval_hours = INTERVAL_MINUTES / 60.0

    for ts in timestamps:
        phase = _daily_fraction(ts) * 2 * math.pi

        t = base_temp + daily_swing * math.sin(phase - math.pi / 2) + rng.gauss(0, 1.2)
        v = NOMINAL_VOLTAGE_KV + rng.gauss(0, 0.08)
        i = base_current * (1.0 + load_swing * math.sin(phase - math.pi / 3)) + rng.gauss(0, 3.0)
        i = max(i, 1.0)
        pf = min(0.999, max(0.850, 0.965 + rng.gauss(0, 0.012)))
        f = NOMINAL_FREQUENCY_HZ + rng.gauss(0, 0.02)

        p = SQRT3 * v * i * pf / 1000.0                       # MW
        q = p * math.tan(math.acos(pf))                        # MVAr
        meter += max(0.0, p * interval_hours)                  # MWh, never decreases

        temperature.append(round(t, 3))
        voltage.append(round(v, 3))
        current.append(round(i, 3))
        active_power.append(round(p, 3))
        reactive_power.append(round(q, 3))
        power_factor.append(round(pf, 3))
        frequency.append(round(f, 3))
        energy.append(round(meter, 3))

    result = {
        "temperature": temperature,
        "voltage": voltage,
        "current": current,
        "active_power": active_power,
        "reactive_power": reactive_power,
        "power_factor": power_factor,
        "frequency": frequency,
        "energy": energy,
    }
    assert set(result) == set(METRIC_KEYS), "generator/metric registry drift"
    return result
