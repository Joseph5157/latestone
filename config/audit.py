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
action. A human-initiated MESSAGE_FORWARDING_* row always carries the
actor's user_id; the NULL-user_id path is used by the 18:30 auto-disable job
(C08-AUTO-DISABLE-1), which reuses MESSAGE_FORWARDING_DISABLED with
``system_originated=True`` rather than a second constant.
"""
from __future__ import annotations

DEVICE_REGISTERED = "DEVICE_REGISTERED"
DEVICE_ASSIGNED = "DEVICE_ASSIGNED"
DEVICE_UNASSIGNED = "DEVICE_UNASSIGNED"
USER_CREATED = "USER_CREATED"
USER_UPDATED = "USER_UPDATED"
MESSAGE_FORWARDING_ENABLED = "MESSAGE_FORWARDING_ENABLED"
MESSAGE_FORWARDING_DISABLED = "MESSAGE_FORWARDING_DISABLED"

#: Written against the stable device entity (PROG-D5): the request row's
#: surrogate key travels inside new_values, never in entity_id.
RTL_PROGRAM_REQUESTED = "RTL_PROGRAM_REQUESTED"

#: Active-list deactivation (OPS-DEACT-1), also against the stable device
#: entity. Only the genuine is_active true→false transition is audited.
RTL_DEACTIVATED = "RTL_DEACTIVATED"

#: Active-list activation (INGEST-1), also against the stable device entity.
#: Only the genuine absent→active / inactive→active transition is audited;
#: an already-active startup is a no-op with no audit row (ACT-D3). Always
#: written system-originated — a startup event has no human actor (ACT-D5).
RTL_ACTIVATED = "RTL_ACTIVATED"

#: C08-AUTO-DISABLE-1: an Administrator setting or clearing the temporary
#: same-day cutoff override. Always human-originated (the actor is whoever
#: clicked the control), against the single global entity — there is
#: deliberately no per-user/per-RTL dimension (development baseline: one
#: global override only).
AUTO_DISABLE_OVERRIDE_SET = "AUTO_DISABLE_OVERRIDE_SET"
AUTO_DISABLE_OVERRIDE_CLEARED = "AUTO_DISABLE_OVERRIDE_CLEARED"

#: The complete allowlist of operations that may be audited with a NULL
#: actor via ``audit_service.record(..., system_originated=True)``.
#: Deliberately minimal (ACT-D5): each entry must correspond to an actually
#: implemented system-originated feature. MESSAGE_FORWARDING_DISABLED is
#: reused here (C08-AUTO-DISABLE-1) exactly as this module's earlier comment
#: anticipated — the scheduled auto-disable writes the same operation a
#: human manual disable does, distinguished only by ``actor_user_id`` being
#: NULL, never by a second constant.
SYSTEM_OPERATIONS = frozenset({RTL_ACTIVATED, MESSAGE_FORWARDING_DISABLED})

ENTITY_DEVICE = "device"
ENTITY_ASSIGNMENT = "device_assignment"
ENTITY_USER = "user"
ENTITY_MESSAGE_FORWARDING = "message_forwarding"

#: C08-AUTO-DISABLE-1's override is a single global row (no per-user/per-RTL
#: entity to name), so its audit entity_id is always the fixed string below,
#: never a database id.
ENTITY_AUTO_DISABLE_SCHEDULE = "forwarding_auto_disable"
AUTO_DISABLE_SCHEDULE_ENTITY_ID = "global"
