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
actor's user_id. BR016's daily cutoff belongs to the RTL Master, so this
application has no system-originated forwarding-disable path.
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

#: Internal alarm acknowledgement.  This records an operator response to one
#: persisted event; it neither clears nor resolves the event/alarm.
ALARM_ACKNOWLEDGED = "ALARM_ACKNOWLEDGED"

#: THRESH-CONFIG-1 (C-01, framework only): an Administrator setting,
#: changing, or clearing the single global warning/critical temperature
#: threshold configuration. Always human-originated — there is no
#: system-originated path for this feature at all (no scheduler, no
#: automatic threshold evaluation exists yet; see AGENTS.md §Data rules).
TEMPERATURE_THRESHOLD_SET = "TEMPERATURE_THRESHOLD_SET"
TEMPERATURE_THRESHOLD_CLEARED = "TEMPERATURE_THRESHOLD_CLEARED"

#: VIB-CONFIG-1 (C-02, framework only): an Administrator recording,
#: changing, or clearing the answer to ONE vibration contract question.
#: Always human-originated. Unlike C08's override or THRESH-CONFIG-1's
#: threshold (each a single global fact), there are up to 15 independent
#: answers — the entity_id is the specific question_key, not a fixed
#: "global" string, so each question's own audit history stays contiguous.
VIBRATION_CONTRACT_ANSWER_SET = "VIBRATION_CONTRACT_ANSWER_SET"
VIBRATION_CONTRACT_ANSWER_CLEARED = "VIBRATION_CONTRACT_ANSWER_CLEARED"

#: FRESHNESS-CONFIG-1: an Administrator setting, changing, or clearing the
#: global Stale-after threshold. Always human-originated.
FRESHNESS_THRESHOLD_SET = "FRESHNESS_THRESHOLD_SET"
FRESHNESS_THRESHOLD_CLEARED = "FRESHNESS_THRESHOLD_CLEARED"

#: TECHNICIAN-REAL-RTL-ACCESS-01: client-RTL Technician assignment lifecycle.
#: entity_id is the client RTL UID as text (a stable identity, per this
#: module's convention); the assignment_id travels in old/new values. A
#: reassignment writes RTL_ASSIGNMENT_ENDED (old row) then
#: RTL_ASSIGNMENT_REASSIGNED (the change) in one transaction. Legacy import
#: writes no per-row audit: it is a controlled bootstrap, recorded by its own
#: evidence, and it has no human actor to record.
RTL_ASSIGNMENT_CREATED = "RTL_ASSIGNMENT_CREATED"
RTL_ASSIGNMENT_REASSIGNED = "RTL_ASSIGNMENT_REASSIGNED"
RTL_ASSIGNMENT_ENDED = "RTL_ASSIGNMENT_ENDED"

#: AUTHENTICATION-LOCAL-HARDENING-01 (ADR-033): account lifecycle and sign-in.
#: entity_type is `user`, entity_id is str(users.user_id) (an unknown login
#: name is recorded as "unknown" and never with the typed text, which may be a
#: mistyped password). NO row ever carries a password, a hash, a token or a
#: cookie; token-bearing events record only the purpose and expiry.
#: LOGIN_FAILED / LOGIN_THROTTLED / ADMIN_BOOTSTRAPPED have no signed-in human
#: actor and are the only entries added to SYSTEM_OPERATIONS for this gate.
LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
LOGIN_FAILED = "LOGIN_FAILED"
LOGIN_THROTTLED = "LOGIN_THROTTLED"
LOGOUT = "LOGOUT"
ACCOUNT_ACTIVATED = "ACCOUNT_ACTIVATED"
ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
ACCOUNT_REENABLED = "ACCOUNT_REENABLED"
PASSWORD_SETUP_ISSUED = "PASSWORD_SETUP_ISSUED"
PASSWORD_SETUP_COMPLETED = "PASSWORD_SETUP_COMPLETED"
PASSWORD_RESET_INITIATED = "PASSWORD_RESET_INITIATED"
PASSWORD_RESET_COMPLETED = "PASSWORD_RESET_COMPLETED"
USER_ROLE_CHANGED = "USER_ROLE_CHANGED"
CLIENT_PERSON_LINK_CHANGED = "CLIENT_PERSON_LINK_CHANGED"
ADMIN_BOOTSTRAPPED = "ADMIN_BOOTSTRAPPED"

#: The complete allowlist of operations that may be audited with a NULL
#: actor via ``audit_service.record(..., system_originated=True)``.
#: Deliberately minimal (ACT-D5): each entry must correspond to an actually
#: implemented system-originated feature. BR016 is intentionally absent: the
#: RTL Master, not this dashboard, owns its daily forwarding cutoff.
SYSTEM_OPERATIONS = frozenset(
    {RTL_ACTIVATED, LOGIN_FAILED, LOGIN_THROTTLED, ADMIN_BOOTSTRAPPED}
)

ENTITY_DEVICE = "device"
ENTITY_ASSIGNMENT = "device_assignment"
ENTITY_USER = "user"
ENTITY_RTL_ASSIGNMENT = "rtl_assignment"
ENTITY_MESSAGE_FORWARDING = "message_forwarding"

#: THRESH-CONFIG-1: same shape as the auto-disable override above — one
#: global row, no per-device/per-user entity to name.
ENTITY_TEMPERATURE_THRESHOLD = "temperature_threshold"
TEMPERATURE_THRESHOLD_ENTITY_ID = "global"

#: VIB-CONFIG-1: entity_id is the vibration contract's own question_key
#: (e.g. "unit", "axes") — a stable identity per question, per this
#: module's own "Entity IDs are stable database identities" convention
#: (see the module docstring), NOT a fixed "global" string like the two
#: single-fact entities above.
ENTITY_VIBRATION_CONTRACT = "vibration_contract"

#: FRESHNESS-CONFIG-1: one global row, same shape as the temperature threshold.
ENTITY_FRESHNESS_THRESHOLD = "freshness_threshold"
FRESHNESS_THRESHOLD_ENTITY_ID = "global"
