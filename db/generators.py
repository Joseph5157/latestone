"""
Deterministic development measurement and registration-history generation.

SYNTHETIC DEVELOPMENT DATA standing in for client measurements and client
device registration records, neither of which is available yet. These are NOT
client-provided readings, the metric set is NOT a client-confirmed measurement
definition, and the registration dates are NOT a client equipment record.

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

#: Span of synthetic registration history (~18 months). A development value:
#: no client rule defines how far back RTL registration records reach.
REGISTRATION_HISTORY_DAYS = 540
_REGISTRATION_SPAN_MINUTES = REGISTRATION_HISTORY_DAYS * 24 * 60

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


def registration_timestamp(device_id: str, anchor: datetime) -> datetime:
    """When this device was administratively registered — synthetic.

    SYNTHETIC DEVELOPMENT SEED HISTORY. These are NOT client-derived
    registration dates. The client has supplied no device registration history
    of any kind, and no client record states when any RTL entered management.
    The value is a stable hash of `device_id` and nothing else, in exactly the
    same spirit as the synthetic transformer/device counts in `db.hierarchy` —
    do not present it, or anything computed from it, as a client-provided fact.

    Registration is an ADMINISTRATIVE event and is deliberately independent of
    the measurement window: `build_timestamps` gives every device the same 30
    days of readings regardless of the date returned here, so a device may
    carry readings that predate its registration. That is not a defect being
    papered over — a fleet reporting before the management records catch up is
    the ordinary case — but it does mean this timestamp must never be used to
    reason about when a device started producing data.

    The offset depends on `device_id` alone, never on `anchor`. Which devices
    fall inside a recency window is therefore a fixed property of the
    hierarchy rather than an accident of when the seed was run, so the figure
    reproduces across reseeds.

    This exists because the seed previously left `created_at` to migration
    002's `now()` server default, which handed all 120 devices one identical
    registration instant and made any recency metric read the whole fleet.
    """
    offset = _seed_for(device_id) % _REGISTRATION_SPAN_MINUTES
    return anchor - timedelta(minutes=offset)


def _base_temp_for_latitude(latitude: float) -> float:
    """Warmer near the equator, cooler at high latitudes - loose climate model."""
    return 34.0 - (abs(latitude) / 90.0) * 18.0


def _daily_fraction(ts: datetime) -> float:
    return (ts.hour + ts.minute / 60.0) / 24.0


def _device_base_params(device_id: str, latitude: float) -> tuple[float, float, float, float]:
    """(base_temp, daily_swing, base_current, load_swing) - the stable per-device
    character shared by the historical batch generator and the live tick
    generator, so a device's baseline never drifts between the seeded 30-day
    window and readings appended after it starts streaming live.
    """
    rng = random.Random(_seed_for(device_id))
    base_temp = _base_temp_for_latitude(latitude) + rng.uniform(-2.0, 2.0)
    daily_swing = 5.0 + rng.uniform(-1.0, 1.0)
    base_current = 150.0 + rng.uniform(-30.0, 60.0)
    load_swing = 0.18 + rng.uniform(-0.05, 0.05)
    return base_temp, daily_swing, base_current, load_swing


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
    base_temp, daily_swing, base_current, load_swing = _device_base_params(device_id, latitude)

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


def generate_live_reading(
    device_id: str,
    latitude: float,
    timestamp: datetime,
    previous_energy: float,
    interval_hours: float,
    *,
    noise_scale: float = 1.0,
    rng: random.Random | None = None,
) -> dict[str, float]:
    """One live tick's coherent 8-metric reading, for db/live_simulator.py.

    Unlike generate_device_series (a full deterministic historical batch,
    reproducible per device), this represents a genuinely new live
    measurement: `_device_base_params` gives the same per-device character
    every call (so the live feed doesn't drift from the seeded history), but
    noise is fresh each call unless `rng` is supplied.

    `previous_energy`/`interval_hours` let the caller keep the energy meter
    accumulating across ticks at whatever real cadence it is actually
    running at, rather than the fixed 30-minute seed interval.
    `noise_scale` scales all Gaussian jitter terms; 0.0 makes the result a
    pure deterministic function of device/timestamp (used by tests).
    """
    live_rng = rng if rng is not None else random.Random()
    base_temp, daily_swing, base_current, load_swing = _device_base_params(device_id, latitude)
    phase = _daily_fraction(timestamp) * 2 * math.pi

    t = base_temp + daily_swing * math.sin(phase - math.pi / 2) + live_rng.gauss(0, 1.2 * noise_scale)
    v = NOMINAL_VOLTAGE_KV + live_rng.gauss(0, 0.08 * noise_scale)
    i = base_current * (1.0 + load_swing * math.sin(phase - math.pi / 3)) + live_rng.gauss(0, 3.0 * noise_scale)
    i = max(i, 1.0)
    pf = min(0.999, max(0.850, 0.965 + live_rng.gauss(0, 0.012 * noise_scale)))
    f = NOMINAL_FREQUENCY_HZ + live_rng.gauss(0, 0.02 * noise_scale)

    p = SQRT3 * v * i * pf / 1000.0                          # MW
    q = p * math.tan(math.acos(pf))                           # MVAr
    meter = previous_energy + max(0.0, p * interval_hours)    # MWh, never decreases

    result = {
        "temperature": round(t, 3),
        "voltage": round(v, 3),
        "current": round(i, 3),
        "active_power": round(p, 3),
        "reactive_power": round(q, 3),
        "power_factor": round(pf, 3),
        "frequency": round(f, 3),
        "energy": round(meter, 3),
    }
    assert set(result) == set(METRIC_KEYS), "generator/metric registry drift"
    return result


def initial_energy_meter(device_id: str) -> float:
    """Starting energy meter value for a device with no prior readings yet.

    Same convention generate_device_series uses for its own seed meter — a
    fallback for db/live_simulator.py when a device has never been through
    db/seed_plant_monitoring.py, not a guarantee of matching the exact value
    the seed would have produced for that device.
    """
    rng = random.Random(_seed_for(device_id))
    return 5000.0 + rng.uniform(0.0, 4000.0)
