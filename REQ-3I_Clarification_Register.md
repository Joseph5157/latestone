# REQ-3I — Authoritative Client Clarification Register

**Project:** Powerplant / Remote Temperature Logger (RTL)
**Purpose:** Consolidate every open clarification / client dependency into a single authoritative register, correct stale conclusions from the exploratory REQ-3 inspection pass, and rank the remaining engineering gates. Documentation-only; no application code is modified by this checkpoint.
**Status:** Baseline established
**Repository baseline:** `main` @ `2248afd7aae8da989f4b1b3ba24d18718b23caaf` ("feat(reports): add development-default CSV export")
**Inputs:**
1. `REQ-1A_Client_Requirement_Inventory.md` §16 (Client Clarification Register)
2. `REQ-1B_Implementation_Gap_Matrix.md` §8, §9, §16, §17
3. `docs/VIBRATION_METRIC_CONTRACT_TBD.md`
4. Direct repository inspection at `2248afd` (including the REPORT-4 export tranche)

**Method:** Every status and evidence citation below was verified by direct repository inspection on the baseline commit. No requirement was invented; no client-gated behaviour was assumed. Where this register conflicts with the exploratory REQ-3 pass or older summaries elsewhere, **this register is authoritative**.

---

## 0. Priority scheme

The label **"blocks engineering now"** means *blocks a candidate tranche we might actually start next* — not that the entire project cannot proceed. Three priority levels are used:

| Priority | Meaning |
|---|---|
| **GATE — leading blocker** | Directly determines whether an identified candidate engineering tranche can begin |
| **Important but deferrable** | Blocks a defined future work item, but that item is not the next candidate tranche |
| **Informational** | Needed for production readiness/rollout, not for any current engineering decision |

---

## 1. Completed decisions recorded here (not to be reopened)

### 1.1 REPORT-4 — development-default CSV export (COMPLETE at `2248afd`)

* Export implemented for exactly two reports: `EXPORTABLE_REPORTS = ("installed_rtls", "rtl_alarms_30d")` (`services/report_export.py:49`) — i.e. **REP-01 (RTL Alarms 30 Days) and REP-02 (Installed RTLs) only**.
* CSV was established as a **specifically reviewed, labelled development default** (`EXPORT_FORMAT_LABEL`, `services/report_export.py:42`; tests in `tests/test_report_export.py`, `tests/test_report_export_db.py`).
* **Recent-report history was deliberately left untouched**: the recent-reports table remains the explicitly-marked in-memory prototype store (`callbacks/report_center.py:39–47`, `_mock_recent_reports`). This was a REPORT-4 scope decision and must not be reopened under register housekeeping.
* **REP-03 (Maximum Temperature) is excluded from export and remains unavailable**, pending the client's reporting-period answer (item C-15 below).

### 1.2 Precedent rule

REPORT-4's CSV default was a reviewed, bounded decision for report delivery format. It does **not** establish a general policy of inventing development defaults for unrelated client-gated requirements. In particular, it must **not** be extended to the REP-03 reporting period or to any threshold/workflow question. Each proposed default requires its own explicit review gate.

---

## 2. Corrections applied against the exploratory REQ-3 pass

| Item | Correction |
|---|---|
| Next-tranche proposal "Export completion (REPORT-4)" | **Rejected.** REPORT-4 is complete and pushed; export is intentionally limited to REP-01/REP-02; recent-report history was deliberately untouched. Nothing may be reopened. |
| Proposed dev-default period for REP-03 | **Rejected.** REP-03's period is an explicit client clarification (REQ-1A §16). Per §1.2 above, the CSV precedent does not carry over. |
| C-04 classification | Reclassified as **engineering development path resolved / production ratification still open**. Not fully closed. |
| C-13 classification | **Not closed internally.** Admin-only invalid-UID ownership remains a deliberate development default; production ownership is a genuine client/operations decision. Kept open at informational priority. |
| C-08, C-05 priority | Elevated to the two **leading engineering blockers** (see §5). |

---

## 3. The register

Each entry: requirement/reference IDs, what implementation is blocked, existing evidence, the exact missing client answer, priority, and whether it can be closed internally from existing evidence (**none can be fully closed internally except where noted as a reclassification**).

### C-01 — High-temperature alarm threshold
* **References:** RTL-EVT-07, RTL-PUR-03
* **Blocks:** Adding `high_temperature` to event semantics (`services/event_semantics.py` structurally omits it); any temperature anomaly/alarm rule; `MonitoringCondition` remains permanently UNKNOWN (EVT-D4).
* **Evidence:** No confirmed threshold exists anywhere in the repo; REQ-1A §7 forbids inventing one.
* **Missing answer:** Confirmed threshold value(s) and severity model.
* **Priority:** Important but deferrable (no real producer exists yet).
* **Internally closable:** No.

### C-02 — Vibration metric contract + anomaly thresholds
* **References:** RTL-PUR-08, RTL-EVT-08
* **Blocks:** Any vibration metric activation, storage model, event mapping, UI exposure.
* **Evidence:** `docs/VIBRATION_METRIC_CONTRACT_TBD.md` enumerates all 14 required contract answers; UI is registry-generic and ready (`config/metrics.py` pattern); implementation rule forbids activating vibration without a real contract.
* **Missing answer:** All 14 contract questions (key, unit, aggregation type, axes, cadence, storage, etc.).
* **Priority:** Important but deferrable.
* **Internally closable:** No.

### C-03 — Full anomaly-detection rules
* **References:** RTL-PUR-03
* **Blocks:** Anomaly detection beyond comms/freshness.
* **Evidence:** Only freshness/comms detection exists; no invented rules anywhere.
* **Missing answer:** Rule set per anomaly type.
* **Priority:** Deferrable.
* **Internally closable:** No.

### C-04 — Production report format + retention/history
* **References:** RTL-PUR-05, RTL-REP-01…03 (export), RTL-ROLE-GEN-03
* **Blocks:** ~~Development export~~ (RESOLVED by REPORT-4); **production sign-off** of format; retention/history requirements.
* **Evidence:** REPORT-4 shipped labelled development-default CSV for REP-01/REP-02 at `2248afd` (§1.1).
* **Missing answer:** Client ratification of CSV (or correction to another format); any production retention/history requirement for reports.
* **Priority:** Important but deferrable — no longer blocks development export; blocks production acceptance.
* **Disposition:** Reclassified per §2. Development path resolved; production clarification remains open.

### C-05 — Modern replacement for legacy SMS workflows / transport & producer contract
* **References:** RTL-PUR-06 execution path, RTL-FWD-03/04/15 delivery, BR011 real-time forwarding, BR006 telemetry, transport selection for all event producers
* **Blocks:** The major remaining physical-device and delivery integrations: programming command transport, forwarding/SMS delivery, real producer/ingestion evidence, real-time power-down forwarding.
* **Evidence:** Requests/preferences/events persist honestly; nothing is transmitted or received (`rtl_programming_service`, `message_forwarding_service`, `device_event_service` — persistence only).
* **Missing answer:** Chosen channel(s) and producer/message-format evidence for device communication.
* **Priority:** **GATE — leading blocker #2.**
* **Internally closable:** No.

### C-06 — Production identity / role-source ownership
* **References:** RTL-SEC-01, users-model evolution (Password, Notification Type fields), BR001 production form
* **Blocks:** Entra ID integration, credential storage model, notification-preference fields.
* **Evidence:** Prototype env-var auth with no credential column, deliberately (`services/auth_service.py`).
* **Missing answer:** Which system owns identity/roles/passwords in production (Entra ID vs app DB vs enterprise service).
* **Priority:** Important but deferrable.
* **Internally closable:** No.

### C-07 — Authoritative production database mapping incl. OU→plant taxonomy
* **References:** REQ-1A §8.3 asset hierarchy; OU/Zone/Sector/CNC/Feeder columns of RTL-REP-01/02
* **Blocks:** Truthful population of taxonomy report columns (currently honest `None` per R2-D2); any production data-migration design.
* **Evidence:** Dev hierarchy is plant → transformer → device only; taxonomy literals exist solely as report headers (`config/reports.py`).
* **Missing answer:** Mapping between client taxonomy (OU/Zone/Sector/CNC/Feeder) and the dev plant model.
* **Priority:** Important but deferrable.
* **Internally closable:** No.

### C-08 — BR016 / RTL-FWD-06 auto-disable ownership
* **References:** BR016, RTL-FWD-06
* **Blocks:** Whether to build application scheduler/background-worker infrastructure at all (the previously identified candidate tranche #2).
* **Evidence:** No scheduler exists in the app; documented not-implemented; ownership never confirmed.
* **Missing answer:** Is the 18:30 daily forwarding auto-disable an application responsibility or an RTL-Master-side responsibility?
* **Priority:** **GATE — leading blocker #1.**
* **Internally closable:** No.

### C-09 — Active-list monitoring semantics
* **References:** RTL-ACT-03, BR007
* **Blocks:** Wiring `rtl_active_state` into monitoring/freshness semantics; closure of BR007/ACT-03 statuses beyond PARTIAL.
* **Evidence:** Application-side active-state transitions are real and tested (activation/deactivation projections); monitoring does not consume them; the semantic question cannot be inferred internally.
* **Missing answer:** Does the web application monitor the active list, or is active-list monitoring purely RTL-Master-side?
* **Priority:** Important but deferrable.
* **Internally closable:** No.

### C-10 — Notification acknowledgement/closure/escalation workflow + retention
* **References:** Notification Center evolution (display-only by frozen decision)
* **Blocks:** Any notification lifecycle state machine, history/retention features.
* **Evidence:** No invented expiry, acknowledgement, or retention logic anywhere; Notification Center applies no time window by frozen decision.
* **Missing answer:** Workflow definition per notification category + retention window.
* **Priority:** Deferrable.
* **Internally closable:** No.

### C-11 — Performance / transaction volume / reading frequency
* **References:** FS explicit TBC items (REQ-1A §16)
* **Blocks:** Ingestion-scale design, event-table indexing strategy, freshness-threshold calibration against real cadence.
* **Evidence:** ~30-minute reading cadence known from screenshots only; volumes stated uncertainly by the client documents themselves.
* **Missing answer:** Real volumes, cadence distribution, latency targets.
* **Priority:** Informational until transport work begins (then rises with C-05).
* **Internally closable:** No.

### C-12 — Browser support list
* **References:** RTL-UX-02
* **Blocks:** Browser-compatibility testing scope.
* **Evidence:** No compatibility constraints or testing found in repo.
* **Missing answer:** Approved browsers/versions.
* **Priority:** Informational.
* **Internally closable:** No.

### C-13 — Operational owner for invalid/unregistered UIDs
* **References:** RTL-EVT-09
* **Blocks:** Widening the `invalid_uid` surface beyond administrators; production remediation workflow.
* **Evidence:** Deliberate development default implemented and tested — admin-only quarantine view with stable per-UID keys, no href, no auto-registration (EVT-D5).
* **Missing answer:** Who owns unregistered-UID remediation in production (administrators, operations, engineering, other?).
* **Priority:** Informational.
* **Disposition:** **Kept open** per §2. The admin-only surface is a development default, not a client-confirmed production decision. Not closed internally.

### C-14 — Transformer name-vs-code presentation (programming context)
* **References:** RTL-PROG-04/05
* **Blocks:** Programming display semantics refinement.
* **Evidence:** Snapshot persistence real (`transformer_id` snapshotted per request); `transformer_code VARCHAR(10)` bound-checked; presentation not confirmed.
* **Missing answer:** Name vs code in the programming context.
* **Priority:** Informational.
* **Internally closable:** No.

### C-15 — Maximum Temperature report period
* **References:** RTL-REP-03
* **Blocks:** Entire REP-03 implementation (generation and export).
* **Evidence:** Contract mirrored (`max_temperature`); period "not defined by spec" honestly surfaced in UI; max-temp values computable from readings today, but the reporting window is client-owned.
* **Missing answer:** The reporting period for the Maximum Temperature report.
* **Priority:** Important but deferrable (ranks behind C-04 ratification and C-07 in rollout order).
* **Disposition:** Explicitly **rejected for dev-default treatment** per §1.2. Remains gated.

### C-16 — Remaining Functional Specification "TBC" items
* **References:** FS security requirements, dependencies, configuration prerequisites/proposed changes, software/module interface details (REQ-1A §16)
* **Blocks:** Nothing directly; completeness of the requirement baseline itself.
* **Evidence:** Recorded verbatim in REQ-1A §16.
* **Missing answer:** Client completion of FS placeholders.
* **Priority:** Informational.
* **Internally closable:** No.

### C-17 — Eskom security standards compliance mapping
* **References:** RTL-SEC-10
* **Blocks:** Compliance evidence pack; production security sign-off.
* **Evidence:** Standards named in PAD, unmapped to verifiable controls in repo.
* **Missing answer:** Which standards apply and required control evidence.
* **Priority:** Informational.
* **Internally closable:** No.

---

## 4. Register integrity rules

1. **No client-gated requirement may be converted into a guessed implementation.** Items marked gated stay gated until the client answer is recorded in this register with its evidence.
2. **Defaults are per-decision.** A labelled development default (e.g., REPORT-4 CSV) applies only to the decision it was reviewed for. It creates no precedent for other gated items (§1.2).
3. **Completed work is not reopened by register maintenance.** REPORT-4's scope decisions (REP-01/REP-02 only; recent-report history untouched; REP-03 excluded) stand unless the client changes them.
4. Statuses in `REQ-1B_Implementation_Gap_Matrix.md` remain valid; where REQ-1B §16's impact map differs from this register (C-04 reclassification), this register supersedes.

---

## 5. Engineering-gate ranking (post-REPORT-4)

Ranked by impact on candidate tranches we might actually start next:

1. **C-08 — BR016/FWD-06 ownership** — directly gates scheduler-infrastructure engineering.
2. **C-05 — Transport/producer/channel contract** — gates physical programming execution, forwarding delivery, real-time power-down forwarding, and all producer-dependent work.
3. **C-04 — Production report-format ratification** — no longer blocks development export (REPORT-4); blocks production sign-off and any retention/history build-out.
4. **C-07 — Asset taxonomy mapping** — blocks truthful population of OU/Zone/Sector/CNC/Feeder fields.
5. **C-15 — REP-03 period** — blocks Maximum Temperature implementation.
6. **C-09 — Active-list monitoring semantics** — blocks BR007/ACT-03 closure.
7. C-10, C-01, C-02, C-03, C-06, C-12, C-17, C-11, C-13, C-14, C-16 follow according to rollout needs.

With both leading gates (C-08, C-05) unresolved, there is currently **no unblocked candidate application-engineering tranche**; remaining work is either documentation/governance or awaits client answers.

---

## 6. REQ-3I completion rule

This register is complete when every open clarification from REQ-1A §16 and REQ-1B has an entry with references, blocked items, cited evidence, the exact missing answer, a priority under the §0 scheme, and an internal-closability disposition — and when all corrections listed in §2 are reflected. No application code is modified by this checkpoint.

**REQ-3I Status: BASELINE ESTABLISHED at `2248afd`**
