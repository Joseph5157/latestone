# SQLSERVER-TARGET-ARCH-01 — Plan: Complete Application-to-Client-Database Mapping

Status: **PLANNED — NOT YET EXECUTED**
Date: 2026-09-29
Baseline: `dd3ea22fdf87fdcba5b2099826ccd49089164762`
Decision record: `docs/decisions/ADR-029-sql-server-only-target-architecture.md`
Executor of the audit: Codex (next gate). Nothing in this file is executed by the
planning task.

## 1. Architecture decision

The final production application uses Microsoft SQL Server only. PostgreSQL is
transitional and is retired only after the SQL Server migration is designed,
approved, implemented and verified. The client RTL database remains
**READ-ONLY** (via `rtl_app_reader`) until the audit is done, changes are
proposed with reasons, and the client approves. A later gate — not this audit —
may modify the schema.

## 2. Business decisions carried into the audit

| # | Decision | State |
|---|---|---|
| 1 | `device_list` = registered RTLs (339 verified); telemetry-only UIDs are not auto-registered | Confirmed |
| 2 | Admin-managed RTL→transformer assignment required; `trfr_list` is reference data to investigate, NOT authoritative; must eventually persist in SQL Server with client approval | Confirmed direction, design open |
| 3 | Offline after "a few hours" of no communication | Hours UNRESOLVED; no threshold implemented |
| 4 | RTL timestamps are SAST (UTC+2) | Confirmed |
| 5 | Show unusual temperatures as received; thresholds may alert | Confirmed |
| 6 | Same-timestamp conflicts: expose identical ties, keep conflicting ambiguous, preserve all, never choose/average | Confirmed as safe rule; no client rule |

Deferred limitation (unchanged): the legacy single-UID
`get_latest_temperature()` orders latest ties by `temperature DESC`. Not an
approved rule; must stay documented.

## 3. Scope: READ-ONLY audit

Compare three sources.

**A. Client SQL Server (`RTL`)** — all 19 user tables and 4 views: columns,
types, keys, relationships, constraints, indexes; existing application data;
device information; temperature telemetry; transformer mappings; status and
comms information; events/messages; any user/security/configuration/workflow
structures. Access only through `rtl_app_reader` SELECT. No DDL, DML, temp
objects, indexes, statistics or views.

**B. Current PostgreSQL application** — all application-owned tables, models,
migrations (Alembic), repositories, services, seed/demo structures.

**C. Application capabilities** — authentication; users; roles; permissions;
registered RTLs; transformers; RTL-transformer assignments; technician
assignments; temperature telemetry; temperature thresholds; alarms; alarm
acknowledgement; commands/actions; activation/deactivation; notifications;
audit history; preferences; dashboard hierarchy; metric data; device status;
communication status; and every other persisted feature found in code.

## 4. Classification (every capability)

1. `EXISTING_SQLSERVER_DIRECT` — client SQL Server already supports it adequately.
2. `EXISTING_SQLSERVER_ADAPT` — relevant structure exists; adaptation or an approved extension may be needed.
3. `SQLSERVER_GAP` — persistent need the client SQL Server does not provide.
4. `POSTGRES_DEMO_RETIRE` — demo/synthetic only; will not migrate.
5. `POSTGRES_MIGRATE` — real application-owned state that must eventually live in SQL Server.
6. `REVIEW_REQUIRED` — evidence insufficient to decide safely.

## 5. Planned deliverables (all under `docs/audit/sqlserver-target-arch-01/`)

1. `APPLICATION_DATABASE_MAPPING.md` — master matrix. Columns: Application
   capability · Current code path · Current PostgreSQL table/model · Client SQL
   Server table/view · Relevant SQL Server fields · Classification · Gap ·
   Recommended direction · Client approval required? · Reason/evidence.
2. `POSTGRESQL_RETIREMENT_MATRIX.md` — EVERY PostgreSQL table classified
   KEEP TEMPORARILY / MIGRATE TO SQL SERVER / REPLACE WITH EXISTING SQL SERVER /
   RETIRE DEMO/SYNTHETIC / REVIEW REQUIRED, with the reason. Nothing is deleted.
3. `SQLSERVER_CAPABILITY_CATALOG.md` — per relevant table/view: contents;
   capability it may support; whether currently safe to consume; data-quality
   limits; relationship limits; whether application writes would eventually be required.
4. `PROPOSED_SQLSERVER_CHANGES.md` — PROPOSAL ONLY. Per potential change:
   requirement · existing support · gap · proposed change · why required ·
   data to store · dependent application feature · consequence if not added ·
   security/audit implications · extend existing table vs new application-owned
   table (preference and rationale) · client approval status. No executable
   migration SQL unless explicitly requested later.
5. Later client document (separate step, not part of the audit run):
   **SQL Server Application Integration & Required Database Changes**, with
   Section A existing capabilities usable unmodified; B structures that may need
   adaptation; C missing capabilities requiring approved changes; D why each
   change is necessary; E changes NOT required / PostgreSQL demo structures to
   retire. Never a vague "we need more tables" — each request carries an
   operational reason.

## 6. Questions the audit must answer

1. What does PostgreSQL currently store?
2. Which PostgreSQL data is real application state versus synthetic/demo?
3. Which PostgreSQL tables can disappear because equivalent client SQL Server data exists?
4. Which PostgreSQL capabilities have no SQL Server equivalent?
5. Can existing SQL Server structures safely support those capabilities?
6. Where would modifying an existing client table create unnecessary risk?
7. Would separate application-owned tables inside SQL Server be safer for application state?
8. What authentication/security structures are required?
9. What data do Administrator, Technician and General User roles need?
10. What data does Admin-managed RTL-to-transformer assignment need?
11. What data do technician RTL assignments need?
12. What data do configurable temperature thresholds need?
13. What data do alarm acknowledgement/history need?
14. What data do commands/actions need?
15. What data do notification delivery/history need?
16. What audit trail is required?
17. What preferences/configuration need persistence?
18. Which dashboard metrics have no real SQL Server telemetry?
19. Which synthetic metric/readings structures should be retired?
20. What application code assumes PostgreSQL-specific SQL or behaviour?
21. Which SQLAlchemy/Alembic/PostgreSQL-specific dependencies must change for SQL Server?
22. What migration sequencing lets PostgreSQL be retired safely?

## 7. Audit rules

- Read-only on SQL Server; nothing altered in PostgreSQL either. Nothing deleted.
- Evidence beats assumption: cite table/column or `file:line`. Mark unknowns `REVIEW_REQUIRED`.
- Do not declare `trfr_list` authoritative, pick a canonical fleet, set an
  offline threshold, or invent a duplicate-resolution rule.
- Timestamps interpreted as SAST per ADR-029; still no UI changes.
- Must NOT modify SQL Server or PostgreSQL schema, repositories, services,
  callbacks, UI, Docker database services; no data migration, no PostgreSQL
  removal, no SQL Server migrations, no unrelated fixes.
- Do not touch `RTL.bak` or `.env`.
- Report authority conflicts before editing (per `AGENTS.md`).

## 8. Suggested migration sequencing (to be validated by the audit)

1. Audit and proposal (this gate) → client review → approval per change.
2. Approved SQL Server additions in a dedicated gate (application-owned objects preferred over altering client tables, decided per change).
3. Introduce a SQL Server repository implementation behind the existing repository boundary; SQLAlchemy dialect and Alembic (or replacement) work.
4. Migrate real application state (`POSTGRES_MIGRATE` items); verify.
5. Retire demo/synthetic structures and PostgreSQL only after verification.

## 9. Project workflow (recorded)

`latestone/main` is the authoritative development checkpoint. For every gate:

1. Start from verified `latestone/main`.
2. Define one bounded gate.
3. Execute it.
4. Run required tests/validation.
5. Independently review higher-risk changes when appropriate.
6. Update `ACTIVE_GATE.md` and `CURRENT_STATE.md`.
7. Commit only the approved gate's files.
8. Push to `latestone` `main`.
9. Verify local `HEAD`, `latestone/main` and `git ls-remote latestone refs/heads/main` all match.
10. Only then begin the next gate.

No completed or approved gate remains only on the local machine.

## 10. Still unresolved

Offline-hours threshold; canonical monitored fleet; `trfr_list` authority;
client duplicate-resolution rule; the SQL Server design for admin-managed
assignment (needs client approval).
