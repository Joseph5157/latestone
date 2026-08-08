# Plant Monitoring Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-device temperature demo with a production-oriented 30-plant monitoring application over a normalized Plant → Transformer → Device → Metric → Reading hierarchy.

**Architecture:** Strict `pages → services → repositories → db` layering. Raw SQL only in `repositories/plant_monitoring_repository.py`. KPI/aggregation/freshness logic only in `services/`. Metric presentation and aggregation semantics centralized in `config/metrics.py`. Dash multi-page routing with URL-addressable device/metric/period state.

**Tech Stack:** Python 3.12, Dash 2.17, Plotly 5.24, PostgreSQL 16 (Docker Compose), SQLAlchemy 2.0, psycopg2, pytest.

**Spec:** `docs/superpowers/specs/2026-08-08-plant-monitoring-architecture-design.md` — read it before starting. It is the authority on any detail this plan compresses.

## Global Constraints

- Raw SQL exists **only** in `repositories/plant_monitoring_repository.py`. No generic raw-query helpers. No SQL string interpolation of metric lists or identifiers — use bound/expanding parameters.
- Business logic (KPI math, aggregation dispatch, freshness) lives **only** in `services/`. Components may read `MetricConfig` presentation fields but must never contain `if metric.key == "..."`.
- **No production warning/critical thresholds.** `MonitoringCondition` always evaluates to `UNKNOWN`. `MetricConfig` carries no threshold fields.
- Three concepts stay independent and are never merged: administrative status (`active`/`inactive`), data freshness (`fresh`/`stale`/`no_data`), monitoring condition (`normal`/`warning`/`critical`/`unknown`).
- Data freshness is **never** labelled "connection state". Application/database errors are a separate state.
- All engineering units are **development display units**. Every module defining them carries a comment saying real client units must be mapped when the client database is available.
- Transformer/device counts and codes are **synthetic development data** derived from `plant_id`, never from `capacity_mw`. Every generating module documents this.
- `AA12` / `29017` is the only client-known naming example; reserved at `plant-01`'s first transformer/device, documented as arbitrary placement.
- Bounded time queries use explicit inclusivity: `reading_ts >= start AND reading_ts <= end`.
- Batched device queries issue **one** SQL statement for all requested metrics.
- `dcc.Store` holds lightweight navigation/UI state only — never historical reading datasets.
- Refresh interval and freshness policy come from `config/settings.py`, never hard-coded in callbacks or services.
- Type hints on all service/repository interfaces. No secrets committed.

## File Structure

**Created**

| File | Responsibility |
|---|---|
| `config/metrics.py` | `Aggregation`, `MetricConfig`, the 8-metric registry, lookup helpers |
| `db/init_plant_monitoring.sql` | `plant_monitoring` schema DDL |
| `db/hierarchy.py` | Pure deterministic hierarchy generation (no DB, no I/O) |
| `db/generators.py` | Pure deterministic measurement generation for the 8 metrics |
| `db/seed_plant_monitoring.py` | Seed orchestration + bulk COPY load |
| `repositories/plant_monitoring_repository.py` | All SQL |
| `services/hierarchy_service.py` | Hierarchy validation + active-filtered listings |
| `services/monitoring_service.py` | (rewrite) view models, aggregation dispatch, freshness |
| `components/app_header.py` | Header shell |
| `components/breadcrumb.py` | Hierarchy trail |
| `components/hierarchy_selector.py` | Cascading Plant→Transformer→Device dropdowns |
| `components/entity_table.py` | Generic sortable listing table |
| `components/equipment_context.py` | Compact device context strip |
| `components/metric_snapshot_strip.py` | 8-tile snapshot |
| `components/metric_chart.py` | Metric-parameterized line chart |
| `components/freshness_badge.py` | Renders a `Freshness` value |
| `components/status_panels.py` | `not_found_panel`, `error_panel`, `empty_data_panel` |
| `pages/plants_overview.py`, `pages/plant_detail.py`, `pages/transformer_detail.py`, `pages/device_dashboard.py` | Page shells (layout only, no queries) |
| `callbacks/routing.py`, `callbacks/auth.py`, `callbacks/listings.py`, `callbacks/device.py` | Callback registration, split by concern |
| `tests/test_metrics_config.py`, `tests/test_hierarchy_generation.py`, `tests/test_generators.py`, `tests/test_monitoring_service.py`, `tests/test_hierarchy_service.py`, `tests/test_plant_monitoring_repository.py`, `tests/test_query_performance.py`, `tests/conftest.py` | Tests |

**Modified:** `config/settings.py`, `db/seed_data/plants.json`, `components/kpi_card.py`, `components/readings_table.py`, `components/period_filter.py`, `app.py`, `assets/app.css`, `docker-compose.yml`, `.env.example`, `README.md`, `CLAUDE.md`, `DATABASE.md`, `ARCHITECTURE.md`, `UI_SPEC.md`, `REQUIREMENTS.md`, `requirements.txt`

**Deleted (Phase 13):** `pages/dashboard.py`, `pages/plants_dashboard.py`, `services/temperature_service.py`, `repositories/temperature_repository.py`, `repositories/monitoring_repository.py`, `components/temperature_chart.py`, `components/plant_selector.py`, `db/seed.py`, `db/seed_multi_plant.py`, `db/init.sql`, `db/init_monitoring.sql`, `tests/test_temperature_service.py`, `tests/test_temperature_repository.py`

---

## Phase 0: Repository Initialization

**Objective:** Make per-phase commits possible. This project is not currently a git repository.

**Files:** Create `.gitignore` entries check only.

- [ ] **Step 1: Confirm with the user before running this phase** — initializing git is a workspace-level change. If the user declines, skip Phase 0 and drop every `git commit` step from later phases.

- [ ] **Step 2: Verify not already a repo**

Run: `git rev-parse --is-inside-work-tree`
Expected: fatal error ("not a git repository")

- [ ] **Step 3: Confirm `.gitignore` excludes venv, caches, env and archives**

Read `.gitignore`. It must contain at least `.venv/`, `__pycache__/`, `.pytest_cache/`, `.env`, `*.zip`. Add any missing line.

- [ ] **Step 4: Initialize and make the baseline commit**

```bash
git init
git add -A
git commit -m "chore: baseline before plant monitoring architecture rework"
```

- [ ] **Step 5: Verify the working tree is clean and secrets are not tracked**

Run: `git status --short` → expect empty. Run: `git ls-files | grep -x ".env"` → expect no output.

**Verification:** `git log --oneline` shows one commit; `.env` untracked.

---

## Phase 1: PostgreSQL Schema Migration

**Objective:** Create the `plant_monitoring` schema with the approved keys, foreign keys, unique constraints and indexes, and wire it into Docker Compose alongside (not yet replacing) the old init scripts.

**Files:**
- Create: `db/init_plant_monitoring.sql`
- Modify: `docker-compose.yml:14-15`, `config/settings.py`, `.env.example`

**Interfaces:**
- Produces: schema `plant_monitoring` with tables `plants`, `transformers`, `devices`, `readings`; `config.settings.monitoring.schema == "plant_monitoring"`.

- [ ] **Step 1: Write the schema DDL**

Create `db/init_plant_monitoring.sql` with a header comment stating: this is our clean normalized internal model; it deliberately does **not** reproduce the client's ~2,112-table physical structure; `status` columns are administrative only and never hold computed monitoring status; metric display metadata lives in `config/metrics.py`, not in the database.

Then the exact DDL from spec Section 1 — `CREATE SCHEMA IF NOT EXISTS plant_monitoring;` and the four `CREATE TABLE IF NOT EXISTS` statements with `ix_transformers_plant_id`, `ix_devices_transformer_id`, `ix_readings_device_metric_ts`.

- [ ] **Step 2: Mount the script in Docker Compose**

In `docker-compose.yml`, add under `volumes:` after the existing init mounts:

```yaml
      - ./db/init_plant_monitoring.sql:/docker-entrypoint-initdb.d/03_init_plant_monitoring.sql:ro
```

- [ ] **Step 3: Add monitoring settings to config**

In `config/settings.py`, add:

```python
@dataclass(frozen=True)
class MonitoringSettings:
    """Freshness policy and refresh cadence.

    expected_interval_minutes: current project/client-known requirement
        (readings arrive roughly every 30 minutes).
    stale_after_intervals: DEVELOPMENT APPLICATION POLICY. Requires client
        confirmation before production use.
    refresh_interval_seconds: UI polling cadence. Short by default for local
        development convenience; production polling should be aligned to
        actual ingestion behaviour.
    """
    schema: str = os.getenv("PLANT_MONITORING_SCHEMA", "plant_monitoring")
    expected_interval_minutes: int = _get_int("EXPECTED_INTERVAL_MINUTES", 30)
    stale_after_intervals: int = _get_int("STALE_AFTER_INTERVALS", 3)
    refresh_interval_seconds: int = _get_int("UI_REFRESH_INTERVAL_SECONDS", 60)

    @property
    def stale_after_minutes(self) -> int:
        return self.expected_interval_minutes * self.stale_after_intervals


monitoring = MonitoringSettings()
```

- [ ] **Step 4: Update `.env.example`**

Add, replacing the `DEMO_WARNING_THRESHOLD_C` block:

```
# Schema
PLANT_MONITORING_SCHEMA=plant_monitoring

# Freshness policy
# 30-minute cadence = project/client-known requirement.
# 3 missed intervals = DEVELOPMENT policy, needs client confirmation.
EXPECTED_INTERVAL_MINUTES=30
STALE_AFTER_INTERVALS=3

# UI refresh cadence (seconds) - short for local dev convenience
UI_REFRESH_INTERVAL_SECONDS=60
```

Leave `DB_SCHEMA=trfr_temperature` in place for now; Phase 13 removes it.

- [ ] **Step 5: Recreate the database volume and verify the schema**

```bash
docker compose down -v
docker compose up -d
docker compose exec postgres psql -U powerplant -d powerplant_demo -c "\dt plant_monitoring.*"
```

Expected: four tables listed — `devices`, `plants`, `readings`, `transformers`.

- [ ] **Step 6: Verify indexes and constraints exist**

```bash
docker compose exec postgres psql -U powerplant -d powerplant_demo -c "\di plant_monitoring.*"
```

Expected output includes `ix_transformers_plant_id`, `ix_devices_transformer_id`, `ix_readings_device_metric_ts`, plus the primary-key and unique-constraint indexes.

- [ ] **Step 7: Commit**

```bash
git add db/init_plant_monitoring.sql docker-compose.yml config/settings.py .env.example
git commit -m "feat(db): add normalized plant_monitoring schema"
```

**Verification:** Both psql commands above return the expected objects against a freshly recreated volume.

---

## Phase 2: 30-Plant Hierarchy Generation

**Objective:** Pure, deterministic, database-free generation of 71 transformers and 120 devices from `plant_id` alone, with `AA12`/`29017` reserved.

**Files:**
- Create: `db/hierarchy.py`, `tests/test_hierarchy_generation.py`
- Modify: `db/seed_data/plants.json`

**Interfaces:**
- Consumes: `db/seed_data/plants.json` (list of dicts with `plant_id`, `name`, `country`, `latitude`, `longitude`, `capacity_mw`, `primary_fuel`).
- Produces:
  ```python
  TRANSFORMER_TIERS: list[tuple[int, int]]          # (plants_in_tier, transformers_each)
  RESERVED_TRANSFORMER_CODE: str = "aa12"
  RESERVED_DEVICE_CODE: str = "29017"

  @dataclass(frozen=True)
  class GeneratedTransformer:
      transformer_id: str
      plant_id: str
      transformer_code: str
      index: int                                     # 1-based within plant

  @dataclass(frozen=True)
  class GeneratedDevice:
      device_id: str
      transformer_id: str
      device_code: str

  def transformer_counts(plant_ids: list[str]) -> dict[str, int]
  def build_hierarchy(plant_ids: list[str], countries: dict[str, str]) -> tuple[list[GeneratedTransformer], list[GeneratedDevice]]
  ```

- [ ] **Step 1: Strip the stale per-plant transformer/device fields from the seed data**

In `db/seed_data/plants.json`, delete the `"transformer"` and `"device"` keys from all 30 entries. They are superseded by generated hierarchy. Keep every other field unchanged.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_hierarchy_generation.py`:

```python
"""Unit tests for db.hierarchy - pure functions, no database required."""
from __future__ import annotations

import json
from pathlib import Path

from db.hierarchy import (
    RESERVED_DEVICE_CODE,
    RESERVED_TRANSFORMER_CODE,
    build_hierarchy,
    transformer_counts,
)

PLANTS_FILE = Path(__file__).parent.parent / "db" / "seed_data" / "plants.json"


def _load():
    with open(PLANTS_FILE, encoding="utf-8") as f:
        plants = json.load(f)
    return [p["plant_id"] for p in plants], {p["plant_id"]: p["country"] for p in plants}


class TestTransformerCounts:
    def test_totals_71_transformers_across_30_plants(self):
        plant_ids, _ = _load()
        counts = transformer_counts(plant_ids)
        assert len(counts) == 30
        assert sum(counts.values()) == 71

    def test_tier_distribution_matches_spec(self):
        plant_ids, _ = _load()
        counts = transformer_counts(plant_ids)
        tally = {n: sum(1 for v in counts.values() if v == n) for n in (1, 2, 3, 4)}
        assert tally == {4: 5, 3: 8, 2: 10, 1: 7}

    def test_is_deterministic_across_calls(self):
        plant_ids, _ = _load()
        assert transformer_counts(plant_ids) == transformer_counts(plant_ids)

    def test_is_independent_of_input_ordering(self):
        plant_ids, _ = _load()
        assert transformer_counts(plant_ids) == transformer_counts(list(reversed(plant_ids)))

    def test_does_not_correlate_with_capacity(self):
        """Guard the explicit requirement that capacity_mw must not drive counts."""
        with open(PLANTS_FILE, encoding="utf-8") as f:
            plants = json.load(f)
        counts = transformer_counts([p["plant_id"] for p in plants])
        by_capacity = sorted(plants, key=lambda p: -(p["capacity_mw"] or 0))
        top_five = [counts[p["plant_id"]] for p in by_capacity[:5]]
        assert top_five != [4, 4, 4, 4, 4]


class TestBuildHierarchy:
    def test_generates_71_transformers_and_120_devices(self):
        plant_ids, countries = _load()
        transformers, devices = build_hierarchy(plant_ids, countries)
        assert len(transformers) == 71
        assert len(devices) == 120

    def test_device_counts_cycle_one_two_three(self):
        plant_ids, countries = _load()
        transformers, devices = build_hierarchy(plant_ids, countries)
        per_transformer = {t.transformer_id: 0 for t in transformers}
        for d in devices:
            per_transformer[d.transformer_id] += 1
        for t in transformers:
            assert per_transformer[t.transformer_id] == ((t.index - 1) % 3) + 1

    def test_all_ids_unique(self):
        plant_ids, countries = _load()
        transformers, devices = build_hierarchy(plant_ids, countries)
        assert len({t.transformer_id for t in transformers}) == 71
        assert len({d.device_id for d in devices}) == 120

    def test_device_codes_unique(self):
        plant_ids, countries = _load()
        _, devices = build_hierarchy(plant_ids, countries)
        assert len({d.device_code for d in devices}) == 120

    def test_transformer_codes_unique_within_each_plant(self):
        plant_ids, countries = _load()
        transformers, _ = build_hierarchy(plant_ids, countries)
        seen: set[tuple[str, str]] = set()
        for t in transformers:
            key = (t.plant_id, t.transformer_code)
            assert key not in seen
            seen.add(key)

    def test_reserves_client_known_naming_example(self):
        plant_ids, countries = _load()
        transformers, devices = build_hierarchy(plant_ids, countries)
        reserved_t = next(t for t in transformers if t.plant_id == "plant-01" and t.index == 1)
        assert reserved_t.transformer_code == RESERVED_TRANSFORMER_CODE
        reserved_d = next(d for d in devices if d.transformer_id == reserved_t.transformer_id)
        assert reserved_d.device_code == RESERVED_DEVICE_CODE

    def test_surrogate_key_format(self):
        plant_ids, countries = _load()
        transformers, devices = build_hierarchy(plant_ids, countries)
        assert any(t.transformer_id == "plant-01-t1" for t in transformers)
        assert any(d.device_id == "plant-01-t1-d1" for d in devices)

    def test_is_deterministic_across_calls(self):
        plant_ids, countries = _load()
        first = build_hierarchy(plant_ids, countries)
        second = build_hierarchy(plant_ids, countries)
        assert first == second
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_hierarchy_generation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db.hierarchy'`

- [ ] **Step 4: Implement `db/hierarchy.py`**

```python
"""
Deterministic development hierarchy generation.

SYNTHETIC DEVELOPMENT DATA. The number of transformers per plant and the
number of devices per transformer are assigned by a stable hash of
plant_id. They have NO relationship to plant capacity, to real transformer
counts, or to any client equipment inventory. Do not present these counts
as client-provided facts.

Transformer and device codes are likewise synthetic, with one documented
exception: plant-01's first transformer/device is reserved to the only
naming example known from the client's pgAdmin screenshots
(transformer AA12, device 29017, observed combined form aa12_29017).
That placement is arbitrary and carries no meaning about real equipment.

Pure functions only: no database access, no I/O, no randomness.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

RESERVED_PLANT_ID = "plant-01"
RESERVED_TRANSFORMER_CODE = "aa12"
RESERVED_DEVICE_CODE = "29017"

DEVICE_CODE_START = 29001

# (number of plants in tier, transformers per plant in that tier)
# 5*4 + 8*3 + 10*2 + 7*1 = 71 transformers.
TRANSFORMER_TIERS: list[tuple[int, int]] = [(5, 4), (8, 3), (10, 2), (7, 1)]


@dataclass(frozen=True)
class GeneratedTransformer:
    transformer_id: str
    plant_id: str
    transformer_code: str
    index: int  # 1-based position within its plant


@dataclass(frozen=True)
class GeneratedDevice:
    device_id: str
    transformer_id: str
    device_code: str


def _hash_key(plant_id: str) -> str:
    return hashlib.sha256(plant_id.encode("utf-8")).hexdigest()


def transformer_counts(plant_ids: list[str]) -> dict[str, int]:
    """Assign transformers per plant from a stable hash of plant_id.

    Deliberately NOT derived from capacity_mw - we have no evidence that
    generating capacity determines monitored transformer count.
    """
    ordered = sorted(plant_ids, key=_hash_key)
    counts: dict[str, int] = {}
    position = 0
    for tier_size, transformers_each in TRANSFORMER_TIERS:
        for plant_id in ordered[position : position + tier_size]:
            counts[plant_id] = transformers_each
        position += tier_size
    for plant_id in ordered[position:]:  # safety net if plant count changes
        counts[plant_id] = 1
    return counts


def _country_prefix(country: str) -> str:
    letters = [c for c in country.lower() if c.isalnum()]
    return "".join(letters[:2]) or "xx"


def _devices_for_index(index: int) -> int:
    return ((index - 1) % 3) + 1


def build_hierarchy(
    plant_ids: list[str], countries: dict[str, str]
) -> tuple[list[GeneratedTransformer], list[GeneratedDevice]]:
    """Build the full synthetic transformer/device hierarchy.

    Iteration order is sorted plant_id -> transformer index -> device index,
    so output is stable regardless of input ordering.
    """
    counts = transformer_counts(plant_ids)

    transformers: list[GeneratedTransformer] = []
    devices: list[GeneratedDevice] = []

    for plant_id in sorted(plant_ids):
        prefix = _country_prefix(countries[plant_id])
        for index in range(1, counts[plant_id] + 1):
            transformer_id = f"{plant_id}-t{index}"
            code = f"{prefix}{index:02d}"
            if plant_id == RESERVED_PLANT_ID and index == 1:
                code = RESERVED_TRANSFORMER_CODE
            transformers.append(
                GeneratedTransformer(
                    transformer_id=transformer_id,
                    plant_id=plant_id,
                    transformer_code=code,
                    index=index,
                )
            )
            for device_index in range(1, _devices_for_index(index) + 1):
                devices.append(
                    GeneratedDevice(
                        device_id=f"{transformer_id}-d{device_index}",
                        transformer_id=transformer_id,
                        device_code="",  # assigned below
                    )
                )

    codes = [str(DEVICE_CODE_START + i) for i in range(len(devices))]
    reserved_slot = next(
        (i for i, d in enumerate(devices) if d.device_id == f"{RESERVED_PLANT_ID}-t1-d1"),
        None,
    )
    if reserved_slot is not None and RESERVED_DEVICE_CODE in codes:
        # Swap so the reserved slot gets 29017 and all codes stay unique.
        current = codes.index(RESERVED_DEVICE_CODE)
        codes[reserved_slot], codes[current] = codes[current], codes[reserved_slot]

    devices = [
        GeneratedDevice(
            device_id=d.device_id, transformer_id=d.transformer_id, device_code=codes[i]
        )
        for i, d in enumerate(devices)
    ]

    return transformers, devices
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_hierarchy_generation.py -v`
Expected: PASS — all tests green.

If `test_tier_distribution_matches_spec` fails, the tier arithmetic is wrong, not the hash — recheck `TRANSFORMER_TIERS` sums to 71. If `test_does_not_correlate_with_capacity` fails, the hash ordering coincidentally matched capacity order; that is a false positive worth investigating manually before changing anything.

- [ ] **Step 6: Commit**

```bash
git add db/hierarchy.py tests/test_hierarchy_generation.py db/seed_data/plants.json
git commit -m "feat(db): deterministic synthetic hierarchy generation (71 transformers, 120 devices)"
```

**Verification:** `python -m pytest tests/test_hierarchy_generation.py -v` — all pass, confirming 30/71/120, reserved `aa12`/`29017`, uniqueness, determinism, and no capacity correlation.

---

## Phase 3: Multi-Metric Reading Generation

**Objective:** Pure deterministic generation of 8 coherent metric series per device, with `energy` as a monotonically increasing cumulative meter; then bulk-load 1,383,360 rows.

**Files:**
- Create: `db/generators.py`, `db/seed_plant_monitoring.py`, `tests/test_generators.py`

**Interfaces:**
- Consumes: `db.hierarchy.build_hierarchy`, `config.metrics.METRIC_KEYS` (Phase 4 — declare the 8 keys locally in Phase 3 and switch the import in Phase 4).
- Produces:
  ```python
  INTERVAL_MINUTES: int = 30
  DAYS_OF_HISTORY: int = 30
  def build_timestamps(anchor: datetime) -> list[datetime]         # 1441 timestamps
  def generate_device_series(device_id: str, latitude: float, timestamps: list[datetime]) -> dict[str, list[float]]
  ```

- [ ] **Step 1: Write the failing tests**

Create `tests/test_generators.py`:

```python
"""Unit tests for db.generators - pure functions, no database required."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db.generators import (
    DAYS_OF_HISTORY,
    INTERVAL_MINUTES,
    build_timestamps,
    generate_device_series,
)

ANCHOR = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
EXPECTED_METRICS = {
    "temperature", "voltage", "current", "active_power",
    "reactive_power", "power_factor", "frequency", "energy",
}


class TestBuildTimestamps:
    def test_produces_1441_timestamps(self):
        assert len(build_timestamps(ANCHOR)) == 1441

    def test_spacing_is_30_minutes(self):
        ts = build_timestamps(ANCHOR)
        assert ts[1] - ts[0] == timedelta(minutes=INTERVAL_MINUTES)

    def test_spans_30_days_ending_at_anchor(self):
        ts = build_timestamps(ANCHOR)
        assert ts[-1] == ANCHOR
        assert ts[0] == ANCHOR - timedelta(days=DAYS_OF_HISTORY)


class TestGenerateDeviceSeries:
    def test_returns_all_eight_metrics(self):
        series = generate_device_series("plant-01-t1-d1", 30.8, build_timestamps(ANCHOR))
        assert set(series) == EXPECTED_METRICS

    def test_every_series_matches_timestamp_count(self):
        ts = build_timestamps(ANCHOR)
        series = generate_device_series("plant-01-t1-d1", 30.8, ts)
        for key, values in series.items():
            assert len(values) == len(ts), key

    def test_energy_is_monotonically_increasing(self):
        series = generate_device_series("plant-01-t1-d1", 30.8, build_timestamps(ANCHOR))
        energy = series["energy"]
        assert all(b >= a for a, b in zip(energy, energy[1:]))

    def test_energy_strictly_grows_over_the_window(self):
        series = generate_device_series("plant-01-t1-d1", 30.8, build_timestamps(ANCHOR))
        assert series["energy"][-1] > series["energy"][0]

    def test_non_energy_metrics_fluctuate(self):
        series = generate_device_series("plant-01-t1-d1", 30.8, build_timestamps(ANCHOR))
        for key in EXPECTED_METRICS - {"energy"}:
            assert len(set(series[key])) > 10, key

    def test_power_factor_within_zero_to_one(self):
        series = generate_device_series("plant-01-t1-d1", 30.8, build_timestamps(ANCHOR))
        assert all(0.0 < v <= 1.0 for v in series["power_factor"])

    def test_frequency_near_nominal(self):
        series = generate_device_series("plant-01-t1-d1", 30.8, build_timestamps(ANCHOR))
        assert all(49.0 < v < 51.0 for v in series["frequency"])

    def test_deterministic_for_same_device(self):
        ts = build_timestamps(ANCHOR)
        assert generate_device_series("plant-01-t1-d1", 30.8, ts) == generate_device_series(
            "plant-01-t1-d1", 30.8, ts
        )

    def test_different_devices_produce_different_series(self):
        ts = build_timestamps(ANCHOR)
        a = generate_device_series("plant-01-t1-d1", 30.8, ts)
        b = generate_device_series("plant-02-t1-d1", 30.8, ts)
        assert a["temperature"] != b["temperature"]

    def test_latitude_influences_temperature_baseline(self):
        ts = build_timestamps(ANCHOR)
        equator = generate_device_series("plant-09-t1-d1", 1.0, ts)["temperature"]
        polar = generate_device_series("plant-09-t1-d1", 65.0, ts)["temperature"]
        assert sum(equator) / len(equator) > sum(polar) / len(polar)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_generators.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db.generators'`

- [ ] **Step 3: Implement `db/generators.py`**

```python
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

    return {
        "temperature": temperature,
        "voltage": voltage,
        "current": current,
        "active_power": active_power,
        "reactive_power": reactive_power,
        "power_factor": power_factor,
        "frequency": frequency,
        "energy": energy,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_generators.py -v`
Expected: PASS

Note: `energy` rounds to 3 decimals after accumulating, so monotonicity holds only because each increment is strictly non-negative and typically ≫ 0.001. If `test_energy_is_monotonically_increasing` ever fails, the increment went negative — fix the `max(0.0, ...)` guard, do not weaken the test.

- [ ] **Step 5: Implement the seed script**

Create `db/seed_plant_monitoring.py`. It must:

- Load `db/seed_data/plants.json`.
- Call `build_hierarchy` for transformers/devices.
- Compute one shared anchor: `datetime.now(timezone.utc)` floored to the previous 30-minute boundary, so all devices share a timeline.
- Insert plants, transformers, devices via parameterized `INSERT ... ON CONFLICT DO NOTHING` through `db.engine.session_scope()`.
- Load readings with `COPY plant_monitoring.readings (device_id, metric, reading_ts, value) FROM STDIN WITH (FORMAT csv)` via `psycopg2`'s `cursor.copy_expert`, one buffer per device (11,528 rows each), obtained from the SQLAlchemy connection's raw DBAPI handle. `executemany` at 1.38M rows is minutes slower; COPY finishes in seconds.
- Support `--reset` (delete readings, devices, transformers, plants in FK-safe order) and skip seeding when readings already exist without `--reset`.
- Print a summary: plant/transformer/device/reading counts.
- Carry a module docstring repeating the synthetic-data provenance warning.

- [ ] **Step 6: Run the seed and verify row counts**

```bash
python -m db.seed_plant_monitoring --reset
docker compose exec postgres psql -U powerplant -d powerplant_demo -c "
SELECT (SELECT COUNT(*) FROM plant_monitoring.plants)       AS plants,
       (SELECT COUNT(*) FROM plant_monitoring.transformers) AS transformers,
       (SELECT COUNT(*) FROM plant_monitoring.devices)      AS devices,
       (SELECT COUNT(*) FROM plant_monitoring.readings)     AS readings;"
```

Expected exactly: `plants=30`, `transformers=71`, `devices=120`, `readings=1383360`.

- [ ] **Step 7: Verify the reserved identifiers and per-metric split landed**

```bash
docker compose exec postgres psql -U powerplant -d powerplant_demo -c "
SELECT t.transformer_code, d.device_code FROM plant_monitoring.devices d
JOIN plant_monitoring.transformers t ON t.transformer_id = d.transformer_id
WHERE d.device_id = 'plant-01-t1-d1';
SELECT metric, COUNT(*) FROM plant_monitoring.readings GROUP BY metric ORDER BY metric;"
```

Expected: `aa12 | 29017`, and 8 rows each showing `172920` (120 × 1441).

- [ ] **Step 8: Commit**

```bash
git add db/generators.py db/seed_plant_monitoring.py tests/test_generators.py
git commit -m "feat(db): multi-metric development data generation and bulk seed"
```

**Verification:** Unit tests pass; the two psql queries return exactly the counts above.

---

## Phase 4: Metric Configuration

**Objective:** Centralize metric presentation and aggregation semantics so no metric-specific logic leaks into services, pages or components.

**Files:**
- Create: `config/metrics.py`, `tests/test_metrics_config.py`
- Modify: `db/generators.py` (import the canonical key list)

**Interfaces:**
- Produces:
  ```python
  class Aggregation(str, Enum):
      STATISTICS = "statistics"
      DELTA = "delta"

  @dataclass(frozen=True)
  class MetricConfig:
      key: str
      label: str
      unit: str
      precision: int
      chart_type: str
      display_order: int
      aggregation: Aggregation

  METRICS: tuple[MetricConfig, ...]           # display_order ascending
  METRIC_KEYS: tuple[str, ...]
  def get_metric(key: str) -> MetricConfig | None
  def ordered_metrics() -> list[MetricConfig]
  def format_value(metric: MetricConfig, value: float | None) -> str   # "—" when None
  ```

- [ ] **Step 1: Write the failing tests**

Create `tests/test_metrics_config.py`:

```python
"""Unit tests for config.metrics."""
from __future__ import annotations

from config.metrics import (
    METRIC_KEYS,
    METRICS,
    Aggregation,
    format_value,
    get_metric,
    ordered_metrics,
)


class TestRegistry:
    def test_defines_eight_metrics(self):
        assert len(METRICS) == 8

    def test_keys_match_spec(self):
        assert set(METRIC_KEYS) == {
            "temperature", "voltage", "current", "active_power",
            "reactive_power", "power_factor", "frequency", "energy",
        }

    def test_display_orders_are_unique_and_sequential(self):
        assert sorted(m.display_order for m in METRICS) == list(range(1, 9))

    def test_ordered_metrics_sorted_by_display_order(self):
        orders = [m.display_order for m in ordered_metrics()]
        assert orders == sorted(orders)

    def test_reactive_power_uses_mvar_casing(self):
        assert get_metric("reactive_power").unit == "MVAr"

    def test_power_factor_has_empty_unit(self):
        assert get_metric("power_factor").unit == ""

    def test_units_match_development_display_units(self):
        expected = {
            "temperature": "°C", "voltage": "kV", "current": "A",
            "active_power": "MW", "reactive_power": "MVAr",
            "power_factor": "", "frequency": "Hz", "energy": "MWh",
        }
        assert {m.key: m.unit for m in METRICS} == expected

    def test_all_charts_are_line_charts(self):
        assert {m.chart_type for m in METRICS} == {"line"}

    def test_no_threshold_fields_defined(self):
        """Guard: production thresholds are explicitly out of scope."""
        fields = set(vars(METRICS[0]))
        assert not any("threshold" in f or "warning" in f or "critical" in f for f in fields)


class TestAggregation:
    def test_energy_uses_delta(self):
        assert get_metric("energy").aggregation is Aggregation.DELTA

    def test_all_other_metrics_use_statistics(self):
        for metric in METRICS:
            if metric.key != "energy":
                assert metric.aggregation is Aggregation.STATISTICS, metric.key


class TestLookup:
    def test_returns_config_for_known_key(self):
        assert get_metric("voltage").label == "Voltage"

    def test_returns_none_for_unknown_key(self):
        assert get_metric("not-a-metric") is None

    def test_returns_none_for_empty_key(self):
        assert get_metric("") is None


class TestFormatValue:
    def test_applies_configured_precision(self):
        assert format_value(get_metric("voltage"), 11.0246) == "11.02 kV"

    def test_temperature_uses_one_decimal(self):
        assert format_value(get_metric("temperature"), 31.44) == "31.4 °C"

    def test_power_factor_omits_unit_suffix(self):
        assert format_value(get_metric("power_factor"), 0.9723) == "0.972"

    def test_none_renders_em_dash(self):
        assert format_value(get_metric("voltage"), None) == "—"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_metrics_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config.metrics'`

- [ ] **Step 3: Implement `config/metrics.py`**

```python
"""
Centralized metric metadata.

Single source of truth for metric presentation (label, unit, precision,
chart type, display order) and for KPI/aggregation semantics. Services
dispatch on `aggregation`; components read presentation fields only.
Nothing outside this module may branch on a specific metric key.

DEVELOPMENT DISPLAY UNITS. Every unit below is a development display unit
chosen so the dashboard reads plausibly. Actual client units and metric
definitions must be mapped here when the real database/schema is available.

No warning/critical thresholds are defined. Thresholds are deliberately
absent until confirmed by the client.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Aggregation(str, Enum):
    """How a metric's period KPIs are computed."""

    STATISTICS = "statistics"  # Current / Minimum / Maximum / Average
    DELTA = "delta"            # Current meter value / Period change = last - first


@dataclass(frozen=True)
class MetricConfig:
    key: str
    label: str
    unit: str          # development display unit; "" for dimensionless
    precision: int     # decimal places for display
    chart_type: str
    display_order: int
    aggregation: Aggregation


METRICS: tuple[MetricConfig, ...] = (
    MetricConfig("temperature", "Temperature", "°C", 1, "line", 1, Aggregation.STATISTICS),
    MetricConfig("voltage", "Voltage", "kV", 2, "line", 2, Aggregation.STATISTICS),
    MetricConfig("current", "Current", "A", 1, "line", 3, Aggregation.STATISTICS),
    MetricConfig("active_power", "Active Power", "MW", 2, "line", 4, Aggregation.STATISTICS),
    MetricConfig("reactive_power", "Reactive Power", "MVAr", 2, "line", 5, Aggregation.STATISTICS),
    MetricConfig("power_factor", "Power Factor", "", 3, "line", 6, Aggregation.STATISTICS),
    MetricConfig("frequency", "Frequency", "Hz", 2, "line", 7, Aggregation.STATISTICS),
    # Cumulative meter: period KPI is last - first, never average/min/max.
    MetricConfig("energy", "Energy", "MWh", 1, "line", 8, Aggregation.DELTA),
)

METRIC_KEYS: tuple[str, ...] = tuple(m.key for m in METRICS)
DEFAULT_METRIC_KEY: str = METRICS[0].key

_BY_KEY: dict[str, MetricConfig] = {m.key: m for m in METRICS}


def get_metric(key: str) -> MetricConfig | None:
    return _BY_KEY.get(key)


def ordered_metrics() -> list[MetricConfig]:
    return sorted(METRICS, key=lambda m: m.display_order)


def format_value(metric: MetricConfig, value: float | None) -> str:
    """Format a value for display, or an em dash when absent."""
    if value is None:
        return "—"
    rendered = f"{value:.{metric.precision}f}"
    return f"{rendered} {metric.unit}" if metric.unit else rendered
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_metrics_config.py -v`
Expected: PASS

- [ ] **Step 5: Point the generator at the canonical key list**

In `db/generators.py`, add `from config.metrics import METRIC_KEYS` and append a guard at the end of `generate_device_series` before the return:

```python
    result = {...}  # the existing dict literal
    assert set(result) == set(METRIC_KEYS), "generator/metric registry drift"
    return result
```

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest tests/test_metrics_config.py tests/test_generators.py tests/test_hierarchy_generation.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add config/metrics.py tests/test_metrics_config.py db/generators.py
git commit -m "feat(config): centralized metric metadata with statistics/delta aggregation"
```

**Verification:** All three test modules pass; registry drift between generator and config is now caught automatically.

---

## Phase 5: Repository Implementation

**Objective:** Implement the only module containing SQL, exposing the hierarchy lookups and the four bounded reading queries, with batched multi-metric retrieval and safely bound parameters.

**Files:**
- Create: `repositories/plant_monitoring_repository.py`, `tests/conftest.py`, `tests/test_plant_monitoring_repository.py`

**Interfaces:**
- Consumes: `db.engine.session_scope`, `config.settings.monitoring.schema`.
- Produces:
  ```python
  @dataclass(frozen=True)
  class PlantRecord:
      plant_id: str; name: str; country: str; latitude: float
      longitude: float; capacity_mw: float | None
      primary_fuel: str | None; status: str

  @dataclass(frozen=True)
  class TransformerRecord:
      transformer_id: str; plant_id: str; transformer_code: str; status: str

  @dataclass(frozen=True)
  class DeviceRecord:
      device_id: str; transformer_id: str; device_code: str; status: str

  @dataclass(frozen=True)
  class DevicePath:
      plant_id: str; plant_name: str
      transformer_id: str; transformer_code: str
      device_id: str; device_code: str; device_status: str

  @dataclass(frozen=True)
  class RawReading:
      device_id: str; metric: str; timestamp: datetime; value: float

  def list_plants() -> list[PlantRecord]
  def get_plant(plant_id: str) -> PlantRecord | None
  def list_transformers(plant_id: str) -> list[TransformerRecord]
  def get_transformer(transformer_id: str) -> TransformerRecord | None
  def list_devices(transformer_id: str) -> list[DeviceRecord]
  def get_device(device_id: str) -> DeviceRecord | None
  def get_device_breadcrumb(device_id: str) -> DevicePath | None
  def count_hierarchy_by_plant() -> dict[str, tuple[int, int]]
  def get_latest_reading(device_id: str, metric: str) -> RawReading | None
  def get_latest_readings_for_device(device_id: str, metrics: list[str] | None = None) -> dict[str, RawReading]
  def get_readings_in_range(device_id: str, metric: str, start: datetime, end: datetime) -> list[RawReading]
  def get_readings_for_device_in_range(device_id: str, metrics: list[str], start: datetime, end: datetime) -> dict[str, list[RawReading]]
  ```

- [ ] **Step 1: Add the database-test marker and fixture**

Create `tests/conftest.py`:

```python
"""Shared pytest configuration.

Repository tests need the seeded local PostgreSQL. They are marked `db` so
the pure-logic suite can run without Docker:
    python -m pytest -m "not db"
"""
from __future__ import annotations

import pytest

from db.engine import check_connection


_DB_AVAILABLE: bool | None = None


def pytest_configure(config):
    config.addinivalue_line("markers", "db: requires a seeded local PostgreSQL")


@pytest.fixture(autouse=True)
def _skip_db_tests_without_database(request):
    """Skip db-marked tests when PostgreSQL is not reachable.

    The connection check runs once per session, not once per test - it opens
    a real connection and there are dozens of db-marked tests.
    """
    global _DB_AVAILABLE
    if not request.node.get_closest_marker("db"):
        return
    if _DB_AVAILABLE is None:
        _DB_AVAILABLE = check_connection()
    if not _DB_AVAILABLE:
        pytest.skip("local PostgreSQL not available")
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_plant_monitoring_repository.py`:

```python
"""Repository tests against the seeded local PostgreSQL."""
from __future__ import annotations

from datetime import timedelta

import pytest

from repositories import plant_monitoring_repository as repo

pytestmark = pytest.mark.db

RESERVED_DEVICE_ID = "plant-01-t1-d1"


class TestHierarchy:
    def test_lists_thirty_plants(self):
        assert len(repo.list_plants()) == 30

    def test_get_plant_returns_record(self):
        plant = repo.get_plant("plant-01")
        assert plant is not None and plant.plant_id == "plant-01"

    def test_get_plant_returns_none_for_unknown_id(self):
        assert repo.get_plant("does-not-exist") is None

    def test_transformers_belong_to_requested_plant(self):
        transformers = repo.list_transformers("plant-01")
        assert transformers
        assert all(t.plant_id == "plant-01" for t in transformers)

    def test_total_transformers_is_71(self):
        total = sum(len(repo.list_transformers(p.plant_id)) for p in repo.list_plants())
        assert total == 71

    def test_devices_belong_to_requested_transformer(self):
        devices = repo.list_devices("plant-01-t1")
        assert devices
        assert all(d.transformer_id == "plant-01-t1" for d in devices)

    def test_get_device_returns_none_for_unknown_id(self):
        assert repo.get_device("nope") is None

    def test_breadcrumb_resolves_full_path_in_one_call(self):
        path = repo.get_device_breadcrumb(RESERVED_DEVICE_ID)
        assert path is not None
        assert path.plant_id == "plant-01"
        assert path.transformer_code == "aa12"
        assert path.device_code == "29017"
        assert path.plant_name

    def test_breadcrumb_returns_none_for_unknown_device(self):
        assert repo.get_device_breadcrumb("nope") is None

    def test_hierarchy_counts_cover_all_plants(self):
        counts = repo.count_hierarchy_by_plant()
        assert len(counts) == 30
        assert sum(t for t, _ in counts.values()) == 71
        assert sum(d for _, d in counts.values()) == 120


class TestLatestReadings:
    def test_returns_latest_reading(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        assert latest is not None
        assert latest.metric == "temperature"
        assert latest.device_id == RESERVED_DEVICE_ID

    def test_returns_none_for_unknown_metric(self):
        assert repo.get_latest_reading(RESERVED_DEVICE_ID, "not-a-metric") is None

    def test_returns_none_for_unknown_device(self):
        assert repo.get_latest_reading("nope", "temperature") is None

    def test_batched_latest_returns_all_eight_metrics(self):
        latest = repo.get_latest_readings_for_device(RESERVED_DEVICE_ID)
        assert len(latest) == 8

    def test_batched_latest_matches_single_metric_query(self):
        batched = repo.get_latest_readings_for_device(RESERVED_DEVICE_ID)
        single = repo.get_latest_reading(RESERVED_DEVICE_ID, "voltage")
        assert batched["voltage"] == single

    def test_batched_latest_honours_metric_filter(self):
        latest = repo.get_latest_readings_for_device(
            RESERVED_DEVICE_ID, ["voltage", "energy"]
        )
        assert set(latest) == {"voltage", "energy"}

    def test_batched_latest_with_empty_metric_list_returns_empty(self):
        assert repo.get_latest_readings_for_device(RESERVED_DEVICE_ID, []) == {}


class TestRangeQueries:
    def test_returns_only_readings_inside_range(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        start = latest.timestamp - timedelta(hours=24)
        rows = repo.get_readings_in_range(RESERVED_DEVICE_ID, "temperature", start, latest.timestamp)
        assert rows
        assert all(start <= r.timestamp <= latest.timestamp for r in rows)

    def test_24h_window_returns_49_inclusive_samples(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        start = latest.timestamp - timedelta(hours=24)
        rows = repo.get_readings_in_range(RESERVED_DEVICE_ID, "temperature", start, latest.timestamp)
        assert len(rows) == 49  # 48 intervals, both endpoints inclusive

    def test_range_is_ordered_ascending(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        rows = repo.get_readings_in_range(
            RESERVED_DEVICE_ID, "temperature", latest.timestamp - timedelta(days=7), latest.timestamp
        )
        assert [r.timestamp for r in rows] == sorted(r.timestamp for r in rows)

    def test_range_outside_data_returns_empty(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        far_past = latest.timestamp - timedelta(days=400)
        rows = repo.get_readings_in_range(
            RESERVED_DEVICE_ID, "temperature", far_past, far_past + timedelta(days=1)
        )
        assert rows == []

    def test_batched_range_returns_requested_metrics(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        start = latest.timestamp - timedelta(hours=24)
        result = repo.get_readings_for_device_in_range(
            RESERVED_DEVICE_ID, ["temperature", "voltage", "energy"], start, latest.timestamp
        )
        assert set(result) == {"temperature", "voltage", "energy"}
        assert all(len(v) == 49 for v in result.values())

    def test_batched_range_matches_single_metric_range(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "voltage")
        start = latest.timestamp - timedelta(hours=24)
        batched = repo.get_readings_for_device_in_range(
            RESERVED_DEVICE_ID, ["voltage"], start, latest.timestamp
        )
        single = repo.get_readings_in_range(RESERVED_DEVICE_ID, "voltage", start, latest.timestamp)
        assert batched["voltage"] == single

    def test_batched_range_includes_key_for_metric_with_no_rows(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        far_past = latest.timestamp - timedelta(days=400)
        result = repo.get_readings_for_device_in_range(
            RESERVED_DEVICE_ID, ["temperature", "voltage"], far_past, far_past + timedelta(days=1)
        )
        assert result == {"temperature": [], "voltage": []}

    def test_batched_range_with_empty_metric_list_returns_empty(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        result = repo.get_readings_for_device_in_range(
            RESERVED_DEVICE_ID, [], latest.timestamp - timedelta(hours=1), latest.timestamp
        )
        assert result == {}

    def test_metric_names_are_bound_not_interpolated(self):
        """A SQL metacharacter in a metric name must be inert, not an error."""
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        result = repo.get_readings_for_device_in_range(
            RESERVED_DEVICE_ID,
            ["temperature", "'); DROP TABLE plant_monitoring.readings; --"],
            latest.timestamp - timedelta(hours=1),
            latest.timestamp,
        )
        assert result["'); DROP TABLE plant_monitoring.readings; --"] == []
        assert repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature") is not None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_plant_monitoring_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'repositories.plant_monitoring_repository'`

- [ ] **Step 4: Implement the repository**

Create `repositories/plant_monitoring_repository.py`. Structure it as:

Module docstring — the only module in the application containing SQL; no generic raw-query helpers; identifiers are never interpolated; metric lists are bound with SQLAlchemy expanding parameters; no unbounded reading query exists by design, because PostgreSQL must always perform device/metric/time-range filtering.

The five dataclasses exactly as listed in the Interfaces block above.

A module-level `_SCHEMA = monitoring.schema` read once from `config.settings`, plus small private row-mapper functions (`_to_plant`, `_to_transformer`, `_to_device`, `_to_reading`) so each query function stays short.

Hierarchy queries — plain parameterized `SELECT`s ordered by `name` / `transformer_code` / `device_code`. `get_device_breadcrumb` is a single JOIN:

```python
def get_device_breadcrumb(device_id: str) -> DevicePath | None:
    with session_scope() as session:
        row = session.execute(
            text(
                f"""
                SELECT p.plant_id, p.name, t.transformer_id, t.transformer_code,
                       d.device_id, d.device_code, d.status
                FROM {_SCHEMA}.devices d
                JOIN {_SCHEMA}.transformers t ON t.transformer_id = d.transformer_id
                JOIN {_SCHEMA}.plants p       ON p.plant_id = t.plant_id
                WHERE d.device_id = :device_id
                """
            ),
            {"device_id": device_id},
        ).first()
    return DevicePath(*row) if row else None
```

`count_hierarchy_by_plant` is one grouped query returning `(plant_id, transformer_count, device_count)` for the overview table:

```sql
SELECT p.plant_id,
       COUNT(DISTINCT t.transformer_id) AS transformers,
       COUNT(d.device_id)               AS devices
FROM {schema}.plants p
LEFT JOIN {schema}.transformers t ON t.plant_id = p.plant_id
LEFT JOIN {schema}.devices d      ON d.transformer_id = t.transformer_id
GROUP BY p.plant_id
```

Reading queries — `get_latest_reading` is `ORDER BY reading_ts DESC LIMIT 1`. The batched latest uses `DISTINCT ON`, with the metric filter applied only when a list is supplied:

```python
def get_latest_readings_for_device(
    device_id: str, metrics: list[str] | None = None
) -> dict[str, RawReading]:
    """One query for all requested metrics - never one query per metric."""
    if metrics is not None and not metrics:
        return {}

    filter_sql = "AND metric IN :metrics" if metrics is not None else ""
    stmt = text(
        f"""
        SELECT DISTINCT ON (metric) device_id, metric, reading_ts, value
        FROM {_SCHEMA}.readings
        WHERE device_id = :device_id {filter_sql}
        ORDER BY metric, reading_ts DESC
        """
    )
    params: dict = {"device_id": device_id}
    if metrics is not None:
        stmt = stmt.bindparams(bindparam("metrics", expanding=True))
        params["metrics"] = metrics

    with session_scope() as session:
        rows = session.execute(stmt, params).all()
    return {r[1]: _to_reading(r) for r in rows}
```

Range queries use explicit inclusive bounds. The batched range pre-seeds every requested metric with an empty list so callers always get a key:

```python
def get_readings_for_device_in_range(
    device_id: str, metrics: list[str], start: datetime, end: datetime
) -> dict[str, list[RawReading]]:
    """One query for all requested metrics over one common time window."""
    if not metrics:
        return {}

    stmt = text(
        f"""
        SELECT device_id, metric, reading_ts, value
        FROM {_SCHEMA}.readings
        WHERE device_id = :device_id
          AND metric IN :metrics
          AND reading_ts >= :start
          AND reading_ts <= :end
        ORDER BY metric, reading_ts ASC
        """
    ).bindparams(bindparam("metrics", expanding=True))

    with session_scope() as session:
        rows = session.execute(
            stmt,
            {"device_id": device_id, "metrics": metrics, "start": start, "end": end},
        ).all()

    result: dict[str, list[RawReading]] = {m: [] for m in metrics}
    for row in rows:
        result[row[1]].append(_to_reading(row))
    return result
```

`_SCHEMA` is the only f-string substitution anywhere in the module, and it comes from application configuration, never from browser or user input.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_plant_monitoring_repository.py -v`
Expected: PASS — 28 tests.

If `test_24h_window_returns_49_inclusive_samples` fails with 48, the query used an exclusive bound — fix the SQL, not the test.

- [ ] **Step 6: Confirm the pure-logic suite still runs without a database**

Run: `python -m pytest -m "not db" -v`
Expected: PASS, with the repository tests deselected.

- [ ] **Step 7: Commit**

```bash
git add repositories/plant_monitoring_repository.py tests/conftest.py tests/test_plant_monitoring_repository.py
git commit -m "feat(repositories): normalized hierarchy and batched bounded reading queries"
```

**Verification:** 28 repository tests pass against seeded PostgreSQL; `pytest -m "not db"` still passes with Docker stopped; the injection test confirms metric names are bound, not interpolated.

---

## Phase 6: Service Implementation

**Objective:** Build the hierarchy-validation service and the monitoring service with view models, statistics/delta dispatch, per-metric freshness, a common dashboard window for the full-device view, and the two empty-data cases.

**Files:**
- Create: `services/hierarchy_service.py`, `tests/test_hierarchy_service.py`, `tests/test_monitoring_service.py`
- Modify: `services/monitoring_service.py` (full rewrite)

**Interfaces:**
- Consumes: everything produced by Phases 4 and 5, plus `config.settings.monitoring`.
- Produces:
  ```python
  # services/monitoring_service.py
  class Freshness(str, Enum):
      FRESH = "fresh"; STALE = "stale"; NO_DATA = "no_data"

  class MonitoringCondition(str, Enum):
      NORMAL = "normal"; WARNING = "warning"
      CRITICAL = "critical"; UNKNOWN = "unknown"

  class Period(str, Enum):
      LAST_24H = "24h"; LAST_7D = "7d"; LAST_30D = "30d"; CUSTOM = "custom"

  @dataclass(frozen=True)
  class Reading:
      timestamp: datetime; value: float

  @dataclass(frozen=True)
  class MetricSnapshot:
      metric: MetricConfig; current: float | None
      last_updated: datetime | None
      freshness: Freshness; condition: MonitoringCondition

  @dataclass(frozen=True)
  class MetricView:
      metric: MetricConfig
      current: float | None
      minimum: float | None; maximum: float | None; average: float | None
      period_change: float | None
      series: list[Reading]
      last_updated: datetime | None
      freshness: Freshness; condition: MonitoringCondition
      has_data: bool

  def evaluate_freshness(last_updated: datetime | None, now: datetime | None = None) -> Freshness
  def period_start(period: Period, anchor: datetime) -> datetime | None
  def get_metric_view(device_id, metric_key, period, custom_start=None, custom_end=None) -> MetricView | None
  def get_device_snapshot(device_id: str) -> list[MetricSnapshot]
  def get_device_full_view(device_id, period, custom_start=None, custom_end=None) -> dict[str, MetricView]

  # services/hierarchy_service.py
  def list_plants(include_inactive: bool = False) -> list[PlantRecord]
  def list_transformers(plant_id: str, include_inactive: bool = False) -> list[TransformerRecord]
  def list_devices(transformer_id: str, include_inactive: bool = False) -> list[DeviceRecord]
  def get_plant_or_none(plant_id: str) -> PlantRecord | None
  def get_transformer_in_plant(plant_id: str, transformer_id: str) -> TransformerRecord | None
  def get_device_in_transformer(transformer_id: str, device_id: str) -> DeviceRecord | None
  def get_device_context(device_id: str) -> DevicePath | None
  def get_plant_hierarchy_counts() -> dict[str, tuple[int, int]]
  ```

- [ ] **Step 1: Write the failing pure-logic tests**

Create `tests/test_monitoring_service.py`. These test the aggregation, freshness and empty-data rules without a database, by exercising the helpers directly and by monkeypatching the repository for the view builders.

```python
"""Unit tests for services.monitoring_service - no database required."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from config.metrics import get_metric
from repositories.plant_monitoring_repository import RawReading
from services import monitoring_service as svc
from services.monitoring_service import (
    Freshness,
    MonitoringCondition,
    Period,
    Reading,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
DEVICE = "plant-01-t1-d1"


def _series(values: list[float], end: datetime = NOW) -> list[Reading]:
    """Build a 30-min-spaced ascending series ending at `end`."""
    return [
        Reading(timestamp=end - timedelta(minutes=30 * (len(values) - 1 - i)), value=v)
        for i, v in enumerate(values)
    ]


class TestEvaluateFreshness:
    def test_no_timestamp_is_no_data(self):
        assert svc.evaluate_freshness(None, NOW) is Freshness.NO_DATA

    def test_recent_reading_is_fresh(self):
        assert svc.evaluate_freshness(NOW - timedelta(minutes=20), NOW) is Freshness.FRESH

    def test_just_inside_threshold_is_fresh(self):
        assert svc.evaluate_freshness(NOW - timedelta(minutes=89), NOW) is Freshness.FRESH

    def test_beyond_three_intervals_is_stale(self):
        assert svc.evaluate_freshness(NOW - timedelta(minutes=91), NOW) is Freshness.STALE

    def test_far_past_is_stale_not_no_data(self):
        """Stale means late data; no_data means no reading ever."""
        assert svc.evaluate_freshness(NOW - timedelta(days=5), NOW) is Freshness.STALE


class TestComputeStatistics:
    def test_returns_min_max_average(self):
        assert svc._compute_statistics(_series([10.0, 20.0, 30.0])) == (10.0, 30.0, 20.0)

    def test_single_reading_returns_that_value(self):
        assert svc._compute_statistics(_series([7.5])) == (7.5, 7.5, 7.5)

    def test_empty_series_returns_all_none(self):
        assert svc._compute_statistics([]) == (None, None, None)


class TestComputeDelta:
    def test_returns_last_minus_first(self):
        assert svc._compute_delta(_series([100.0, 110.0, 125.0])) == pytest.approx(25.0)

    def test_requires_at_least_two_readings(self):
        assert svc._compute_delta(_series([100.0])) is None

    def test_empty_series_returns_none(self):
        assert svc._compute_delta([]) is None

    def test_negative_delta_is_returned_not_suppressed(self):
        """A counter reset shows as a negative delta; we surface it, not hide it."""
        assert svc._compute_delta(_series([500.0, 10.0])) == pytest.approx(-490.0)


class TestPeriodStart:
    def test_24h(self):
        assert svc.period_start(Period.LAST_24H, NOW) == NOW - timedelta(hours=24)

    def test_7d(self):
        assert svc.period_start(Period.LAST_7D, NOW) == NOW - timedelta(days=7)

    def test_30d(self):
        assert svc.period_start(Period.LAST_30D, NOW) == NOW - timedelta(days=30)

    def test_custom_returns_none(self):
        assert svc.period_start(Period.CUSTOM, NOW) is None


class TestGetMetricView:
    @pytest.fixture(autouse=True)
    def _stub_repo(self, monkeypatch):
        self.latest: RawReading | None = RawReading(DEVICE, "temperature", NOW, 31.4)
        self.range_rows: list[RawReading] = [
            RawReading(DEVICE, "temperature", r.timestamp, r.value)
            for r in _series([30.0, 31.0, 32.0])
        ]
        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo, "get_latest_reading", lambda device_id, metric: self.latest
        )
        monkeypatch.setattr(
            svc.repo,
            "get_readings_in_range",
            lambda device_id, metric, start, end: self.range_rows,
        )

    def test_returns_none_for_unknown_metric(self):
        assert svc.get_metric_view(DEVICE, "not-a-metric", Period.LAST_24H) is None

    def test_statistics_metric_populates_min_max_average(self):
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert (view.minimum, view.maximum, view.average) == (30.0, 32.0, 31.0)

    def test_statistics_metric_leaves_period_change_none(self):
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert view.period_change is None

    def test_current_is_latest_available_not_period_last(self):
        """Current must ignore the period; series ends at 32.0 but latest is 31.4."""
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert view.current == pytest.approx(31.4)

    def test_condition_is_always_unknown(self):
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert view.condition is MonitoringCondition.UNKNOWN

    def test_delta_metric_populates_period_change_only(self, monkeypatch):
        self.latest = RawReading(DEVICE, "energy", NOW, 8142.0)
        self.range_rows = [
            RawReading(DEVICE, "energy", r.timestamp, r.value)
            for r in _series([8000.0, 8070.0, 8142.0])
        ]
        view = svc.get_metric_view(DEVICE, "energy", Period.LAST_24H)
        assert view.period_change == pytest.approx(142.0)
        assert (view.minimum, view.maximum, view.average) == (None, None, None)

    def test_delta_metric_with_single_reading_has_no_period_change(self):
        self.latest = RawReading(DEVICE, "energy", NOW, 8142.0)
        self.range_rows = [RawReading(DEVICE, "energy", NOW, 8142.0)]
        view = svc.get_metric_view(DEVICE, "energy", Period.LAST_24H)
        assert view.period_change is None

    def test_no_reading_ever_yields_empty_view(self):
        self.latest = None
        self.range_rows = []
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert view.has_data is False
        assert view.current is None
        assert view.last_updated is None
        assert view.series == []
        assert (view.minimum, view.maximum, view.average, view.period_change) == (
            None, None, None, None,
        )
        assert view.freshness is Freshness.NO_DATA

    def test_empty_period_keeps_current_and_last_updated(self):
        """Latest exists but the selected range holds no points."""
        self.range_rows = []
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert view.has_data is True
        assert view.current == pytest.approx(31.4)
        assert view.last_updated == NOW
        assert view.series == []
        assert (view.minimum, view.maximum, view.average) == (None, None, None)

    def test_custom_period_uses_explicit_bounds(self, monkeypatch):
        captured: dict = {}

        def _capture(device_id, metric, start, end):
            captured["start"], captured["end"] = start, end
            return self.range_rows

        monkeypatch.setattr(svc.repo, "get_readings_in_range", _capture)
        start = NOW - timedelta(days=3)
        end = NOW - timedelta(days=1)
        svc.get_metric_view(DEVICE, "temperature", Period.CUSTOM, start, end)
        assert (captured["start"], captured["end"]) == (start, end)

    def test_custom_period_without_bounds_returns_empty_series(self):
        view = svc.get_metric_view(DEVICE, "temperature", Period.CUSTOM, None, None)
        assert view.series == []


class TestGetDeviceSnapshot:
    def test_returns_one_snapshot_per_metric_in_display_order(self, monkeypatch):
        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo,
            "get_latest_readings_for_device",
            lambda device_id, metrics=None: {
                "temperature": RawReading(DEVICE, "temperature", NOW, 31.4)
            },
        )
        snapshots = svc.get_device_snapshot(DEVICE)
        assert len(snapshots) == 8
        assert [s.metric.display_order for s in snapshots] == list(range(1, 9))

    def test_metric_without_reading_is_no_data(self, monkeypatch):
        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo,
            "get_latest_readings_for_device",
            lambda device_id, metrics=None: {
                "temperature": RawReading(DEVICE, "temperature", NOW, 31.4)
            },
        )
        snapshots = {s.metric.key: s for s in svc.get_device_snapshot(DEVICE)}
        assert snapshots["temperature"].freshness is Freshness.FRESH
        assert snapshots["voltage"].freshness is Freshness.NO_DATA
        assert snapshots["voltage"].current is None

    def test_issues_exactly_one_repository_call(self, monkeypatch):
        calls = []
        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo,
            "get_latest_readings_for_device",
            lambda device_id, metrics=None: calls.append(device_id) or {},
        )
        svc.get_device_snapshot(DEVICE)
        assert len(calls) == 1


class TestGetDeviceFullView:
    @pytest.fixture(autouse=True)
    def _stub_repo(self, monkeypatch):
        self.range_calls: list[tuple] = []
        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo,
            "get_latest_readings_for_device",
            lambda device_id, metrics=None: {
                # temperature is 2h behind the newest metric on this device
                "temperature": RawReading(DEVICE, "temperature", NOW - timedelta(hours=2), 31.4),
                "voltage": RawReading(DEVICE, "voltage", NOW, 11.02),
            },
        )

        def _batched(device_id, metrics, start, end):
            self.range_calls.append((tuple(metrics), start, end))
            return {m: [] for m in metrics}

        monkeypatch.setattr(svc.repo, "get_readings_for_device_in_range", _batched)

    def test_issues_exactly_one_batched_range_call(self):
        svc.get_device_full_view(DEVICE, Period.LAST_24H)
        assert len(self.range_calls) == 1

    def test_uses_one_common_window_anchored_to_newest_metric(self):
        svc.get_device_full_view(DEVICE, Period.LAST_24H)
        _, start, end = self.range_calls[0]
        assert end == NOW
        assert start == NOW - timedelta(hours=24)

    def test_each_metric_keeps_its_own_last_updated(self):
        views = svc.get_device_full_view(DEVICE, Period.LAST_24H)
        assert views["temperature"].last_updated == NOW - timedelta(hours=2)
        assert views["voltage"].last_updated == NOW

    def test_freshness_evaluated_per_metric_independently(self):
        views = svc.get_device_full_view(DEVICE, Period.LAST_24H)
        assert views["temperature"].freshness is Freshness.STALE
        assert views["voltage"].freshness is Freshness.FRESH

    def test_returns_a_view_for_every_metric(self):
        views = svc.get_device_full_view(DEVICE, Period.LAST_24H)
        assert len(views) == 8

    def test_custom_range_uses_explicit_bounds_not_anchor(self):
        start = NOW - timedelta(days=3)
        end = NOW - timedelta(days=1)
        svc.get_device_full_view(DEVICE, Period.CUSTOM, start, end)
        _, used_start, used_end = self.range_calls[0]
        assert (used_start, used_end) == (start, end)

    def test_device_with_no_readings_at_all(self, monkeypatch):
        monkeypatch.setattr(
            svc.repo, "get_latest_readings_for_device", lambda device_id, metrics=None: {}
        )
        views = svc.get_device_full_view(DEVICE, Period.LAST_24H)
        assert len(views) == 8
        assert all(v.has_data is False for v in views.values())
        assert all(v.freshness is Freshness.NO_DATA for v in views.values())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_monitoring_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'Freshness' from 'services.monitoring_service'`

- [ ] **Step 3: Rewrite `services/monitoring_service.py`**

Replace the file entirely. Structure:

Module docstring — owns view models, aggregation dispatch and freshness; the only place that branches on `MetricConfig.aggregation`; three concepts stay independent (administrative status lives in `hierarchy_service`, freshness is computed here, monitoring condition is not implemented and always `UNKNOWN`); freshness policy comes from `config.settings.monitoring`, never hard-coded.

```python
from repositories import plant_monitoring_repository as repo
from config.metrics import Aggregation, MetricConfig, ordered_metrics, get_metric, METRIC_KEYS
from config.settings import monitoring
```

The `Freshness`, `MonitoringCondition`, `Period` enums and the `Reading`, `MetricSnapshot`, `MetricView` dataclasses exactly as in the Interfaces block.

```python
def _now() -> datetime:
    """Indirection so tests can pin the clock."""
    return datetime.now(timezone.utc)


def _align_tz(value: datetime, reference: datetime) -> datetime:
    """Attach the reference's tzinfo to a naive datetime (Dash date pickers
    hand us naive values; stored timestamps are timestamptz)."""
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    return value


def evaluate_freshness(last_updated: datetime | None, now: datetime | None = None) -> Freshness:
    """Data-delivery signal only. NEVER an electrical warning condition."""
    if last_updated is None:
        return Freshness.NO_DATA
    reference = now or _now()
    age = reference - _align_tz(last_updated, reference)
    return (
        Freshness.STALE
        if age > timedelta(minutes=monitoring.stale_after_minutes)
        else Freshness.FRESH
    )


def _current_condition(_view_inputs) -> MonitoringCondition:
    """Placeholder. No client-confirmed thresholds exist, so every metric
    reports UNKNOWN. Wiring this through now means adding real thresholds
    later requires no change to view models, components or callbacks."""
    return MonitoringCondition.UNKNOWN


def _compute_statistics(series: list[Reading]) -> tuple[float | None, float | None, float | None]:
    if not series:
        return None, None, None
    values = [r.value for r in series]
    return min(values), max(values), sum(values) / len(values)


def _compute_delta(series: list[Reading]) -> float | None:
    """Period change for cumulative meters.

    Requires at least TWO readings - a single point has no change. A negative
    result may indicate a counter reset or data-quality condition; it is
    surfaced as-is, with no reset handling at this stage.
    """
    if len(series) < 2:
        return None
    return series[-1].value - series[0].value


def period_start(period: Period, anchor: datetime) -> datetime | None:
    deltas = {
        Period.LAST_24H: timedelta(hours=24),
        Period.LAST_7D: timedelta(days=7),
        Period.LAST_30D: timedelta(days=30),
    }
    delta = deltas.get(period)
    return anchor - delta if delta else None  # CUSTOM handled by the caller
```

A single private builder both view functions share, so aggregation dispatch exists in exactly one place:

```python
def _build_metric_view(
    metric: MetricConfig,
    latest: repo.RawReading | None,
    series: list[Reading],
    now: datetime,
) -> MetricView:
    minimum = maximum = average = period_change = None
    if metric.aggregation is Aggregation.DELTA:
        period_change = _compute_delta(series)
    else:
        minimum, maximum, average = _compute_statistics(series)

    last_updated = latest.timestamp if latest else None
    return MetricView(
        metric=metric,
        current=latest.value if latest else None,   # latest available, period-independent
        minimum=minimum,
        maximum=maximum,
        average=average,
        period_change=period_change,
        series=series,
        last_updated=last_updated,
        freshness=evaluate_freshness(last_updated, now),
        condition=_current_condition(None),
        has_data=latest is not None,
    )


def _resolve_window(
    period: Period, anchor: datetime | None,
    custom_start: datetime | None, custom_end: datetime | None,
) -> tuple[datetime, datetime] | None:
    """Return the (start, end) window, or None when no window is computable."""
    if period is Period.CUSTOM:
        if custom_start is None or custom_end is None:
            return None
        return custom_start, custom_end
    if anchor is None:
        return None
    start = period_start(period, anchor)
    return (start, anchor) if start else None
```

Then the three public functions:

- `get_metric_view` — validate `metric_key` via `get_metric`, return `None` if unknown. Call `repo.get_latest_reading`. If `None`, build an empty view immediately with no range query. Otherwise resolve the window (anchor = `latest.timestamp`, aligned via `_align_tz` for custom bounds), call `repo.get_readings_in_range`, map to `Reading`, and hand both to `_build_metric_view`.
- `get_device_snapshot` — one `repo.get_latest_readings_for_device(device_id)` call, then one `MetricSnapshot` per metric from `ordered_metrics()`, using `.get(key)` so metrics with no reading become `NO_DATA`.
- `get_device_full_view` — one batched latest call; **dashboard anchor = `max(r.timestamp for r in latest.values())`** across the requested metrics; resolve one common window from that anchor (or the explicit custom bounds); one batched `repo.get_readings_for_device_in_range` call; build one `MetricView` per metric, each passing **its own** `latest.get(key)` so `last_updated` and freshness stay per-metric. If no latest readings exist at all, return eight empty views without a range query.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_monitoring_service.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing hierarchy-service tests**

Create `tests/test_hierarchy_service.py`:

```python
"""Unit tests for services.hierarchy_service."""
from __future__ import annotations

import pytest

from repositories.plant_monitoring_repository import (
    DevicePath,
    DeviceRecord,
    PlantRecord,
    TransformerRecord,
)
from services import hierarchy_service as svc


def _plant(plant_id: str, status: str = "active") -> PlantRecord:
    return PlantRecord(plant_id, f"Plant {plant_id}", "Testland", 0.0, 0.0, 100.0, "Gas", status)


def _transformer(tid: str, plant_id: str, status: str = "active") -> TransformerRecord:
    return TransformerRecord(tid, plant_id, "tt01", status)


def _device(did: str, tid: str, status: str = "active") -> DeviceRecord:
    return DeviceRecord(did, tid, "29001", status)


class TestActiveFiltering:
    def test_list_plants_excludes_inactive_by_default(self, monkeypatch):
        monkeypatch.setattr(
            svc.repo, "list_plants", lambda: [_plant("a"), _plant("b", "inactive")]
        )
        assert [p.plant_id for p in svc.list_plants()] == ["a"]

    def test_list_plants_can_include_inactive(self, monkeypatch):
        monkeypatch.setattr(
            svc.repo, "list_plants", lambda: [_plant("a"), _plant("b", "inactive")]
        )
        assert len(svc.list_plants(include_inactive=True)) == 2

    def test_list_transformers_excludes_inactive_by_default(self, monkeypatch):
        monkeypatch.setattr(
            svc.repo,
            "list_transformers",
            lambda plant_id: [_transformer("t1", "a"), _transformer("t2", "a", "inactive")],
        )
        assert [t.transformer_id for t in svc.list_transformers("a")] == ["t1"]

    def test_list_devices_excludes_inactive_by_default(self, monkeypatch):
        monkeypatch.setattr(
            svc.repo,
            "list_devices",
            lambda tid: [_device("d1", "t1"), _device("d2", "t1", "inactive")],
        )
        assert [d.device_id for d in svc.list_devices("t1")] == ["d1"]


class TestParentValidation:
    def test_transformer_in_correct_plant_is_returned(self, monkeypatch):
        monkeypatch.setattr(svc.repo, "get_transformer", lambda tid: _transformer("t1", "a"))
        assert svc.get_transformer_in_plant("a", "t1") is not None

    def test_transformer_in_wrong_plant_returns_none(self, monkeypatch):
        """Confused-deputy guard: valid ID, wrong parent."""
        monkeypatch.setattr(svc.repo, "get_transformer", lambda tid: _transformer("t1", "a"))
        assert svc.get_transformer_in_plant("b", "t1") is None

    def test_unknown_transformer_returns_none(self, monkeypatch):
        monkeypatch.setattr(svc.repo, "get_transformer", lambda tid: None)
        assert svc.get_transformer_in_plant("a", "t9") is None

    def test_device_in_wrong_transformer_returns_none(self, monkeypatch):
        monkeypatch.setattr(svc.repo, "get_device", lambda did: _device("d1", "t1"))
        assert svc.get_device_in_transformer("t2", "d1") is None

    def test_device_in_correct_transformer_is_returned(self, monkeypatch):
        monkeypatch.setattr(svc.repo, "get_device", lambda did: _device("d1", "t1"))
        assert svc.get_device_in_transformer("t1", "d1") is not None


class TestDeviceContext:
    def test_returns_path_for_known_device(self, monkeypatch):
        path = DevicePath("p1", "Plant One", "t1", "aa12", "d1", "29017", "active")
        monkeypatch.setattr(svc.repo, "get_device_breadcrumb", lambda did: path)
        assert svc.get_device_context("d1") == path

    def test_returns_none_for_unknown_device(self, monkeypatch):
        monkeypatch.setattr(svc.repo, "get_device_breadcrumb", lambda did: None)
        assert svc.get_device_context("nope") is None
```

- [ ] **Step 6: Run to verify failure, then implement `services/hierarchy_service.py`**

Run: `python -m pytest tests/test_hierarchy_service.py -v` → FAIL (`No module named 'services.hierarchy_service'`).

Implement it as a thin validation/filtering layer over the repository. Docstring: administrative `status` is read **only here**, only to decide what is selectable for live monitoring; it is never combined with, or used as a substitute for, computed monitoring status or data freshness.

```python
ACTIVE = "active"


def _active_only(records: list, include_inactive: bool) -> list:
    return records if include_inactive else [r for r in records if r.status == ACTIVE]


def list_plants(include_inactive: bool = False) -> list[PlantRecord]:
    return _active_only(repo.list_plants(), include_inactive)
```

`list_transformers` / `list_devices` follow the same shape. `get_plant_or_none` delegates to `repo.get_plant`. `get_transformer_in_plant` fetches the transformer and returns `None` unless `transformer.plant_id == plant_id`. `get_device_in_transformer` mirrors that with `device.transformer_id`. `get_device_context` delegates to `repo.get_device_breadcrumb`. `get_plant_hierarchy_counts` delegates to `repo.count_hierarchy_by_plant`.

- [ ] **Step 7: Run both service test modules**

Run: `python -m pytest tests/test_hierarchy_service.py tests/test_monitoring_service.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add services/hierarchy_service.py services/monitoring_service.py tests/test_hierarchy_service.py tests/test_monitoring_service.py
git commit -m "feat(services): hierarchy validation, metric view models, statistics/delta dispatch, freshness"
```

**Verification:** Both service suites pass with no database. Key guarantees covered by tests: delta needs ≥2 readings; current is period-independent; full-device view issues one batched range call over one common window while keeping per-metric `last_updated`/freshness; both empty-data cases behave as specified; condition is always `UNKNOWN`.

---

## Phase 7: Generic UI Components

**Objective:** Build the reusable, metric-driven components. No component may query the database, and none may branch on a specific metric key.

**Files:**
- Create: `components/freshness_badge.py`, `components/status_panels.py`, `components/breadcrumb.py`, `components/entity_table.py`, `components/equipment_context.py`, `components/metric_snapshot_strip.py`, `components/metric_chart.py`, `components/app_header.py`, `components/hierarchy_selector.py`, `tests/test_components.py`
- Modify: `components/kpi_card.py`, `components/readings_table.py`, `components/period_filter.py`

**Interfaces:**
- Consumes: `config.metrics` (`MetricConfig`, `format_value`, `ordered_metrics`), `services.monitoring_service` (`MetricView`, `MetricSnapshot`, `Freshness`, `Reading`), repository record types.
- Produces:
  ```python
  # freshness_badge.py
  FRESHNESS_LABELS: dict[Freshness, str]      # {FRESH: "Fresh", STALE: "Stale", NO_DATA: "No data"}
  def freshness_badge(freshness: Freshness, component_id: str | None = None)
  def freshness_class(freshness: Freshness) -> str

  # status_panels.py
  def not_found_panel(entity_type: str)       # entity_type e.g. "plant", "transformer", "device"
  def error_panel(message: str = "...")
  def empty_data_panel(message: str = "No data available for the selected period")

  # breadcrumb.py
  def breadcrumb(items: list[tuple[str, str | None]])   # (label, href) - href None = current

  # entity_table.py
  def entity_table(table_id: str, columns: list[dict], rows: list[dict], sort_by: str | None = None)

  # equipment_context.py
  def equipment_context(plant_name, transformer_code, device_code, admin_status, last_updated_text)

  # metric_snapshot_strip.py
  def metric_snapshot_strip(snapshots: list[MetricSnapshot], active_metric_key: str, device_id: str)
  def snapshot_tile(snapshot: MetricSnapshot, is_active: bool, device_id: str)

  # metric_chart.py
  def build_metric_figure(metric: MetricConfig, series: list[Reading]) -> go.Figure
  def metric_chart(chart_id: str = "metric-chart")

  # kpi_card.py  (modified)
  def kpi_card(label: str, value: str, accent: bool = False)
  def kpi_row(view: MetricView)

  # readings_table.py (modified)
  def build_table_rows(metric: MetricConfig, readings: list[Reading]) -> list[dict]
  def readings_table(table_id: str = "readings-table", metric: MetricConfig | None = None)

  # app_header.py
  def app_header(breadcrumb_children=None, freshness=None, selector_children=None)

  # hierarchy_selector.py
  def hierarchy_selector(plants, transformers, devices, plant_id, transformer_id, device_id)
  ```

- [ ] **Step 1: Write the failing component tests**

Create `tests/test_components.py`. Components are pure layout functions, so test the logic that matters: aggregation-driven KPI labelling, metric-driven formatting, and freshness independence.

```python
"""Unit tests for presentation logic in components - no database, no browser."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config.metrics import get_metric
from components.kpi_card import kpi_row
from components.metric_chart import build_metric_figure
from components.readings_table import build_table_rows
from services.monitoring_service import (
    Freshness,
    MetricView,
    MonitoringCondition,
    Reading,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def _view(metric_key: str, **overrides) -> MetricView:
    defaults = dict(
        metric=get_metric(metric_key),
        current=10.0,
        minimum=5.0,
        maximum=15.0,
        average=10.0,
        period_change=None,
        series=[Reading(NOW, 10.0)],
        last_updated=NOW,
        freshness=Freshness.FRESH,
        condition=MonitoringCondition.UNKNOWN,
        has_data=True,
    )
    defaults.update(overrides)
    return MetricView(**defaults)


def _labels(component) -> list[str]:
    """Collect KPI card labels from the rendered Dash component tree."""
    found = []
    def walk(node):
        children = getattr(node, "children", None)
        if isinstance(children, list):
            for c in children:
                walk(c)
        elif children is not None:
            walk(children)
        if getattr(node, "className", "") == "kpi-card__label":
            found.append(node.children)
    walk(component)
    return found


class TestKpiRow:
    def test_statistics_metric_shows_min_max_average(self):
        labels = _labels(kpi_row(_view("temperature")))
        assert labels == ["Current", "Minimum", "Maximum", "Average"]

    def test_delta_metric_shows_period_change_instead(self):
        view = _view("energy", minimum=None, maximum=None, average=None, period_change=142.0)
        labels = _labels(kpi_row(view))
        assert labels == ["Current", "Period Change"]
        assert "Average" not in labels

    def test_no_data_view_renders_em_dashes(self):
        view = _view(
            "temperature", current=None, minimum=None, maximum=None,
            average=None, series=[], last_updated=None,
            freshness=Freshness.NO_DATA, has_data=False,
        )
        rendered = str(kpi_row(view))
        assert "—" in rendered


class TestBuildTableRows:
    def test_formats_values_with_metric_precision_and_unit(self):
        rows = build_table_rows(get_metric("voltage"), [Reading(NOW, 11.0246)])
        assert rows[0]["value"] == "11.02 kV"

    def test_power_factor_row_has_no_unit_suffix(self):
        rows = build_table_rows(get_metric("power_factor"), [Reading(NOW, 0.9723)])
        assert rows[0]["value"] == "0.972"

    def test_includes_formatted_timestamp(self):
        rows = build_table_rows(get_metric("voltage"), [Reading(NOW, 11.0)])
        assert rows[0]["timestamp"] == "2026-08-08 12:00"

    def test_empty_readings_produce_no_rows(self):
        assert build_table_rows(get_metric("voltage"), []) == []

    def test_rows_contain_no_status_column(self):
        """Status columns implied thresholds we do not have."""
        rows = build_table_rows(get_metric("voltage"), [Reading(NOW, 11.0)])
        assert "status" not in rows[0]


class TestBuildMetricFigure:
    def test_axis_title_comes_from_metric_config(self):
        fig = build_metric_figure(get_metric("voltage"), [Reading(NOW, 11.0)])
        assert fig.layout.yaxis.title.text == "Voltage (kV)"

    def test_dimensionless_metric_omits_parenthetical_unit(self):
        fig = build_metric_figure(get_metric("power_factor"), [Reading(NOW, 0.97)])
        assert fig.layout.yaxis.title.text == "Power Factor"

    def test_plots_one_trace_for_the_series(self):
        readings = [Reading(NOW - timedelta(minutes=30), 10.0), Reading(NOW, 11.0)]
        fig = build_metric_figure(get_metric("voltage"), readings)
        assert len(fig.data) == 1
        assert len(fig.data[0].x) == 2

    def test_empty_series_renders_annotation_and_no_trace(self):
        fig = build_metric_figure(get_metric("voltage"), [])
        assert len(fig.data) == 0
        assert len(fig.layout.annotations) == 1

    def test_no_threshold_line_is_drawn(self):
        """No client-confirmed thresholds exist, so no threshold line."""
        fig = build_metric_figure(get_metric("temperature"), [Reading(NOW, 31.4)])
        assert not fig.layout.shapes
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_components.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'components.metric_chart'`

- [ ] **Step 3: Implement `components/freshness_badge.py` and `components/status_panels.py`**

```python
"""Freshness badge.

Renders DATA FRESHNESS only - how recently this device/metric delivered a
reading. It does NOT indicate database or network connectivity, and it is
NOT an electrical warning condition. Application/database errors use
components.status_panels.error_panel instead.
"""
FRESHNESS_LABELS = {
    Freshness.FRESH: "Fresh",
    Freshness.STALE: "Stale",
    Freshness.NO_DATA: "No data",
}


def freshness_class(freshness: Freshness) -> str:
    return f"freshness-badge freshness-badge--{freshness.value}"


def freshness_badge(freshness: Freshness, component_id: str | None = None):
    props = {"id": component_id} if component_id else {}
    return html.Span(
        FRESHNESS_LABELS[freshness], className=freshness_class(freshness), **props
    )
```

`status_panels.py` provides three `html.Div` panels with headings and short bodies. `not_found_panel(entity_type)` renders "This {entity_type} was not found." plus a `dcc.Link` back to `/plants`. `error_panel(message)` defaults to "Something went wrong loading this data. Please try again." — it must never surface SQL, stack traces, connection strings or credentials. `empty_data_panel(message)` defaults to "No data available for the selected period".

- [ ] **Step 4: Implement `components/metric_chart.py`**

```python
def _axis_title(metric: MetricConfig) -> str:
    return f"{metric.label} ({metric.unit})" if metric.unit else metric.label


def build_metric_figure(metric: MetricConfig, series: list[Reading]) -> go.Figure:
    """Line chart driven entirely by MetricConfig.

    No threshold line is drawn: no client-confirmed warning/critical
    thresholds exist. When they do, add them here, driven by config.
    """
    fig = go.Figure()
    if series:
        fig.add_trace(
            go.Scatter(
                x=[r.timestamp for r in series],
                y=[r.value for r in series],
                mode="lines",
                name=metric.label,
                line=dict(color=LINE_COLOR, width=2),
                hovertemplate=(
                    "%{x|%Y-%m-%d %H:%M}<br>%{y:."
                    + str(metric.precision)
                    + "f} "
                    + metric.unit
                    + "<extra></extra>"
                ),
            )
        )
    else:
        fig.add_annotation(
            text="No data available for the selected period",
            showarrow=False,
            font=dict(size=14, color="#6b7280"),
        )

    fig.update_layout(
        margin=dict(l=40, r=20, t=30, b=40),
        height=380,
        xaxis_title="Time",
        yaxis_title=_axis_title(metric),
        template="plotly_white",
        hovermode="x unified",
        showlegend=False,
        uirevision=metric.key,  # preserve zoom/pan across refresh, reset on metric change
    )
    return fig


def metric_chart(chart_id: str = "metric-chart"):
    return dcc.Graph(
        id=chart_id,
        figure=go.Figure(),
        config={"displayModeBar": True, "scrollZoom": True, "responsive": True},
        className="metric-chart",
    )
```

`chart_type` is read but only `"line"` is implemented today; raise a clear `ValueError` for any other value so adding a chart type is a deliberate change rather than a silent fallback.

- [ ] **Step 5: Rewrite `components/kpi_card.py`**

```python
def kpi_row(view: MetricView):
    """KPI cards for one metric.

    This is the ONLY component that branches on aggregation, and it branches
    once - on MetricConfig.aggregation, never on a metric key.
    """
    metric = view.metric
    cards = [kpi_card("Current", format_value(metric, view.current), accent=True)]

    if metric.aggregation is Aggregation.DELTA:
        cards.append(kpi_card("Period Change", format_value(metric, view.period_change)))
    else:
        cards.append(kpi_card("Minimum", format_value(metric, view.minimum)))
        cards.append(kpi_card("Maximum", format_value(metric, view.maximum)))
        cards.append(kpi_card("Average", format_value(metric, view.average)))

    return html.Div(className="kpi-row", children=cards)
```

- [ ] **Step 6: Rewrite `components/readings_table.py`**

Drop the `Status` column and the threshold-driven conditional styling entirely — both implied thresholds we do not have. Columns become `Timestamp` and a value column whose header is `metric.label`. `build_table_rows(metric, readings)` formats via `format_value` and expects readings newest-first. `readings_table(table_id, metric)` builds the `DataTable` with the metric-driven header, defaulting to the first registry metric when `metric is None`.

- [ ] **Step 7: Implement the remaining layout components**

- `breadcrumb.py` — renders `dcc.Link` for items with an href and `html.Span` for the current item, separated by `html.Span("›", className="breadcrumb__sep")`.
- `entity_table.py` — wraps `dash_table.DataTable` with `sort_action="native"`, `filter_action="native"`, `page_size=30`, `style_as_list_view=True`, and `style_table={"overflowX": "auto"}` for the responsive requirement. Cell renderers use Dash's Markdown link support so a row can link into the next hierarchy level.
- `equipment_context.py` — a single compact `html.Div` with five `html.Div` label/value pairs (Plant, Transformer, Device, Administrative status, Last data received) under `className="equipment-context"`. Deliberately not KPI cards.
- `metric_snapshot_strip.py` — `snapshot_tile` renders label, `format_value(metric, current)`, and `freshness_badge`, wrapped in a `dcc.Link` to `/devices/<device_id>?metric=<key>` so tiles are navigable and shareable. Each tile includes an empty `html.Div(className="snapshot-tile__condition")` placeholder documented as the mount point for a future monitoring-condition indicator, so adding condition later requires no restructuring. `metric_snapshot_strip` maps `ordered_metrics()` order onto tiles, marking the active one with `snapshot-tile--active`.
- `app_header.py` — brand, breadcrumb slot, hierarchy-selector slot, freshness slot, logout button. The freshness slot is labelled "Data:" and never "Connection" or "System".
- `hierarchy_selector.py` — three `dcc.Dropdown`s (`hier-plant`, `hier-transformer`, `hier-device`), searchable, with the transformer and device dropdowns disabled until their parent has a value.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `python -m pytest tests/test_components.py -v`
Expected: PASS

- [ ] **Step 9: Verify no component contains metric-key business logic**

Run: `grep -rnE 'metric\.key *== *"|metric_key *== *"' components/`
Expected: no output.

- [ ] **Step 10: Commit**

```bash
git add components/ tests/test_components.py
git commit -m "feat(components): metric-driven KPI, chart, table, snapshot strip and shared panels"
```

**Verification:** Component tests pass; the grep confirms no metric-specific branching in `components/`; KPI labels switch on aggregation, not metric name.

---

## Phase 8: Routing and Navigation

**Objective:** Replace the two-route demo router with hierarchy routing, URL-addressable metric/period state, page shells that never query in the layout function, and lightweight `page-context`.

**Files:**
- Create: `callbacks/__init__.py`, `callbacks/routing.py`, `callbacks/auth.py`, `pages/plants_overview.py`, `pages/plant_detail.py`, `pages/transformer_detail.py`, `pages/device_dashboard.py`, `tests/test_routing.py`
- Modify: `app.py`, `pages/__init__.py`

**Interfaces:**
- Produces:
  ```python
  # callbacks/routing.py
  @dataclass(frozen=True)
  class Route:
      name: str                       # "overview" | "plant" | "transformer" | "device" | "unknown"
      plant_id: str | None = None
      transformer_id: str | None = None
      device_id: str | None = None

  def parse_pathname(pathname: str | None) -> Route
  def parse_query(search: str | None) -> tuple[str, str]     # (metric_key, period_value), defaulted
  def device_href(device_id: str, metric_key: str | None = None, period: str | None = None) -> str
  def register(app) -> None

  # callbacks/auth.py
  def register(app) -> None
  ```

- [ ] **Step 1: Write the failing routing tests**

Create `tests/test_routing.py`:

```python
"""Unit tests for URL parsing/building - pure functions, no Dash runtime."""
from __future__ import annotations

from callbacks.routing import device_href, parse_pathname, parse_query
from config.metrics import DEFAULT_METRIC_KEY


class TestParsePathname:
    def test_root_is_overview(self):
        assert parse_pathname("/").name == "overview"

    def test_plants_is_overview(self):
        assert parse_pathname("/plants").name == "overview"

    def test_trailing_slash_is_tolerated(self):
        assert parse_pathname("/plants/").name == "overview"

    def test_plant_detail(self):
        route = parse_pathname("/plants/plant-01")
        assert (route.name, route.plant_id) == ("plant", "plant-01")

    def test_transformer_detail(self):
        route = parse_pathname("/plants/plant-01/plant-01-t1")
        assert route.name == "transformer"
        assert route.plant_id == "plant-01"
        assert route.transformer_id == "plant-01-t1"

    def test_device_dashboard(self):
        route = parse_pathname("/devices/plant-01-t1-d1")
        assert (route.name, route.device_id) == ("device", "plant-01-t1-d1")

    def test_none_pathname_is_overview(self):
        assert parse_pathname(None).name == "overview"

    def test_unrecognised_path_is_unknown(self):
        assert parse_pathname("/nope/nope/nope/nope").name == "unknown"

    def test_device_path_without_id_is_unknown(self):
        assert parse_pathname("/devices").name == "unknown"


class TestParseQuery:
    def test_defaults_when_search_is_empty(self):
        assert parse_query("") == (DEFAULT_METRIC_KEY, "24h")

    def test_defaults_when_search_is_none(self):
        assert parse_query(None) == (DEFAULT_METRIC_KEY, "24h")

    def test_reads_metric_and_period(self):
        assert parse_query("?metric=voltage&period=7d") == ("voltage", "7d")

    def test_unknown_metric_falls_back_to_default(self):
        metric, _ = parse_query("?metric=not-a-metric")
        assert metric == DEFAULT_METRIC_KEY

    def test_unknown_period_falls_back_to_24h(self):
        _, period = parse_query("?period=nonsense")
        assert period == "24h"


class TestDeviceHref:
    def test_bare_device_link(self):
        assert device_href("d1") == "/devices/d1"

    def test_with_metric(self):
        assert device_href("d1", "voltage") == "/devices/d1?metric=voltage"

    def test_with_metric_and_period(self):
        assert device_href("d1", "voltage", "7d") == "/devices/d1?metric=voltage&period=7d"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_routing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'callbacks'`

- [ ] **Step 3: Implement `callbacks/routing.py` URL helpers**

Parse with `urllib.parse` — never regex the path into SQL, and never trust these values beyond passing them to `hierarchy_service` for validation.

```python
def parse_pathname(pathname: str | None) -> Route:
    parts = [p for p in (pathname or "/").strip("/").split("/") if p]
    if not parts or parts == ["plants"]:
        return Route("overview")
    if parts[0] == "plants" and len(parts) == 2:
        return Route("plant", plant_id=parts[1])
    if parts[0] == "plants" and len(parts) == 3:
        return Route("transformer", plant_id=parts[1], transformer_id=parts[2])
    if parts[0] == "devices" and len(parts) == 2:
        return Route("device", device_id=parts[1])
    return Route("unknown")


def parse_query(search: str | None) -> tuple[str, str]:
    """Read metric/period from the query string, falling back to defaults.

    Unknown values fall back silently rather than erroring - a stale
    bookmarked link should still open a usable dashboard.
    """
    params = parse_qs((search or "").lstrip("?"))
    metric_key = (params.get("metric") or [DEFAULT_METRIC_KEY])[0]
    if get_metric(metric_key) is None:
        metric_key = DEFAULT_METRIC_KEY
    period = (params.get("period") or [Period.LAST_24H.value])[0]
    if period not in {p.value for p in Period}:
        period = Period.LAST_24H.value
    return metric_key, period
```

- [ ] **Step 4: Run the routing tests to verify they pass**

Run: `python -m pytest tests/test_routing.py -v`
Expected: PASS

- [ ] **Step 5: Write the page shell modules**

Each page module exports a layout function that takes already-resolved context and returns markup with **empty** data containers. No page module imports a repository, and no page module calls a service inside its layout function — the current `plants_dashboard_layout()` calls `list_plants()` inline and blocks first paint; that pattern is removed.

- `pages/plants_overview.py` → `plants_overview_layout()` — header, `html.H2("Power Plants")`, `dcc.Loading(entity_table("plants-table", PLANT_COLUMNS, []))`.
- `pages/plant_detail.py` → `plant_detail_layout(plant, breadcrumb_items)` — header with breadcrumb, plant summary line, `dcc.Loading(entity_table("transformers-table", ...))`.
- `pages/transformer_detail.py` → `transformer_detail_layout(transformer, breadcrumb_items)` — same shape for devices.
- `pages/device_dashboard.py` → `device_dashboard_layout(context, metric_key, period_value)` — header, `equipment_context(...)`, `html.Div(id="snapshot-strip")`, metric dropdown (`id="metric-dropdown"`, options from `ordered_metrics()`), `period_filter()`, `html.Div(id="kpi-row-container")`, `dcc.Loading(metric_chart())`, `readings_table()`, and the single `dcc.Interval(id="device-refresh-interval", interval=monitoring.refresh_interval_seconds * 1000)`.

- [ ] **Step 6: Rewrite `app.py` and implement the router callback**

`app.py` shrinks to app construction, the top-level layout, and callback registration:

```python
app = dash.Dash(__name__, suppress_callback_exceptions=True, title="Power Plant Monitoring")
server = app.server

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="auth-store", storage_type="memory", data={"authenticated": False}),
    # Lightweight navigation state ONLY - resolved IDs and selections.
    # Never historical readings: PostgreSQL does the filtering.
    dcc.Store(id="page-context", storage_type="memory", data={}),
    html.Div(id="page-content"),
])

auth.register(app)
routing.register(app)
listings.register(app)
device.register(app)
```

`callbacks/routing.py::register` adds the router callback: `Output("page-content", "children")`, `Output("page-context", "data")`, `Input("url", "pathname")`, `Input("url", "search")`, `State("auth-store", "data")`.

It gates on auth, parses the route, validates IDs through `hierarchy_service` (`get_plant_or_none`, `get_transformer_in_plant`, `get_device_context`), returns `not_found_panel(...)` on any `None`, wraps repository access in `try/except Exception` returning `error_panel()` so a database outage never leaks a stack trace, and writes only IDs, labels and selections into `page-context`.

`callbacks/auth.py::register` moves the existing login, password-toggle and logout callbacks over unchanged except that successful login redirects to `/plants`.

- [ ] **Step 7: Verify routing end to end in the browser**

```bash
docker compose up -d
python app.py
```

Visit and confirm each renders without error: `/` (redirects to overview), `/plants`, `/plants/plant-01`, `/plants/plant-01/plant-01-t1`, `/devices/plant-01-t1-d1`, `/devices/plant-01-t1-d1?metric=voltage&period=7d`.

Then confirm the not-found path: `/plants/does-not-exist` and `/devices/does-not-exist` both show the not-found panel, not a stack trace or a blank page.

Then confirm the confused-deputy guard: `/plants/plant-02/plant-01-t1` shows not-found, because that transformer belongs to `plant-01`.

- [ ] **Step 8: Commit**

```bash
git add callbacks/ pages/ app.py tests/test_routing.py
git commit -m "feat(routing): hierarchy routes, URL-addressable metric/period, validated page shells"
```

**Verification:** Routing unit tests pass; all six valid URLs render; all three invalid URLs show the not-found panel; no page layout function performs a query.

---

## Phase 9: Plant, Transformer and Device Listing Pages

**Objective:** Populate the three drill-down listings and the persistent cascading selector, each with one bounded query per page load.

**Files:**
- Create: `callbacks/listings.py`
- Modify: `pages/plants_overview.py`, `pages/plant_detail.py`, `pages/transformer_detail.py`, `components/hierarchy_selector.py`

**Interfaces:**
- Consumes: `services.hierarchy_service` (`list_plants`, `list_transformers`, `list_devices`, `get_plant_hierarchy_counts`), `callbacks.routing.device_href`, `page-context` store.
- Produces: `callbacks/listings.py::register(app) -> None`.

- [ ] **Step 1: Populate the 30-plant overview**

In `callbacks/listings.py`, add a callback with `Output("plants-table", "data")` and `Output("plants-table", "columns")`, `Input("page-context", "data")`, firing only when `context["route"] == "overview"` (otherwise `raise PreventUpdate`).

It calls `hierarchy_service.list_plants()` and `hierarchy_service.get_plant_hierarchy_counts()` — **two** queries total for the page, not one per plant. Rows carry: plant name rendered as a Markdown link to `/plants/<plant_id>`, country, primary fuel, `capacity_mw` formatted with thousands separators and a `MW` suffix, transformer count, device count.

Columns are defined once as a module constant:

```python
PLANT_COLUMNS = [
    {"name": "Plant", "id": "plant", "presentation": "markdown"},
    {"name": "Country", "id": "country"},
    {"name": "Fuel", "id": "fuel"},
    {"name": "Capacity", "id": "capacity"},
    {"name": "Transformers", "id": "transformers", "type": "numeric"},
    {"name": "Devices", "id": "devices", "type": "numeric"},
]
```

No status rollup column — aggregating freshness across 120 devices on every overview load buys a value whose "warning" definition does not exist yet. Add a code comment recording this as the deliberate phase-2 extension point.

- [ ] **Step 2: Verify the overview against the seeded database**

```bash
python app.py
```

Open `/plants`. Confirm: 30 rows; the transformer column sums to 71 and the device column to 120 (sort by each column to eyeball, or run the psql check below); sorting and the native filter work; clicking a plant name navigates to `/plants/<plant_id>`.

```bash
docker compose exec postgres psql -U powerplant -d powerplant_demo -c "
SELECT COUNT(DISTINCT t.transformer_id) AS transformers, COUNT(d.device_id) AS devices
FROM plant_monitoring.transformers t
LEFT JOIN plant_monitoring.devices d ON d.transformer_id = t.transformer_id;"
```

Expected: `71 | 120`.

- [ ] **Step 3: Populate the plant and transformer detail listings**

Two more callbacks in the same module, each reading resolved IDs from `page-context` rather than re-querying the parent entity:

- Plant detail → `hierarchy_service.list_transformers(plant_id)`. Columns: Transformer code (Markdown link to `/plants/<plant_id>/<transformer_id>`), Devices count, Administrative status.
- Transformer detail → `hierarchy_service.list_devices(transformer_id)`. Columns: Device code (Markdown link built with `device_href(device_id)`), Administrative status.

Administrative status renders as a plain text badge here and nowhere else in the app. Add a comment: this is administrative `active`/`inactive`, never computed monitoring status or data freshness.

The device-count column on plant detail reuses `get_plant_hierarchy_counts()`; do not issue one `list_devices` call per transformer.

- [ ] **Step 4: Wire the cascading hierarchy selector**

Three callbacks in `callbacks/listings.py`:

1. Populate the plant dropdown from `page-context` on every page (one `list_plants()` call — accept this; it is 30 rows off an indexed table).
2. `Input("hier-plant", "value")` → populate and enable the transformer dropdown via `list_transformers`.
3. `Input("hier-transformer", "value")` → populate and enable the device dropdown via `list_devices`.

A fourth callback navigates: `Input("hier-device", "value")` → `Output("url", "pathname")` using `device_href(device_id)`, with `prevent_initial_call=True` so merely rendering the header never navigates.

The selector's current values are seeded from `page-context` so it always reflects the active route.

- [ ] **Step 5: Verify navigation both ways**

With the app running: from `/plants`, drill Plant → Transformer → Device by clicking, confirming the breadcrumb grows correctly at each step and each crumb links back. Then from a device page, use the header selector to jump to a device under a *different* plant and confirm the URL, breadcrumb and equipment context all update together.

- [ ] **Step 6: Commit**

```bash
git add callbacks/listings.py pages/ components/hierarchy_selector.py
git commit -m "feat(pages): plant overview, drill-down listings and cascading equipment selector"
```

**Verification:** `/plants` shows 30 rows totalling 71 transformers and 120 devices; drill-down and header-selector navigation both work; each listing page issues at most two queries.

---

## Phase 10: Device Monitoring Dashboard

**Objective:** Assemble the operator view — equipment context, 8-tile snapshot strip, metric selector, aggregation-aware KPIs, chart and readings table — with metric and period synchronized to the URL.

**Files:**
- Create: `callbacks/device.py`
- Modify: `pages/device_dashboard.py`, `components/metric_snapshot_strip.py`

**Interfaces:**
- Consumes: `services.monitoring_service` (`get_device_snapshot`, `get_metric_view`, `Period`), `components` from Phase 7, `page-context`.
- Produces: `callbacks/device.py::register(app) -> None`.

- [ ] **Step 1: Implement the single device-dashboard callback**

One callback owns the whole dashboard body, so the snapshot strip and the active-metric detail can never drift apart:

```python
@app.callback(
    Output("snapshot-strip", "children"),
    Output("kpi-row-container", "children"),
    Output("metric-chart", "figure"),
    Output("readings-table", "data"),
    Output("readings-table", "columns"),
    Output("header-freshness", "children"),
    Output("equipment-last-data", "children"),
    Input("page-context", "data"),
    Input("metric-dropdown", "value"),
    Input("period-radio", "value"),
    Input("custom-date-range", "start_date"),
    Input("custom-date-range", "end_date"),
    Input("device-refresh-interval", "n_intervals"),
)
def refresh_device_dashboard(context, metric_key, period_value, custom_start, custom_end, _n):
    ...
```

Body outline — thin: gather inputs, call services, format outputs. No SQL, no KPI math, no threshold logic.

1. `raise PreventUpdate` unless `context.get("route") == "device"`.
2. Wrap everything in `try/except Exception` → return `error_panel()` in the strip slot and empty figure/rows. Never surface the exception text.
3. `snapshots = monitoring_service.get_device_snapshot(device_id)` — one batched query.
4. Resolve `period`, and parse `custom_start`/`custom_end` with `datetime.fromisoformat` only when `period is Period.CUSTOM`.
5. `view = monitoring_service.get_metric_view(device_id, metric_key, period, start, end)`.
6. Build outputs: `metric_snapshot_strip(snapshots, metric_key, device_id)`, `kpi_row(view)`, `build_metric_figure(view.metric, view.series)`, `build_table_rows(view.metric, sorted(view.series, key=lambda r: r.timestamp, reverse=True))`, the metric-driven column definition, `freshness_badge(view.freshness)`, and the formatted last-data text.

Because snapshot and detail come from the same callback invocation, every refresh updates both together — the required consistency guarantee.

- [ ] **Step 2: Synchronize metric and period into the URL**

A second, small callback keeps links shareable:

```python
@app.callback(
    Output("url", "search"),
    Input("metric-dropdown", "value"),
    Input("period-radio", "value"),
    State("page-context", "data"),
    prevent_initial_call=True,
)
def sync_query_string(metric_key, period_value, context):
    if not context or context.get("route") != "device":
        raise PreventUpdate
    return f"?metric={metric_key}&period={period_value}"
```

Custom start/end are deliberately not encoded, per the approved design.

A third callback makes snapshot tiles set the active metric: the tiles are already `dcc.Link`s carrying `?metric=<key>`, so clicking one updates `url.search`; add a callback with `Input("url", "search")` → `Output("metric-dropdown", "value")` so the dropdown follows the URL. Guard it against feedback loops by returning `no_update` when the dropdown already holds that value.

- [ ] **Step 3: Toggle the custom-range picker**

```python
@app.callback(
    Output("custom-range-container", "style"),
    Input("period-radio", "value"),
)
def toggle_custom_range(period_value):
    return {"display": "block"} if period_value == Period.CUSTOM.value else {"display": "none"}
```

- [ ] **Step 4: Verify the dashboard against seeded data**

With the app running, open `/devices/plant-01-t1-d1` and confirm:

- Equipment context shows the plant name, `AA12`, `29017`, `active`, and a last-data timestamp.
- The snapshot strip shows 8 tiles in registry order with plausible values and units — Temperature in °C, Voltage in kV, Reactive Power in **MVAr**, Power Factor with no unit and 3 decimals, Energy in MWh.
- Selecting Temperature shows four KPI cards: Current, Minimum, Maximum, Average.
- Selecting **Energy** shows exactly two: Current and **Period Change** — no Average.
- Switching 24h → 7d → 30d changes the chart span and recomputes Min/Max/Average, while **Current stays the same value** across all three (it is latest-available, not period-scoped).
- The readings table header reads the active metric's label, and values carry the configured precision.
- Clicking a snapshot tile switches the active metric and updates the URL.

- [ ] **Step 5: Verify URL addressability**

Open `/devices/plant-01-t1-d1?metric=voltage&period=7d` in a fresh tab. The Voltage metric and 7-day period must already be selected on first paint. Copy the URL after clicking through to another metric and confirm reopening it lands on the same view.

- [ ] **Step 6: Verify energy behaves as a cumulative meter**

```bash
docker compose exec postgres psql -U powerplant -d powerplant_demo -c "
SELECT COUNT(*) AS decreases FROM (
  SELECT value - LAG(value) OVER (ORDER BY reading_ts) AS d
  FROM plant_monitoring.readings
  WHERE device_id = 'plant-01-t1-d1' AND metric = 'energy'
) s WHERE d < 0;"
```

Expected: `0`. Then confirm in the UI that the Energy chart rises monotonically and Period Change is positive.

- [ ] **Step 7: Commit**

```bash
git add callbacks/device.py pages/device_dashboard.py components/metric_snapshot_strip.py
git commit -m "feat(dashboard): device monitoring view with snapshot strip and aggregation-aware KPIs"
```

**Verification:** All checks in Steps 4–6 pass, in particular: Energy shows Period Change (never Average), Current is invariant across period changes, and the query-string round trip restores the exact view.

---

## Phase 11: Refresh and Data-Freshness Behaviour

**Objective:** Prove the refresh trigger keeps the dashboard internally consistent, that the interval is configuration-driven, and that freshness is never presented as connectivity.

**Files:**
- Modify: `pages/device_dashboard.py`, `components/app_header.py`, `callbacks/device.py`, `.env.example`, `README.md`
- Create: `tests/test_freshness_policy.py`

**Interfaces:**
- Consumes: `config.settings.monitoring` (`refresh_interval_seconds`, `expected_interval_minutes`, `stale_after_intervals`, `stale_after_minutes`).

- [ ] **Step 1: Write the failing configuration tests**

Create `tests/test_freshness_policy.py`:

```python
"""Freshness policy comes from configuration, never hard-coded."""
from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone

from config.settings import monitoring
from services.monitoring_service import Freshness, evaluate_freshness

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


class TestPolicyDefaults:
    def test_expected_interval_is_thirty_minutes(self):
        assert monitoring.expected_interval_minutes == 30

    def test_stale_after_three_intervals(self):
        assert monitoring.stale_after_intervals == 3

    def test_derived_threshold_is_ninety_minutes(self):
        assert monitoring.stale_after_minutes == 90


class TestPolicyIsHonoured:
    def test_threshold_boundary_follows_configuration(self, monkeypatch):
        """Changing config must change behaviour - proving it is not hard-coded."""
        import services.monitoring_service as svc

        class _Stub:
            stale_after_minutes = 10

        monkeypatch.setattr(svc, "monitoring", _Stub())
        assert evaluate_freshness(NOW - timedelta(minutes=5), NOW) is Freshness.FRESH
        assert evaluate_freshness(NOW - timedelta(minutes=15), NOW) is Freshness.STALE


class TestRefreshInterval:
    def test_interval_is_configurable_and_positive(self):
        assert monitoring.refresh_interval_seconds > 0

    def test_interval_read_from_environment(self, monkeypatch):
        monkeypatch.setenv("UI_REFRESH_INTERVAL_SECONDS", "300")
        import config.settings as settings

        importlib.reload(settings)
        assert settings.monitoring.refresh_interval_seconds == 300
        monkeypatch.delenv("UI_REFRESH_INTERVAL_SECONDS")
        importlib.reload(settings)
```

- [ ] **Step 2: Run to verify, then confirm the interval is not hard-coded**

Run: `python -m pytest tests/test_freshness_policy.py -v`
Expected: PASS if Phase 1 and Phase 6 were implemented correctly. If the boundary test fails, `evaluate_freshness` hard-coded 90 — fix the service to read `monitoring.stale_after_minutes`.

Then: `grep -rnE '\b(90|1800000|60000)\b' callbacks/ pages/ services/`
Expected: no interval literals. The only interval expression allowed is `monitoring.refresh_interval_seconds * 1000` in `pages/device_dashboard.py`.

- [ ] **Step 3: Confirm the refresh trigger updates snapshot and detail together**

Already guaranteed structurally by Phase 10 Step 1 — `device-refresh-interval` is an `Input` to the same callback that produces both the snapshot strip and the metric detail. Verify no second callback writes `snapshot-strip`:

Run: `grep -rn 'snapshot-strip' callbacks/`
Expected: exactly one `Output("snapshot-strip", ...)`.

- [ ] **Step 4: Verify refresh behaviour live**

Set a short interval for the test, restart, and watch:

```bash
UI_REFRESH_INTERVAL_SECONDS=10 python app.py
```

Open a device page. While it is open, insert a newer reading for one metric only and confirm that within ~10s **both** that metric's snapshot tile **and** (when it is the active metric) the KPI/chart update in the same tick:

```bash
docker compose exec postgres psql -U powerplant -d powerplant_demo -c "
INSERT INTO plant_monitoring.readings (device_id, metric, reading_ts, value)
VALUES ('plant-01-t1-d1','voltage', NOW(), 99.999);"
```

Expected: the Voltage tile shows `100.00 kV` and reads Fresh. Remove the row afterwards:

```bash
docker compose exec postgres psql -U powerplant -d powerplant_demo -c "
DELETE FROM plant_monitoring.readings WHERE device_id='plant-01-t1-d1' AND value = 99.999;"
```

- [ ] **Step 5: Verify stale and no-data presentation**

Temporarily raise the strictness rather than mutating data: run `STALE_AFTER_INTERVALS=0 python app.py`, open a device page, and confirm every tile and the header badge read **Stale** while values still display. Confirm the wording is "Stale" / "Data:" and that nothing anywhere says "Connected", "System connected", or "Connection state".

Run: `grep -rniE 'connection state|system connected|connected' components/ pages/ callbacks/`
Expected: no output.

Then stop PostgreSQL and confirm the separate error path:

```bash
docker compose stop postgres
```

Reload the device page. Expected: the shared `error_panel()` message — not a stack trace, not "Stale", not a blank page. Restart with `docker compose start postgres`.

- [ ] **Step 6: Document the policy in `.env.example` and `README.md`**

Both must state plainly: the ~30-minute cadence is a **project/client-known requirement**; "stale after 3 missed intervals" is a **development application policy requiring client confirmation before production**; and data freshness describes measurement recency and does **not** prove database or network connectivity.

- [ ] **Step 7: Commit**

```bash
git add tests/test_freshness_policy.py pages/device_dashboard.py components/app_header.py callbacks/device.py .env.example README.md
git commit -m "feat(refresh): configuration-driven refresh cadence and freshness presentation"
```

**Verification:** Policy tests pass; no hard-coded intervals; exactly one writer for the snapshot strip; live refresh updates strip and detail in the same tick; stale/no-data/error states are visually and textually distinct; no "connection" wording anywhere.

---

## Phase 12: Responsive CSS

**Objective:** Make the industrial layout usable from wide desktop down to a phone, without redesigning components.

**Files:**
- Modify: `assets/app.css`

- [ ] **Step 1: Establish the layout primitives**

Add styles for the new class names introduced in Phase 7: `.app-header`, `.breadcrumb`, `.breadcrumb__sep`, `.equipment-context`, `.snapshot-strip`, `.snapshot-tile`, `.snapshot-tile--active`, `.snapshot-tile__condition`, `.freshness-badge` (with `--fresh`, `--stale`, `--no_data` modifiers), `.metric-chart`, `.status-panel`.

Keep the existing visual language — no redesign. `.snapshot-tile__condition` is styled as an empty inline slot that collapses to zero height until a future condition indicator populates it.

- [ ] **Step 2: Implement the snapshot strip behaviour**

```css
.snapshot-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 1024px) {
  .snapshot-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .snapshot-strip {
    display: flex;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
  }
  .snapshot-tile { flex: 0 0 60%; scroll-snap-align: start; }
}
```

- [ ] **Step 3: Implement the KPI 4 → 2 → 1 degradation**

```css
.kpi-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
@media (max-width: 1024px) { .kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px)  { .kpi-row { grid-template-columns: 1fr; } }
```

This must also look right with **two** cards (the `delta` case) — verify Energy's Current/Period Change pair does not stretch awkwardly at wide widths; constrain with `max-width` on the row's children if it does.

- [ ] **Step 4: Chart, tables and header**

Chart: `.metric-chart { width: 100%; }` and rely on Plotly's `responsive: true`, already set in Phase 7.

Tables: the `overflow-x: auto` wrapper is already applied in `entity_table` and `readings_table`; add `.dash-table-container { max-width: 100%; }` so long plant names cannot force page-level horizontal scroll.

Header: below `768px`, hide the three inline dropdowns and reveal a single full-width "Jump to device" control:

```css
@media (max-width: 768px) {
  .hierarchy-selector { display: none; }
  .hierarchy-selector--compact { display: block; width: 100%; }
}
```

Add the compact control to `components/hierarchy_selector.py` as a single device dropdown, rendered alongside the three-dropdown version and toggled purely by CSS — no extra callbacks.

- [ ] **Step 5: Verify at three widths**

With the app running on a device page, use browser dev tools to check 1440px, 900px and 390px:

- 1440px — 4 snapshot columns, 4 KPI columns, three-dropdown selector.
- 900px — 2 snapshot columns, 2 KPI columns.
- 390px — snapshot strip scrolls horizontally with snapping, KPIs stack to 1 column, chart fits, the page body itself does **not** scroll horizontally, and the compact "Jump to device" control replaces the three dropdowns.

Also load `/plants` at 390px and confirm the 6-column table scrolls inside its own container rather than widening the page.

- [ ] **Step 6: Commit**

```bash
git add assets/app.css components/hierarchy_selector.py
git commit -m "style: responsive layout for snapshot strip, KPI row, tables and header"
```

**Verification:** All three widths behave as described; no page-level horizontal scrolling at 390px on either the overview or a device dashboard.

---

## Phase 13: Legacy Single-Temperature Demo Retirement

**Objective:** Delete the superseded single-device demo and the old flat multi-plant demo, leaving exactly one schema and one application.

**Files:**
- Delete: `pages/dashboard.py`, `pages/plants_dashboard.py`, `services/temperature_service.py`, `repositories/temperature_repository.py`, `repositories/monitoring_repository.py`, `components/temperature_chart.py`, `components/plant_selector.py`, `db/seed.py`, `db/seed_multi_plant.py`, `db/init.sql`, `db/init_monitoring.sql`, `tests/test_temperature_service.py`, `tests/test_temperature_repository.py`
- Modify: `docker-compose.yml`, `config/settings.py`, `.env.example`, `powerplant-dashboard.zip` (delete)

- [ ] **Step 1: Confirm nothing still imports the legacy modules**

```bash
grep -rnE 'temperature_service|temperature_repository|monitoring_repository|temperature_chart|plant_selector|demo_device|warning_settings|seed_multi_plant' \
  --include=*.py . | grep -v '\.venv' | grep -v 'seed_multi_plant.py:' | grep -v 'temperature_repository.py:'
```

Expected: no output. If anything appears, fix that import before deleting — do not delete a module that is still referenced.

- [ ] **Step 2: Delete the legacy Python modules and tests**

```bash
git rm pages/dashboard.py pages/plants_dashboard.py \
       services/temperature_service.py \
       repositories/temperature_repository.py repositories/monitoring_repository.py \
       components/temperature_chart.py components/plant_selector.py \
       db/seed.py db/seed_multi_plant.py \
       tests/test_temperature_service.py tests/test_temperature_repository.py
```

- [ ] **Step 3: Delete the legacy SQL and unmount it**

```bash
git rm db/init.sql db/init_monitoring.sql
```

In `docker-compose.yml`, remove both legacy volume mounts and renumber the remaining one:

```yaml
      - ./db/init_plant_monitoring.sql:/docker-entrypoint-initdb.d/01_init_plant_monitoring.sql:ro
```

- [ ] **Step 4: Remove the legacy configuration**

In `config/settings.py`, delete `DemoDeviceSettings`, `WarningSettings`, the `demo_device` and `warning_settings` instances, and the `schema` field on `DatabaseSettings` (the schema now lives on `MonitoringSettings`). In `.env.example`, delete `DB_SCHEMA` and `DEMO_WARNING_THRESHOLD_C`.

Keep `DemoAuthSettings` — demo authentication stays isolated so it can later be replaced by client authentication.

- [ ] **Step 5: Remove the stale build artifact**

```bash
git rm --cached powerplant-dashboard.zip 2>/dev/null; rm -f powerplant-dashboard.zip
```

Confirm `*.zip` is in `.gitignore`.

- [ ] **Step 6: Drop the legacy schemas from a clean database**

```bash
docker compose down -v
docker compose up -d
python -m db.seed_plant_monitoring --reset
docker compose exec postgres psql -U powerplant -d powerplant_demo -c "\dn"
```

Expected: `plant_monitoring` and `public` only — no `trfr_temperature`, no `monitoring`.

- [ ] **Step 7: Run the full suite and the app**

Run: `python -m pytest -v` → all pass, no import errors, no collection errors.
Run: `python app.py` → app starts; log in; `/plants` and a device dashboard both render.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: retire single-device temperature demo and flat monitoring schema"
```

**Verification:** `\dn` lists only `plant_monitoring` and `public`; the grep in Step 1 returns nothing; full test suite and app both run clean.

---

## Phase 14: Automated Test Consolidation

**Objective:** Close the remaining coverage gaps and make the suite runnable in two modes — pure logic without Docker, and full with a seeded database.

**Files:**
- Create: `pytest.ini`
- Modify: `tests/conftest.py`, `tests/test_monitoring_service.py`
- Create: `tests/test_seed_integrity.py`

- [ ] **Step 1: Add pytest configuration**

Create `pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
markers =
    db: requires a seeded local PostgreSQL (run `docker compose up -d && python -m db.seed_plant_monitoring`)
addopts = -q --strict-markers
```

- [ ] **Step 2: Write seed-integrity tests**

Create `tests/test_seed_integrity.py` — these guard the data contract the whole application assumes:

```python
"""Integrity checks on the seeded development dataset."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from config.metrics import METRIC_KEYS
from db.engine import session_scope

pytestmark = pytest.mark.db

SCHEMA = "plant_monitoring"


def _scalar(sql: str):
    with session_scope() as session:
        return session.execute(text(sql)).scalar_one()


class TestRowCounts:
    def test_thirty_plants(self):
        assert _scalar(f"SELECT COUNT(*) FROM {SCHEMA}.plants") == 30

    def test_seventy_one_transformers(self):
        assert _scalar(f"SELECT COUNT(*) FROM {SCHEMA}.transformers") == 71

    def test_one_hundred_twenty_devices(self):
        assert _scalar(f"SELECT COUNT(*) FROM {SCHEMA}.devices") == 120

    def test_total_readings(self):
        assert _scalar(f"SELECT COUNT(*) FROM {SCHEMA}.readings") == 1_383_360


class TestPerMetricCoverage:
    def test_every_metric_has_equal_coverage(self):
        with session_scope() as session:
            rows = session.execute(
                text(f"SELECT metric, COUNT(*) FROM {SCHEMA}.readings GROUP BY metric")
            ).all()
        counts = dict(rows)
        assert set(counts) == set(METRIC_KEYS)
        assert set(counts.values()) == {172_920}  # 120 devices x 1441 timestamps

    def test_every_device_has_every_metric(self):
        missing = _scalar(
            f"""
            SELECT COUNT(*) FROM {SCHEMA}.devices d
            CROSS JOIN (SELECT DISTINCT metric FROM {SCHEMA}.readings) m
            WHERE NOT EXISTS (
                SELECT 1 FROM {SCHEMA}.readings r
                WHERE r.device_id = d.device_id AND r.metric = m.metric
            )
            """
        )
        assert missing == 0


class TestSamplingCadence:
    def test_thirty_minute_spacing(self):
        irregular = _scalar(
            f"""
            SELECT COUNT(*) FROM (
              SELECT reading_ts - LAG(reading_ts) OVER (ORDER BY reading_ts) AS gap
              FROM {SCHEMA}.readings
              WHERE device_id = 'plant-01-t1-d1' AND metric = 'temperature'
            ) s WHERE gap IS NOT NULL AND gap <> INTERVAL '30 minutes'
            """
        )
        assert irregular == 0

    def test_thirty_days_of_history(self):
        with session_scope() as session:
            span = session.execute(
                text(
                    f"SELECT MAX(reading_ts) - MIN(reading_ts) FROM {SCHEMA}.readings "
                    "WHERE device_id = 'plant-01-t1-d1' AND metric = 'temperature'"
                )
            ).scalar_one()
        assert span == timedelta(days=30)


class TestEnergyIsCumulative:
    def test_no_metric_decreases_for_any_device(self):
        decreases = _scalar(
            f"""
            SELECT COUNT(*) FROM (
              SELECT value - LAG(value) OVER (
                       PARTITION BY device_id ORDER BY reading_ts
                     ) AS d
              FROM {SCHEMA}.readings WHERE metric = 'energy'
            ) s WHERE d < 0
            """
        )
        assert decreases == 0


class TestReferentialIntegrity:
    def test_reserved_client_naming_example_present(self):
        with session_scope() as session:
            row = session.execute(
                text(
                    f"""
                    SELECT t.transformer_code, d.device_code
                    FROM {SCHEMA}.devices d
                    JOIN {SCHEMA}.transformers t ON t.transformer_id = d.transformer_id
                    WHERE d.device_id = 'plant-01-t1-d1'
                    """
                )
            ).first()
        assert row == ("aa12", "29017")

    def test_device_codes_are_globally_unique(self):
        assert _scalar(f"SELECT COUNT(DISTINCT device_code) FROM {SCHEMA}.devices") == 120
```

- [ ] **Step 3: Run both suite modes**

Run: `python -m pytest -m "not db" -v` (Docker may be stopped)
Expected: PASS — metric config, hierarchy generation, generators, services, routing, components, freshness policy.

Run: `python -m pytest -v` (Docker running, seeded)
Expected: PASS — everything, including repository and seed integrity.

- [ ] **Step 4: Confirm the required coverage areas from CLAUDE.md are all present**

Map each and confirm a test exists: identifier/route validation (`test_routing.py`, `test_hierarchy_service.py::TestParentValidation`), timestamp handling (`test_generators.py::TestBuildTimestamps`, `test_seed_integrity.py::TestSamplingCadence`), numeric parsing/formatting (`test_metrics_config.py::TestFormatValue`), KPI calculations (`test_monitoring_service.py::TestComputeStatistics`/`TestComputeDelta`), status calculation (`test_monitoring_service.py::TestEvaluateFreshness`), empty-data behaviour (`TestGetMetricView` empty cases, `test_components.py`), repository range filtering (`test_plant_monitoring_repository.py::TestRangeQueries`).

Add any missing test rather than marking the item done.

- [ ] **Step 5: Commit**

```bash
git add pytest.ini tests/
git commit -m "test: seed integrity checks and two-mode test configuration"
```

**Verification:** `pytest -m "not db"` passes with Docker stopped; `pytest` passes fully with Docker running; every CLAUDE.md testing requirement maps to a named test.

---

## Phase 15: Database and Query Performance Verification

**Objective:** Prove the indexes are actually used and that no query degrades as the reading table grows.

**Files:**
- Create: `tests/test_query_performance.py`

- [ ] **Step 1: Verify index usage with EXPLAIN**

```bash
docker compose exec postgres psql -U powerplant -d powerplant_demo -c "
EXPLAIN (ANALYZE, BUFFERS)
SELECT reading_ts, value FROM plant_monitoring.readings
WHERE device_id = 'plant-01-t1-d1' AND metric = 'temperature'
  AND reading_ts >= NOW() - INTERVAL '7 days' AND reading_ts <= NOW()
ORDER BY reading_ts ASC;"
```

Expected: an `Index Scan` (or `Index Only Scan`) using `ix_readings_device_metric_ts`. A `Seq Scan` here is a failure — re-check that the index exists and that `ANALYZE` has run.

- [ ] **Step 2: Verify the batched latest query**

```bash
docker compose exec postgres psql -U powerplant -d powerplant_demo -c "
EXPLAIN (ANALYZE, BUFFERS)
SELECT DISTINCT ON (metric) metric, reading_ts, value
FROM plant_monitoring.readings WHERE device_id = 'plant-01-t1-d1'
ORDER BY metric, reading_ts DESC;"
```

Expected: index scan, no external sort. Record the reported execution time.

- [ ] **Step 3: Write the performance regression tests**

Create `tests/test_query_performance.py`:

```python
"""Query performance guards against the seeded 1.38M-row dataset.

Thresholds are deliberately loose - they catch a missing index or an
accidental full-table scan, not small machine-to-machine variation.
"""
from __future__ import annotations

import time
from datetime import timedelta

import pytest
from sqlalchemy import text

from config.metrics import METRIC_KEYS
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import monitoring_service as svc

pytestmark = pytest.mark.db

DEVICE = "plant-01-t1-d1"
SLOW_QUERY_SECONDS = 1.0


def _elapsed(fn) -> float:
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


class TestIndexUsage:
    def test_range_query_uses_the_composite_index(self):
        with session_scope() as session:
            plan = "\n".join(
                r[0]
                for r in session.execute(
                    text(
                        """
                        EXPLAIN SELECT reading_ts, value FROM plant_monitoring.readings
                        WHERE device_id = :d AND metric = 'temperature'
                          AND reading_ts >= NOW() - INTERVAL '7 days'
                          AND reading_ts <= NOW()
                        ORDER BY reading_ts ASC
                        """
                    ),
                    {"d": DEVICE},
                ).all()
            )
        assert "ix_readings_device_metric_ts" in plan
        assert "Seq Scan" not in plan

    def test_transformer_lookup_avoids_sequential_scan(self):
        with session_scope() as session:
            plan = "\n".join(
                r[0]
                for r in session.execute(
                    text(
                        "EXPLAIN SELECT * FROM plant_monitoring.transformers WHERE plant_id = 'plant-01'"
                    )
                ).all()
            )
        assert "Seq Scan" not in plan or "transformers" not in plan


class TestQueryLatency:
    def test_latest_reading_is_fast(self):
        assert _elapsed(lambda: repo.get_latest_reading(DEVICE, "temperature")) < SLOW_QUERY_SECONDS

    def test_batched_latest_for_all_metrics_is_fast(self):
        assert _elapsed(lambda: repo.get_latest_readings_for_device(DEVICE)) < SLOW_QUERY_SECONDS

    def test_thirty_day_range_is_fast(self):
        latest = repo.get_latest_reading(DEVICE, "temperature")
        start = latest.timestamp - timedelta(days=30)
        assert (
            _elapsed(
                lambda: repo.get_readings_in_range(DEVICE, "temperature", start, latest.timestamp)
            )
            < SLOW_QUERY_SECONDS
        )

    def test_full_device_view_is_fast(self):
        assert _elapsed(lambda: svc.get_device_full_view(DEVICE, svc.Period.LAST_30D)) < SLOW_QUERY_SECONDS


class TestBoundedResultSizes:
    def test_thirty_day_single_metric_returns_1441_rows(self):
        latest = repo.get_latest_reading(DEVICE, "temperature")
        rows = repo.get_readings_in_range(
            DEVICE, "temperature", latest.timestamp - timedelta(days=30), latest.timestamp
        )
        assert len(rows) == 1441

    def test_full_device_thirty_day_view_is_bounded(self):
        """8 metrics x 1441 samples - never the whole 1.38M-row table."""
        views = svc.get_device_full_view(DEVICE, svc.Period.LAST_30D)
        total = sum(len(v.series) for v in views.values())
        assert total == 1441 * len(METRIC_KEYS)
```

- [ ] **Step 4: Run the performance tests**

Run: `python -m pytest tests/test_query_performance.py -v`
Expected: PASS

If a latency test fails, run `ANALYZE plant_monitoring.readings;` first — a freshly bulk-loaded table has no statistics. If it still fails, the plan is wrong; fix the query or the index, do not raise the threshold.

- [ ] **Step 5: Confirm no unbounded query path exists**

```bash
grep -rn 'get_all_readings\|SELECT \* FROM plant_monitoring.readings' --include=*.py . | grep -v '\.venv'
```

Expected: no output. Every reading query must be bounded by device, metric and time range.

- [ ] **Step 6: Commit**

```bash
git add tests/test_query_performance.py
git commit -m "test: query plan and latency guards against the 1.38M-row dataset"
```

**Verification:** `EXPLAIN` confirms index scans on both hot paths; all latency tests pass under 1s; no unbounded reading query exists anywhere in the codebase.

---

## Phase 16: End-to-End Verification

**Objective:** Walk the complete operator journey on a freshly built environment and confirm every acceptance criterion.

**Files:** None modified — this phase is verification only. Fix any defect found in the phase that owns it, then re-run this phase.

- [ ] **Step 1: Rebuild from scratch**

```bash
docker compose down -v
docker compose up -d
python -m db.seed_plant_monitoring --reset
python -m pytest -v
python app.py
```

Expected: clean database, seed reports 30/71/120/1,383,360, full suite green, app starts without warnings.

- [ ] **Step 2: Authentication**

Confirm: the login page appears for an unauthenticated visit to `/plants`; wrong credentials show "Invalid username or password." with no stack trace; correct credentials land on `/plants`; the Logout button returns to login; and after logout, navigating directly to `/devices/plant-01-t1-d1` shows login rather than data.

- [ ] **Step 3: Hierarchy navigation**

Confirm the full journey: `/plants` (30 rows) → click a plant → transformer list → click a transformer → device list → click a device → dashboard. At every step the breadcrumb is correct and each crumb navigates back. Then use the header selector to jump directly to a device under a different plant.

- [ ] **Step 4: Device dashboard, all eight metrics**

On `/devices/plant-01-t1-d1`, select each of the 8 metrics in turn and confirm for each: the KPI labels match its aggregation, the chart axis reads `Label (unit)` (or bare label for Power Factor), values carry the configured precision, and the readings-table header matches. Specifically confirm Reactive Power reads **MVAr** and Energy shows **Period Change**, never Average.

- [ ] **Step 5: Time ranges**

For Temperature and again for Energy, cycle 24h → 7d → 30d → custom. Confirm: the chart span changes; Min/Max/Average (or Period Change) recompute; **Current does not change**; a custom range narrower than the data returns a correct subset; and a custom range entirely before the data shows the empty-data panel while Current and Last-data still display.

- [ ] **Step 6: Scale check across the hierarchy**

Spot-check five devices from five different plants, including one from a single-transformer plant and one from a four-transformer plant. Each must load its own distinct data with no cross-contamination of identity, and each dashboard must render in well under a second.

- [ ] **Step 7: Failure and edge states**

Confirm all four: not-found (`/devices/does-not-exist`), confused-deputy (`/plants/plant-02/plant-01-t1`), database down (`docker compose stop postgres`, reload → error panel, then `start`), and stale data (`STALE_AFTER_INTERVALS=0 python app.py` → Stale badges with values still shown).

In every failure state confirm no SQL, table name, stack trace, connection string, password or internal identifier beyond the URL's own IDs is visible.

- [ ] **Step 8: URL sharing**

Copy `/devices/plant-01-t1-d1?metric=reactive_power&period=7d`, open it in a private window, log in, and confirm it lands on exactly that metric and period.

- [ ] **Step 9: Record results**

Write the outcome of Steps 1–8 into the phase checklist as pass/fail with notes. Any failure is fixed in its owning phase and this phase re-run from Step 1 — do not patch around a defect here.

**Verification:** Every step above passes on a from-scratch environment.

---

## Phase 17: Documentation Updates

**Objective:** Make every document describe the application that now exists, with data provenance stated unambiguously.

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `PROJECT_CONTEXT.md`, `REQUIREMENTS.md`, `ARCHITECTURE.md`, `DATABASE.md`, `UI_SPEC.md`, `IMPLEMENTATION_PLAN.md`

- [ ] **Step 1: Rewrite `README.md`**

Must contain, and every command must be verified by running it: prerequisites; `docker compose up -d`; `python -m db.seed_plant_monitoring --reset`; `python app.py`; the login URL and demo credentials source (`.env`, never hard-coded in the doc); `python -m pytest` and `python -m pytest -m "not db"`; the full environment-variable table including `UI_REFRESH_INTERVAL_SECONDS`, `EXPECTED_INTERVAL_MINUTES`, `STALE_AFTER_INTERVALS`; and a route table.

Add a prominent **Data provenance** section reproducing the table from the spec: plant metadata is real (Kaggle/WRI); hierarchy distribution, all identifiers except `AA12`/`29017`, all measurements and all units are synthetic development data; no client thresholds exist.

- [ ] **Step 2: Rewrite `CLAUDE.md`**

The current file describes the retired single-device demo and now actively misleads. Replace the Fixed Demo Scope section with the real hierarchy scope, and update: Mission, Required Stack (unchanged), Critical Architecture Rules (rules 4–6 about `aa12_29017` resolution no longer apply — replace with the normalized-model rules), Client Database Facts vs Assumptions (keep, it is still accurate and valuable), Data Rules (8 metrics, cumulative energy, no thresholds), UI Requirements (the new operator workflow), Testing Expectations (the Phase 14 mapping), and Definition of Done.

Keep the instruction to read the numbered design docs, updating the list to include the new spec.

- [ ] **Step 3: Rewrite `DATABASE.md`**

Document the `plant_monitoring` schema: the four tables with every column, all keys, foreign keys, unique constraints and the three indexes, plus why each index exists. State plainly that we deliberately do not reproduce the client's ~2,112-table structure, and that `status` is administrative only.

Preserve the existing "Client Database Facts vs Assumptions" content — it remains the record of what is actually known from the client's screenshots — and mark clearly which parts of our model are our own design.

- [ ] **Step 4: Rewrite `ARCHITECTURE.md`**

Document the layering with the new module map, the rule that SQL exists only in `repositories/plant_monitoring_repository.py`, the three-independent-concepts rule (administrative status / freshness / monitoring condition), the metric-metadata pattern and why aggregation lives in config rather than components, the batched-query strategy, and the callback organization including the single-writer rule for the device dashboard.

- [ ] **Step 5: Rewrite `UI_SPEC.md`**

Document the routes, the operator workflow, each page's contents, the snapshot-strip and KPI behaviour per aggregation, the freshness presentation and its explicit distinction from connectivity, the empty/not-found/error states, and the responsive breakpoints.

- [ ] **Step 6: Update `REQUIREMENTS.md`, `PROJECT_CONTEXT.md` and `IMPLEMENTATION_PLAN.md`**

`REQUIREMENTS.md` — restate scope as the 30-plant primary application. `PROJECT_CONTEXT.md` — record the direction change, that the 30-plant system is now primary and the single-device demo is retired. `IMPLEMENTATION_PLAN.md` — replace with a pointer to this plan and the spec, so there is one authoritative plan rather than two competing ones.

- [ ] **Step 7: Verify every documented command actually runs**

Work through `README.md` top to bottom on a clean checkout, executing each command verbatim. Any command that fails or produces different output than documented is a documentation bug — fix the document.

- [ ] **Step 8: Check for stale references across all docs**

```bash
grep -rniE 'trfr_temperature|aa12_29017|seed_multi_plant|temperature_service|DEMO_WARNING_THRESHOLD|/plants dashboard demo' \
  --include=*.md . | grep -v '\.venv' | grep -v docs/superpowers
```

Expected: only intentional historical references inside "Client Database Facts" sections, where `trfr_temperature` and `aa12_29017` correctly describe the **client's** production database. Every reference describing **our** application must be gone.

- [ ] **Step 9: Commit**

```bash
git add *.md
git commit -m "docs: document the 30-plant monitoring application and data provenance"
```

**Verification:** Every README command runs as documented on a clean checkout; the stale-reference grep returns only intentional client-database references; no document still describes the retired demo as current.

---

## Self-Review Notes

Checked against the spec:

- **Coverage** — all six approved spec sections map to phases: §1→P1, §2→P2, §3→P4, §4→P5, §5→P6, §6→P7–P12. All 17 requested phases are present, plus P0 for git initialization.
- **Type consistency** — `Freshness`, `MonitoringCondition`, `Period`, `Aggregation`, `MetricConfig`, `Reading`, `MetricSnapshot`, `MetricView`, `PlantRecord`, `TransformerRecord`, `DeviceRecord`, `DevicePath`, `RawReading` are each defined once and referenced identically thereafter. Repository function names in P5 match every later call site.
- **Spec amendment** — the spec's `aggregation: str` is implemented as `Aggregation(str, Enum)`, a `str` subclass, which satisfies the stated contract while removing stringly-typed comparisons. Noted in the spec.
- **Reconciled contradiction** — the earlier "placeholder thresholds" answer is superseded by the later no-thresholds instruction. `MonitoringCondition` exists and always returns `UNKNOWN`; `MetricConfig` has no threshold fields; a test asserts their absence.
- **Known dependency** — Phase 3 declares the 8 metric keys locally and Phase 4 replaces that with the `config.metrics` import plus a drift assertion. Executing P3 and P4 out of order will fail at P4 Step 5.

