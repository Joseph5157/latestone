"""Device registration — backed by plant_monitoring.devices (DB-4).

Thin service boundary between callbacks/device_register.py and
repositories/plant_monitoring_repository.py, matching the layering
services/prototype_users.py (DB-2) and services/prototype_assignments.py
(DB-3) already established. The callback must not call the repository
directly.

Registration is create-only: there is no edit/update path wired to any UI
yet, so this module does not expose one beyond the repository-level
update_device_metadata passthrough (kept for a later commissioning phase).

AUD-1: every registration writes a DEVICE_REGISTERED audit row in the SAME
transaction as the device insert — an audit failure rolls the registration
back. The actor is the authenticated administrator's user_id from the
session store, passed through unchanged (strict D2: no re-resolution).
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import UNSET, DeviceRecord, _Unset
from services import audit_service
from services.rtl_uid import uid_format_error

logger = logging.getLogger(__name__)


class RegistrationError(Exception):
    """A registration attempt failed for a reason safe to show the user."""


def device_code_problem(device_code: str | None, *, session=None) -> str | None:
    """Why `device_code` cannot be registered, or None if it can (ADR-022).

    Checks the shared 5-digit UID format first, then whether the code is
    already registered anywhere in the fleet. The RTL Master addresses a
    device by UID alone, and event ingestion attributes an ambiguous UID to
    no device, so a second registration would silence both. The message
    names where the existing device is, so the operator can go and look.

    Application-level only: the schema guarantees uniqueness per transformer,
    not fleet-wide, until the client confirms the rule.
    """
    format_error = uid_format_error(device_code)
    if format_error:
        return format_error
    code = device_code.strip()
    existing = repo.find_device_ids_by_code(code, session=session)
    if not existing:
        return None
    path = repo.get_device_breadcrumb(existing[0])
    if path is None:
        return f"Device code {code} is already registered."
    return (
        f"Device code {code} is already registered at {path.plant_name}, "
        f"transformer {path.transformer_code}."
    )


def register_device(
    transformer_id: str,
    device_code: str,
    status: str = "active",
    *,
    actor_user_id: int,
) -> DeviceRecord:
    """Register a new device and record who did it. Raises RegistrationError
    with a friendly message on a code that is not 5 digits or is already
    registered anywhere in the fleet (ADR-022), an unknown transformer, a
    rare concurrent-registration race caught by the database's own
    constraints, or an audit failure — never lets SQL or a stack trace
    surface.
    """
    try:
        with session_scope() as session:
            problem = device_code_problem(device_code, session=session)
            if problem:
                raise RegistrationError(problem)
            device_code = device_code.strip()
            device = repo.create_device(
                transformer_id, device_code, status, session=session
            )
            audit_service.record(
                session,
                operation=audit_cfg.DEVICE_REGISTERED,
                entity_type=audit_cfg.ENTITY_DEVICE,
                entity_id=device.device_id,
                old_values=None,
                new_values={
                    "device_id": device.device_id,
                    "transformer_id": device.transformer_id,
                    "device_code": device.device_code,
                    "status": device.status,
                },
                actor_user_id=actor_user_id,
            )
            return device
    except ValueError as exc:
        raise RegistrationError(str(exc)) from exc
    except audit_service.AuditError as exc:
        logger.error(
            "Audit failure blocked device registration: transformer_id=%s "
            "device_code=%s actor=%s",
            transformer_id,
            device_code,
            actor_user_id,
        )
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
