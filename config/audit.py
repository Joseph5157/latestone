"""Audit operation and entity vocabulary (AUD-1).

Constants only — no logic. The audit_log.operation column deliberately has
no CHECK constraint (alembic/versions/007_audit_log.py documents the list
as open-ended), so this module is the application-side source of truth for
the operations written so far. Every constant must stay within the column's
VARCHAR(50) limit; tests/test_audit_vocabulary.py asserts that.

Entity IDs are stable database identities, not per-row surrogate keys:
    device           -> devices.device_id
    device_assignment-> user_device_assignments.device_id  (NOT assignment_id)
    user             -> str(users.user_id)
    message_forwarding -> str(actor's users.user_id)      (FWD-D6)
so an entity's audit stream is contiguous across its row changes. Row-level
identifiers (assignment_id) travel inside old_values/new_values instead.

The forwarding entity deliberately has no device dimension (FWD-D1): the
state belongs to the acting user; the device drawer only authorizes the
action. MESSAGE_FORWARDING_* rows are always written with the human actor
from the session — the NULL-user_id path stays reserved for the future
18:30 system job, which will reuse MESSAGE_FORWARDING_DISABLED.
"""
from __future__ import annotations

DEVICE_REGISTERED = "DEVICE_REGISTERED"
DEVICE_ASSIGNED = "DEVICE_ASSIGNED"
DEVICE_UNASSIGNED = "DEVICE_UNASSIGNED"
USER_CREATED = "USER_CREATED"
USER_UPDATED = "USER_UPDATED"
MESSAGE_FORWARDING_ENABLED = "MESSAGE_FORWARDING_ENABLED"
MESSAGE_FORWARDING_DISABLED = "MESSAGE_FORWARDING_DISABLED"

ENTITY_DEVICE = "device"
ENTITY_ASSIGNMENT = "device_assignment"
ENTITY_USER = "user"
ENTITY_MESSAGE_FORWARDING = "message_forwarding"
