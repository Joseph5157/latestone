# CLIENT CLARIFICATION PACK

**Project:** Powerplant / Remote Temperature Logger (RTL)
**Purpose:** Concise client-facing decision pack — only unresolved questions that block implementation or production integration.
**Date:** 2026-09-04
**Authoritative register:** `REQ-3I_Clarification_Register.md` (C-01 through C-17)
**Baseline:** `main` @ `c2ab10a`

---

## 1. Decisions Needed Now

These directly unblock near-term development. Ranked by engineering impact.

### C-08 — 18:30 Auto-Disable Ownership

**Decision needed:** Is the daily 18:30 forwarding auto-disable (BR016) an **application responsibility** or an **RTL-Master-side responsibility**?

**Why it matters:** Determines whether we build application scheduler/background-worker infrastructure at all. If the app owns it, we need a new engineering tranche for job scheduling. If the RTL Master owns it, the app side is complete (preference persistence exists).

**What it blocks:** BR016 auto-disable forwarding; message forwarding delivery completeness; scheduler infrastructure engineering.

**Recommended option:** Repository evidence allows no safe recommendation — ownership is a client/operations decision. The app-side forwarding state machine (`message_forwarding_service.py`, OPS-FWD-1) is complete regardless of who owns the timer.

**Other valid options:** Application-owned (background worker), RTL Master-owned (external timer), hybrid (app sets state, Master enforces timing).

**If deferred:** No scheduler infrastructure is built. Forwarding state persistence remains real but the 18:30 transition never fires.

---

### C-05 — Transport / Producer / Channel Contract

**Decision needed:** What channel(s) carry device communication? MQTT, SMS, proprietary API, or another mechanism? What is the producer message format? This encompasses the MQTT broker selection (RTL-INT-07/08), SMS gateway selection (RTL-INT-06), and the legacy SMS workflow replacement.

**Why it matters:** Every physical-device integration depends on this: programming command transport, event producer adapters, message forwarding delivery, real-time power-down forwarding, telemetry reception.

**What it blocks:** Physical RTL programming execution (RTL-PROG-01/02); message forwarding delivery (RTL-FWD-03/04); event producers for battery/power-down/sensor-error; real-time power-down forwarding (BR011); telemetry ingestion at production scale.

**Recommended option:** No safe recommendation from repository evidence — this is a client/architecture decision.

**Other valid options:** MQTT broker (Azure IoT Hub or standalone), direct SMS via gateway, REST API to RTL Master, hybrid (MQTT for events, SMS for commands).

**If deferred:** All device-side integrations remain BLOCKED. App-side persistence (programming requests, forwarding preferences, event ingestion) stays real but nothing is transmitted or received.

---

### C-15 — Maximum Temperature Report Period

**Decision needed:** What is the **reporting period** for the Maximum Temperature report (RTL-REP-03)? The Functional Specification does not define one.

**Why it matters:** REP-03 cannot generate data without a period. This is explicitly CLIENT CLARIFICATION REQUIRED per REQ-1A §16. REPORT-4's CSV precedent does not carry over — REQ-3I §1.2 explicitly rejected dev-default treatment for C-15.

**What it blocks:** Maximum Temperature report implementation and export (RTL-REP-03).

**Recommended option:** No safe recommendation — the reporting period is a client-owned business decision.

**Other valid options:** Last 30 days, last 7 days, rolling window, calendar month, user-selectable.

**If deferred:** REP-03 stays prototype-only. Values are computable from readings, but the reporting window is client-owned.

---

### C-04 — Production Report Format

**Decision needed:** What is the **production report output format**? CSV, PDF, Excel, or another format? Also: are retention/history requirements needed for generated reports?

**Why it matters:** CSV export exists as a labelled development default (REPORT-4, `services/report_export.py:42`). Production sign-off requires client ratification of CSV or correction to another format. Report retention/history is undefined.

**What it blocks:** Production report acceptance (RTL-REP-01/02/03 export); any retention/history build-out.

**Recommended option:** CSV is already implemented and labelled as development default. Client ratification of CSV for production would close the format question with zero code changes. No safe recommendation for retention — client decision required.

**Other valid options:** PDF for formal distribution, Excel for analysis, dual-format (CSV for data, PDF for presentation). Retention: none, per-report, configurable.

**If deferred:** Development export continues as CSV. Production export blocked.

---

### C-07 — Asset Hierarchy Taxonomy Mapping

**Decision needed:** What is the mapping between the client taxonomy (OU / Zone / Sector / CNC / Feeder / Feeder Name) and the development plant model (plant → transformer → device)?

**Why it matters:** Report columns for OU, Zone, Sector, CNC, Feeder exist in `config/reports.py` but are populated as `None` (R2-D2). Both the Installed RTLs and RTL Alarms reports carry these empty columns. Any production deployment needs truthful values.

**What it blocks:** Truthful population of taxonomy report columns in RTL-REP-01 and RTL-REP-02; any production data-migration design.

**Recommended option:** No safe recommendation — the mapping is a client data-architecture decision. The dev hierarchy (plant → transformer → device) is a simplification of the client's real structure.

**Other valid options:** OU = plant, Zone = region grouping, Sector = sub-region, CNC = control center, Feeder = transformer, Feeder Name = transformer name. Or a different mapping entirely.

**If deferred:** Report columns stay as "—" placeholders. Reports remain functionally correct but incomplete for production sign-off.

---

## 2. Production Integration Decisions

These are external integration dependencies — not internal engineering choices. They block production deployment but not necessarily the next development tranche.

### C-06 — Production Identity / Role-Source Ownership

**Decision needed:** Which system owns identity, roles, and passwords in production — Microsoft Entra ID, the application database, or another enterprise service?

**Why it matters:** Prototype authentication (`services/auth_service.py`) uses environment-variable credentials with no credential column. Production deployment requires a real identity provider. The three-role model (Administrator / Technician / General) is enforced end-to-end in the app but the *source* of role assignment is undefined.

**What it blocks:** Production authentication (RTL-SEC-01); credential storage model; notification-preference fields.

**If deferred:** Demo credentials remain the authentication mechanism. App works locally; cannot deploy to production.

---

### C-10 — Notification Acknowledgement / Closure / Escalation Workflow + Retention

**Decision needed:** Do notifications have acknowledgement, closure, escalation, or retention rules? Per-category or global? What is the retention window?

**Why it matters:** Notification Center applies no time window by frozen decision. No expiry, acknowledgement, or retention logic exists anywhere in the repository.

**What it blocks:** Any notification lifecycle state machine, history/retention features.

**Recommended option:** Client decision required — no safe default for lifecycle rules or retention window.

**Other valid options:** Display-only (current state), acknowledge-only, full lifecycle with escalation. Retention: none, configurable per category, fixed window.

**If deferred:** Notifications stay as a current-state display. No history, no workflow.

---

### Production Environment / Network Ownership

**Decision needed:** Who owns the production deployment — Azure subscription, network configuration, private APN, firewall rules?

**Why it matters:** The target architecture (Azure, ExpressRoute, VNets, Kubernetes) is documented in the PAD but explicitly DEFERRED until pilot success is confirmed. No infrastructure code exists. This falls under C-16 (FS TBC items).

**If deferred:** Application stays local-first. Docker Compose for development; no production deployment path.

---

## 3. Business Rules Still Undefined

These are client-owned business rules that the application must not invent.

### High-Temperature Alarm Threshold (C-01 / RTL-EVT-07)

**Decision needed:** What temperature value(s) trigger a high-temperature alarm? Single threshold or warning/critical pair? Per-transformer or global?

**Why it matters:** `services/event_semantics.py` deliberately has no entry for `high_temperature` — structural absence is a decision (SOURCE_AUTHORITY.md: "Absence is not permission"). REQ-1A §7 forbids inventing thresholds.

**If deferred:** `MonitoringCondition` stays permanently UNKNOWN. No temperature alarms are classified or displayed.

---

### Vibration Metric Contract (C-02 / RTL-EVT-08)

**Decision needed:** Full metric contract — 15 questions in `docs/VIBRATION_METRIC_CONTRACT_TBD.md` covering key, unit, precision, aggregation type, axes, cadence, storage, API access, thresholds, and data model.

**Why it matters:** Vibration is structurally absent from event semantics. UI is registry-generic and ready (`config/metrics.py`), but the implementation rule forbids activating vibration without a real contract.

**If deferred:** Vibration stays unactivated. No fake values, no NO_DATA rows, no vibration-specific logic.

---

### Active-List Monitoring Semantics (C-09 / ACT-03)

**Decision needed:** Does the web application need active-list monitoring semantics, or is active-list monitoring purely RTL-Master-side?

**Why it matters:** Application-side active-state transitions are real and tested (INGEST-1, OPS-DEACT-1). But monitoring does not consume `rtl_active_state`. The semantic question cannot be inferred internally.

**If deferred:** BR007 and ACT-03 stay PARTIAL. Monitoring runs over registered devices regardless of active-list status.

---

### Full Anomaly-Detection Rules (C-03 / RTL-PUR-03)

**Decision needed:** What is the complete set of anomaly-detection rules beyond comms/freshness? Per anomaly type?

**Why it matters:** Only freshness/comms detection exists. No invented rules exist anywhere in the repository.

**If deferred:** Anomaly detection limited to data freshness and communications status.

---

### Browser Support List (C-12 / RTL-UX-02)

**Decision needed:** Which browsers and versions must be supported?

**Why it matters:** No compatibility testing has been performed. Desktop/laptop is the primary target per UI_SPEC.md, but the approved list is undefined.

**If deferred:** Development continues targeting modern evergreen browsers. No formal compatibility sign-off.

---

### Unregistered UID Operational Owner (C-13 / EVT-09)

**Decision needed:** Who owns unregistered-UID remediation in production — administrators, operations, engineering, or another group?

**Why it matters:** Admin-only quarantine view is a development default (EVT-D5). Production ownership determines whether the surface widens beyond administrators.

**If deferred:** Admin-only default stands. No widening of the invalid_uid surface.

---

### Eskom Security Standards Compliance (C-17 / RTL-SEC-10)

**Decision needed:** Which Eskom security standards apply, and what control evidence is required?

**Why it matters:** Standards named in the PAD are not mapped to verifiable controls in the repository. Production sign-off requires this mapping.

**If deferred:** No compliance evidence pack. Blocks production security sign-off only.

---

### Transformer Name-vs-Code Presentation (C-14 / RTL-PROG-04/05)

**Decision needed:** In the programming context, should the transformer be displayed by name or by code?

**Why it matters:** Snapshot persistence is real; presentation semantics are unconfirmed.

**If deferred:** Current display remains. Low impact.

---

### Remaining FS "TBC" Items (C-16)

**Decision needed:** Client completion of Functional Specification placeholders — security requirements, dependencies, configuration prerequisites, software/module interface details.

**Why it matters:** Completeness of the requirement baseline itself.

**If deferred:** No direct engineering impact. Baseline remains incomplete.

---

### Performance / Transaction Volume (C-11)

**Decision needed:** Real volumes, cadence distribution, latency targets for event ingestion and reading storage.

**Why it matters:** Ingestion-scale design, event-table indexing strategy, freshness-threshold calibration against real cadence.

**If deferred:** No direct impact until transport work begins. Then rises with C-05.

---

## 4. Recommended Client Meeting Order

Ranked by highest development-unblocking value:

| # | Question | ID | Unblocks |
|---|---|---|---|
| 1 | 18:30 auto-disable ownership (app vs RTL Master) | C-08 | Scheduler infrastructure; message forwarding completeness |
| 2 | Transport / producer / channel contract | C-05 | Physical programming, event producers, forwarding delivery, all device integration |
| 3 | Maximum Temperature report period | C-15 | REP-03 implementation and export |
| 4 | Report production format (ratify CSV or specify alternative) | C-04 | Production report sign-off (zero code changes if CSV ratified) |
| 5 | OU/Zone/Sector/CNC/Feeder taxonomy mapping | C-07 | Truthful report columns |
| 6 | High-temperature alarm threshold | C-01 | Temperature alarm events; MonitoringCondition |
| 7 | Active-list monitoring semantics | C-09 | BR007/ACT-03 closure |
| 8 | Vibration metric contract (15 questions) | C-02 | Vibration activation |
| 9 | Production identity source (Entra ID vs DB) | C-06 | Production authentication |
| 10 | Notification lifecycle rules | C-10 | Notification history/acknowledgement |

**Minimum to unblock the next engineering tranche:** Items 1–2. With C-08 and C-05 answered, either the scheduler tranche or the transport adapter tranche can begin.

**Minimum to close all PARTIAL items:** Items 1–9. Each closed item converts a 🟠 BLOCKED or 🟡 PARTIAL to ✅ COMPLETE or 🟢 IMPLEMENTED.

---

## 5. Development We Can Continue While Waiting

Only genuinely dependency-free work. Do not list blocked work as executable.

### Product Feature Work

| # | Task | Rationale |
|---|---|---|
| 1 | Frontend polish (visual refinements, responsive improvements, accessibility, component cleanup) | No backend dependency. Per RTL_CLIENT_REVIEW_GATE.md §8 GO gate. |

### Technical Hardening / Maintenance

| # | Task | Rationale |
|---|---|---|
| 2 | Production cookie/deployment hardening | Non-blocking follow-up from AUTH-HARDEN-1: `SESSION_COOKIE_SECURE`, explicit `SameSite`, HTTPS enforcement, production `FLASK_SECRET_KEY`. Can proceed with information we control. |
| 3 | Test coverage expansion | Pure-logic tests can grow without client decisions. Existing 2669 tests provide strong baseline. Does not advance any blocked client requirement. |
| 4 | Documentation and context record maintenance | ADR backfill, CURRENT_STATE refresh, ledger updates. No code changes. |
| 5 | Internal code quality (dead code removal, type hint completion, docstring improvements) | No functional changes; improves maintainability for future tranches. |

**Note:** Several client-gated features are currently blocked:
- **C-08** unlocks scheduler infrastructure and 18:30 auto-disable work.
- **C-05** unlocks physical device integration — RTL programming execution, message forwarding delivery, event transport, and all producer-dependent work.
- **C-15** independently unlocks Maximum Temperature Report implementation and export.
- **C-04** independently unlocks production report-format acceptance (zero code changes if CSV ratified).
- **C-07** independently unlocks truthful taxonomy population in report columns.
- Other client-gated features remain blocked by their own clarification IDs (C-01, C-02, C-09, C-10, C-06, etc.).
