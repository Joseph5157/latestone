# RTL Database Evolution Plan

## Purpose

This document is the working handoff for evolving the Powerplant / Remote Temperature Logger (RTL) development database so that it can support the client-defined §3.4 workflow without copying the client's legacy database design.

It is intended to be used with OpenCode before and during implementation.

---

# 1. Source-of-Truth Rules

Use the following hierarchy when making implementation decisions:

1. **Latest GitHub ZIP** — source of truth for the current codebase and current implementation.
2. **Client RTL PAD v0.7** — source for target architecture, process flow, target entities, and future-state design.
3. **Client RTL Functional Specification v0.3** — source for business rules, roles, RTL programming, message forwarding, alarms, reports, and testing requirements.
4. **Client database screenshots / CSV evidence** — source for understanding the current legacy operational database and real data patterns.
5. **Our Docker PostgreSQL database** — development database only; it may evolve independently as long as it preserves the client's business behavior and remains adaptable to future backend/database changes.

Important:

- Do **not** assume the client's current legacy database is the final target schema.
- Do **not** tightly couple frontend pages/components to physical database tables.
- Keep all raw SQL inside repository/data-access code.
- Treat unknown backend integrations as TBD.
- Do not simulate successful production-side integrations that do not exist yet.

---

# 2. Client Database Discovery — What We Know

## 2.1 Client Database

Observed current database:

```text
Database: RTL
User: postgres
```

Observed application schemas:

```text
system
trfr_temperature
```

## 2.2 Observed Base Tables

### `system`

```text
alarm_log
client_id
comms_alarm
contact_list
device_list
invalid_uid_log
message_forwarding_list
powerdown_log
sensor_error_log
settings_upload_log
startup_msg_log
technician_device_list
trfr_list
tug_report
```

### `trfr_temperature`

```text
master_temperature
```

## 2.3 Important Observed Legacy Relationships

### Device registry

```text
system.device_list
device_uid
cell_number
```

Observed meaning:

```text
RTL Device
├── UID
└── SIM / cell number
```

### Transformer to RTL

```text
system.trfr_list
trfr
device_uid
```

Observed meaning:

```text
Transformer -> RTL Device
```

### Technician to RTL

```text
system.technician_device_list
full_name
device_uid
```

Observed behavior strongly suggests:

```text
One technician -> many RTLs
One RTL -> one current technician assignment
```

### User/contact information

```text
system.contact_list
full_name
cell_number
designation
email_address
```

Observed role/designation values include:

```text
Administrator
Technician
```

### Message forwarding

```text
system.message_forwarding_list
full_name
cell_number
designation
```

This appears to behave like a membership list:

```text
Present in list -> forwarding enabled
Absent from list -> forwarding disabled
```

### Temperature history

Observed legacy structure includes:

```text
trfr_temperature.master_temperature
```

The older screenshots also showed legacy per-device/per-transformer temperature tables.

---

# 3. Important Database Finding

The client database appears to use **very few or no foreign-key constraints** for several logical relationships.

Example logical relationships:

```text
technician_device_list.device_uid
    -> device_list.device_uid

trfr_list.device_uid
    -> device_list.device_uid

technician_device_list.full_name
    -> contact_list.full_name
```

These may be enforced by application logic rather than PostgreSQL foreign keys.

Therefore:

> Do not copy the client's legacy relational weaknesses into our new development schema.

Use the client DB as evidence of business behavior, not as a schema template.

---

# 4. Current Local Development Model

Current normalized development hierarchy:

```text
Plant
  -> Transformer
      -> Device
          -> Reading
```

Current core tables:

```text
plant_monitoring.plants
plant_monitoring.transformers
plant_monitoring.devices
plant_monitoring.readings
```

Current `readings` model:

```text
device_id
metric
reading_ts
value
```

This generic metric model should be preserved.

Do **not** regress it into:

```text
one table per transformer/device
```

or into a fixed wide temperature-only schema.

---

# 5. Database Evolution Strategy

## Core Principle

Use an **additive migration strategy**.

Do not rebuild the database from scratch around the client's legacy schema.

Do not perform a large breaking rewrite of the existing monitoring model.

Target architecture:

```text
Pages / Callbacks
        |
        v
Services
        |
        v
Repositories
        |
        v
PostgreSQL
```

Database-specific changes should be absorbed mainly in the repository/service layers.

---

# 6. Proposed Target Tables

## 6.1 `users`

Purpose:

- Persist application users.
- Replace in-memory prototype user storage.
- Support Administrator, Technician, and General User roles.

Suggested fields:

```text
user_id              PK
username             UNIQUE
full_name
email_address
mobile_number
role
status
created_at
updated_at
```

Initial role values:

```text
administrator
technician
general
```

### Decision

Do **not** implement the complete PAD Role / Privilege / Permission framework yet unless required.

For the current pilot workflow, the three operational roles are enough.

---

## 6.2 `user_device_assignments`

Purpose:

- Persist technician-to-RTL assignments.
- Replace in-memory technician assignment state.
- Preserve assignment history.

Suggested fields:

```text
assignment_id        PK
device_id            FK -> devices.device_id
user_id              FK -> users.user_id
assigned_at
assigned_by          FK -> users.user_id
ended_at              NULL
```

Business rule:

```text
One device -> maximum one active technician assignment
One technician -> many active RTL assignments
```

Recommended enforcement:

- Partial unique index for one active assignment per device, or
- Service-level validation plus database constraint where practical.

Do not simply overwrite assignment history.

---

## 6.3 Extend `devices`

Current fields:

```text
device_id
transformer_id
device_code
status
```

Recommended additive fields:

```text
msisdn
hardware_version
firmware_version
installed_at
created_at
updated_at
```

Reason:

- Client legacy DB contains UID + cell number.
- PAD target Device entity includes hardware and firmware information.
- Programming/configuration workflow needs communication/device identity.

Important:

`devices.status` should remain **administrative device status**.

Do not use it for:

- Fresh/Stale/No Data
- RTL Master active-list membership
- alarm state

Those are separate concepts.

---

## 6.4 `rtl_programming_requests`

Purpose:

- Persist programming/configuration requests.
- Represent the current workflow honestly before real hardware/backend integration exists.

Suggested fields:

```text
request_id           PK
device_id            FK
transformer_id       FK
requested_by         FK -> users
master_msisdn
requested_at
request_method
status
completed_at
error_message
```

Suggested status values:

```text
pending
queued
sent
successful
failed
```

Important:

Until real RTL communication is available:

> Persist the request, but do not pretend the physical RTL was actually programmed.

This table maps conceptually to the client's legacy:

```text
settings_upload_log
```

---

## 6.5 `message_forwarding`

Purpose:

- Persist whether message forwarding is enabled for a user.

Suggested fields:

```text
user_id              PK/FK
enabled
enabled_at
disabled_at
updated_at
```

Initial interpretation:

```text
message forwarding is per-user
```

The documented automatic 18:30 / 6:30 PM disable rule can later be implemented by backend scheduling.

Do not add a scheduler until required.

---

## 6.6 `rtl_active_state`

Purpose:

- Represent whether an RTL is currently on the RTL Master's active monitoring list.

Suggested fields:

```text
device_id            PK/FK
is_active
activated_at
deactivated_at
updated_at
```

Important distinction:

```text
devices.status
    !=
rtl_active_state.is_active
```

Example:

```text
Device administratively active
but
not currently on RTL Master's active list
```

This separation is required for correct business semantics.

---

## 6.7 `device_events`

Purpose:

Normalize several legacy event/alarm tables into one event model.

Do **not** recreate separate local tables such as:

```text
alarm_log
comms_alarm
powerdown_log
sensor_error_log
startup_msg_log
invalid_uid_log
```

Suggested fields:

```text
event_id             PK
device_id            FK NULLABLE
transformer_id       FK NULLABLE
event_type
severity
event_ts
temperature
battery_voltage
message
source
created_at
```

Suggested event types:

```text
startup
check_in
sensor_error
battery_low
power_down
comms_alarm
high_temperature
vibration_event
invalid_uid
```

This model can later feed:

- Notifications
- Alarm history
- Device timeline
- Reports
- Audit/review workflows

---

## 6.8 `audit_log`

Purpose:

Store system user activity required by the PAD.

Suggested fields:

```text
audit_id             PK
user_id              FK
operation
entity_type
entity_id
old_values           JSONB
new_values           JSONB
occurred_at
```

Audit operations should later include:

```text
assign technician
reassign technician
register device
program request
enable message forwarding
disable message forwarding
deactivate RTL
user update
role change
```

---

# 7. Future Table — Do Not Implement First

## `device_transformer_assignments`

The PAD target model supports historical Device <-> Transformer assignments.

Future structure:

```text
assignment_id
device_id
transformer_id
start_at
end_at
updated_at
```

Long-term model:

```text
RTL 29044
2024-01 -> 2025-02   Transformer A
2025-02 -> present   Transformer B
```

However:

> Do not migrate away from `devices.transformer_id` during the first database evolution.

Reason:

- Existing monitoring queries already depend on the current relationship.
- Changing it early creates unnecessary regression risk.
- Introduce assignment history only after the new persistence layers are stable.

---

# 8. Preserve the Generic Readings Model

Keep:

```text
plant_monitoring.readings
```

with:

```text
device_id
metric
reading_ts
value
```

This model can support:

```text
temperature
vibration
battery_voltage
voltage
active_power
reactive_power
power_factor
energy
...
```

without schema changes.

Do not replace it with:

- per-device tables,
- per-transformer tables,
- a temperature-only schema,
- fixed wide columns unless a later backend contract requires it.

---

# 9. Proposed Schema After Initial Evolution

```text
plant_monitoring
|
├── plants
├── transformers
├── devices
├── readings
|
├── users                         NEW
├── user_device_assignments       NEW
├── rtl_programming_requests      NEW
├── message_forwarding            NEW
├── rtl_active_state              NEW
├── device_events                 NEW
└── audit_log                     NEW
```

Later:

```text
device_transformer_assignments
```

---

# 10. Implementation Phases

## DB-0 — Read-Only Impact Audit

Do not modify code.

Inspect:

```text
db/
repositories/
services/
callbacks/
pages/
tests/
```

Find:

- current DDL mechanism,
- current prototype/in-memory stores,
- affected repository/service interfaces,
- affected tests,
- migration risks.

Output audit only.

---

## DB-1 — Additive Schema

Create new tables/columns only.

No frontend behavior changes.

Goals:

- preserve all existing monitoring behavior,
- preserve current tests,
- no deletion of old columns,
- no breaking repository changes.

Run complete regression suite.

---

## DB-2 — Persistent Users

Replace in-memory user persistence with repository-backed `users`.

Preserve existing public service interfaces where practical.

Avoid frontend churn.

---

## DB-3 — Persistent Technician Assignments

Replace in-memory technician/device assignment state with:

```text
user_device_assignments
```

Ensure:

```text
one active technician per device
```

Keep assignment history.

---

## DB-4 — Device Operational Metadata

Persist:

```text
msisdn
hardware_version
firmware_version
installed_at
```

Expose through repository/service methods.

Do not change monitoring semantics.

---

## DB-5 — RTL Operational State

Persist:

```text
rtl_programming_requests
message_forwarding
rtl_active_state
```

Do not communicate with real devices yet.

Do not fake production integration success.

---

## DB-6 — Device Events / Notifications

Create and seed synthetic device events:

```text
startup
check_in
comms_alarm
battery_low
power_down
sensor_error
high_temperature
vibration_event
```

Connect Notifications to this normalized event model.

---

## DB-7 — Audit

Add audit recording for mutating workflows.

Initial audit targets:

```text
technician assignment
technician reassignment
device registration
program request
message-forwarding changes
RTL deactivation
user changes
role changes
```

---

## DB-8 — Historical Device/Transformer Assignment

Only after DB-1 through DB-7 are stable.

Introduce:

```text
device_transformer_assignments
```

Migrate existing direct relationship carefully.

Do not rush this phase.

---

# 11. Migration Strategy

Current Docker initialization based only on:

```text
/docker-entrypoint-initdb.d/
```

is not sufficient once an existing database must evolve over time.

Recommended options:

## Preferred

Use a proper migration system.

Candidate:

```text
Alembic
```

Use it only if justified after the read-only impact audit.

## Alternative

Versioned SQL migrations:

```text
db/
└── migrations/
    ├── 001_baseline.sql
    ├── 002_users.sql
    ├── 003_user_device_assignments.sql
    ├── 004_device_metadata.sql
    ├── 005_rtl_operations.sql
    ├── 006_device_events.sql
    └── 007_audit_log.sql
```

Requirements:

- migrations must be deterministic,
- reruns must be handled safely,
- existing data must be preserved,
- schema changes must be reviewable in Git.

---

# 12. Important Business Rules to Preserve

## Roles

### Administrator

Can:

```text
view/manage RTLs
assign RTLs to technicians
program/configure RTLs
manage relevant operational workflows
```

### Technician

Can:

```text
work with assigned RTLs
program only assigned RTLs
deactivate/remove assigned RTLs where permitted
use message-forwarding workflow
```

### General User

Can:

```text
log in
view transformer data
export data
```

Should not receive programming/assignment controls.

---

# 13. Alarm / Operational Rules to Keep Separate

Documented rules include:

```text
battery low threshold: below 3.75 V
power-down threshold: below 3.61 V
no data > 24 hours: communication alarm
startup/check-in event
sensor error behavior
message forwarding enable/disable
automatic forwarding disable at 18:30
```

Do not hard-code new thresholds without source support.

---

# 14. Client vs Development Database

Important distinction:

## Client Current Legacy DB

Observed PostgreSQL structure:

```text
system
trfr_temperature
```

with operational legacy tables.

## Client PAD Target

The PAD describes a cleaner target architecture including:

```text
User
Role
UserRole
Device
TransformerDetails
DeviceTransformer
UserDeviceAssignment
DeviceReading
NotificationType
Audit
```

It also describes Microsoft SQL Server as a target data tier.

## Our Development DB

We currently use PostgreSQL in Docker.

Therefore:

> Our PostgreSQL model is a development/domain implementation and should remain database-agnostic at the application boundary.

Do not claim our Docker PostgreSQL schema is the client's final production DB architecture.

---

# 15. What OpenCode Must Not Do

OpenCode must not:

- rewrite the entire monitoring schema,
- copy the client's legacy DB table-for-table,
- introduce one table per device,
- remove the generic readings model,
- move SQL into pages/components,
- make frontend components aware of physical table names,
- fake successful RTL/SMS/Entra/Maximo integrations,
- implement device-transformer history before the safer additive phases,
- change business rules without source evidence,
- perform destructive migrations without explicit approval.

---

# 16. First OpenCode Prompt — Read-Only Audit

Use this before any implementation:

```text
We are preparing an additive database evolution for the RTL §3.4 workflow.

IMPORTANT:
- Treat the current repository as source of truth.
- Do not modify any files yet.
- Do not redesign the existing Plant -> Transformer -> Device -> Reading monitoring model.
- Do not copy the client's legacy PostgreSQL schema.
- Do not change frontend behavior.
- Do not introduce production RTL/SMS/Entra/Maximo integrations.

Inspect the complete current codebase, especially:

db/
repositories/
services/
callbacks/device_assign.py
callbacks/device_register.py
callbacks/device_manage.py
callbacks/user_admin.py
services/prototype_users.py
tests/

Our intended future database capabilities are:

1. persistent users with roles administrator/technician/general
2. persistent technician-to-device assignment
3. device MSISDN/hardware/firmware metadata
4. RTL programming request history
5. per-user message-forwarding state
6. RTL Master active-list state separate from administrative device status
7. normalized device event history
8. audit log
9. later, but NOT now, device-transformer assignment history

Perform a READ-ONLY impact audit.

Return:

A. Exact current schema and DDL mechanism.
B. Every in-memory/prototype store that should eventually become persistent.
C. Repository/service/callback/page/test files affected by each proposed capability.
D. Current public functions/interfaces that should be preserved to minimize frontend churn.
E. Risks of each schema change.
F. Which changes can be additive with zero monitoring regression.
G. Recommended migration mechanism for this repository, including whether Alembic is justified.
H. Recommended implementation order.
I. Exact tests that should be added before implementation.
J. Any conflict between this proposed model and the current code.

Do not implement anything.
Do not edit documentation.
Do not create migrations.
Stop after the audit.
```

---

# 17. Review Gate After OpenCode Audit

Before implementation, verify:

- [ ] Current codebase audit matches this plan.
- [ ] No hidden prototype store was missed.
- [ ] Existing repository boundaries can be preserved.
- [ ] Monitoring pages remain unaffected.
- [ ] No destructive schema change is required.
- [ ] Migration strategy is agreed.
- [ ] New tests are identified.
- [ ] Client-unknown integrations remain mocked/TBD.
- [ ] Device/Transformer historical migration is postponed.
- [ ] All new persistence is additive.

Only after this review should DB-1 implementation begin.

---

# 18. Recommended Immediate Next Step

1. Save this file in the repository, for example:

```text
docs/planning/RTL_DATABASE_EVOLUTION_PLAN.md
```

2. Give OpenCode the read-only audit prompt above.
3. Do not allow implementation in the same prompt.
4. Review OpenCode's audit.
5. Compare its findings against this plan.
6. Then prepare the DB-1 implementation prompt.

---

# 19. Status

```text
CLIENT DATABASE DISCOVERY:
Sufficient for current frontend/database planning.

CURRENT DEVELOPMENT DATABASE:
Stable normalized monitoring core.

NEXT DATABASE ACTION:
Read-only impact audit.

IMPLEMENTATION MODE:
Additive migrations only.

DEVICE-TRANSFORMER HISTORY:
Deferred.

PRODUCTION INTEGRATIONS:
TBD / not to be simulated as complete.
```
