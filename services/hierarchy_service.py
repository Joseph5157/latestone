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


def entity_in_scope(
    scope: DeviceScope,
    *,
    device_id: str | None = None,
    plant_id: str | None = None,
    transformer_id: str | None = None,
) -> bool:
    """Whether a resolved entity is visible to `scope`.

    AUTH-HARDEN-1R (blocker 2). Moved here from `callbacks/routing.py`
    (re-exported there unchanged) so callers OTHER than the router — the
    plant/transformer detail data callbacks in `callbacks/listings.py` — can
    revalidate an entity against the CURRENT trusted scope too. The router's
    own check only ever guarded the render that BUILT `page-context`; a data
    callback listening on that same store as an Input is independently
    invokable with a forged plant_id/transformer_id, exactly the class of
    bypass P0-3 closed for device telemetry. This is that same fix for plant
    and transformer metadata.

    AUTH-HARDEN-1R2: for a RESTRICTED scope, call this FIRST, before any
    unrestricted existence lookup — never after. This function is itself
    scope-filtered (`list_transformers`/`list_devices` take
    `allowed_device_ids`), so a nonexistent entity and a real-but-out-of-scope
    one both simply come back False from here; the caller must not run its
    own existence lookup first to tell the two apart, because for a
    restricted Technician that IS the distinction ROLE-1 froze as
    unacceptable at the identity/route layer and AUTH-HARDEN-1R2 closed here:
    a restricted caller must not be able to learn that an id exists at all
    once it is confirmed not theirs. `callbacks/routing.py`'s plant/
    transformer/device branches and `callbacks/listings.py`'s detail
    callbacks all call this before their own existence lookup for exactly
    this reason. (Existence-then-membership, in that order, remains correct
    ONLY for an UNRESTRICTED scope — Administrator/General — where this
    function short-circuits True with no query below, so the caller's own
    existence lookup is the only check that ever really runs and Not Found
    stays the honest answer.)

    A plant or transformer is visible when it holds at least one visible
    device, so a Technician cannot hand-type a path to an otherwise-valid
    plant containing none of their RTLs.

    The unrestricted short-circuit is first for cost, not just clarity: an
    Administrator would otherwise pay for a listing query on every plant and
    transformer render purely to discard the answer.

    Default-deny: called with no identifier, it refuses.
    """
    if scope.is_unrestricted:
        return True
    if device_id is not None:
        return scope.allows(device_id)
    if transformer_id is not None:
        return bool(list_devices(transformer_id, scope=scope))
    if plant_id is not None:
        return bool(list_transformers(plant_id, scope=scope))
    return False


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
