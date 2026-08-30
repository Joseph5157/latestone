"""
Hierarchy service — validation and active-entity filtering.

Administrative status is read **only here**, only to decide what is selectable
for live monitoring. It is never combined with, or used as a substitute for,
computed monitoring status or data freshness.
"""
from __future__ import annotations

from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import (
    AdminDeviceRow,
    DevicePath,
    DeviceRecord,
    PlantRecord,
    TransformerRecord,
)
from services.device_scope import DeviceScope

ACTIVE = "active"


def _active_only(records: list, include_inactive: bool) -> list:
    return records if include_inactive else [r for r in records if r.status == ACTIVE]


def list_plants(
    *, scope: DeviceScope, include_inactive: bool = False
) -> list[PlantRecord]:
    """Plants within the caller's scope.

    Scope and `include_inactive` are independent filters and both apply.
    """
    return _active_only(
        repo.list_plants(allowed_device_ids=scope.device_ids), include_inactive
    )


def list_transformers(
    plant_id: str, *, scope: DeviceScope, include_inactive: bool = False
) -> list[TransformerRecord]:
    """Transformers under one plant, within the caller's scope."""
    return _active_only(
        repo.list_transformers(plant_id, allowed_device_ids=scope.device_ids),
        include_inactive,
    )


def list_devices(
    transformer_id: str, *, scope: DeviceScope, include_inactive: bool = False
) -> list[DeviceRecord]:
    """Devices under one transformer, within the caller's scope.

    `scope` is keyword-only and undefaulted for the same reason
    `allowed_device_ids` is: the fail-open seam closes at both boundaries or
    at neither.

    Scope and `include_inactive` are independent filters and both apply. Scope
    narrows the population; it never widens it past an existing filter, so an
    assigned-but-inactive device stays hidden under the active-only default.
    """
    return _active_only(
        repo.list_devices(transformer_id, allowed_device_ids=scope.device_ids),
        include_inactive,
    )


def list_device_paths(device_ids, *, scope: DeviceScope) -> list[DevicePath]:
    """Label paths (plant name / transformer code / device code) for a
    bounded set of devices, within the caller's scope (ADR-008, Phase 9).

    Deliberately has no `include_inactive` flag and applies no `_active_only`
    filter. Every other listing here decides what is SELECTABLE for live
    monitoring; this one names assets on records of things that already
    happened, and an event does not stop needing a name because its RTL was
    deactivated afterwards. Adding the flag would invite a caller to hide
    real history behind an administrative status.
    """
    return repo.list_device_paths(device_ids, allowed_device_ids=scope.device_ids)


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


def get_plant_hierarchy_counts(
    *, scope: DeviceScope, include_inactive: bool = False
) -> dict[str, tuple[int, int]]:
    """Counts matching what the drill-down pages actually list, within scope.

    The default must stay aligned with `list_transformers`/`list_devices`, or
    an overview row will disagree with the page it opens — and now that
    includes agreeing about scope.
    """
    return repo.count_hierarchy_by_plant(
        allowed_device_ids=scope.device_ids, include_inactive=include_inactive
    )


def list_all_devices(include_inactive: bool = False) -> list[AdminDeviceRow]:
    """Every device in the fleet with its plant/transformer path.

    Follows the same active-only default as `list_devices`. The admin page
    owns the view; this service function owns the data boundary.
    """
    return repo.list_all_devices(include_inactive=include_inactive)


def is_active(record) -> bool:
    """Administrative state only — never a monitoring or freshness signal.

    Inactive equipment stays reachable by direct URL so its history can still be
    inspected; the pages mark it rather than hiding it.
    """
    return getattr(record, "status", ACTIVE) == ACTIVE
