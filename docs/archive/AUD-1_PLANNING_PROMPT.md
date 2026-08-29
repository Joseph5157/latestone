# AUD-1 — Read-Only Implementation Planning Prompt (for CodeX)

**Phase:** AUD-1 — Wire audit records into existing real mutations
**Mode:** READ-ONLY INSPECTION AND PLANNING ONLY
**Baseline:** `main` @ `1db0f60bbb99d61f6908363772e2667e97ccc7fc` (verify with `git rev-parse HEAD`; report any drift before proceeding)

---

## 0. Role and hard constraints

You are performing the **planning half** of AUD-1. You must produce a written implementation plan. You must **not modify, create, delete, or format any repository file**, run migrations, commit, or push. The modification phase will be a separate, later task that consumes your plan.

Non-negotiable architecture rules (from CLAUDE.md, apply to the plan you write):

1. UI/page/component/callback code never executes raw SQL.
2. All PostgreSQL access lives in `repositories/`.
3. Domain logic (including audit orchestration) lives in services.
4. Callbacks stay thin: gather inputs → call service → format outputs.
5. No new dependencies without justification.
6. Do not expand scope beyond the three AUD-1 mutation flows listed below.
7. Never log or expose secrets, connection strings, SQL, or stack traces in UI-facing error paths.

## 1. Background (established by REQ-1A / REQ-1B — do not re-litigate)

- Client PAD requires user activity auditing (RTL-AUD-01…07): activity record, timestamp, user who performed it, operation performed, old values, new values, persistence in the application database.
- `audit_log` already exists and structurally satisfies all seven fields: see `alembic/versions/007_audit_log.py` (`occurred_at`, nullable `user_id` for system actions, `operation`, `entity_type`, `entity_id`, JSONB `old_values`/`new_values`). Exhaustive grep confirms **zero writers and zero readers** today.
- Three real, persisted mutations exist in the codebase and are the AUD-1 coverage targets:
  1. **Device registration** — admin registers a device into the hierarchy (`/admin/devices/new`; callback in `callbacks/device_admin.py`, downstream service/repository).
  2. **Technician assignment / reassignment** — `user_device_assignments` close-and-insert under FOR UPDATE (`repositories/plant_monitoring_repository.py` ~985–1089), driven from `callbacks/device_assign.py`.
  3. **User creation / modification** — user upsert from `pages/user_admin.py` / `callbacks/user_admin.py`.
- Prototype-only actions (program RTL toggle, forwarding toggle, deactivate) are explicitly OUT OF SCOPE for AUD-1; they will adopt the same audit architecture when they become real (OPS-* phases).

## 2. Required inspections

Read each of these on the baseline commit and cite findings as `path:line`. If reality differs from anything stated above, STOP that section and report the discrepancy instead of planning around an assumption.

### 2.1 Audit schema and conventions
- Exact DDL of `audit_log` (columns, nullability, defaults, indexes/constraints) in `alembic/versions/007_audit_log.py`.
- How other tables handle timestamps (DB `now()` vs app-supplied) — match existing convention.
- Whether any Alembic change is needed at all (preferred answer: none).

### 2.2 Database session/connection model (critical)
Determine precisely how the app currently talks to PostgreSQL:
- Where the SQLAlchemy engine is created and how connections/sessions are obtained per request/callback (`repositories/plant_monitoring_repository.py`, any `db/` connection module).
- Whether each repository function opens its own connection/transaction, whether there is a shared session, and where commits/rollbacks happen today.
- Concurrency handling in evidence: e.g., the FOR UPDATE pattern in assignment (~985–1089).
This determines whether "mutation + audit in one transaction" is achievable today or requires introducing a transaction-scoping helper. Document both options with concrete evidence.

### 2.3 The three mutation flows, end to end
For EACH flow, trace and document the full call chain:
`page component → callback → (service?) → repository function → commit`
- Entry points, exact repository functions mutated, inputs available at each layer (actor identity, entity ids, pre/post values), and current return/error contract.
- What "old values" means per flow:
  - Registration: no old values (creation); capture what was created.
  - Assignment/reassignment: previous active assignment row(s) closed = old values; new assignment = new values.
  - User upsert: diff between stored row before and after.
- Where the actor's `user_id` can be resolved from the session/store at each call site, and how the nullable system-actor case should be handled.
- Existing error handling in each flow (what the user sees today on failure) so audit failure semantics integrate rather than fight it.

### 2.4 Test infrastructure
- How db-marked tests obtain a database (`tests/conftest.py` fixtures), naming conventions (`pytest -m "not db"` vs full suite), and one representative repository-level DB test to mirror (e.g., `tests/test_action_guard_db.py`, seed-integrity tests).
- Existing pure-logic test style for services (for testing audit payload building without a DB).

## 3. Design questions the plan must answer explicitly

1. **Service API shape.** Propose the central API (conceptually `audit_service.record(actor, operation, entity_type, entity_id, old_values, new_values)`). Decide: sync vs queued, single-row vs batch, and the exact signature/type hints. Keep it small — this is a foundation API others will adopt.
2. **Operation vocabulary.** Propose the initial constant set (e.g., `DEVICE_REGISTERED`, `DEVICE_ASSIGNED`, `DEVICE_UNASSIGNED`, `USER_CREATED`, `USER_UPDATED`) and where constants live. Follow existing config/constants-module precedent.
3. **JSONB serialization.** Who converts domain rows to JSONB-safe dicts (datetimes, Decimals)? Service, caller, or repository? Pick one, justify, keep callers thin.
4. **Failure semantics (the architectural decision).** Compare, with evidence-based feasibility from §2.2:
   - **(A) Same transaction**: mutation + audit insert commit atomically (requires transaction scoping across two repository calls). Mutation cannot succeed while silently claiming an unaudited state.
   - **(B) Best-effort post-commit**: audit after success; log-on-failure. Simpler but violates the "no silent unaudited mutation" principle.
   - **(C) Compensating/outbox**: over-engineered for current scope unless evidence says otherwise.
   Recommend ONE option for AUD-1 and state exactly what infrastructure (if any) it requires. Note: if (A) is infeasible without refactoring the connection model, say so plainly and recommend the smallest refactor that makes it feasible — do not silently fall back to (B).
5. **Audit-write failure UX.** If the audit insert fails, what happens to the user? (Fail the whole operation with a generic error is acceptable; never show SQL/internal detail.)
6. **Timestamps and actor.** DB clock vs app clock; how `system` actor is represented (NULL `user_id`?) consistent with migration 007 intent.
7. **Layer placement.** Confirm: callbacks call the business/service function; the service performs mutation + audit via repositories. If any of the three flows currently has NO service layer, decide whether AUD-1 introduces one for that flow or keeps the orchestration minimal — justify against CLAUDE.md rule 3.
8. **Migration impact.** Expected answer: none. If you believe a migration is needed, flag it as a deviation requiring human approval.

## 4. Deliverable format

Produce the plan as your response message (do not write it to a file):

1. **Verification header** — confirmed baseline commit; any discrepancies found vs this prompt.
2. **Current-state map** — session/transaction model summary + the three flows' call chains with `path:line` citations.
3. **Proposed design** — answers to every item in §3, each with a one-paragraph rationale.
4. **Implementation step list** — ordered, file-by-file (new modules named; existing functions touched cited by `path:line`), suitable to hand to the modification phase verbatim.
5. **Test plan** — which tests to add/mirror (audit rows asserted per flow, atomicity/failure-injection test if option A, pure-logic tests for payload building), mapped to the repo's existing db/pure test split.
6. **Risks & open questions** — anything that needs human/client decision before code changes.
7. **Explicit statement** that no repository files were modified during planning.

## 5. Out of scope reminders

- No prototype-action auditing (program/forward/deactivate toggles).
- No audit *viewer* UI, retention policy, or read path — AUD-1 is write-path only.
- No Entra ID, no scheduler, no integrations.
- No renaming/refactoring beyond the minimum required for the chosen transaction strategy.
