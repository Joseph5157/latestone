# ADR-029: Final production database is Microsoft SQL Server only

Status: Approved
Date: 2026-09-29
Evidence: client organization decision relayed by the user on 2026-09-29;
`docs/plans/SQLSERVER_TARGET_ARCH_01_PLAN.md`,
`docs/database/RTL_READ_ONLY_ACCESS.md`
Implemented-by: not yet

## Context

`AGENTS.md` and `REPOSITORY_AND_DEPLOYMENT_MAP.md` §4 recorded the production
database platform as unknown / a client-side decision. The client has now
decided.

## Decision

- **Target:** the final production application uses Microsoft SQL Server only.
  PostgreSQL is transitional development/application infrastructure, to be
  retired after the SQL Server migration is designed, approved, implemented
  and verified.
- **The client RTL database stays READ-ONLY** until: (1) the existing schema
  is fully mapped, (2) all application/PostgreSQL requirements are mapped,
  (3) real gaps are identified, (4) SQL Server changes are proposed,
  (5) each change has a written reason, (6) the client approves. Only a later,
  separate gate may modify the SQL Server schema. This ADR grants no write
  permission.
- **Recorded business decisions (current):**
  1. `device_list` is the registered RTL list; verified count 339. Telemetry-only
     UIDs do not automatically become registered devices.
  2. Administrator-managed RTL-to-transformer assignment is a required
     capability. `trfr_list` is to be investigated as existing/reference
     mapping data and is **not** declared authoritative. Eventual persistence
     must be in SQL Server, subject to client approval. Not implemented now.
  3. Offline = no communication for "a few hours". The exact hours are
     UNRESOLVED; no threshold is implemented.
  4. RTL source timestamps are South African local time (SAST, UTC+2).
     Supersedes the "timezone unresolved" statements in earlier gate records.
     Future implementation may interpret them accordingly.
  5. Unusual temperature values are displayed as received, never silently
     discarded or corrected; configured thresholds may raise alerts.
  6. Conflicting same-timestamp readings: no client rule exists. Identical tied
     latest values expose their common value; conflicting ones stay ambiguous
     and are preserved; never pick highest/lowest/average. The legacy
     single-UID `get_latest_temperature()` limitation stays deferred and
     documented (see ACTIVE_GATE).
- **Workflow:** `latestone/main` is the authoritative development checkpoint
  (see ACTIVE_GATE and the plan). This supersedes the "authoritative
  development source" wording for `origin` in `REPOSITORY_AND_DEPLOYMENT_MAP.md` §1.

## Consequences

`AGENTS.md`'s PostgreSQL stack describes the current development
application, not the final target. Rules 2 and 9 remain in force until a
migration gate changes them. Still unresolved: offline-hours threshold,
canonical fleet, `trfr_list` authority, duplicate-resolution rule.
