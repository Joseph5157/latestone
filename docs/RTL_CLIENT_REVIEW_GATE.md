# RTL Client Review Gate

*Phase 9 deliverable — created 2026-08-18.*
*Purpose: a single, meeting-ready summary of what the RTL frontend can demonstrate today, what is prototype-only, what is blocked on backend/data, and the exact decisions the client/backend team must make before further implementation.*

---

## 1. Current Scope Basis

Current frontend work is based on exactly two approved inputs:

1. **Client PAD, Sections 1–3.4** (Business Architecture)
   - Source: `DEM-2788838 Digital Incubator - RTL PAD v0.7`
   - Audit: `docs/PAD_SECTIONS_1_TO_3_4_AUDIT.md`
2. **RTL Functional Specification extract**
   - Source: `Remote Temperature Logger Functional Specification RTL v0.3.pdf`, doc ID `240-137264801`, revision 1
   - Extract: `docs/RTL_FUNCTIONAL_SPEC_EXTRACT.md`

**Boundary:** Later PAD technical sections are *not* permission to implement backend, API, database, integration, or infrastructure. The current scope is a frontend-focused RTL application with preserved monitoring.

### Audit Classification at a Glance

| Area | Classification |
|------|----------------|
| Authentication shell | COMPLETE FRONTEND (demo) |
| Application navigation | COMPLETE FRONTEND |
| Fleet Overview | COMPLETE FRONTEND |
| Plant monitoring | COMPLETE FRONTEND |
| Transformer monitoring | COMPLETE FRONTEND |
| Device dashboard | COMPLETE FRONTEND |
| Device Administration | COMPLETE FRONTEND (shell) |
| Register Device | PROTOTYPE FRONTEND |
| Asset Assignment | PROTOTYPE FRONTEND |
| Technician Assignment | PROTOTYPE FRONTEND |
| Program RTL | PROTOTYPE FRONTEND |
| Message Forwarding | PROTOTYPE FRONTEND |
| Deactivate RTL | PROTOTYPE FRONTEND |
| User Administration | PROTOTYPE FRONTEND |
| Roles | COMPLETE FRONTEND (definitions); CLIENT DECISION REQUIRED (source) |
| Reports | COMPLETE FRONTEND (definitions/layout); DATA/BACKEND BLOCKED (generation) |
| Notifications | COMPLETE FRONTEND (derivable >24h); DATA/BACKEND BLOCKED (other categories) |
| Metric extensibility | COMPLETE FRONTEND |
| Vibration readiness | COMPLETE FRONTEND (structure); CLIENT DECISION REQUIRED (activation) |

---

## 2. What Is Complete

"Complete" here means: a live, working frontend screen driven by current local/development data. **Prototype persistence is not production-ready** and is never presented as such.

- **Authenticated application shell** — login/logout gate using the isolated demo `auth_service` (memory-only auth store). Brand header, breadcrumbs, freshness slot, logout.
- **Top-level navigation** — Overview, Devices, Reports, Notifications, Administration, plus the global Plant → Transformer → Device equipment selector.
- **Fleet → Plant → Transformer → Device drill-down** — full hierarchy navigation with shareable device URLs.
- **Fleet Overview** — 30 plants with transformer/device counts, KPI cards, fleet health distribution, exception-first sortable table, **Needs Attention** panel.
- **Plant monitoring** — transformers worst-data-first, plant context fields, KPIs, metric-health grid, hottest-temperature attribution card.
- **Transformer monitoring** — devices worst-data-first, transformer context fields, KPIs, metric-health grid, hottest-temperature attribution card.
- **Device dashboard** — equipment context, 8-metric snapshot strip, metric selector, period filter (24h/7d/30d/custom), aggregation-aware KPIs (Statistics vs Delta), Plotly chart, quick-trend grid, readings table, freshness badge, auto-refresh.
- **Data freshness** — LIVE/STALE/NO_DATA badges and **Needs Attention** data-freshness exceptions. Freshness is deliberately separate from the formal >24h notification rule.
- **User role definitions** — Administrator / Technician / General User confirmed from the Functional Specification; prototype role selector; pure permission helpers (`prototype_access.py`) ready for future real authorization; legacy users safely shown as Unassigned.
- **Device Administration shell** — full device table (search, status filter, summary counts, freshness) with View / Assign / Manage actions.
- **Report definitions** — RTL Alarms (30 Days), Installed RTLs, Maximum Temperature with the client-confirmed column sets (`config/reports.py`); report center layout, layout preview, asset-scope cascade, date-range semantics.
- **Notification Center** — formal **>24h no-data** notifications derived live from reading data (BR008), separate from freshness; supported-types table for all confirmed categories.
- **Metric-extensible frontend** — registry-driven metrics; snapshot strip, trend grid, health grid and charts are driven by `ordered_metrics()` with no fixed-8 assumptions (Phase 8).
- **Vibration readiness** — generic metric UI is ready for a ninth metric, but vibration is deliberately **not activated** pending a real data contract.

---

## 3. What Is Prototype Only

These features have a real UI and a demonstrable workflow, but **no production operation is executed** and **no production state is changed**. Each requires a backend/API/data contract before it can become a production workflow.

| Feature | UI exists | Workflow demonstrable | Production operation NOT executed | Needs backend/API/data contract |
|---------|:---:|:---:|:---:|:---:|
| Register Device | Yes | Yes | No database write; success screen says "No data was persisted to the production database" | Yes — registration persistence + required fields |
| Asset Assignment | Yes | Yes | In-memory mock only; no DB write | Yes — assignment persistence + reassignment rules |
| Technician Assignment | Yes | Yes | In-memory mock only; no identity write | Yes — real technician data + persistence |
| Program RTL | Yes | Yes | No command sent to RTL Master; MSISDN field is disabled ("Not available in current frontend data") | Yes — command transport + MSISDN source |
| Message Forwarding | Yes | Yes | In-memory state only; production forwarding unchanged; no 6:30 PM auto-disable | Yes — state source + enable/disable API |
| Deactivate RTL | Yes | Yes | Active-list state unchanged; confirmation says so explicitly | Yes — active-list mutation API |
| Add/Edit User persistence | Yes | Yes | In-memory prototype user store; not connected to any identity system | Yes — identity source + durable users |
| Report generation | Yes | Yes | "No report file was generated or delivered"; recent-reports rows are demo data | Yes — report service, formats, delivery |

---

## 4. What Is Waiting for Backend/Data

| Feature | Current frontend | Missing backend/data | Blocking impact |
|---------|------------------|----------------------|-----------------|
| Production users | Demo credential only | Durable user store | No real login |
| Authentication/authorization source | Demo `auth_service`, memory-only store | Real auth (Entra ID / DB / API / session) | No production security boundary |
| Device registration persistence | Prototype form | Registration API/table | Registrations cannot be saved |
| Technician assignment persistence | In-memory mock | Assignment API/table | Technician access cannot be enforced |
| RTL programming transport | Prototype confirm only | API/SMS/backend command | No real programming |
| RTL Master MSISDN | Field disabled | Field source | Programming form incomplete |
| Active-list state | Prototype confirm only | Active-list source/mutation | Deactivate/monitor scope not real |
| Message forwarding state | In-memory mock | Forwarding state source + API | Forwarding workflow not real |
| Battery voltage | Not displayed | Battery(V) readings | Battery Alarm / Power Down notifications blocked |
| Firmware | Report column only | Firmware field | RTL Alarms report incomplete |
| RTL operational status | Not available | Status source | Installed RTLs report incomplete |
| OU | Not available | Field source | Reports blocked |
| Zone | Not available | Field source | Reports blocked |
| Sector | Not available | Field source | Reports blocked |
| CNC | Not available | Field source | Reports blocked |
| Feeder / Feeder Name | Not available | Field source | Reports blocked |
| Date Installed | Not available | Field source | Maximum Temperature report blocked |
| Alarm/event history | Not available | Event store | Battery/Power Down/Sensor Error notifications blocked |
| Activation timestamp | Not available | Start/activation event | Never-reported RTLs cannot be judged for >24h notification |
| Sensor error state | Not available | Error-state source | Sensor Error notifications blocked |
| Report data | Report column definitions only | Report service/data mapping | No real report output |
| Notification history | Current-state table only | History store + acknowledgement | No audit/acknowledgement workflow |
| Vibration mapping | Metric UI ready, not activated | Metric key, unit, schema, API | Vibration cannot be activated |

---

## 5. Client Decisions Required

Implementable questions, by priority. Answers to Priority 1 unlock the architecture; later priorities refine it.

### Priority 1 — Backend/Data Ownership

1. Will the frontend consume an API, or directly query the managed database?
2. Who owns the application backend/API layer?
3. When will the production/current database schema be supplied?
4. Will there be one API for monitoring + administration, or separate services?

### Priority 2 — Authentication and Roles

5. Confirm the runtime roles: **Administrator / Technician / General User**.
6. What is the source of role assignment — Entra ID, database, API, or another identity source?
7. Is Technician access restricted to assigned RTLs at the **backend** level (BR005)?

### Priority 3 — Device Lifecycle

8. What are the exact required fields for registering an RTL device?
9. What is the exact distinction between administrative active/inactive status and the RTL Master active list (BR012)?
10. Do asset reassignment and technician assignment require history?
11. Do assignment changes require an audit trail?

### Priority 4 — RTL Programming

12. What is the production programming interface (API / SMS / backend command mechanism)?
13. What is the source of the RTL Master MSISDN?
14. What validation and error responses are required (e.g. GM002 `Request denied. User is not authorised to program this logger.`)?

### Priority 5 — Message Forwarding

15. What is the current forwarding-state source?
16. Is there an enable/disable API (BR003/BR004)?
17. Is the 6:30 PM daily auto-disable (BR016) backend-owned?
18. Does the frontend need to display a countdown/expiry for forwarding?

### Priority 6 — Notifications

19. What is the source of **Battery Alarm** events (BR009, battery < 3.75 V)?
20. What is the source of **Power Down** events (BR011, battery < 3.61 V)?
21. What is the source of **sensor-error** events (BR013/BR014)?
22. Is startup/check-in history available (BR010)?
23. Should never-reported RTLs trigger a >24h notification after their activation timestamp?
24. What are the notification recipient rules (SMS/Email, by role)?
25. Is notification history and acknowledgement required?

### Priority 7 — Reports

26. What output formats are required: PDF / Excel / CSV / other?
27. Are reports generated client-side or backend-side?
28. What production scope filtering is required (fleet / plant / transformer / device)?
29. Is retention/history required for generated reports?
30. What export permissions apply per role?

### Priority 8 — Vibration

Copied unchanged from `docs/VIBRATION_METRIC_CONTRACT_TBD.md` — do not invent answers:

| Question | Why It Matters |
|----------|----------------|
| What is the metric key? | Must match database column/API field |
| What is the operator-facing label? | UI display name |
| What is the unit? | mm/s, m/s², in/s, g, µm, etc. |
| What precision is needed? | Decimal places for display |
| Is it instantaneous or cumulative? | Determines STATISTICS vs DELTA aggregation |
| What is the chart type? | Line, bar, or something else? |
| What is the sampling cadence? | Freshness policy alignment |
| What is the source resolution? | Chart binning and energy-like metrics |
| Is there a valid sensor range? | Future threshold support |
| Do thresholds exist? | Warning/critical states |
| Are there multiple axes? | X/Y/Z or single combined value? |
| Is this continuous data or event data? | Storage and display model |
| What does the value represent? | Displacement, velocity, acceleration, RMS, peak? |
| How is it stored in the database? | Column name, table, schema |
| How is it accessed via API? | Endpoint, query pattern |

---

## 6. Data/API Contract Required

Compact checklist of the capabilities/data the frontend needs. No endpoint names are invented — the backend team defines those.

| Capability / data | Current frontend data exists | Prototype only | API/data required |
|-------------------|:---:|:---:|:---:|
| Authentication | — | Yes (demo) | Yes |
| Current user + role | — | Yes (in-memory) | Yes |
| User list | — | Yes (in-memory) | Yes |
| Device list | Yes (dev schema) | — | Production mapping |
| Plant/Transformer hierarchy | Yes (dev schema) | — | Production mapping |
| Latest readings | Yes (dev schema) | — | Production mapping |
| Historical readings | Yes (dev schema) | — | Production mapping |
| Device assignment | — | Yes (mock) | Yes |
| Technician assignment | — | Yes (mock) | Yes |
| Program RTL | — | Yes (mock) | Yes |
| Deactivate RTL | — | Yes (mock) | Yes |
| Message forwarding | — | Yes (mock) | Yes |
| Alarm/events | — | No rows fabricated | Yes |
| Reports | — | Yes (definitions/demo rows) | Yes |
| Vibration data | No | No | Yes (contract TBD) |

---

## 7. Recommended Demo Flow

Each step is labelled **live frontend with current data** or **frontend prototype** so nobody mistakes a prototype action for a production operation.

1. **Login** — live frontend (demo credentials; not production authentication).
2. **Overview** — live frontend with current data (30 plants, counts, health).
3. **Needs Attention** — live frontend with current data (data-freshness exceptions only; no fabricated electrical warnings).
4. **Plant** — live frontend (transformers worst-first, attribution card).
5. **Transformer** — live frontend (devices worst-first).
6. **Device Dashboard** — live frontend (metric selector, period filter, KPIs, chart, readings table, freshness).
7. **Device Administration** — live frontend shell (search, filter, View/Assign/Manage actions).
8. **Technician Assignment prototype** — frontend prototype (drawer, in-memory only).
9. **Program RTL prototype** — frontend prototype (no command sent; MSISDN unavailable).
10. **Message Forwarding / Deactivate RTL prototypes** — frontend prototype (in-memory state only).
11. **User Administration / Roles** — frontend prototype (in-memory user store; role selector).
12. **Reports** — frontend prototype (confirmed definitions + layout preview; no files generated).
13. **Notifications** — live derivable >24h rows; other categories shown as "requires backend/data integration".

---

## 8. Go / No-Go Gates

### GO — frontend polish (can continue without backend)

- Visual refinements
- Responsive improvements
- Accessibility
- Component cleanup
- Client-approved copy

### NO-GO — production workflow implementation (do not proceed until a backend/data contract exists)

- Device writes
- User writes
- Assignment persistence
- RTL programming
- Message forwarding
- Alarms
- Real reports
- Notification history
- Vibration activation

---

## 9. Recommended Next Steps

1. Client/backend team reviews this gate and answers **Priority 1–2** questions first (ownership, auth, roles).
2. Client supplies the production/current database schema or API contract.
3. Confirm the vibration data contract (`docs/VIBRATION_METRIC_CONTRACT_TBD.md`).
4. Confirm notification sources, report formats, and role-based access.
5. Only then plan the next implementation phase. No further phase is planned automatically.

**Current state: CLIENT / BACKEND REVIEW REQUIRED.** Further production implementation is gated on client/backend/data-contract decisions.