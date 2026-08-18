"""Prototype role-based access helpers — pure functions, no side effects.

These helpers answer "can a user with this role perform this action?" using
confirmed business rules from the Functional Specification. They are ready
for future real-auth integration; current demo login does not yet carry a
production role context, so these are not enforced globally.

All functions are pure and testable without Dash, database, or identity system.
"""
from __future__ import annotations


def can_program_rtl(role: str, is_assigned_to_user: bool = False) -> bool:
    """Can this user program/upload settings to an RTL?

    Business rules (BR005, §194-212):
    - Administrator: may program any RTL on the system.
    - Technician: may program only RTLs assigned to them.
    - General User: must NOT receive programming actions.
    """
    if role == "administrator":
        return True
    if role == "technician":
        return is_assigned_to_user
    return False


def can_manage_assignment(role: str) -> bool:
    """Can this user assign/reassign devices to transformers?

    Business rules (§194-212):
    - Administrator: broader RTL management access.
    - Technician: works with assigned RTLs only.
    - General User: no device-management actions.
    """
    return role == "administrator"


def can_toggle_message_forwarding(role: str, is_assigned_to_user: bool = False) -> bool:
    """Can this user enable/disable message forwarding?

    Business rules (BR003, BR004, §194-212):
    - Administrator: may enable/disable forwarding.
    - Technician: may enable/disable forwarding for assigned RTLs.
    - General User: message-forwarding options should not be available.
    """
    if role == "administrator":
        return True
    if role == "technician":
        return is_assigned_to_user
    return False


def can_deactivate_rtl(role: str, is_assigned_to_user: bool = False) -> bool:
    """Can this user deactivate/remove an RTL from the active list?

    Business rules (BR012, §194-212):
    - Administrator: may remove any RTL from active list.
    - Technician: may remove RTLs assigned to them after device removal.
    - General User: must NOT receive device-management actions.
    """
    if role == "administrator":
        return True
    if role == "technician":
        return is_assigned_to_user
    return False


def can_view_device(role: str) -> bool:
    """Can this user view transformer/device data?

    All confirmed roles can view data (§194-212).
    """
    return role in ("administrator", "technician", "general")


def can_export_data(role: str) -> bool:
    """Can this user export data?

    All confirmed roles can export data (§194-212).
    """
    return role in ("administrator", "technician", "general")
