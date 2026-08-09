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
