"""
Live-append demo/dev data feed for plant_monitoring.

SYNTHETIC DEVELOPMENT DATA — same status as db/seed_plant_monitoring.py.
Runs continuously, inserting one fresh reading per device per metric on a
timer using wall-clock timestamps, so the freshness badge, latest-value
KPIs, and charts visibly update while the dashboard is open. This is NOT
part of the seed pipeline: seed_plant_monitoring.py remains the one-time
historical loader; this appends on top of whatever is already seeded.

Usage:
    python -m db.live_simulator

Configuration (see config.settings.LiveSimSettings / .env.example):
    LIVE_SIM_INTERVAL_SECONDS  seconds between ticks (default 10)
    LIVE_SIM_DEVICE_IDS        comma-separated device ids (default: all)
    LIVE_SIM_METRICS           comma-separated metric keys (default: all)
    LIVE_SIM_NOISE_SCALE       jitter multiplier (default 1.0)
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

from config.metrics import METRIC_KEYS
from config.settings import live_sim
from db.generators import generate_live_reading, initial_energy_meter
from db.seed_freshness_demo import CAPTURE_PATH, silenced_feeds
from repositories.plant_monitoring_repository import (
    RawReading,
    get_latest_reading,
    insert_readings,
    list_all_devices,
    list_plants,
)


class ConfigurationError(ValueError):
    """A LIVE_SIM_* env var names a device id or metric that doesn't exist."""


def resolve_device_scope(configured_ids: tuple[str, ...], known_ids: set[str]) -> list[str]:
    """Validate LIVE_SIM_DEVICE_IDS against the real fleet.

    Empty configuration means "every device" — returns known_ids sorted for
    a stable, reproducible tick order.
    """
    if not configured_ids:
        return sorted(known_ids)
    unknown = [d for d in configured_ids if d not in known_ids]
    if unknown:
        raise ConfigurationError(
            f"LIVE_SIM_DEVICE_IDS names unknown device id(s): {', '.join(unknown)}"
        )
    return list(configured_ids)


def resolve_metric_scope(
    configured_metrics: tuple[str, ...], known_metrics: tuple[str, ...] = METRIC_KEYS
) -> list[str]:
    """Validate LIVE_SIM_METRICS against the metric registry.

    Empty configuration means "every metric".
    """
    if not configured_metrics:
        return list(known_metrics)
    unknown = [m for m in configured_metrics if m not in known_metrics]
    if unknown:
        raise ConfigurationError(
            f"LIVE_SIM_METRICS names unknown metric key(s): {', '.join(unknown)}"
        )
    return list(configured_metrics)


def active_silenced_feeds() -> frozenset[tuple[str, str]]:
    """Feeds to skip: the freshness demo's, only while it is applied.

    Without this the first tick refills every feed db/seed_freshness_demo.py
    removed, and its Stale / No Data RTLs go Fresh again.
    """
    return silenced_feeds() if CAPTURE_PATH.exists() else frozenset()


def is_silenced(
    device_id: str, metric: str, silenced: frozenset[tuple[str, str]]
) -> bool:
    return (device_id, metric) in silenced


def _device_latitudes() -> dict[str, float]:
    """device_id -> its plant's latitude, for every administratively active device."""
    devices = list_all_devices()
    plant_latitudes = {p.plant_id: p.latitude for p in list_plants(allowed_device_ids=None)}
    return {
        d.device_id: plant_latitudes[d.plant_id]
        for d in devices
        if d.plant_id in plant_latitudes
    }


def _initial_energy(device_id: str) -> float:
    latest = get_latest_reading(device_id, "energy")
    return latest.value if latest is not None else initial_energy_meter(device_id)


def run() -> None:
    latitudes = _device_latitudes()
    device_ids = resolve_device_scope(live_sim.device_ids, set(latitudes))
    metrics = resolve_metric_scope(live_sim.metrics)
    interval_hours = live_sim.interval_seconds / 3600.0

    energy_state = {d: _initial_energy(d) for d in device_ids} if "energy" in metrics else {}

    print(
        f"Live simulator: {len(device_ids)} device(s), metrics={metrics}, "
        f"every {live_sim.interval_seconds}s (Ctrl+C to stop)"
    )
    silenced = active_silenced_feeds()
    if silenced:
        print(f"  skipping {len(silenced)} silenced feed(s) (freshness demo applied)")

    while True:
        now = datetime.now(timezone.utc)
        rows: list[RawReading] = []
        for device_id in device_ids:
            reading = generate_live_reading(
                device_id,
                latitudes[device_id],
                now,
                energy_state.get(device_id, 0.0),
                interval_hours,
                noise_scale=live_sim.noise_scale,
            )
            for metric in metrics:
                if is_silenced(device_id, metric, silenced):
                    continue
                rows.append(RawReading(device_id, metric, now, reading[metric]))
            if "energy" in metrics:
                energy_state[device_id] = reading["energy"]

        insert_readings(rows)
        print(f"  {now.isoformat()} -- wrote {len(rows)} readings")
        time.sleep(live_sim.interval_seconds)


if __name__ == "__main__":
    try:
        run()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped.")
