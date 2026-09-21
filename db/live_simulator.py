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
    LIVE_SIM_TEMPERATURE_SCENARIOS  keep Warning/Critical RTLs visible (default true)
    LIVE_SIM_WARNING_RTLS      RTLs held at Warning (default 7)
    LIVE_SIM_CRITICAL_RTLS     RTLs held at Critical (default 3)
    LIVE_SIM_EVENTS_PER_DAY    simulated RTL events per day (default 0 = off)

    python -m db.live_simulator --backfill-events-days 7
        one-shot: emit LIVE_SIM_EVENTS_PER_DAY events over the last 7 days, exit
"""
from __future__ import annotations

import argparse
import hashlib
import random
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Mapping

from config.metrics import METRIC_KEYS
from config.settings import live_sim
from db.generators import generate_live_reading, initial_energy_meter
from db.live_events import emit_planned, plan_events
from db.seed_freshness_demo import CAPTURE_PATH, silenced_feeds
from repositories.plant_monitoring_repository import (
    RawReading,
    get_latest_reading,
    insert_readings,
    list_all_devices,
    list_plants,
)
from services.temperature_threshold_service import get_current_threshold_config


TEMPERATURE_WARNING_SCENARIO = "warning"
TEMPERATURE_CRITICAL_SCENARIO = "critical"

#: Problem RTLs deliberately concentrated on one plant, so a plant-level
#: rollup has something to roll up and one plant reads as the worst.
HOT_SPOT_DEVICE_COUNT = 3

#: Where in the Administrator's Warning..Critical band a Warning RTL sits,
#: as a share of that band. Kept clear of both ends so no rounding can push
#: an RTL over a limit it is meant to sit below.
WARNING_BAND_SPAN = (Decimal("0.2"), Decimal("0.8"))

#: How far above the Critical limit a Critical RTL sits, also as a share of
#: the band, so the overshoot scales with how the limits were configured.
CRITICAL_OVERSHOOT_SPAN = (Decimal("0.1"), Decimal("0.6"))


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


def _spaced_positions(total: int, count: int) -> set[int]:
    """`count` positions spread evenly through `range(total)`, always incl. 0."""
    if count <= 0 or total <= 0:
        return set()
    return {(index * total) // count for index in range(count)}


def _critical_share(slots: int, warning_count: int, critical_count: int) -> int:
    """How many of `slots` are Critical.

    A scope too small to satisfy both quotas keeps their ratio rather than
    spending every slot on Critical.
    """
    wanted = warning_count + critical_count
    if slots >= wanted:
        return critical_count
    return round(slots * critical_count / wanted)


def _scenario_candidates(by_plant: dict[str, list[str]], wanted: int) -> list[str]:
    """Which RTLs become problems, in the order conditions are handed out.

    The first plant in scope supplies the hot spot; the rest come one per
    plant on a stride across the remaining plants, so the fleet map is
    sprinkled rather than bunched at the top. A scope too small for that
    falls back to whatever devices are left, so a handful-of-devices
    simulator still demonstrates both conditions.
    """
    plants = sorted(by_plant)
    candidates = by_plant[plants[0]][:HOT_SPOT_DEVICE_COUNT][:wanted]

    others = plants[1:]
    scatter = min(wanted - len(candidates), len(others))
    candidates += [by_plant[others[p]][0] for p in sorted(_spaced_positions(len(others), scatter))]

    if len(candidates) < wanted:
        taken = set(candidates)
        leftovers = (d for plant in plants for d in by_plant[plant] if d not in taken)
        candidates += list(leftovers)[: wanted - len(candidates)]
    return candidates


def plan_temperature_scenarios(
    device_ids: list[str],
    plant_of: Mapping[str, str],
    *,
    warning_count: int,
    critical_count: int,
) -> dict[str, str]:
    """Lay out which scoped RTLs continuously demonstrate Warning and Critical.

    Stable by construction: the same fleet always yields the same plan, so an
    RTL keeps its condition across ticks and across simulator restarts.
    Critical RTLs are spaced through the order rather than grouped, so no one
    plant owns every Critical.
    """
    warning_count = max(warning_count, 0)
    critical_count = max(critical_count, 0)
    wanted = warning_count + critical_count
    if wanted == 0:
        return {}

    by_plant: dict[str, list[str]] = {}
    for device_id in sorted(device_ids):
        plant_id = plant_of.get(device_id)
        if plant_id is not None:
            by_plant.setdefault(plant_id, []).append(device_id)
    if not by_plant:
        return {}

    candidates = _scenario_candidates(by_plant, wanted)
    critical_positions = _spaced_positions(
        len(candidates), _critical_share(len(candidates), warning_count, critical_count)
    )
    return {
        device_id: (
            TEMPERATURE_CRITICAL_SCENARIO
            if position in critical_positions
            else TEMPERATURE_WARNING_SCENARIO
        )
        for position, device_id in enumerate(candidates)
    }


def _device_fraction(device_id: str, low: Decimal, high: Decimal) -> Decimal:
    """A stable value in [low, high] derived from the device id alone.

    Deterministic, so an RTL's reading does not jump around between ticks,
    and spread out, so ten scenario RTLs do not all report an identical
    temperature and make the hottest-RTL panel look fabricated.
    """
    digest = hashlib.sha256(device_id.encode("utf-8")).digest()
    position = Decimal(int.from_bytes(digest[:4], "big")) / Decimal(2**32)
    return low + (high - low) * position


def scenario_temperature(
    device_id: str,
    scenarios: dict[str, str],
    *,
    warning_c: Decimal | None,
    critical_c: Decimal | None,
) -> float | None:
    """Return a limit-relative scenario value, or ``None`` for no override.

    The limits remain Administrator-owned (ADR-023). The simulator merely
    supplies recent values on the appropriate side of those live limits, and
    expresses its spread as a share of the band between them so a narrow band
    still lands every RTL on its intended side.
    """
    scenario = scenarios.get(device_id)
    if scenario is None or warning_c is None or critical_c is None:
        return None
    if scenario not in (TEMPERATURE_WARNING_SCENARIO, TEMPERATURE_CRITICAL_SCENARIO):
        raise ValueError(f"Unknown temperature scenario: {scenario}")
    band = critical_c - warning_c
    if band <= 0:
        return None
    if scenario == TEMPERATURE_WARNING_SCENARIO:
        return float(warning_c + band * _device_fraction(device_id, *WARNING_BAND_SPAN))
    return float(critical_c + band * _device_fraction(device_id, *CRITICAL_OVERSHOOT_SPAN))


def _device_latitudes() -> dict[str, float]:
    """device_id -> its plant's latitude, for every administratively active device."""
    devices = list_all_devices()
    plant_latitudes = {p.plant_id: p.latitude for p in list_plants(allowed_device_ids=None)}
    return {
        d.device_id: plant_latitudes[d.plant_id]
        for d in devices
        if d.plant_id in plant_latitudes
    }


def _device_plants() -> dict[str, str]:
    """device_id -> plant_id for every device, so scenarios can spread by plant."""
    return {d.device_id: d.plant_id for d in list_all_devices()}


def _initial_energy(device_id: str) -> float:
    latest = get_latest_reading(device_id, "energy")
    return latest.value if latest is not None else initial_energy_meter(device_id)


def _device_transformers() -> dict[str, str]:
    """device_id -> transformer_id for every device, for event attribution."""
    return {d.device_id: d.transformer_id for d in list_all_devices()}


def backfill_events(days: float, now: datetime, rng: random.Random) -> int:
    """One-shot: plan and emit events spread over the last `days`.

    Events are append-only (INGEST-D3): running this twice doubles them.
    """
    if live_sim.events_per_day <= 0:
        print("LIVE_SIM_EVENTS_PER_DAY is 0 - nothing to backfill.")
        return 0
    transformer_of = _device_transformers()
    planned = plan_events(
        rng, sorted(transformer_of), now - timedelta(days=days), now,
        live_sim.events_per_day,
    )
    return emit_planned(planned, transformer_of)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Live-append synthetic readings (and, if enabled, events)."
    )
    parser.add_argument(
        "--backfill-events-days", type=float, default=None,
        help="Emit LIVE_SIM_EVENTS_PER_DAY events spread over the last N days, "
             "then exit. Events are append-only: running this twice doubles them.",
    )
    return parser.parse_args(argv)


def run() -> None:
    latitudes = _device_latitudes()
    device_ids = resolve_device_scope(live_sim.device_ids, set(latitudes))
    metrics = resolve_metric_scope(live_sim.metrics)
    interval_hours = live_sim.interval_seconds / 3600.0

    energy_state = {d: _initial_energy(d) for d in device_ids} if "energy" in metrics else {}
    temperature_scenarios = (
        plan_temperature_scenarios(
            device_ids,
            _device_plants(),
            warning_count=live_sim.warning_rtls,
            critical_count=live_sim.critical_rtls,
        )
        if live_sim.temperature_scenarios and "temperature" in metrics
        else {}
    )

    print(
        f"Live simulator: {len(device_ids)} device(s), metrics={metrics}, "
        f"every {live_sim.interval_seconds}s (Ctrl+C to stop)"
    )
    silenced = active_silenced_feeds()
    rng = random.Random()
    transformer_of = _device_transformers() if live_sim.events_per_day > 0 else {}
    last_tick = datetime.now(timezone.utc)
    if silenced:
        print(f"  skipping {len(silenced)} silenced feed(s) (freshness demo applied)")
    if temperature_scenarios:
        planned = Counter(temperature_scenarios.values())
        print(
            f"  temperature scenarios: {planned[TEMPERATURE_WARNING_SCENARIO]} Warning, "
            f"{planned[TEMPERATURE_CRITICAL_SCENARIO]} Critical "
            f"(values follow the Administrator's limits; none stored = no override)"
        )

    while True:
        now = datetime.now(timezone.utc)
        threshold_config = (
            get_current_threshold_config() if temperature_scenarios else None
        )
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
            scenario_value = scenario_temperature(
                device_id,
                temperature_scenarios,
                warning_c=(
                    threshold_config.warning_c if threshold_config is not None else None
                ),
                critical_c=(
                    threshold_config.critical_c if threshold_config is not None else None
                ),
            )
            if scenario_value is not None:
                reading["temperature"] = scenario_value
            for metric in metrics:
                if is_silenced(device_id, metric, silenced):
                    continue
                rows.append(RawReading(device_id, metric, now, reading[metric]))
            if "energy" in metrics:
                energy_state[device_id] = reading["energy"]

        insert_readings(rows)
        print(f"  {now.isoformat()} -- wrote {len(rows)} readings")
        if live_sim.events_per_day > 0:
            planned = plan_events(
                rng, device_ids, last_tick, now, live_sim.events_per_day
            )
            emitted = emit_planned(planned, transformer_of)
            if emitted:
                print(f"  {now.isoformat()} -- emitted {emitted} event(s)")
        last_tick = now
        time.sleep(live_sim.interval_seconds)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    try:
        if args.backfill_events_days is not None:
            count = backfill_events(
                args.backfill_events_days, datetime.now(timezone.utc), random.Random()
            )
            print(f"Backfilled {count} event(s).")
        else:
            run()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped.")
