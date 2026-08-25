# AUD-1I — Implementation Specification (frozen)

**Supersedes:** §3/§4 of the AUD-1P plan output, amended by the AUD-1P review decision.
**Baseline:** `main` @ `1db0f60bbb99d61f6908363772e2667e97ccc7fc`
**Status:** APPROVED WITH ADJUSTMENTS — implementation authorised

## Frozen architecture

```
CALLBACK  (supplies actor_user_id from auth-store session)
   ↓
DOMAIN SERVICE
   ↓
session_scope()                      ← ONE transaction
   ├── repo mutation(..., session=s)
   └── audit_service.record(s, ...)  ← repo insert_audit_log(session=s)
   ↓
single COMMIT — any failure ROLLS BACK BOTH
```

## Approved adjustments applied

| ID | Decision |
|---|---|
| D1 | Genuine assignment no-op (same technician) writes NO audit row |
| D2 | UI mutations require a valid non-null `actor_user_id` (from session store `AuthenticatedUser.user_id`, `auth_service.py:58`). Missing/invalid actor FAILS the operation. `audit_log.user_id = NULL` reserved for future system-originated actions only. No username→id re-resolution. |
| UPS | No `xmax`. `create_or_update_user` uses SELECT…FOR UPDATE before-image inside the transaction: absent → INSERT (USER_CREATED), present → UPDATE (USER_UPDATED); RETURNING row = after image. Concurrent-insert race now surfaces as IntegrityError (explicit retry) instead of silent merge — accepted trade-off of the approved design. |
| EID | Stable entity IDs: device registration → (`device`, device_id); assignment ops → (`device_assignment`, **device_id**); user ops → (`user`, str(user_id)). Assignment IDs + technician details live inside old/new values. |

## Snapshot allowlists (JSONB payloads — explicit fields only, never object dumps; never credentials/secrets/env/connection data)

| Operation | old_values | new_values |
|---|---|---|
| DEVICE_REGISTERED | null | {device_id, transformer_id, device_code, status} |
| DEVICE_ASSIGNED (fresh) | null | {assignment_id, technician_user_id, technician_username} |
| DEVICE_ASSIGNED (reassign) | {assignment_id, technician_user_id, technician_username} of closed row | same shape, new row |
| DEVICE_UNASSIGNED | closed-row snapshot | null |
| USER_CREATED | null | {username, full_name, email_address, role, status} |
| USER_UPDATED | before image (same fields) | after image (same fields) |

## Signature changes (all call sites updated in this phase)

Repository:
- `insert_audit_log(*, operation, entity_type, entity_id, old_values=None, new_values=None, actor_user_id=None, session=None) -> int` — JSONB bound via json.dumps + `CAST(… AS jsonb)`; occurred_at stays server_default now().
- `create_device(transformer_id, device_code, status="active", *, session=None)` — behavior unchanged without session.
- `assign_device_to_user(device_id, technician_username, assigned_by_user_id=None, *, session=None, with_change_info=False)` — third param renamed username→user_id (verified: no caller ever passed a non-null value). Returns `AssignmentRecord`, or `AssignmentChange(previous, current, changed)` when with_change_info.
- `end_active_device_assignment(device_id, ended_at=None, *, session=None) -> list[AssignmentRecord]` — UPDATE…RETURNING; returns closed snapshots (existing callers ignore return value).
- `create_or_update_user(username, full_name, role, status, email_address=None, mobile_number=None, *, session=None, with_change_info=False)` — returns UserRecord, or `(UserRecord, created: bool, before: UserRecord | None)` when with_change_info.

Services:
- `services/audit_service.py` (new): `record(session, *, operation, entity_type, entity_id, old_values=None, new_values=None, actor_user_id: int) -> None` — session REQUIRED (composition only; never commits), actor_user_id REQUIRED int (strict D2).
- `register_device(transformer_id, device_code, status="active", *, actor_user_id: int)`
- `assign_technician(device_id, technician_username, *, actor_user_id: int)` — also populates `user_device_assignments.assigned_by` with the actor (fixes existing gap at callbacks/device_assign.py:269)
- `unassign_technician(device_id, *, actor_user_id: int)` — silent no-op (no audit) when nothing to close
- `upsert_user(username, identifier="", role="general", status="active", *, actor_user_id: int)`

Callbacks (thin edits only):
- `device_register._submit_registration` — capture the already-resolved session user, pass its id
- `device_assign` confirm — same
- `user_admin.confirm_user_form` — currently receives NO auth data: add `State("auth-store","data")`, resolve actor; absent/invalid session fails closed (cannot audit ⇒ cannot proceed, per D2). NOTE: no MANAGE_USERS policy constant exists yet — adding full in-callback capability policy for this page is recommended follow-up, out of AUD-1 scope.

Known behaviour note: user rename path (remove+create, callbacks/user_admin.py:244–249) audits as USER_CREATED of the new username; deletions remain unaudited (out of approved flow list).

## Scope fence

Only: device registration, technician assign/reassign/unassign, user create/update. NOT audited: Program RTL prototype, forwarding mock toggle, deactivate prototype, report generation mock, notification views. Repo-level callers (seeds, test helpers using repository functions directly) are unchanged and write no audit rows.

## Test plan

Update existing service-level call sites (test_device_register.py, test_device_assign.py, test_action_guard_db.py) to pass actor ids from fixture-created admin users. New `tests/test_audit_wiring.py` (db-marked, isolated_schema): atomicity proof (patched failing audit insert ⇒ primary mutation rolled back), register/assign/reassign/unassign/user-create/user-update audit content, D1 no-op suppression, unknown-actor IntegrityError failure.
