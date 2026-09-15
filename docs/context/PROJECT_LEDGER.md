# POWER / RTL PROJECT LEDGER

## 1. Authoritative Checkpoint

- **Branch:** `main`
- **SHA:** `72dd1cf95e94b642f05b517c804cea235a0067b4` — "test(seed): skip the ADR check only where no ADRs are delivered" (pushed to `origin/main`; local `HEAD`, `origin/main`, and `git ls-remote` all verified to match — see the CLIENT-SYNC-2B section of `docs/context/ACTIVE_GATE.md`)
- **Last updated:** 2026-09-07 (advanced from `603e158` past RTL-PROG-SIM-1, LOCAL-DB-CATCHUP-1, CLIENT-SYNC-2A/2A-FIX and CLIENT-SYNC-2B to this commit's push)
- **Client delivery:** branch `cc-1-command-center-progress` @ `983c17169a0cedd2282a0df4731228e0b05feac7` on `powerplant-dashboard-client` (CLIENT-SYNC-3, 2026-09-11 — adds the Technician "My RTLs" work list on top of CLIENT-SYNC-2B's `3f21c3a` milestone). The client repo's `main` remains `aa1dd3c` and the stale local `client-release` (`d89a090`, pre-Command-Center) is **not** the delivery branch — see §7a.
- **Working tree expectation:** `debug.log` (untracked) only, plus `docs/context/Power_RTL_Master_Build_Plan_2026-09-04.md` (untracked, pending adoption per POWER-MASTER-PLAN-1).
- **Real development database revision: `012_vibration_contract_answers`** — level with the code as of 2026-09-07 (`LOCAL-DB-CATCHUP-1`). **This replaces the long-standing "real dev DB is deliberately at `007_audit_log`" caveat repeated by every gate from C08-AUTO-DISABLE-1 through RTL-PROG-SIM-1**; those statements were true when written and are now historical. The upgrade was non-destructive (`alembic upgrade head` only — no reset, purge, schema recreation or seed script) and every pre-existing population was preserved exactly. Migrations continue to be exercised in tests through the `isolated_schema` fixture, never against this schema.
- **Test baseline (at RTL-IF-4 close):** 2690 passed (non-db), 510 deselected; 3200 passed full suite — unchanged by RTL-IF-1..4, which added focused test files without modifying this baseline's pre-existing tests (see ACTIVE_GATE.md verification log for RTL-IF-4).
- **Roadmap:** `docs/context/Power_RTL_Master_Build_Plan_2026-09-04.md` is the adopted high-level roadmap (validated by POWER-MASTER-PLAN-1); this ledger remains the executive/detailed status record it is built from.
- **Source of truth:** `docs/context/SOURCE_AUTHORITY.md` — code outranks prose
- **Amendment (2026-09-06):** Development baselines recorded for C-08,
  C-15, C-04 (format), C-01 (framework), C-02 (framework) — internal
  decisions made by the development team/user so implementation can
  proceed, **not confirmed Eskom/client answers unless repository evidence
  proves otherwise**; formal client confirmation remains pending for all
  five (full detail in `REQ-3I_Clarification_Register.md` and
  `docs/context/CLIENT_QUESTIONS.md`). C-07 remains genuinely on hold
  pending the client. C-05/C-06/Azure/private-APN/Entra reconfirmed as
  Eskom-controlled/external. Next implementation gate updated to
  `C08-AUTO-DISABLE-1` in `docs/context/ACTIVE_GATE.md`. Documentation
  only — this row does not change the checkpoint SHA above, which still
  reflects the last actual commit.
- **Amendment (2026-09-07):** `C08-AUTO-DISABLE-1` implemented (migration
  010, `services/forwarding_auto_disable_service.py`, standalone scheduler
  entry point, Administrator-only override panel, full audit coverage),
  independently re-verified (38 focused + 100 regression tests, full suite,
  sole Alembic head, `git diff --check` clean), then **committed and pushed**
  as `d10c566ef5e400d9163fdba2413580f3ca4517d9` (see checkpoint above). Real
  dev Postgres was deliberately left at migration `007` — commit/push do not
  run migrations against it; `alembic upgrade head` is its own later,
  deliberate step. Full detail in `docs/context/ACTIVE_GATE.md`.
- **Amendment (2026-09-07b):** `REPORT-MAXTEMP-1` implemented and verified
  (Maximum Temperature is now data-backed, one row per transformer; rolling
  30-day default plus custom range; 30 focused tests + full report-center
  regression + full suite all passed), then **committed and pushed** as
  `95bdfa59487b0c171e9d7c07f96a6fa32d0bd81d` (see checkpoint above). Full
  detail in `docs/context/ACTIVE_GATE.md`.
- **Amendment (2026-09-07c):** `REPORT-EXPORT-1` implemented and verified:
  all three real reports (Installed RTLs, RTL Alarms 30 Days, Maximum
  Temperature) now export as CSV and PDF (C-04 baseline — PDF + CSV, no
  native XLSX; a development baseline pending client confirmation, not an
  Eskom-confirmed production format). Installed RTLs'/RTL Alarms' existing
  CSV bytes and filenames are unchanged; Maximum Temperature's CSV keeps
  the exact report header as row 1 with no metadata preamble and no fake
  Period column, and identifies its resolved period in its filename and
  the export status panel instead. PDF visibly shows report title, scope,
  period, generated time, table headers, and paginated/repeated-header
  rows, using fpdf2's normal compression. Maximum Temperature's export
  reuses the identical period-resolution path the preview uses (R4-D7);
  authorization still runs before any row is fetched, for every report
  and format. 64 focused tests + full report-center regression + full
  suite all passed; `git diff --check` and context-pack validation clean,
  then **committed and pushed** as
  `7969324f377a5fee52b74617e4f7a17c5678f4b5` (see checkpoint above). Full
  detail in `docs/context/ACTIVE_GATE.md`.
- **Amendment (2026-09-07d):** `THRESH-CONFIG-1` implemented and verified:
  the C-01 framework — one global, Administrator-managed temperature
  warning/critical threshold pair, unconfigured-by-absence, no invented
  Eskom values. Both values are canonicalized to exact `decimal.Decimal`
  at `NUMERIC(12,3)`'s scale before any comparison or write (a
  correctness fix applied before this closure: validating on raw `float`
  could let two distinct values satisfy `warning < critical` and still
  collapse to the same stored value); excess precision is rejected, never
  rounded. `warning < critical` is enforced by both the service and a new
  migration-011 database CHECK. Identical canonical re-save and
  already-unconfigured clear are no-ops; every real transition is
  audited. Admin-only; Technician/General denied. No `high_temperature`
  activation, no reading-to-alarm evaluation, `MonitoringCondition`
  unchanged. 75 focused tests + regression + full suite all passed;
  migration `011_temperature_threshold_config` is the sole Alembic head,
  then **committed and pushed** as
  `c83cf94b25cbd3ceec0e079938c355e221fe03b2` (see checkpoint above). Full
  detail in `docs/context/ACTIVE_GATE.md`.
- **Amendment (2026-09-07e):** `VIB-CONFIG-1` implemented and verified:
  the C-02 framework — an audited, Administrator-editable place to
  record answers to vibration's 15-question sensor contract (not 14 —
  corrected by direct count this session; the file itself never changed,
  the earlier count was a miscount). Genuine multi-row key-value
  persistence (`vibration_contract_answers`, migration 012): one row per
  ANSWERED question, absence = unanswered, independently per key, no
  invented defaults. The 15 question slots are defined in
  `config/vibration_contract.py`, transcribed verbatim from the TBD
  document. Answers are free-text contract capture only — not
  operational sensor semantics. Identical re-save and clearing an
  already-unanswered item are no-ops; every real transition is audited
  and transactionally rolled back if the audit write fails. Admin-only;
  Technician/General denied. Vibration remains completely inactive in
  the metric registry/selectors, charts/KPIs, readings queries,
  freshness/`MonitoringCondition`, event semantics, and alarm generation
  — zero diff to any of those files. No unit, threshold, axis model,
  aggregation, cadence, sensor range, storage contract, or API contract
  was invented anywhere. 54 focused tests + regression + full suite all
  passed; migration `012_vibration_contract_answers` is the sole Alembic
  head, then **committed and pushed** as
  `859dbe28dd62584545d2c096dfc3017492682b61` (see checkpoint above). Full
  detail in `docs/context/ACTIVE_GATE.md`.
- **Amendment (2026-09-07f):** `RTL-PROG-EXEC-1` implemented and verified:
  connects `rtl_programming_service.py` (RTL-IF-1's request + one
  `rtl_commands` row per accepted request) to the existing command
  lifecycle (RTL-IF-2, ADR-018) so the request now reconciles truthfully
  instead of staying `QUEUED`/`pending` forever. No migration —
  `rtl_programming_requests`' existing status/completed_at/error_message
  columns (migration 005) already supported the required lifecycle.
  Every command transition (`config/commands.py`'s
  `REQUEST_STATUS_FOR_COMMAND_STATE`: `QUEUED→queued`, `SENT`/
  `ACKNOWLEDGED→sent`, `SUCCEEDED→successful`, `FAILED`/`TIMED_OUT→failed`)
  now also projects the request's status, in the SAME transaction as the
  command's own conditional UPDATE (`services/rtl_command_service.py`) —
  a failure on either write rolls back both. `error_message` is derived
  only from the command's own normalized, bounded failure fields, never a
  raw exception; a successful/in-flight projection carries no error by
  construction. New `services/rtl_programming_execution_service.
  execute_request(request_id, transport)` is the protocol-neutral
  orchestration seam: it resolves a request's existing command and hands
  it to the existing dispatcher, never imports/constructs
  `SimulatorTransport`, is not called from any callback, and adds no
  retry/worker/scheduler. Existing command-transition legality and
  concurrency protection (`ALLOWED_TRANSITIONS`, the conditional
  `WHERE state = :expected_state` UPDATE) are unchanged and remain
  authoritative. The Program RTL confirmation copy was corrected from "is
  saved and pending" to "is saved and queued" (a request is never
  observably `pending` once accepted) — the "not confirmed programmed"
  disclaimer is unchanged. 83 focused tests + full auth/audit/migration-
  foundation/callback regression + full suite all passed; Alembic head
  remains `012_vibration_contract_answers`; real dev DB remains
  intentionally untouched at migration `007`, then **committed and
  pushed** as `0787b90a3f658b2bf347f1ae58b659b181d33c52` (see checkpoint
  above). Full detail in `docs/context/ACTIVE_GATE.md`.
- **Amendment (2026-09-07g):** `RTL-PROG-SIM-1` implemented and verified:
  the local/demo flow **Program RTL → request queued → explicitly
  simulate → sent → successful/failed** now runs end to end, on
  RTL-PROG-EXEC-1's `execute_request()` seam plus the existing
  deterministic `SimulatorTransport` (ADR-018). **No migration required.**
  `RTL_PROGRAMMING_SIMULATOR_ENABLED` is parsed only in
  `config/settings.py` and **defaults OFF**; explicit enablement together
  with `APP_ENV=production` **fails closed at startup with a
  `RuntimeError`** rather than silently enabling or silently downgrading,
  while production with the flag unset/false starts normally with no
  simulator controls and no simulation callback registered (both verified
  by importing the app under each environment).
  `services/rtl_programming_simulation_service.py` is **the only
  application service that constructs a `SimulatorTransport`**, and only
  after checking enablement and non-production; it **delegates execution
  to `rtl_programming_execution_service.execute_request` and duplicates no
  lifecycle logic**. Supported outcomes are **Success / Failure / Timeout
  only — simulation semantics, not Eskom protocol semantics**. Simulation
  requires an explicit operator click AFTER a request has been
  recorded/queued; recording never auto-executes. The UI appears only when
  explicitly enabled and states that no physical RTL/MQTT/SMS/Eskom
  communication occurs. Existing `PROGRAM_RTL` authorization is reused
  (Administrator any RTL; Technician assigned only; General denied), runs
  **before** the request lookup, and browser-owned request ids must belong
  to the already-authorized device — with unknown and mismatched ids
  sharing one refusal so the control is not an existence oracle. **A
  simulated success is not evidence that a physical RTL was programmed**;
  no MQTT/SMS/HTTP/Eskom payload, retry, scheduler or production transport
  was introduced. 63 focused + 117 RTL regression + 340 auth/settings/
  wiring regression tests and the full suite all passed; Alembic head
  remains `012_vibration_contract_answers`; real dev DB remained
  intentionally at migration `007_audit_log` at that point, then
  **committed and pushed** as
  `603e1581a53a42e15c1ed865f774e8751363a770` (see checkpoint above). Full
  detail in `docs/context/ACTIVE_GATE.md`.
- **Amendment (2026-09-07h):** `LOCAL-DB-CATCHUP-1` **COMPLETED /
  VERIFIED** — an environment/verification gate, documentation-only in
  repository terms (no application code changed). The real development
  database was advanced non-destructively from `007_audit_log` to
  `012_vibration_contract_answers` via a single `alembic upgrade head`
  (`008_rtl_commands` → `009_rtl_command_lifecycle` →
  `010_forwarding_auto_disable` → `011_temperature_threshold_config` →
  `012_vibration_contract_answers`); **no reset, purge, schema recreation
  or seed script was used**. Preflight proved the target first:
  `APP_ENV=development`, Docker container `plant_monitoring_postgres`,
  `localhost` port **5436**, database `powerplant_demo`, schema
  `plant_monitoring`, server self-identifying as
  `172.24.0.3:5432` inside the local Docker network — **not a client or
  production target**; only non-secret connection metadata was reported.
  A **validated PostgreSQL custom-format backup was created outside the
  repository before migrating** (non-zero size **11,921,321 bytes**;
  `pg_restore --list` read it successfully — 184 TOC entries, 27 table-data
  entries; no secrets recorded). **All pre-existing populations were
  preserved exactly**: plants 30, transformers 71, devices 120, readings
  1,383,360, users 7, user_device_assignments 96, device_events 13,
  audit_log 3, message_forwarding 1, rtl_active_state 2,
  rtl_programming_requests 0 — the migration itself added no business
  records and no audit rows. New schema objects verified: `rtl_commands`
  with its lifecycle columns and constraints,
  `forwarding_auto_disable_override`, `temperature_threshold_config`,
  `vibration_contract_answers` — **all four empty/unconfigured
  afterwards; no business values were invented**. Administrator browser
  smoke against the upgraded real DB passed (Fleet Overview; C08
  auto-disable panel; temperature threshold panel reading "Not
  configured"; vibration contract panel showing 15 unanswered / "0 of 15
  questions answered"), with **no fake thresholds or contract answers
  created**. Simulator smoke: disabled state verified; temporary
  process-only enablement rendered the development simulator controls and
  their warning; callback reachability confirmed; **no real simulated
  execution was performed** because the dev DB held zero legitimate queued
  programming requests, and **no fake Master MSISDN or programming history
  was created** (isolated-schema tests already cover Success/Failure/
  Timeout execution). The simulator flag was removed afterwards and the
  final local state is **simulator disabled**. Non-blocking observations:
  a pre-existing React uncontrolled→controlled input warning in the
  Program RTL drawer (predates this work, unrelated), and two pre-existing
  `app.py` processes left untouched because ownership was uncertain.
  Next queued gate: `CLIENT-SYNC-2`. Full detail in
  `docs/context/ACTIVE_GATE.md`.
- **Amendment (2026-09-07i):** `CLIENT-SYNC-2A` (inspection, read-only —
  **neither repository modified**) and `CLIENT-SYNC-2A-FIX` (implemented
  and verified, pending commit) completed. The inspection verified the
  client progress branch at `3d4897cdd903d6012fca94620caedc73e081f517`
  (client `main` = `aa1dd3c`), read the gitignored `docs/CLIENT_DELIVERY.md`
  authority and the CLIENT-SYNC-1 provenance, and established that the
  client branch is at migration `007_audit_log` and that **the delta is
  not feature-separable**: an import-closure walk from `app.py` gives 118
  runtime files on dev vs 86 on the client (28 missing, 51 differing), and
  because `app.py`/`callbacks/routing.py` are import hubs, omitting the
  simulator, vibration, threshold or C08 each requires editing `app.py`
  and `pages/plants_overview.py` — permanent client/dev source divergence
  rather than a file-selection choice. It also found that the client
  branch holds **five documents that exist nowhere on `main`** which a
  blanket mirror would delete, and that migrations 008–012 are
  additive-only so a non-destructive `alembic upgrade head` is supported
  on the client laptop. `CLIENT-SYNC-2A-FIX` then prepared the boundary:
  **the client leakage guard was strengthened** (nine previously-uncaught
  internal paths added — including our own vibration open-question
  register and the client's own specification PDF — plus refusal by shape
  for any `.env*` other than `.env.example` and any
  `.log`/`.dump`/`.bak`/`.sql.gz`/`.pyc`, because a hand-written list is
  what rotted; violations on `main` 84 → 93, client branch still clean at
  263 files); **client-visible internal terminology was scrubbed** from
  four rendered strings (`C-01`, `C-02`, two `development baseline C-15`
  notices) with the user meaning preserved rather than deleted, keeping
  the client's own `BR016`/`BR008` ids; and **the reset-contract table
  classification was fixed** — migrations 010/011/012 had each added a
  table with neither `KNOWN_TABLES` nor `RESET_PRESERVES` updated, so the
  equality assertion passed while three tables sat unclassified (no
  behavioural defect: `RESET_REPLACES` is readings-only and all three FK
  only to `users`, which `PURGE_ORDER` never deletes), now corrected on
  both sides with `KNOWN_TABLES` **derived from the migrations' own
  `op.create_table(...)`** so it cannot rot again. Full suite passed
  (exit 0), context pack CLEAN, `git diff --check` clean, leakage guard
  re-run against both branches. **The client repository was not touched.**
  Committed and pushed as `65a5ceab6f79896a223a4f4ef3eb9bd5a67657ae`. Full
  detail in `docs/context/ACTIVE_GATE.md`.
- **Amendment (2026-09-07j):** `CLIENT-SYNC-2` is **CLOSED** — all three
  parts (`CLIENT-SYNC-2A` inspection, `CLIENT-SYNC-2A-FIX` boundary
  preparation, `CLIENT-SYNC-2B` curation and delivery) completed against
  development baseline `72dd1cf95e94b642f05b517c804cea235a0067b4`. The
  accepted milestone was delivered to **client branch
  `cc-1-command-center-progress` as
  `3f21c3a000de5026868c2031eb865569c368e509`** (217 files changed; local
  `HEAD` and the client remote ref verified to match). Runtime **parity**
  was curated rather than a surgical subset, because 2A's import-closure
  analysis showed `app.py`/`callbacks/routing.py` are hubs and a subset
  would mean permanent client/dev divergence re-applied weekly; the 357
  delivered paths are byte-identical to `main`. **Migrations 008–012
  delivered** (client `007_audit_log` → `012_vibration_contract_answers`,
  all additive, non-destructive upgrade documented in the client README
  with an explicit instruction not to reseed), plus the `tzdata`/`fpdf2`
  dependencies. **The simulator ships default OFF** — commented in
  `.env.example`, described in client-facing language, production
  fail-closed intact, and no screen implies a physical RTL was programmed.
  **The five client-only documents were preserved.** **Full client suite
  passed (exit 0)** and the **staged leakage check reported 366 files with
  zero violations**. **Client `main` (`aa1dd3c`) and the stale local
  `client-release` (`d89a090`) were both untouched** — only the one branch
  was pushed. Two blockers were found and resolved en route: a delivered
  test depending on undelivered material (fixed on `main` at `72dd1cf` so
  the delivered file stays byte-identical rather than diverging), and a
  stale documented push target (`client-release`) corrected in the local
  `docs/CLIENT_DELIVERY.md`. Next queued gate: `CLIENT-PC-SYNC-2`. Full
  detail in `docs/context/ACTIVE_GATE.md`.
- **Amendment (2026-09-11):** `TECH-WORKSPACE-MERGE-1` merged
  `TECH-WORKSPACE-1` (the Technician "My RTLs" work list, closed on branch
  `tech-workspace-1` 2026-09-10) into `main` at
  `fa69c9c66f3d28d9bb6620040a93ffba918022ef`. `CLIENT-SYNC-3` is **CLOSED**
  — it curated exactly the 8 runtime files that changed since CLIENT-SYNC-2B
  (established by a full-repo diff between the two dev baselines, not
  reasoning about the merge alone) to client branch
  `cc-1-command-center-progress` as
  `983c17169a0cedd2282a0df4731228e0b05feac7` (parent `3f21c3a`, 8 files
  changed, 749 insertions, 3 deletions). Full client suite: 6 failed
  (pre-existing dev-DB drift, reproduced identically on dev `main`), 3623
  passed, 3 skipped; leakage check zero violations; `git diff --check`
  clean; client `main` (`aa1dd3c`) and `client-release` (`d89a090`)
  untouched. **`CLIENT-PC-SYNC-2` is superseded before execution, not
  completed** — it was never started, and CLIENT-SYNC-3 moved the delivery
  branch one milestone past what it was queued against (`3f21c3a`). Next
  queued gate: `CLIENT-PC-SYNC-3` (identical non-destructive
  backup/migrate/smoke procedure, re-targeted at `983c171`, with Technician
  My RTLs added to the browser-smoke checklist). Full detail in
  `docs/context/ACTIVE_GATE.md`.
- **Amendment (2026-09-15):** `CLIENT-PC-SYNC-3` is **CLOSED / PASS**,
  reported by the user who performed the sync directly on the client's
  laptop over Remote Desktop (outside this repository/session's reach, so
  recorded as reported, not independently re-verified here): client branch
  `cc-1-command-center-progress` confirmed at `983c17169a0cedd2282a0df4731228e0b05feac7`;
  database migrated non-destructively `007_audit_log` →
  `012_vibration_contract_answers`; protected row counts unchanged;
  Administrator and Technician (`demo.tech01`) browser acceptance both
  PASS; 24 assigned RTLs visible; My RTLs navigation works; unassigned RTL
  access refused; no Admin UI leakage; `RTL_PROGRAMMING_SIMULATOR_ENABLED=False`.
  No defect reported. No application code touched. Per explicit
  instruction, no new implementation gate is opened by this closure — see
  `docs/context/ACTIVE_GATE.md`.

## 2. Executive Project Position

The application is a mature **Python/Plotly Dash power-plant monitoring dashboard** with:
- 30-plant hierarchy, 71 transformers, 120 devices, 1.38M synthetic readings
- 8 metrics with aggregation-aware KPIs, Plotly charts, freshness badges
- Three-role authorization (Administrator / Technician / General) backed by a server-trusted Flask session
- Persisted RTL operations: programming requests, message forwarding state, active-list transitions, event ingestion, activation projection, audit trail
- Event-driven notification center (BR008 + persisted device events)
- Two data-backed reports with CSV export; one prototype report
- Command Center with fleet health, priority investigation, affected locations
- 16 ADRs, 7 Alembic migrations, 2669+ pure-logic tests

**The gap between "what our software can do" and "what works end-to-end for the client" is now almost entirely external integration**: physical RTL device communication, MQTT/transport, Entra ID, SMS delivery, production reporting format, and client-confirmed thresholds. Most remaining client-requirement work is BLOCKED on external decisions, not developer backlog.

## 3. Client Requirement Status

| Area | Requirement | Status | Implemented | Missing | Next Action |
|---|---|---|---|---|---|
| **Three-role model** | RTL-ROLE-ADM/TECH/GEN-01–05 | ✅ COMPLETE | Three roles enforced end-to-end: route policy, capability policy, action policy, device scope all wired and tested; server-trusted session re-reads role every call (AUTH-HARDEN-1); 3 roles × route/capability/action matrices fully covered | Production role source (Entra ID) — separate integration concern | None — app-side role enforcement complete |
| **Technician scope** | Technician sees only assigned RTLs | 🟢 IMPLEMENTED | `DeviceScope` resolves from assignment table; enforced in every protected callback and SQL query; central `require_action` guard checks live assignment; DB-tested (`test_action_guard_db.py`, `test_scope_repository.py`) | Physical RTL scope enforcement on device side — external | None — app-side scope enforcement complete |
| **Administrator assignment** | RTL-ROLE-ADM-02: Assign RTLs to technicians | ✅ COMPLETE | Full persisted flow: assign drawer → `prototype_assignments.assign_technician` → `user_device_assignments` with FOR UPDATE close-and-insert; admin-only guard `MANAGE_ASSIGNMENT`; DB-tested (`test_action_guard_db.py`) | Production technician data source — separate integration concern | None — app-side assignment complete |
| **Audit write path** | RTL-AUD-01–07 | ✅ COMPLETE | `audit_log` table; write path wired for ALL persisted mutations (registration, assignments, users, forwarding, programming, active-list transitions) with atomic audit; system-originated NULL-actor path for activation (ACT-D5, INGEST-D6); verified by `test_audit_wiring.py` | Audit viewer/read UI — no client requirement identified | None — write path complete |
| **Authentication** | BR001: System must authenticate users | 🟢 IMPLEMENTED | Demo credential auth with server-trusted session (`auth_service.py`); Flask signed cookie; `current_identity()` reloads from DB every call; fails closed | Microsoft Entra ID / real SSO (RTL-SEC-01) — external integration | 🟠 BLOCKED — C-06 (production role-source ownership) |
| **RTL Programming** | BR005/RTL-PROG-01–10: Program RTL | 🟠 BLOCKED — EXTERNAL (physical delivery only) | Application request persistence exists: atomic insert + audit (`rtl_programming_service.py`, OPS-PROG-1); authorization enforced; Master MSISDN captured; confirmation honest ("request recorded ≠ programmed"). The request's `rtl_commands` row (RTL-IF-1) and its lifecycle (RTL-IF-2, ADR-018) are CONNECTED (`RTL-PROG-EXEC-1`, `0787b90`): every command transition reconciles a truthful status back onto the request in one transaction, and a protocol-neutral `execute_request()` seam runs a request's command through any injected `DeviceTransport`. `RTL-PROG-SIM-1` (implemented/verified, pending commit) adds a development/demo-only simulated execution path on that seam — default OFF, fail-closed in production, clearly labelled as simulation — so the local demo runs Program RTL → queued → explicitly simulate → sent → successful/failed. No production transport is wired in any environment | Physical command transport to RTL device (C-05); RTL Master MSISDN source; device-side programming confirmation | 🟠 BLOCKED — C-05 (transport/device protocol) only; request→dispatch→lifecycle wiring complete, and a simulated demo path exists for local use |
| **Message forwarding** | BR003/BR004/RTL-FWD-01–07 | 🟠 BLOCKED — EXTERNAL (delivery only) | Per-user forwarding preference persisted with atomic mutation + audit (`message_forwarding_service.py`, OPS-FWD-1); drawer prefilled from DB; feedback truthful; 18:30 auto-disable scheduler now implemented and committed (C08-AUTO-DISABLE-1, `d10c566`) | SMS/message transport (C-05 family); recipient eligibility rules (FWD-D1 vs FWD-03); actual message delivery | 🟠 BLOCKED — C-05 (transport) only; scheduler ownership no longer blocking |
| **18:30 auto-disable** | BR016: Auto-disable forwarding at 18:30 daily | 🟢 CLOSED / PUSHED / REMOTE-VERIFIED (`d10c566`) | `services/forwarding_auto_disable_service.py`: idempotent bulk-disable of all currently-enabled forwarding users at cutoff (default 18:30 Africa/Johannesburg, `config/forwarding_schedule.py`); Administrator-only same-day override with mandatory reason, auto-expiring next day (`components/auto_disable_override_panel.py`); every real transition audited, identical re-set/empty clear is a no-op; standalone entry point `scripts/run_forwarding_auto_disable.py`, not embedded in Dash/Gunicorn; migration 010. 38 focused + 100 regression tests passed, full suite passed | Real dev DB is now at `012` and this panel was browser-smoked against it (`LOCAL-DB-CATCHUP-1`, 2026-09-07); which users/RTLs are affected and fleet-wide-vs-scoped override remain open, per C-08 baseline | None — implementation complete; see `docs/context/ACTIVE_GATE.md` |
| **RTL active lifecycle** | BR010/BR012/RTL-ACT-01–06 | 🟡 PARTIAL | Startup event ingestion persists + activates `rtl_active_state` (INGEST-1, ACT-D1–D7); deactivation persists with audit (OPS-DEACT-1); active-list state separate from admin status (RTL-ACT-05) | Physical RTL device producer; Master-side list is its own system; monitoring semantics for active-list (ACT-03 client question) | 🟠 BLOCKED — ACT-03 (active-list semantics) |
| **Notifications/alarms** | BR008–BR012/RTL-EVT-01–09 | 🟡 PARTIAL | Notification Center derives BR008 >24h from readings; persisted device events (battery_low, power_down, sensor_error, startup, check-in, invalid_uid) render via shared `event_semantics.py` layer; categories scoped per device scope | Real device event producers (MQTT/C-05); delivery to users (SMS/email); notification history/acknowledgement; high-temperature threshold (C-01 — corrected 2026-09-06, was mislabeled C-15 in this row; see note below §8); vibration contract (C-16/C-02) | 🟠 BLOCKED — C-05 + C-01 + C-16 |
| **RTL Alarms report** | RTL-REP-01: RTL Alarms (30 Days) | 🟢 CLOSED / PUSHED (`7969324`) | Data-backed from persisted `device_events` via `rtl_alarms_30d_rows()` (REPORT-3); scope-filtered; zero rows is legitimate empty report; CSV export working, unchanged; PDF export now also working (REPORT-EXPORT-1) | Production delivery format (C-04: development baseline set 2026-09-06, pending client confirmation — PDF + CSV, no XLSX; both now built); OU/Zone/Sector/CNC/Feeder taxonomy mapping (C-07: HOLD, reconfirmed 2026-09-06) | 🟠 BLOCKED — C-07 (taxonomy) |
| **Installed RTL report** | RTL-REP-02: Installed RTLs | 🟢 CLOSED / PUSHED (`7969324`) | Data-backed from readings via `installed_rtls_rows()` (REPORT-2); OU/Zone/Sector/CNC/Feeder stay None per R2-D2; CSV export working, unchanged; PDF export now also working (REPORT-EXPORT-1) | Production delivery format (C-04: development baseline set 2026-09-06, pending client confirmation — PDF + CSV, no XLSX; both now built); taxonomy mapping (C-07: HOLD, reconfirmed 2026-09-06) | 🟠 BLOCKED — C-07 (taxonomy) |
| **Max Temperature report** | RTL-REP-03: Maximum Temperature | 🟢 CLOSED / PUSHED — report `95bdfa5`, export `7969324` | Data-backed, one row per transformer: highest temperature reading per transformer in the resolved window, deterministic tie-break, Date Installed from the winning device's own `installed_at`. Default rolling 30 days (C-15 baseline) plus a custom range; period shown in the UI and, for export, in the filename/status panel. CSV keeps the exact report header as row 1, no preamble; PDF shows title/scope/period/generated/headers, paginated | OU/Zone/Sector/CNC/Feeder Name still unmapped (C-07, HOLD) | 🟢 COMPLETE for this baseline — see `docs/context/ACTIVE_GATE.md` |
| **Export/delivery** | RTL-PUR-05 | 🟢 CLOSED / PUSHED (`7969324`) — CSV + PDF for all three reports | Export pipeline (`report_export.py`) now registers both `format_csv` and `format_pdf` (fpdf2, normal compression, repeated page headers); `EXPORTABLE_REPORTS` covers Installed RTLs, RTL Alarms, and Maximum Temperature; authorization enforced (`require_capability(EXPORT_DATA)`) before any row fetch, for every report and format; honest format label names both formats | Production format baseline (C-04: PDF + CSV, no native XLSX) — both now built as development defaults, still pending formal client confirmation; native XLSX remains explicitly out of scope | 🟢 COMPLETE for this baseline — see `docs/context/ACTIVE_GATE.md` |
| **Entra ID** | RTL-SEC-01 | 🟠 BLOCKED — EXTERNAL | Zero implementation; login test bans SSO branding; prototype auth via env-var comparison with no credential column | Full Entra ID integration; production credential source | 🟠 BLOCKED — external integration dependency |
| **MQTT / RTL device comm** | RTL-INT-07/08 | 🟠 BLOCKED — EXTERNAL | No implementation; `device_events.source` provides forward-compatible hook; `rtl_programming_requests` has persistence hooks | MQTT broker integration; device command protocol; producer adapters | 🟠 BLOCKED — external integration dependency |
| **SMS gateway** | RTL-INT-06 | 🟠 BLOCKED — EXTERNAL | Zero implementation | SMS gateway configuration; delivery pipeline | 🟠 BLOCKED — external integration dependency |
| **High-temperature threshold** | RTL-EVT-07, RTL-PUR-03 | 🟢 FRAMEWORK CLOSED / PUSHED (`THRESH-CONFIG-1`, `c83cf94`); values unconfirmed | One global Administrator-managed warning/critical pair (`temperature_threshold_config`, migration 011), unconfigured-by-absence; exact `Decimal` semantics matching `NUMERIC(12,3)`, excess precision rejected not rounded, `warning < critical` enforced by both service and a database CHECK; every real change audited. `MonitoringCondition` stays permanently UNKNOWN — no alarm/event logic reads this configuration; `high_temperature` remains inactive | Actual Eskom threshold values still unconfirmed (C-01) — not part of this gate, not invented | 🟢 FRAMEWORK COMPLETE — see `docs/context/ACTIVE_GATE.md`; actual values remain 🟠 BLOCKED — C-01 |
| **Vibration metric** | RTL-PUR-08, RTL-EVT-08 | 🟢 CONTRACT-CAPTURE FRAMEWORK CLOSED / PUSHED / REMOTE-VERIFIED (`VIB-CONFIG-1`, `859dbe2`); values unconfirmed | `docs/VIBRATION_METRIC_CONTRACT_TBD.md` has 15 open questions (corrected 2026-09-07 — this row previously said 14, itself a miscount from an earlier 16→14 correction on 2026-09-06; verified by direct count both times). Administrator-editable, audited capture of each answer individually (`vibration_contract_answers`, migration 012, key-value, unanswered-by-absence); structurally absent from event semantics, `vibration_event` remains inactive, no reading/alarm/threshold logic exists | Framework baseline set 2026-09-06, pending client confirmation (C-02: configurable vibration framework, not hardcoded); production sensor semantics/values still unconfirmed — all 15 TBD-doc questions remain open | 🟢 FRAMEWORK COMPLETE — see `docs/context/ACTIVE_GATE.md`; actual answers remain 🟠 BLOCKED — C-02 |
| **Taxonomy mapping** | OU/Zone/Sector/CNC/Feeder | 🟠 BLOCKED — EXTERNAL | Report column headers exist in `config/reports.py`; all values are None per R2-D2; no mapping between client taxonomy and dev plant model | Client must supply mapping (C-07) | 🟠 BLOCKED — C-07 |

## 4. Feature Layer Breakdown

### RTL Programming

| Layer | Status | Notes |
|---|---|---|
| UI | 🟢 IMPLEMENTED | Program RTL drawer in device management; MSISDN field captured |
| Authorization | 🟢 IMPLEMENTED | `PROGRAM_RTL` action guard; assignment check via `action_guard.py` |
| Backend/service | 🟢 IMPLEMENTED | Request persists atomically with audit (`rtl_programming_service.py`) |
| Database | 🟢 IMPLEMENTED | `rtl_programming_requests` table; `alembic/versions/005` |
| Integration | 🟠 BLOCKED — EXTERNAL | No MQTT/SMS/backend command transport (C-05); no device response path |
| Acceptance | 🟠 BLOCKED — EXTERNAL | Physical programming impossible without transport |

Request creation and Programming Activity/History **visibility** are
implemented. The device page renders recent persisted request/command activity
through a scope-aware, batched reader: Administrator may inspect any RTL,
Technician only a current assignment, and General User receives none. It is
explicitly application request/command history, with development simulation
labelled separately from absent physical RTL delivery. See RTL-PROG-VIS-1 in
§10 and `docs/context/ACTIVE_GATE.md`.

### Message Forwarding

| Layer | Status | Notes |
|---|---|---|
| UI | 🟢 IMPLEMENTED | Forwarding toggle drawer; prefilled from DB |
| Authorization | 🟢 IMPLEMENTED | `TOGGLE_MESSAGE_FORWARDING` action guard; admin + assigned technician |
| Backend/service | 🟢 IMPLEMENTED | Per-user state persisted with atomic mutation + audit (`message_forwarding_service.py`) |
| Database | 🟢 IMPLEMENTED | `message_forwarding` table; `alembic/versions/005` |
| Integration | 🟠 BLOCKED — EXTERNAL | No SMS transport (C-05); no 18:30 scheduler (C-08); no recipient eligibility rules |
| Acceptance | 🟠 BLOCKED — EXTERNAL | State persistence real; message delivery impossible without transport |

### RTL Active Lifecycle

| Layer | Status | Notes |
|---|---|---|
| UI | 🟢 IMPLEMENTED | Deactivation confirmation; active-list indicator |
| Authorization | 🟢 IMPLEMENTED | `DEACTIVATE_RTL` action guard; admin + assigned technician |
| Backend/service | 🟡 PARTIAL | Startup ingestion → activation projection (INGEST-1); deactivation with audit (OPS-DEACT-1); no physical RTL Master contact |
| Database | 🟢 IMPLEMENTED | `rtl_active_state` table; `alembic/versions/005` |
| Integration | 🟠 BLOCKED — EXTERNAL | No RTL Master communication; active-list is app-internal only |
| Acceptance | 🟡 PARTIAL | App-side state machine complete; Master-side semantics unverifiable |

### Alarm Pipeline

| Layer | Status | Notes |
|---|---|---|
| UI | 🟢 IMPLEMENTED | Notification Center with categories; Report Center with alarm report |
| Authorization | 🟢 IMPLEMENTED | Scope-filtered per user; admin-only for unregistered UIDs |
| Backend/service | 🟡 PARTIAL | `event_semantics.py` single-sources meaning; `notification_service.py` composes BR008 + persisted events; `report_service.py` populates RTL Alarms report |
| Database | 🟢 IMPLEMENTED | `device_events` table; `alembic/versions/006` |
| Integration | 🟠 BLOCKED — EXTERNAL | No event producers (C-05); no delivery channel; high-temperature/vibration thresholds client-gated (C-01, C-02 — corrected 2026-09-06; framework baselines set pending client confirmation, values unconfirmed) |
| Acceptance | 🟡 PARTIAL | Consumption pipeline complete; production events absent |

## 5. Completed Milestones

| Milestone | SHA | Status | Evidence |
|---|---|---|---|
| AUTH-HARDEN-1 (+ 1R, 1R2) | `5e01433` | CLOSED/PUSHED | Server-trusted session; 3161 tests at closure; S-4/S-5 closed |
| ROLE-BROWSER-1 | `0c40478` | PASSED | General persona audit complete; ROLE-4B/4C provenance backfilled |
| LOCAL-ENV-CLEAN-1 | — | COMPLETE | Docker PostgreSQL, Alembic sole DDL authority, 30/71/120 hierarchy |
| ENERGY-SPARK-2 | `ead3a4e` | CLOSED/PUSHED | Energy bar rendering stabilized |
| AUTH-PROD-HARDEN-1 | `669fffb` | CLOSED / PUSHED / REMOTE-VERIFIED | `APP_ENV` setting, `FLASK_SECRET_KEY` fail-closed in production, explicit cookie Secure/HttpOnly/SameSite, HTTPS boundary documented (not middleware); 21 new tests, 3200 total passing; remote-verified at `d9f7838` |
| CC-1 (Command Center) | `2c9a17d` | CLOSED/PUSHED | Fleet health, priority investigation, affected locations; 10 ADRs |
| CC-2 (rank bars) | `24d010d` | CLOSED/PUSHED | ADR-012 implemented; bar cap, route-scoped tokens |
| FIX-1 (callback hardening) | `5901945` | CLOSED/PUSHED | 8 callback defects found and fixed; regression coverage added |
| AUD-1 (audit wiring) | — | COMPLETE | All real mutations atomically audited |
| OPS-FWD-1 (forwarding persistence) | — | COMPLETE | Per-user state persisted with audit |
| OPS-PROG-1 (programming persistence) | — | COMPLETE | Request lifecycle real with audit |
| OPS-DEACT-1 (active-list deactivation) | — | COMPLETE | Active-list transition persisted with audit |
| INGEST-1 (canonical ingestion) | — | COMPLETE | Event ingestion + startup activation projection |
| EVT-CONSUME-1 (notifications + alarms) | — | COMPLETE | Event-backed notifications + alarm report population |
| REPORT-2 (Installed RTLs) | — | COMPLETE | Data-backed generation from readings |
| REPORT-3 (RTL Alarms 30 Days) | — | COMPLETE | Data-backed generation from persisted events |
| REPORT-4 (CSV export pipeline) | — | COMPLETE | Development-default CSV export for REP-01/REP-02 |
| UI-A11Y-POLISH-1 | `5383a8f` | CLOSED / PUSHED / REMOTE-VERIFIED | Narrow, targeted fix — not a general accessibility audit: accessible name added for one input (`device-admin-search`, via native `<label for>` + new `.visually-hidden` CSS utility, not `display:none`, confirmed non-empty in a Chromium accessibility-tree check) and shared `listing-error` styling added to two named error containers. Drawer/dialog accessibility and the rest of the Device Management toolbar were explicitly out of scope and not reviewed. 2696 non-db tests passing. See `docs/context/ACTIVE_GATE.md`. |

## 6. Paused Work

None currently recorded. The project reached a natural pause at the Phase 9 Client Review Gate (`docs/RTL_CLIENT_REVIEW_GATE.md`) where frontend phases 0–9 are complete and further implementation is gated on client/backend/data-contract decisions.

## 6a. RTL-IF-1 — CLOSED / PUSHED / REMOTE-VERIFIED

**RTL-IF-1** (protocol-neutral command contract and persistence):
`rtl_commands` table added (migration 008) — one command per accepted
programming request, created atomically alongside the request and its
audit row, initial state `QUEUED`. `rtl_programming_requests` remains the
immutable operator-intent record, untouched by this gate. No MQTT/Eskom
protocol, no ACK/retry/simulator — no transport exists yet. Independently
verified by Codex (RTL-IF-1V: PASS on migration, transaction atomicity,
request/command integrity, programming provenance, command contract,
authorization, audit, reset/seed, tests, architecture boundary;
`rtl_commands.device_id` duplication is a repository write-path invariant —
`create_command()` resolves it from the referenced request row — not an
additional cross-table database constraint).

Commit `831ea2b3ea612921d9fb44813924aeea43922fb0` — "feat(integration): add
protocol-neutral RTL command foundation" — pushed to `origin/main`; local
`HEAD` (at push time), `origin/main`, and `git ls-remote` all verified to
match. See `docs/context/ACTIVE_GATE.md` and
`docs/decisions/ADR-017-rtl-commands-are-the-protocol-neutral-transport-seam.md`
for the full record. This note describes that already-pushed commit only —
not whatever commit this documentation edit itself becomes part of, which
is a separate, later push (RTL-IF-1-CLOSE Step 6). The checkpoint in
Section 1 above is updated by a future gate's own opening step, per this
ledger's existing convention (Section 11) — not rewritten here as a side
effect of closing this one.

## 6b. RTL-IF-2 — CLOSED / PUSHED / REMOTE-VERIFIED

**RTL-IF-2** (SimulatorTransport + command lifecycle): extends
`rtl_commands` (migration 009) with `sent_at`/`acknowledged_at`/
`completed_at`/`failure_code`/`failure_detail`, and adds the six-state
lifecycle (`QUEUED→SENT→ACKNOWLEDGED→SUCCEEDED`, or `SENT→FAILED`/
`TIMED_OUT`) enforced by `services/rtl_command_service.py` against
`config/commands.py`'s `ALLOWED_TRANSITIONS` map — the database has no
CHECK on the state vocabulary itself, only on timestamp/failure-field
ordering. Adds a deterministic `SimulatorTransport`
(`services/simulator_transport.py`) and an explicit-caller-only dispatcher
(`services/rtl_command_dispatch_service.py::dispatch_command`); the
conditional `QUEUED→SENT` database update prevents duplicate dispatch under
concurrency, and a transport exception leaves the command coherently
`SENT` — recovery/retry from that state is intentionally deferred, no
worker or scheduler exists yet. No automatic dispatch, no MQTT/SMS/Eskom
protocol, no real device integration of any kind: `ACKNOWLEDGED`/
`SUCCEEDED` are `SimulatorTransport`'s own internal test-contract
semantics, not proof of physical RTL programming. The existing Program RTL
UI action still stops at `command = QUEUED`.

Independently verified by Codex (RTL-IF-2V: PASS on diff scope, migration
009, state machine, timestamp integrity, dispatch transaction, transport
contract, programming provenance, authorization, audit, test quality,
architecture boundary; concurrent dispatch CONCURRENCY SAFE; transport
exception ACCEPTABLE WITH DOCUMENTED RECOVERY REQUIREMENT).

Commit `bb7fea3af0c85cff3cdf84dd82a36a2ed397644a` — "feat(integration): add
simulated RTL command lifecycle" — pushed to `origin/main`; local `HEAD`
(at push time), `origin/main`, and `git ls-remote` all verified to match.
See `docs/context/ACTIVE_GATE.md` and
`docs/decisions/ADR-018-simulator-transport-is-not-the-eskom-protocol.md`
for the full record. This note describes that already-pushed commit only —
not whatever commit this documentation edit itself becomes part of, which
is a separate, later push (RTL-IF-2-CLOSE Step 6). The checkpoint in
Section 1 above is updated by a future gate's own opening step, per this
ledger's existing convention (Section 11) — not rewritten here as a side
effect of closing this one. **Caveats preserved**: `SimulatorTransport` is
not the Eskom protocol; no physical device integration exists yet;
recovery for a command stuck at `SENT` after a transport exception remains
deferred; no real retry/worker/scheduler exists yet.

## 6c. RTL-IF-3 — CLOSED / PUSHED / REMOTE-VERIFIED

**RTL-IF-3** (simulated incoming device-event integration): adds
`services/simulated_event_source.py`, a thin front end onto the existing
`device_event_service.ingest_event()` boundary — no second event pipeline,
no schema migration, no changes to
`repositories/plant_monitoring_repository.py`, `event_semantics.py`,
`notification_service.py`, or `report_service.py`. `SUPPORTED_EVENT_TYPES`
(`startup`, `check_in`, `battery_low`, `power_down`, `sensor_error`) is
exactly `config/events.py`'s already-meaningful vocabulary — a
simulator-only allowlist layered on top of `ingest_event()`'s own open
vocabulary (INGEST-D7), never a change to it. Simulated startup exercises
the existing `rtl_active_state` activation projection and its audit row
unchanged; simulated battery-low events reach the Notification Center and
RTL Alarms report through their existing, unmodified consumer code. No
voltage-threshold evaluation, no high-temperature/vibration rules, no
browser wiring (confirmed structurally, not merely asserted). See
`docs/context/ACTIVE_GATE.md` and
`docs/decisions/ADR-019-simulated-event-source-reuses-canonical-ingestion.md`
for the full record.

Independently verified by Codex (RTL-IF-3V: PASS on diff scope, canonical
ingestion, simulator allowlist, startup activation, unknown UID behavior,
canonical validation, downstream consumers, architecture boundary, test
quality; non-blocking note — no dedicated Command Center recent-events
test, accepted because that consumer reads the same persisted
`device_events` path already exercised by the Notification Center/RTL
Alarms report tests).

Commit `a89fbf97b523aee6b63f8f6b80d5bda0fd0876e8` — "feat(integration): add
simulated RTL event ingestion" — pushed to `origin/main`; local `HEAD` (at
push time), `origin/main`, and `git ls-remote` all verified to match. See
`docs/context/ACTIVE_GATE.md` and
`docs/decisions/ADR-019-simulated-event-source-reuses-canonical-ingestion.md`
for the full record. This note describes that already-pushed commit only —
not whatever commit this documentation edit itself becomes part of, which
is a separate, later push (RTL-IF-3-CLOSE Step 6). The checkpoint in
Section 1 above is updated by a future gate's own opening step, per this
ledger's existing convention (Section 11) — not rewritten here as a side
effect of closing this one. **Caveats preserved**: the simulator is not
the Eskom protocol; no physical MQTT/device integration exists yet; no new
alarm-rule engine exists; no notification delivery integration exists; no
monitoring semantics changed.

## 6d. RTL-IF-4 — CLOSED / PUSHED / REMOTE-VERIFIED

**RTL-IF-4** (notification delivery abstraction): adds
`services/notification_delivery.py` (provider-neutral `DeliveryRequest`/
`DeliveryResult`/`NotificationDelivery` contract) and
`services/mock_notification_delivery.py` (deterministic
`MockNotificationDelivery`) — no changes to `notification_service.py`,
`event_semantics.py`, `message_forwarding_service.py`,
`device_event_service.py`, or the repository layer; no schema migration.
The existing in-app Notification Center is structurally uncoupled from
delivery (proven via `ast`-based import inspection, not just absence of a
diff). `DeliveryRequest.recipient_endpoint` is always caller-supplied — no
recipient-resolution policy exists, since who receives what by which
channel is still a client-undecided item (§8). No `notification_deliveries`
table: delivery lifecycle/acknowledgement/escalation/retention/retry are
all still open decisions. Message forwarding is unchanged and not
"completed" by this tranche — enabling it still sends nothing (FWD-D9).
See `docs/context/ACTIVE_GATE.md` and
`docs/decisions/ADR-020-notification-delivery-is-separate-from-the-in-app-projection.md`
for the full record.

Independently verified by Codex (RTL-IF-4V: PASS on diff scope, in-app
notification separation, provider-neutral delivery contract, deterministic
mock delivery, recipient boundary, privacy/security, forwarding
regression, event semantics, no persistence/schema additions, test
quality, architecture boundary; non-blocking note — provider-specific
endpoint/body validation deferred until real provider formats/limits are
known).

Commit `0b2a4d5ec2c88d5a395729d30dee86abf1b6fb4d` — "feat(integration): add
notification delivery abstraction" — pushed to `origin/main`; local `HEAD`
(at push time), `origin/main`, and `git ls-remote` all verified to match.
See `docs/context/ACTIVE_GATE.md` and
`docs/decisions/ADR-020-notification-delivery-is-separate-from-the-in-app-projection.md`
for the full record. This note describes that already-pushed commit only —
not whatever commit this documentation edit itself becomes part of, which
is a separate, later push (RTL-IF-4-CLOSE Step 6). The checkpoint in
Section 1 above is updated by a future gate's own opening step, per this
ledger's existing convention (Section 11) — not rewritten here as a side
effect of closing this one. **Caveats preserved**: mock delivery only; no
real SMS/email; no production recipient policy; the Notification Center
remains independent; forwarding is not completed; the durable delivery
lifecycle remains client-dependent.

## 7. Client Demo / Priority Overrides

- **Client delivery branch**: `cc-1-command-center-progress` is the LIVE delivery branch (corrected 2026-09-07 by CLIENT-SYNC-2A; see `docs/CLIENT_DELIVERY.md`). The older `client-release` (`d89a090`, 218 files, pre-Command-Center) and `client-demo-1` are superseded history — **do not push from them**, and in particular do not run the old `git push client client-release:main`, which would deliver a pre-Command-Center tree. The client now sees the full curated runtime milestone, not a login-only subset; internal engineering material still never crosses.
- **Client Review Gate (Phase 9)**: The frontend phase cycle explicitly paused at `docs/RTL_CLIENT_REVIEW_GATE.md` with the instruction: "Do not start new implementation until those decisions are provided."
- No evidence of unplanned demo/UI interruptions to active requirement work found in repository context.

## 7a. Client Delivery Operating Workflow (2026-09-06)

- Accepted development is synchronized to the client GitHub repo
  (`powerplant-dashboard-client`) at suitable weekly milestones.
- The user accesses the client's own laptop by Remote Desktop, pulls the
  accepted client update, and demonstrates that week's development there.
- Unclear Eskom requirements are asked directly to the client, who may
  escalate to their own superiors and return with the answer.
- Non-blocked development continues on `main` in the meantime — this
  workflow does not pause other work while a question is outstanding.
- The existing `client-release` leakage safeguards are preserved unchanged:
  the never-curate list, the curation-by-hand model, and
  `scripts/check_client_release.py` still govern every push, per
  `docs/CLIENT_DELIVERY.md`.

## 8. External Dependencies / Client Input Required

**Numbering correction (2026-09-06):** several rows below previously cited
the wrong `REQ-3I_Clarification_Register.md` ID — report format was labelled
`C-10` (that ID actually names the separate notification acknowledgement/
retention question) and the vibration contract was labelled `C-16` (that ID
actually names unrelated remaining FS "TBC" items). Corrected here to `C-04`
and `C-02` respectively, matching REQ-3I, this ledger's own cited source of
truth (§1). The high-temperature threshold row was also split out from the
Max Temperature reporting-period row — REQ-3I treats them as separate items,
`C-01` and `C-15`.

**Provenance note (2026-09-06):** the "baseline set" statuses below (C-08,
C-15, C-04, C-01, C-02) are internal decisions made by the development
team/user so implementation can proceed. **They are not confirmed
Eskom/client answers unless repository evidence proves otherwise**, and
formal client confirmation is still pending for each. C-07 is the opposite
case — genuinely on hold pending the client, not a development decision.

| Dependency | Blocks | Status | Reference |
|---|---|---|---|
| C-05: MQTT / RTL device transport protocol | Physical programming, event producers, active-list contact, message forwarding delivery | 🟠 BLOCKED — sole remaining leading gate | No protocol defined; `device_events.source` is forward-compatible hook; reconfirmed 2026-09-06 as Eskom-controlled/external |
| C-06: Production role-source ownership (Entra ID vs DB) | Production authentication | 🟠 BLOCKED | Zero Entra ID implementation; prototype auth only; reconfirmed 2026-09-06 as Eskom-controlled/external, alongside Azure/private-APN infrastructure |
| C-07: Asset hierarchy taxonomy mapping (OU/Zone/Sector/CNC/Feeder) | Report columns; Installed RTLs and RTL Alarms reports | 🟠 HOLD | Mapping between client taxonomy and dev plant model undefined; explicitly placed on HOLD by the client 2026-09-06, pending hierarchy clarification |
| C-08: 18:30 scheduler ownership (app vs RTL Master) | BR016 auto-disable forwarding | 🟢 CLOSED / PUSHED (baseline still pending client confirmation) | App-owned, not RTL Master; default 18:30 Africa/Johannesburg; admin same-day override with mandatory reason, auto-expiring; overrides and automatic disables both audited. Internal decision, not a client answer. `C08-AUTO-DISABLE-1` committed and pushed as `d10c566` — see `docs/context/ACTIVE_GATE.md` |
| C-01: High-temperature alarm threshold | RTL-EVT-07, RTL-PUR-03 | 🟢 FRAMEWORK CLOSED, COMMITTED, PUSHED (`c83cf94`) (baseline still pending client confirmation) | Administrator-configurable warning/critical thresholds, never hardcoded, changes audited; internal decision, not a client answer. `THRESH-CONFIG-1` closed — see `docs/context/ACTIVE_GATE.md`. Actual Eskom values still unconfirmed |
| C-02: Vibration metric contract + anomaly thresholds | RTL-PUR-08, RTL-EVT-08 | 🟢 CONTRACT-CAPTURE FRAMEWORK CLOSED, COMMITTED, PUSHED (`859dbe2`) (baseline still pending client confirmation) | Must be a configurable framework, not hardcoded; internal decision, not a client answer; production sensor semantics/values still unconfirmed — all 15 questions in `docs/VIBRATION_METRIC_CONTRACT_TBD.md` remain open. `VIB-CONFIG-1` closed — see `docs/context/ACTIVE_GATE.md` |
| C-04: Report delivery format (CSV vs PDF vs XLSX) + retention/history | Production report export | 🟢 IMPLEMENTED, COMMITTED, PUSHED (`7969324`) as CSV+PDF for all 3 reports (baseline still pending client confirmation) | PDF + CSV required; native XLSX not required and remains out of scope. Internal decision, not a client answer. `REPORT-EXPORT-1` closed — see `docs/context/ACTIVE_GATE.md`. Retention/history for reports still open |
| C-15: Maximum Temperature reporting period | RTL-REP-03 | 🟢 IMPLEMENTED, COMMITTED, PUSHED (baseline still pending client confirmation) | Rolling 30 days by default, plus custom date range; period must be shown on report/export. Internal decision, not a client answer. REP-03 (`REPORT-MAXTEMP-1`, `95bdfa5`) and its export (`REPORT-EXPORT-1`, `7969324`) both closed; period identified in the filename and export status |
| Notification delivery channel & recipient rules (C-10: acknowledgement/closure/escalation/retention) | BR008–BR012 delivery | 🟠 BLOCKED | Display-only by frozen decision; not part of this round's baselines |
| Active-list monitoring semantics (ACT-03/C-09) | BR007, RTL-ACT-03 | 🟠 BLOCKED | Does web app need active-list semantics or is that RTL-Master-only? Not part of this round's baselines |
| Browser support list | RTL-UX-02 | 🟠 BLOCKED | No compatibility testing performed |
| Production cookie/deployment hardening | Security posture | 🟢 APP-SIDE DONE — Railway service vars not yet confirmed set | `SESSION_COOKIE_SECURE`/`SameSite`/`HttpOnly`/`FLASK_SECRET_KEY` fail-closed implemented (AUTH-PROD-HARDEN-1, committed); HTTPS enforcement is Railway's edge by design, not app code |

## 9. Verified — Do Not Rebuild

These foundations are mature, tested, and should be reused by future agents:

- **Hierarchy generation**: 30 plants / 71 transformers / 120 devices; deterministic; reserved `plant-01-t1-d1` = `aa12`/`29017` — `db/hierarchy.py`, `tests/test_hierarchy_generation.py`
- **Metric configuration**: 8 metrics with aggregation types, units, precision — `config/metrics.py`, `tests/test_metrics_config.py`
- **Repository layer**: All SQL in `repositories/plant_monitoring_repository.py`; parameterized; identifier validation via `hierarchy_service`; bounded queries per ADR-014
- **Service layer**: `monitoring_service.py` (view models, freshness, statistics/delta), `hierarchy_service.py` (validation), `auth_service.py` (session identity), `authorization.py` (pure policy tables), `device_scope.py` (scope resolution)
- **Event semantics**: Single-source mapping from persisted events to consumer meaning — `services/event_semantics.py`; no duplicated thresholds or category literals in consumers
- **Audit pattern**: Atomic mutation + audit in single transaction — `services/audit_service.py`; pattern used by forwarding, programming, deactivation, ingestion
- **Authorization architecture**: Route policy → capability policy → action policy → device scope — four dimensions, default-deny, tested end-to-end
- **Server-trusted session (AUTH-HARDEN-1)**: Flask signed cookie carries only `user_id`; role/status reloaded from DB every call; `auth-store` is presentation-only
- **Report export pipeline**: Format-neutral document model → CSV formatter — `services/report_export.py`; new formats are new formatters, nothing more
- **Test suite**: 2669 pure-logic tests; 153 test files; coverage across hierarchy, metrics, services, auth, routing, components, seed integrity

**Do not confuse these two similarly-named simulators — they are unrelated:**

- **`db/live_simulator.py`** — the telemetry/chart simulator. Appends
  synthetic `readings` rows on a timer so the dashboard's freshness badge,
  KPIs, and charts visibly move during local development (README §8). Has
  nothing to do with RTL commands, events, or integration; it only writes
  to the `readings` table.
- **`services/simulator_transport.py`** (`SimulatorTransport`) — the RTL
  command transport simulator (RTL-IF-2, ADR-018). A deterministic
  `DeviceTransport` implementation used by `rtl_command_dispatch_service` to
  exercise the `rtl_commands` state machine without a real MQTT/Eskom
  connection. Has nothing to do with `readings` or the chart/telemetry
  layer.

They must remain separate modules serving separate concerns; do not merge
them or let one import the other.

**Who may construct a `SimulatorTransport` (RTL-PROG-SIM-1):** exactly one
application module — `services/rtl_programming_simulation_service.py` — and
only after it has verified that `RTL_PROGRAMMING_SIMULATOR_ENABLED` is
explicitly on AND the environment is not production. Tests are the only
other legitimate constructor. `rtl_programming_execution_service.py`,
`rtl_programming_service.py` and `callbacks/device_manage.py` must never
import or construct one — this is enforced by `ast`-based import
inspection in `tests/test_rtl_programming_simulation.py`, not merely by
convention. A future production adapter implements `DeviceTransport` on
its own terms; it does not extend, wrap, or get injected in place of this
class.

## 10. Resume Queue

### Ready Now

Work that can be implemented without unresolved client/external decisions:

| # | Task | Status | Rationale |
|---|---|---|---|
| 1 | **CLIENT-CLARIFICATION-PACK-1** | 🟡 DEVELOPMENT BASELINES SET FOR PART (2026-09-06); STILL NOT CLIENT-CONFIRMED | `docs/context/CLIENT_CLARIFICATION_PACK.md` and `docs/context/CLIENT_QUESTIONS.md` exist and are committed (2026-09-04), collecting all client decisions needed before blocked work can resume: C-05, C-06, C-07, C-08, C-04, C-15, C-02, C-01, C-09/ACT-03. Internal development baselines now set for C-08 (full), C-15 (full), C-04 (format only), C-01 and C-02 (framework shape only) — these are development-team/user decisions so implementation can proceed, **not confirmed Eskom/client answers**. Genuinely unanswered by the client: C-05, C-06, C-07 (HOLD), C-09/ACT-03. See `REQ-3I_Clarification_Register.md` and `docs/context/CLIENT_QUESTIONS.md`. |
| 2 | **C08-AUTO-DISABLE-1** | 🟢 CLOSED / PUSHED / REMOTE-VERIFIED (`d10c566`, 2026-09-07) | Built per the C-08 development baseline: app-owned, default 18:30 Africa/Johannesburg, admin same-day override with mandatory reason (auto-expiring), full audit. Only flips the existing `message_forwarding` preference off on a schedule — no transport dependency, so it does not wait on C-05. Standalone entry point (`scripts/run_forwarding_auto_disable.py`), never a timer embedded in a Dash/Gunicorn worker; the actual production scheduling mechanism (cron/Railway job) stays deployment-configurable, unchanged from the original decision. 38 focused + 100 regression tests passed, full suite passed, migration 010 is sole Alembic head. See `docs/context/ACTIVE_GATE.md`. |
| 3 | **REPORT-MAXTEMP-1** | 🟢 CLOSED / PUSHED / REMOTE-VERIFIED (`95bdfa5`, 2026-09-07) | Maximum Temperature is now data-backed: one row per transformer, highest temperature reading in the resolved window, deterministic tie-break (earliest `reading_ts`, then `device_id`, then `readings.id`), Date Installed from the winning device's own `installed_at` (blank when it has none — never invented). Default rolling 30 days (C-15) plus a custom range; the resolved period is shown in the UI. Two scope gates: transformer visibility and winning-reading visibility, matching `list_transformers`'s no-leak convention. See `docs/context/ACTIVE_GATE.md`. |
| 4 | **REPORT-EXPORT-1** | 🟢 CLOSED / PUSHED / REMOTE-VERIFIED (`7969324`, 2026-09-07) | All three reports export as CSV and PDF (C-04 baseline: PDF + CSV, no native XLSX — development baseline, pending client confirmation). Installed RTLs'/RTL Alarms' CSV bytes and filenames unchanged. Maximum Temperature's CSV keeps the exact column-contract header as row 1, no preamble, no fake Period column; its resolved period is identified in its filename and the export status panel instead, using the SAME period-resolution path as its preview (R4-D7). PDF (fpdf2, normal compression) shows title/scope/period/generated/headers with paginated, repeated-header rows, for all three reports. Authorization runs before any row fetch, for every report and format. See `docs/context/ACTIVE_GATE.md`. |
| 5 | **THRESH-CONFIG-1** | 🟢 CLOSED / PUSHED / REMOTE-VERIFIED (`c83cf94`, 2026-09-07) | One global Administrator-managed warning/critical temperature threshold pair (C-01 framework baseline), unconfigured-by-absence, no invented Eskom values. Exact `Decimal` semantics matching `NUMERIC(12,3)` (a correctness fix applied before this closure — validating on raw `float` could let two distinct values collapse to the same stored value); excess precision rejected, never rounded; `warning < critical` enforced by both the service and a new migration-011 database CHECK. Identical canonical re-save / already-unconfigured clear are no-ops; real transitions audited. Admin-only. No `high_temperature` activation, no reading-to-alarm evaluation. See `docs/context/ACTIVE_GATE.md`. |
| 6 | **VIB-CONFIG-1** | 🟢 CLOSED / PUSHED / REMOTE-VERIFIED (`859dbe2`, 2026-09-07) | An audited, Administrator-editable place to record answers to vibration's 15-question sensor contract (C-02 framework baseline; TBD doc question count corrected 14→15 by direct count this session). Genuine multi-row key-value persistence (`vibration_contract_answers`, migration 012): one row per answered question, absence = unanswered, no invented defaults. Questions defined in `config/vibration_contract.py`, transcribed verbatim. Identical re-save / clearing an unanswered item are no-ops; real transitions audited and rolled back on audit failure. Admin-only. Vibration remains completely inactive in the metric registry, selectors, charts/KPIs, readings queries, freshness/`MonitoringCondition`, event semantics, and alarm generation — zero diff to any of those files; no unit/axis/threshold/aggregation/cadence/range/storage/API contract invented. See `docs/context/ACTIVE_GATE.md`. |
| 7 | **RTL-PROG-EXEC-1** | 🟢 CLOSED / PUSHED / REMOTE-VERIFIED (`0787b90`, 2026-09-07) | Connected `rtl_programming_service.py` (OPS-PROG-1: persists the request + one `rtl_commands` row, RTL-IF-1) to the existing command lifecycle (RTL-IF-2, ADR-018) — the command row no longer stays `QUEUED` forever with no reconciliation. No migration: the request's existing status/completed_at/error_message columns already supported the lifecycle. Every command transition projects a truthful request status (`QUEUED→queued`, `SENT`/`ACKNOWLEDGED→sent`, `SUCCEEDED→successful`, `FAILED`/`TIMED_OUT→failed`) in the SAME transaction as its own conditional UPDATE — no command/request split-brain; `error_message` is safe/normalized, never a raw exception. New `services/rtl_programming_execution_service.execute_request(request_id, transport)` is the protocol-neutral orchestration seam — no `SimulatorTransport` import/construction, no callback wiring, no retry/worker. Existing transition legality/concurrency protection unchanged. 83 focused tests + full regression + full suite passed; no migration; real dev DB untouched at 007. See `docs/context/ACTIVE_GATE.md`. |
| 8 | **RTL-PROG-SIM-1** | 🟢 CLOSED / PUSHED / REMOTE-VERIFIED (`603e158`, 2026-09-07) | A development/demo-only simulated programming execution path on RTL-PROG-EXEC-1's `execute_request()` seam, using the existing deterministic `SimulatorTransport` (ADR-018). No migration. `RTL_PROGRAMMING_SIMULATOR_ENABLED` is centralized in `config/settings.py`, defaults OFF, and **fails closed with a `RuntimeError` at startup** if enabled under `APP_ENV=production`; production without it starts normally with no controls and no callback registered. `services/rtl_programming_simulation_service.py` is the only application service that constructs a `SimulatorTransport`, and delegates execution rather than duplicating lifecycle logic. Outcomes are Success/Failure/Timeout — simulation semantics, not Eskom protocol semantics. Simulation needs an explicit click after a request is recorded; recording never auto-executes. Existing `PROGRAM_RTL` authorization is reused and runs before the request lookup; browser-owned request ids must belong to the authorized device, with unknown and mismatched ids sharing one refusal (no existence oracle). A simulated success is not evidence a physical RTL was programmed. 63 focused + 117 RTL + 340 auth/settings regression tests and the full suite passed. See `docs/context/ACTIVE_GATE.md`. |
| 9 | **LOCAL-DB-CATCHUP-1** | 🟢 COMPLETED / VERIFIED (2026-09-07) | The real development database was advanced non-destructively from `007_audit_log` to `012_vibration_contract_answers` — `alembic upgrade head` only, no reset/purge/schema-recreation/seed. Target proven first (`APP_ENV=development`, `plant_monitoring_postgres`, `localhost:5436`, `powerplant_demo`, schema `plant_monitoring`, server self-identifying inside the local Docker network — not client/production), and a validated custom-format backup (11,921,321 bytes, `pg_restore --list` OK) was taken outside the repository beforehand. All eleven pre-existing populations preserved exactly; the migration added no business records and no audit rows; the four new tables verified present and empty. Administrator browser smoke passed (Fleet Overview, C08 panel, threshold panel "Not configured", vibration panel 15 unanswered) with nothing invented. Simulator smoke verified disabled state, temporary process-only enablement, controls/warning and callback reachability; real simulated execution was NOT performed because zero legitimate queued requests existed, and no fake MSISDN/programming history was created. Flag removed afterwards; final local state simulator-disabled. See `docs/context/ACTIVE_GATE.md`. |
| 10 | **CLIENT-SYNC-2A** | 🟢 COMPLETED / INSPECTION ONLY (2026-09-07) | Read-only curation inspection; **neither repository modified**. Verified both SHAs, read the gitignored `docs/CLIENT_DELIVERY.md` authority and CLIENT-SYNC-1 provenance (`34d5d73` + `3d4897c`). Established: client branch at migration `007_audit_log`; the delta is **not feature-separable** (import closure from `app.py` — 118 dev runtime files vs 86 client, 28 missing + 51 differing; `app.py`/`callbacks/routing.py` are hubs, so omitting simulator/vibration/threshold/C08 each needs `app.py` + `pages/plants_overview.py` surgery and permanent source divergence); ~112 test-file operations on top; five client-only documents exist that a mirror would delete; migrations 008–012 are additive-only so non-destructive `alembic upgrade head` is supported. See `docs/context/ACTIVE_GATE.md`. |
| 11 | **CLIENT-SYNC-2A-FIX** | 🟡 IMPLEMENTED, VERIFIED, PENDING COMMIT (2026-09-07) | Prepared the curation boundary; **client repo untouched**. Leakage guard strengthened: nine previously-uncaught internal paths added (our vibration open-question register, the internal review-gate doc, the client's own spec PDF + extracted text, `check_databases.py`, both workflow-PDF generators, `railway.json`) plus refusal by SHAPE — any `.env*` except `.env.example`, any `.log`/`.dump`/`.bak`/`.sql.gz`/`.pyc` — since a hand-written list is what rotted. Violations on `main` 84 → 93; client branch still clean at 263 files. Client-visible internal terminology scrubbed from four rendered strings (C-01, C-02, two `development baseline C-15` notices) with the user meaning preserved, keeping the client's own BR016/BR008. Reset-contract classification fixed: 010/011/012 had each added a table without updating `KNOWN_TABLES` or `RESET_PRESERVES` (no behavioural defect — `RESET_REPLACES` is readings-only, and all three FK only to `users`, which `PURGE_ORDER` never deletes), now classified and `KNOWN_TABLES` **derived from the migrations' own DDL** so it cannot rot again. Full suite exit 0; context pack CLEAN; `git diff --check` clean. See `docs/context/ACTIVE_GATE.md`. |
| 12 | **CLIENT-SYNC-2B** | 🟢 COMPLETED / DELIVERED / REMOTE-VERIFIED (client `3f21c3a`, 2026-09-07) | Runtime **parity** curated to client branch `cc-1-command-center-progress` and pushed: 217 files changed (106 added, 107 modified, 3 deleted, 1 rename), 357 paths byte-identical to `main`, client tree 263 → 366 files and 109 → 170 test files. Migrations 008–012 delivered (`007_audit_log` → `012_vibration_contract_answers`, additive; README gained a non-destructive "Upgrading an existing installation" section that explicitly says not to reseed) plus `tzdata`/`fpdf2`. Simulator ships **default OFF** (commented in `.env.example`, client-facing wording, production fail-closed intact). Five client-only documents preserved; client-tailored README/`.env.example`/`.gitignore`/`.gitattributes`/`GETTING_STARTED.md` not overwritten. Full client suite exit 0; staged leakage check 366 files / zero violations. Client `main` (`aa1dd3c`) and stale `client-release` (`d89a090`) untouched. Two blockers resolved en route — a delivered test depending on undelivered material (fixed on `main` at `72dd1cf`, no client divergence) and the stale documented push target. See `docs/context/ACTIVE_GATE.md`. |
| 13 | **CLIENT-PC-SYNC-3** (supersedes `CLIENT-PC-SYNC-2`, never started) | 🟢 CLOSED / PASS (2026-09-15) | Client laptop updated over Remote Desktop to `cc-1-command-center-progress` @ `983c17169a0cedd2282a0df4731228e0b05feac7`; database migrated non-destructively `007_audit_log` → `012_vibration_contract_answers`, protected row counts unchanged. Administrator and Technician (`demo.tech01`) browser acceptance both PASS: 24 assigned RTLs visible, My RTLs navigation works, unassigned RTL access refused, no Admin UI leakage. `RTL_PROGRAMMING_SIMULATOR_ENABLED=False`. Reported directly by the user who performed the sync — outside this session's reach, recorded as reported, not independently re-verified. No defect found; no application code touched. No new implementation gate opened by this closure. See `docs/context/ACTIVE_GATE.md`. |
| 14 | Production cookie/deployment hardening | 🟢 APP-SIDE COMPLETE (AUTH-PROD-HARDEN-1, committed) | `APP_ENV` setting added; `FLASK_SECRET_KEY` fails closed under `APP_ENV=production`; `SESSION_COOKIE_SECURE`/`HTTPONLY`/`SAMESITE` explicit; HTTPS enforcement documented as Railway's edge, not app middleware. Real Railway service still needs `APP_ENV`/`FLASK_SECRET_KEY` set to activate it. |
| 15 | **RTL-PROG-VIS-1** | 🟢 CLOSED / PASS (2026-09-15) | Shared RTL device-page Programming Activity now exposes recent persisted request/command history (requester display identity, Master MSISDN, request/command state, completion/result/error) through one scoped, windowed query. Administrator sees any RTL; Technician visibility is limited to current `DeviceScope` assignments; General User receives none. The callback uses trusted server identity, not browser store identity, and the reader repeats scope in SQL. Queued means recorded only; progressed lifecycle is explicitly labelled development Simulation; physical RTL delivery/acknowledgement remains absent. No migration, transport, retry, protocol or new command payload was added; fleet-level summary remains deferred. 111 focused tests, context gate and private-temp non-DB suite (2979 passed, 687 deselected) passed; DB/browser checks not run because PostgreSQL/Dash were not started. See `docs/context/ACTIVE_GATE.md`. |
| 16 | **TECH-WORKSPACE-1 / TECH-WORKSPACE-MERGE-1 / CLIENT-SYNC-3** | 🟢 CLOSED / MERGED / DELIVERED / REMOTE-VERIFIED (dev `fa69c9c`, client `983c171`, 2026-09-11) | Technician "My RTLs" work list (closed on branch `tech-workspace-1`) merged to dev `main` (`TECH-WORKSPACE-MERGE-1`, resolving an `ACTIVE_GATE.md`/`CURRENT_STATE.md` merge conflict caused by the branch's own isolated header rewrite — reverted so `main` kept its real active-gate declaration), then curated to client branch `cc-1-command-center-progress` (`CLIENT-SYNC-3`) as exactly the 8 runtime files that changed since CLIENT-SYNC-2B. Full client suite 6 failed (pre-existing dev-DB drift, reproduced on dev `main`) / 3623 passed / 3 skipped; leakage check zero violations; `git diff --check` clean; client `main`/`client-release` untouched. Superseded `CLIENT-PC-SYNC-2` before execution — see #13. See `docs/context/ACTIVE_GATE.md`. |

### Blocked / Waiting for Client or Integration

| # | Task | Blocked By | Dependency |
|---|---|---|---|
| 1 | Physical RTL programming delivery | 🟠 | C-05 (MQTT/transport protocol). The request/dispatch/lifecycle reconciliation (`RTL-PROG-EXEC-1`) is CLOSED / PUSHED (`0787b90`), and `RTL-PROG-SIM-1` (pending commit) exercises it end-to-end against the SIMULATOR only — development/demo, default OFF, fail-closed in production. Neither is physical delivery, and neither moves C-05 forward — see Ready Now |
| 2 | Message forwarding delivery (actual send) | 🟠 | C-05 (transport) — 18:30 auto-disable itself is unblocked; see Ready Now #2 |
| 3 | RTL active-list monitoring semantics | 🟠 | ACT-03/C-09 (client question: app or Master-side?) |
| 4 | Alarm pipeline — event producers | 🟠 | C-05 (MQTT/device communication) |
| 5 | Notification delivery (SMS/email) | 🟠 | C-05 (transport) + C-10 (delivery channel/recipient rules) |
| 6 | High-temperature threshold — values | 🟠 | C-01 (pending client confirmation; actual values still client must supply, must not be invented). The FRAMEWORK itself (admin-configurable, never hardcoded, audited) is `THRESH-CONFIG-1`, CLOSED and pushed as `c83cf94` — see Ready Now |
| 7 | Vibration metric activation — values | 🟠 | C-02 (framework baseline set 2026-09-06, pending client confirmation; 15 open questions in TBD doc still unconfirmed). The CONTRACT-CAPTURE framework itself is `VIB-CONFIG-1`, CLOSED / PUSHED (`859dbe2`) — see Ready Now |
| 8 | Maximum Temperature report — implementation | 🟢 CLOSED / PUSHED (`95bdfa5`) — `REPORT-MAXTEMP-1` | C-15 baseline set 2026-09-06, pending client confirmation (rolling 30 days + custom range). Built: data-backed, one row per transformer, deterministic tie-break, Date Installed from the winning device's own record. |
| 9 | Report production PDF export | 🟢 CLOSED / PUSHED (`7969324`) — `REPORT-EXPORT-1` | C-04 baseline (PDF + CSV, no XLSX), pending client confirmation. Both formats now built for all three reports; native XLSX remains explicitly out of scope |
| 10 | OU/Zone/Sector/CNC/Feeder taxonomy | 🟠 HOLD | C-07 (client mapping; explicitly on hold 2026-09-06) |
| 11 | Production authentication (Entra ID) | 🟠 | C-06 (role-source ownership; reconfirmed 2026-09-06 as Eskom-controlled/external) |
| 12 | MQTT / RTL device communication | 🟠 | External integration dependency (C-05 family; Azure/private-APN infrastructure) |
| 13 | SMS gateway | 🟠 | External integration dependency |
| 14 | Browser support validation | 🟠 | RTL-UX-02 (client support list) |

## 11. Rules for Updating This Ledger

- Update after every completed, paused, or resumed tranche of work.
- Never mark an external integration COMPLETE without end-to-end evidence (producer → persistence → consumer → delivery).
- Record commit SHA for completed milestones when available in repository.
- Preserve historical completed entries — never delete a completed row.
- When client interrupts development, record PAUSED + exact resume point in the queue.
- Repository code and tests override stale chat, documentation, or agent-memory claims.
- Do not classify a client-gated item as merely NOT STARTED — use 🟠 BLOCKED — EXTERNAL.
- The REQ-1B Implementation Gap Matrix (`REQ-1B_Implementation_Gap_Matrix.md`) is the detailed requirement-by-requirement tracker; this ledger is the executive summary and planning control document.
