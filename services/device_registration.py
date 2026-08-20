"""Device registration — backed by plant_monitoring.devices (DB-4).

Thin service boundary between callbacks/device_register.py and
repositories/plant_monitoring_repository.py, matching the layering
services/prototype_users.py (DB-2) and services/prototype_assignments.py
(DB-3) already established. The callback must not call the repository
directly.

Registration is create-only: there is no edit/update path wired to any UI
yet, so this module does not expose one beyond the repository-level
update_device_metadata passthrough (kept for a later commissioning phase).
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import UNSET, DeviceRecord, _Unset

logger = logging.getLogger(__name__)


class RegistrationError(Exception):
    """A registration attempt failed for a reason safe to show the user."""


def register_device(
    transformer_id: str, device_code: str, status: str = "active"
) -> DeviceRecord:
    """Register a new device. Raises RegistrationError with a friendly
    message on an unknown transformer, a duplicate device_code under the
    same transformer, or a rare concurrent-registration race caught by the
    database's own constraints — never lets SQL or a stack trace surface.
    """
    try:
        return repo.create_device(transformer_id, device_code, status)
    except ValueError as exc:
        raise RegistrationError(str(exc)) from exc
    except IntegrityError:
        logger.exception(
            "Device registration race: transformer_id=%s device_code=%s",
            transformer_id, device_code,
        )
        raise RegistrationError(
            "This device could not be registered — it may already exist. "
            "Please try again."
        ) from None


def update_device_metadata(
    device_id: str,
    *,
    msisdn: str | None | _Unset = UNSET,
    hardware_version: str | None | _Unset = UNSET,
    firmware_version: str | None | _Unset = UNSET,
    installed_at: datetime | None | _Unset = UNSET,
) -> DeviceRecord | None:
    """Persist operational metadata for an existing device. No current UI
    calls this — see repositories.plant_monitoring_repository.update_device_metadata
    for the partial-update contract (an omitted argument leaves that column
    unchanged; pass it explicitly as None to clear it).
    """
    return repo.update_device_metadata(
        device_id,
        msisdn=msisdn,
        hardware_version=hardware_version,
        firmware_version=firmware_version,
        installed_at=installed_at,
    )
