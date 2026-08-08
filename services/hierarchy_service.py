"""
Hierarchy service — validation and active-entity filtering.

Administrative status is read **only here**, only to decide what is selectable
for live monitoring. It is never combined with, or used as a substitute for,
computed monitoring status or data freshness.
"""
from __future__ import annotations

from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import (
    DevicePath,
    DeviceRecord,
    PlantRecord,
    TransformerRecord,
)

ACTIVE = "active"


def _active_only(records: list, include_inactive: bool) -> list:
    return records if include_inactive else [r for r in records if r.status == ACTIVE]


def list_plants(include_inactive: bool = False) -> list[PlantRecord]:
    return _active_only(repo.list_plants(), include_inactive)


def list_transformers(plant_id: str, include_inactive: bool = False) -> list[TransformerRecord]:
    return _active_only(repo.list_transformers(plant_id), include_inactive)


def list_devices(transformer_id: str, include_inactive: bool = False) -> list[DeviceRecord]:
    return _active_only(repo.list_devices(transformer_id), include_inactive)


def get_plant_or_none(plant_id: str) -> PlantRecord | None:
    return repo.get_plant(plant_id)


def get_transformer_in_plant(plant_id: str, transformer_id: str) -> TransformerRecord | None:
    transformer = repo.get_transformer(transformer_id)
    if transformer is None or transformer.plant_id != plant_id:
        return None
    return transformer


def get_device_in_transformer(transformer_id: str, device_id: str) -> DeviceRecord | None:
    device = repo.get_device(device_id)
    if device is None or device.transformer_id != transformer_id:
        return None
    return device


def get_device_context(device_id: str) -> DevicePath | None:
    return repo.get_device_breadcrumb(device_id)


def get_plant_hierarchy_counts() -> dict[str, tuple[int, int]]:
    return repo.count_hierarchy_by_plant()
