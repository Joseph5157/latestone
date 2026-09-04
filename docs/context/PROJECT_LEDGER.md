# POWER / RTL PROJECT LEDGER

## 1. Authoritative Checkpoint

- **Branch:** `main`
- **SHA:** `669fffb` — "fix(auth): harden production session configuration" (committed HEAD, not yet pushed)
- **Last updated:** 2026-09-04
- **Working tree expectation:** `debug.log` (untracked) only. AUTH-PROD-HARDEN-1 committed.
- **Test baseline:** 2690 passed (non-db, includes 21 new AUTH-PROD-HARDEN-1 tests), 510 deselected; 3200 passed full suite
- **Source of truth:** `docs/context/SOURCE_AUTHORITY.md` — code outranks prose

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
| **RTL Programming** | BR005/RTL-PROG-01–10: Program RTL | 🟠 BLOCKED — EXTERNAL | Application request persistence exists: atomic insert + audit (`rtl_programming_service.py`, OPS-PROG-1); authorization enforced; Master MSISDN captured; confirmation honest ("request recorded ≠ programmed") | Physical command transport to RTL device (C-05); RTL Master MSISDN source; device-side programming confirmation | 🟠 BLOCKED — C-05 (transport/device protocol) |
| **Message forwarding** | BR003/BR004/RTL-FWD-01–07 | 🟠 BLOCKED — EXTERNAL | Per-user forwarding preference persisted with atomic mutation + audit (`message_forwarding_service.py`, OPS-FWD-1); drawer prefilled from DB; feedback truthful | SMS/message transport (C-05 family); 18:30 auto-disable scheduler (C-08); recipient eligibility rules (FWD-D1 vs FWD-03); actual message delivery | 🟠 BLOCKED — C-05 (transport) + C-08 (scheduler ownership) |
| **18:30 auto-disable** | BR016: Auto-disable forwarding at 18:30 daily | 🟠 BLOCKED — EXTERNAL | None implemented | No scheduler/background worker; app vs RTL Master ownership unconfirmed (C-08); needs job infrastructure | 🟠 BLOCKED — C-08 (ownership decision) |
| **RTL active lifecycle** | BR010/BR012/RTL-ACT-01–06 | 🟡 PARTIAL | Startup event ingestion persists + activates `rtl_active_state` (INGEST-1, ACT-D1–D7); deactivation persists with audit (OPS-DEACT-1); active-list state separate from admin status (RTL-ACT-05) | Physical RTL device producer; Master-side list is its own system; monitoring semantics for active-list (ACT-03 client question) | 🟠 BLOCKED — ACT-03 (active-list semantics) |
| **Notifications/alarms** | BR008–BR012/RTL-EVT-01–09 | 🟡 PARTIAL | Notification Center derives BR008 >24h from readings; persisted device events (battery_low, power_down, sensor_error, startup, check-in, invalid_uid) render via shared `event_semantics.py` layer; categories scoped per device scope | Real device event producers (MQTT/C-05); delivery to users (SMS/email); notification history/acknowledgement; high-temperature threshold (C-15); vibration contract (C-16) | 🟠 BLOCKED — C-05 + C-15 + C-16 |
| **RTL Alarms report** | RTL-REP-01: RTL Alarms (30 Days) | 🟡 PARTIAL | Data-backed from persisted `device_events` via `rtl_alarms_30d_rows()` (REPORT-3); scope-filtered; zero rows is legitimate empty report; CSV export working | Production delivery format (C-10); OU/Zone/Sector/CNC/Feeder taxonomy mapping (C-07) | 🟠 BLOCKED — C-10 + C-07 |
| **Installed RTL report** | RTL-REP-02: Installed RTLs | 🟡 PARTIAL | Data-backed from readings via `installed_rtls_rows()` (REPORT-2); OU/Zone/Sector/CNC/Feeder stay None per R2-D2; CSV export working | Production delivery format (C-10); taxonomy mapping (C-07) | 🟠 BLOCKED — C-10 + C-07 |
| **Max Temperature report** | RTL-REP-03: Maximum Temperature | 🟠 BLOCKED — EXTERNAL | Report definition confirmed in `config/reports.py`; UI renders "prototype only" panel | Reporting period not defined by spec (C-15); data population; export | 🟠 BLOCKED — C-15 (reporting period) |
| **Export/delivery** | RTL-PUR-05 | 🟡 PARTIAL | CSV export pipeline exists for Installed RTLs and RTL Alarms (`report_export.py`); authorization enforced (`require_capability(EXPORT_DATA)`); honest format label ("CSV is development default") | Production format confirmation (C-10: CSV vs PDF); file delivery mechanism | 🟠 BLOCKED — C-10 (format confirmation) |
| **Entra ID** | RTL-SEC-01 | 🟠 BLOCKED — EXTERNAL | Zero implementation; login test bans SSO branding; prototype auth via env-var comparison with no credential column | Full Entra ID integration; production credential source | 🟠 BLOCKED — external integration dependency |
| **MQTT / RTL device comm** | RTL-INT-07/08 | 🟠 BLOCKED — EXTERNAL | No implementation; `device_events.source` provides forward-compatible hook; `rtl_programming_requests` has persistence hooks | MQTT broker integration; device command protocol; producer adapters | 🟠 BLOCKED — external integration dependency |
| **SMS gateway** | RTL-INT-06 | 🟠 BLOCKED — EXTERNAL | Zero implementation | SMS gateway configuration; delivery pipeline | 🟠 BLOCKED — external integration dependency |
| **High-temperature threshold** | RTL-EVT-07, RTL-PUR-03 | 🟠 BLOCKED — EXTERNAL | Structurally absent from event semantics per REQ-1A; `MonitoringCondition` permanently UNKNOWN; no threshold logic exists anywhere | Client must supply threshold value (C-15) | 🟠 BLOCKED — C-15 (client must not be invented) |
| **Vibration metric** | RTL-PUR-08, RTL-EVT-08 | 🟠 BLOCKED — EXTERNAL | Structurally absent from event semantics; `docs/VIBRATION_METRIC_CONTRACT_TBD.md` has 16 open questions | Client must supply full metric contract (C-16) | 🟠 BLOCKED — C-16 (16 open questions) |
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
| Integration | 🟠 BLOCKED — EXTERNAL | No event producers (C-05); no delivery channel; high-temperature/vibration thresholds client-gated (C-15, C-16) |
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

## 7. Client Demo / Priority Overrides

- **Client delivery branches**: `client-release` and `client-demo-1` branches exist for curated client-facing snapshots (see `docs/CLIENT_DELIVERY.md`). Client sees login-only subset; full app stays on `main`.
- **Client Review Gate (Phase 9)**: The frontend phase cycle explicitly paused at `docs/RTL_CLIENT_REVIEW_GATE.md` with the instruction: "Do not start new implementation until those decisions are provided."
- No evidence of unplanned demo/UI interruptions to active requirement work found in repository context.

## 8. External Dependencies / Client Input Required

| Dependency | Blocks | Status | Reference |
|---|---|---|---|
| C-05: MQTT / RTL device transport protocol | Physical programming, event producers, active-list contact, message forwarding delivery | 🟠 BLOCKED | No protocol defined; `device_events.source` is forward-compatible hook |
| C-06: Production role-source ownership (Entra ID vs DB) | Production authentication | 🟠 BLOCKED | Zero Entra ID implementation; prototype auth only |
| C-07: Asset hierarchy taxonomy mapping (OU/Zone/Sector/CNC/Feeder) | Report columns; Installed RTLs and RTL Alarms reports | 🟠 BLOCKED | Mapping between client taxonomy and dev plant model undefined |
| C-08: 18:30 scheduler ownership (app vs RTL Master) | BR016 auto-disable forwarding | 🟠 BLOCKED | No background worker infrastructure; ownership unconfirmed |
| C-10: Report delivery format (CSV vs PDF) | Production report export | 🟠 BLOCKED | Pipeline ready; format is client decision |
| C-15: High-temperature alarm threshold + Max Temperature reporting period | RTL-EVT-07, RTL-PUR-03, RTL-REP-03 | 🟠 BLOCKED | Structurally absent from event semantics; must not be invented |
| C-16: Vibration metric contract (16 questions) | RTL-PUR-08, RTL-EVT-08 | 🟠 BLOCKED | Structurally absent; 16 open questions in `docs/VIBRATION_METRIC_CONTRACT_TBD.md` |
| Notification delivery channel & recipient rules | BR008–BR012 delivery | 🟠 BLOCKED | Display-only by frozen decision |
| Active-list monitoring semantics (ACT-03) | BR007, RTL-ACT-03 | 🟠 BLOCKED | Does web app need active-list semantics or is that RTL-Master-only? |
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

## 10. Resume Queue

### Ready Now

Work that can be implemented without unresolved client/external decisions:

| # | Task | Status | Rationale |
|---|---|---|---|
| 1 | **CLIENT-CLARIFICATION-PACK-1** | ⚪ NOT STARTED | A concise document collecting all client decisions needed before blocked work can resume: C-05 (transport), C-06 (auth source), C-07 (taxonomy), C-08 (scheduler ownership), C-10 (report format), C-15 (thresholds/period), C-16 (vibration), ACT-03 (active-list semantics). This is the true critical path — unblocks most blocked items. |
| 2 | Production cookie/deployment hardening | 🟢 APP-SIDE COMPLETE (AUTH-PROD-HARDEN-1, committed) | `APP_ENV` setting added; `FLASK_SECRET_KEY` fails closed under `APP_ENV=production`; `SESSION_COOKIE_SECURE`/`HTTPONLY`/`SAMESITE` explicit; HTTPS enforcement documented as Railway's edge, not app middleware. Real Railway service still needs `APP_ENV`/`FLASK_SECRET_KEY` set to activate it. |

### Blocked / Waiting for Client or Integration

| # | Task | Blocked By | Dependency |
|---|---|---|---|
| 1 | Physical RTL programming delivery | 🟠 | C-05 (MQTT/transport protocol) |
| 2 | Message forwarding delivery | 🟠 | C-05 (transport) + C-08 (18:30 scheduler ownership) |
| 3 | 18:30 auto-disable forwarding | 🟠 | C-08 (ownership decision: app vs RTL Master) |
| 4 | RTL active-list monitoring semantics | 🟠 | ACT-03 (client question: app or Master-side?) |
| 5 | Alarm pipeline — event producers | 🟠 | C-05 (MQTT/device communication) |
| 6 | Notification delivery (SMS/email) | 🟠 | C-05 (transport) + delivery channel/recipient rules |
| 7 | High-temperature threshold | 🟠 | C-15 (client must supply; must not be invented) |
| 8 | Vibration metric activation | 🟠 | C-16 (16 open questions in TBD doc) |
| 9 | Maximum Temperature report | 🟠 | C-15 (reporting period undefined by spec) |
| 10 | Report production format (CSV vs PDF) | 🟠 | C-10 (format confirmation) |
| 11 | OU/Zone/Sector/CNC/Feeder taxonomy | 🟠 | C-07 (client mapping) |
| 12 | Production authentication (Entra ID) | 🟠 | C-06 (role-source ownership) |
| 13 | MQTT / RTL device communication | 🟠 | External integration dependency |
| 14 | SMS gateway | 🟠 | External integration dependency |
| 15 | Browser support validation | 🟠 | RTL-UX-02 (client support list) |

## 11. Rules for Updating This Ledger

- Update after every completed, paused, or resumed tranche of work.
- Never mark an external integration COMPLETE without end-to-end evidence (producer → persistence → consumer → delivery).
- Record commit SHA for completed milestones when available in repository.
- Preserve historical completed entries — never delete a completed row.
- When client interrupts development, record PAUSED + exact resume point in the queue.
- Repository code and tests override stale chat, documentation, or agent-memory claims.
- Do not classify a client-gated item as merely NOT STARTED — use 🟠 BLOCKED — EXTERNAL.
- The REQ-1B Implementation Gap Matrix (`REQ-1B_Implementation_Gap_Matrix.md`) is the detailed requirement-by-requirement tracker; this ledger is the executive summary and planning control document.
