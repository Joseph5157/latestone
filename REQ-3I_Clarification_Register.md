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

**Amendment (2026-09-06):** Development baselines recorded for C-08, C-15,
C-04 (format), C-01 (framework), and C-02 (framework) — see each entry
below and the updated §5 ranking. **These are internal decisions made by
the development team/user so implementation can proceed. They are NOT
confirmed Eskom/client answers unless repository evidence proves
otherwise**, and formal client confirmation remains pending for all five.
C-07 remains genuinely on hold pending the client (its status is unchanged,
not a new baseline). C-05, C-06, and the Azure/private-APN/Entra ID family
remain Eskom-controlled/external, reconfirmed as still unanswered. This
amendment is documentation-only; no application code changed.

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
* **Development baseline (2026-09-06, pending client confirmation):** Warning/critical temperature thresholds must be administrator-configurable — never permanently hardcoded — and every threshold change must be audited. This is an internal development-team/user decision so design can proceed; it is not a confirmed Eskom/client answer. The actual Eskom-specific threshold values remain unconfirmed.
* **Missing answer:** The confirmed numeric threshold value(s) and severity model, and formal client confirmation of the configurable/audited shape itself.
* **Priority:** Important but deferrable (no real producer exists yet; values still unconfirmed).
* **Internally closable:** No — a development baseline only, not a client answer. The configurability/audit requirement may inform design; do not implement threshold evaluation logic or pick default values.

### C-02 — Vibration metric contract + anomaly thresholds
* **References:** RTL-PUR-08, RTL-EVT-08
* **Blocks:** Any vibration metric activation, storage model, event mapping, UI exposure.
* **Evidence:** `docs/VIBRATION_METRIC_CONTRACT_TBD.md` enumerates all 15 required contract answers (corrected 2026-09-07 by direct count — a prior 2026-09-06 correction had already fixed an earlier "16" to "14", which was itself a miscount); UI is registry-generic and ready (`config/metrics.py` pattern); implementation rule forbids activating vibration without a real contract.
* **Development baseline (2026-09-06, pending client confirmation):** Vibration must be built as a configurable framework, not hardcoded. This is an internal development-team/user decision so design can proceed; it is not a confirmed Eskom/client answer. Production sensor semantics and values remain unconfirmed.
* **Missing answer:** All 15 contract questions (key, unit, aggregation type, axes, cadence, storage, etc.) remain open, and formal client confirmation of the configurable-framework baseline itself.
* **Priority:** Important but deferrable.
* **Internally closable:** No — a development baseline only (framework shape), not a client answer.

### C-03 — Full anomaly-detection rules
* **References:** RTL-PUR-03
* **Blocks:** Anomaly detection beyond comms/freshness.
* **Evidence:** Only freshness/comms detection exists; no invented rules anywhere.
* **Missing answer:** Rule set per anomaly type.
* **Priority:** Deferrable.
* **Internally closable:** No.

### C-04 — Production report format + retention/history
* **References:** RTL-PUR-05, RTL-REP-01…03 (export), RTL-ROLE-GEN-03
* **Blocks:** ~~Development export~~ (RESOLVED by REPORT-4); production format (baseline set, see below — client confirmation still pending); retention/history requirements.
* **Evidence:** REPORT-4 shipped labelled development-default CSV for REP-01/REP-02 at `2248afd` (§1.1).
* **Development baseline (2026-09-06, pending client confirmation):** Production report format is PDF + CSV. Native XLSX is not required at this time. This is an internal development-team/user decision so implementation can proceed; it is not a confirmed Eskom/client answer.
* **Missing answer:** Formal client ratification of PDF + CSV (or correction to another format); any production retention/history requirement for reports remains open.
* **Priority:** Important but deferrable — a working baseline now exists for format; still blocks retention/history build-out and formal client sign-off.
* **Disposition:** **Development baseline set (format), 2026-09-06 — pending client confirmation.** PDF generation may be built alongside the existing CSV export against this baseline; native XLSX is out of scope for now. Retention/history remains open.

### C-05 — Modern replacement for legacy SMS workflows / transport & producer contract
* **References:** RTL-PUR-06 execution path, RTL-FWD-03/04/15 delivery, BR011 real-time forwarding, BR006 telemetry, transport selection for all event producers
* **Blocks:** The major remaining physical-device and delivery integrations: programming command transport, forwarding/SMS delivery, real producer/ingestion evidence, real-time power-down forwarding.
* **Evidence:** Requests/preferences/events persist honestly; nothing is transmitted or received (`rtl_programming_service`, `message_forwarding_service`, `device_event_service` — persistence only).
* **Client reconfirmation (2026-09-06):** Remains Eskom-controlled/external. Not answered; no contract supplied.
* **Missing answer:** Chosen channel(s) and producer/message-format evidence for device communication.
* **Priority:** **GATE — sole remaining leading blocker as of 2026-09-06** (C-08 resolved; see §5).
* **Internally closable:** No.

### C-06 — Production identity / role-source ownership
* **References:** RTL-SEC-01, users-model evolution (Password, Notification Type fields), BR001 production form
* **Blocks:** Entra ID integration, credential storage model, notification-preference fields.
* **Evidence:** Prototype env-var auth with no credential column, deliberately (`services/auth_service.py`).
* **Client reconfirmation (2026-09-06):** Remains Eskom-controlled/external (Entra ID), along with the Azure/private-APN infrastructure family. Not answered; no contract supplied.
* **Missing answer:** Which system owns identity/roles/passwords in production (Entra ID vs app DB vs enterprise service).
* **Priority:** Important but deferrable.
* **Internally closable:** No.

### C-07 — Authoritative production database mapping incl. OU→plant taxonomy
* **References:** REQ-1A §8.3 asset hierarchy; OU/Zone/Sector/CNC/Feeder columns of RTL-REP-01/02
* **Blocks:** Truthful population of taxonomy report columns (currently honest `None` per R2-D2); any production data-migration design.
* **Evidence:** Dev hierarchy is plant → transformer → device only; taxonomy literals exist solely as report headers (`config/reports.py`).
* **Status check (2026-09-06):** Still HOLD — pending client hierarchy clarification. No mapping supplied yet. This is genuinely awaiting the client, not a development baseline.
* **Missing answer:** Mapping between client taxonomy (OU/Zone/Sector/CNC/Feeder) and the dev plant model.
* **Priority:** Important but deferrable.
* **Internally closable:** No — explicitly placed on hold by the client, not merely unaddressed.

### C-08 — BR016 / RTL-FWD-06 auto-disable ownership
* **References:** BR016, RTL-FWD-06
* **Blocks:** Whether to build application scheduler/background-worker infrastructure at all (the previously identified candidate tranche #2).
* **Evidence:** No scheduler exists in the app; documented not-implemented; ownership never confirmed by the client.
* **Development baseline (2026-09-06, pending client confirmation):** The RTL Application (this repository) will own BR016's daily auto-disable — not the RTL Master — default cutoff 18:30 Africa/Johannesburg, with an Administrator able to set a temporary, same-day-only override of the cutoff with a mandatory reason; the override expires automatically at end of day, and the default 18:30 cutoff resumes automatically the next day without administrator action. Every override change and every automatic-disable action must be audited. **This is an internal development-team/user decision made so implementation can proceed — it is not a confirmed Eskom/client answer** unless repository evidence proves otherwise.
* **Missing answer:** Formal client confirmation of ownership/timezone/override/audit. Also still open and not to be invented: which users/RTLs the disable applies to (all forwarding-enabled users, or scoped by technician/RTL?), and whether an override is fleet-wide or per-user/per-RTL.
* **Priority:** **DEVELOPMENT BASELINE SET 2026-09-06 — was GATE leading blocker #1.** Treated as internally unblocked for engineering purposes; unblocks a new candidate tranche `C08-AUTO-DISABLE-1` (see `docs/context/ACTIVE_GATE.md`). Formal client confirmation remains pending.
* **Internally closable:** No — a development baseline, not a client answer. Revisit if the client's eventual answer differs.

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
* **Development baseline (2026-09-06, pending client confirmation):** Rolling 30 days by default, plus a custom date range option. The report and its export must display which period was used. This is an internal development-team/user decision so implementation can proceed; it is not a confirmed Eskom/client answer.
* **Missing answer:** Formal client confirmation of the period itself.
* **Priority:** Important but deferrable (a working baseline now exists; REP-03 implementation is a separate future tranche, not started by this documentation update).
* **Disposition:** **Development baseline set, 2026-09-06 — pending client confirmation.** The dev-default rejection in §1.2 concerned silently inventing a period with no review; this is a reviewed, explicit baseline decision, not a silent invention — but it still requires eventual client ratification and must not be presented as if the client already confirmed it.

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
5. **A development baseline is not a client answer.** An entry marked "development baseline" (or "baseline set") records a decision the development team/user made internally so implementation can proceed without waiting indefinitely — it is explicitly not evidence that Eskom/the client confirmed it. Only mark an entry as a genuine client answer when repository evidence (a cited client document, email, or meeting record) proves the client actually said so. A development baseline may later be overridden by a real client answer; when that happens, update the entry rather than treating the baseline as already correct.

---

## 5. Engineering-gate ranking (post-REPORT-4)

Ranked by impact on candidate tranches we might actually start next:

1. **C-08 — BR016/FWD-06 ownership — DEVELOPMENT BASELINE SET 2026-09-06, pending client confirmation.** Not a confirmed client answer; treated as internally unblocked for engineering purposes only. Unblocks `C08-AUTO-DISABLE-1` as the next candidate application-engineering tranche.
2. **C-05 — Transport/producer/channel contract — the sole remaining leading gate.** Reconfirmed 2026-09-06 as Eskom-controlled/external, still unanswered. Gates physical programming execution, forwarding delivery, real-time power-down forwarding, and all producer-dependent work.
3. **C-04 — Production report-format — baseline set 2026-09-06 (PDF + CSV; native XLSX not required), pending client confirmation.** Retention/history still open.
4. **C-07 — Asset taxonomy mapping — HOLD, reconfirmed still pending 2026-09-06.** Genuinely waiting on the client; not a development baseline.
5. **C-15 — REP-03 period — baseline set 2026-09-06 (rolling 30 days default + custom date range; period must be shown on report/export), pending client confirmation.**
6. **C-09 — Active-list monitoring semantics** — blocks BR007/ACT-03 closure. Unchanged.
7. **C-01, C-02 — development baselines set 2026-09-06, pending client confirmation.** Both set as configurable, admin-controlled/audited frameworks by internal decision; the actual threshold values (C-01) and full vibration contract (C-02) remain unconfirmed by the client.
8. **C-06 — reconfirmed 2026-09-06 as Eskom-controlled/external, unanswered**, alongside the Azure/private-APN infrastructure family. C-10, C-03, C-12, C-17, C-11, C-13, C-14, C-16 follow according to rollout needs, unchanged.

**Amendment (2026-09-06):** With a development baseline now set for C-08
(pending client confirmation, per §4's rules below — this is an internal
decision, not a client answer), `C08-AUTO-DISABLE-1` is the first
internally unblocked candidate application-engineering tranche since this
register was established — the auto-disable action only flips the existing
per-user `message_forwarding` preference off on a schedule and requires no
transport, so it does not depend on C-05. C-05 remains the sole leading gate
for the larger physical-integration body of work (programming execution,
forwarding delivery, real event producers). See
`docs/context/ACTIVE_GATE.md` for the queued gate definition and
`docs/context/PROJECT_LEDGER.md` §8 for the updated dependency table.

---

## 6. REQ-3I completion rule

This register is complete when every open clarification from REQ-1A §16 and REQ-1B has an entry with references, blocked items, cited evidence, the exact missing answer, a priority under the §0 scheme, and an internal-closability disposition — and when all corrections listed in §2 are reflected. No application code is modified by this checkpoint.

**REQ-3I Status: BASELINE ESTABLISHED at `2248afd`**
