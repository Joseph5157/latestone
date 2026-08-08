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
