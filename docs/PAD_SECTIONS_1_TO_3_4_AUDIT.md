# AUDIT REPORT: Powerplant Dashboard vs. PAD Sections 1–3.4

*Client supplied document: DEM-2788838 Digital Incubator - RTL PAD v0.7*
*Scope: PAD Sections 1 through 3.4 only (Business Architecture)*
*Purpose: Planning and audit — no implementation was performed.*

> **Status note (2026-08-18).** This is the Phase 0 baseline audit. The gaps it
> listed in sections 9–10 (Needs Attention panel, Device/User Administration,
> reports, notification center, vertical budget, role model) have since been
> addressed through Phases 1–9, and the frontend planning cycle is now closed at
> the client review gate. For current status see
> `docs/RTL_FRONTEND_CURRENT_STATUS.md` and `docs/RTL_CLIENT_REVIEW_GATE.md`.
>
> **Specifically superseded (2026-09-25, PROJECT-AUDIT-1):** this document's
> body describes authentication throughout as "Demo auth only... single
> hardcoded credential pair" and "no role model" (§1, §3). Both are now
> factually wrong, not just superseded-in-spirit — ROLE-3/ROLE-4 landed a
> persisted, credentialed multi-user login with a real Administrator/
> Technician/General User role model (ADR-015: credential config names
> logins, the `users` row names the role). Treat every auth/role claim below
> as a snapshot of 2026-08-18, never as current behaviour.

---

## 1. Current Application Map

| Route | Page | Purpose | Main Components/Features | Status |
|-------|------|---------|-------------------------|--------|
| `/` (unauth) | `pages/login.py` | Demo login with hero image, username/password, show/hide password, error state | `login_layout()` — full-bleed hero, floating card, accessible form | **COMPLETE** (production-quality) |
| `/plants` | `pages/plants_overview.py` | Fleet overview — 30 plants with transformer/device counts, data freshness, KPI cards, health distribution bar, entity table | `app_header`, `breadcrumb`, `entity_table` (7 cols: Plant, Country, Fuel, Capacity MW, Transformers, Devices, Data), fleet KPIs, health distribution | **COMPLETE** |
| `/plants/<plant_id>` | `pages/plant_detail.py` | Plant detail — transformers list, metric health grid, hottest temperature attribution, KPIs, context | `app_header`, `breadcrumb`, `entity_table` (4 cols: Transformer, Devices, Status, Data), plant KPIs, metric health overview, temperature attribution | **COMPLETE** |
| `/plants/<plant_id>/<transformer_id>` | `pages/transformer_detail.py` | Transformer detail — devices list, metric health grid, hottest temperature attribution, KPIs, context | `app_header`, `breadcrumb`, `entity_table` (3 cols: Device, Status, Data), transformer KPIs, metric health overview, temperature attribution | **COMPLETE** |
| `/devices/<device_id>` | `pages/device_dashboard.py` | **Primary operator workspace** — equipment context, 8-metric snapshot strip, metric selector, period filter, KPI row, Plotly chart, trend grid, readings table, auto-refresh | `app_header`, `breadcrumb`, equipment context (5 fields), metric snapshot strip (8 tiles), metric dropdown, period radio + custom date picker, KPI row (aggregation-aware), `metric_chart`, `trend_grid`, `readings_table`, refresh interval | **COMPLETE** (reference implementation) |
| Global | `components/equipment_selector.py` | Cross-plant cascading Plant → Transformer → Device navigation (global shell, hidden on login) | 3 cascading dropdowns, click-to-navigate | **COMPLETE** |

**Note**: There is no `/dashboard` or `plants_dashboard` page in active use — `plants_overview` is the active fleet page.

---

## 2. Current Navigation / Information Architecture

```
Login (/)
    │
    └─► Fleet Overview (/plants)
           │
           ├─► Plant Detail (/plants/<plant_id>)
           │      │
           │      └─► Transformer Detail (/plants/<plant_id>/<transformer_id>)
           │             │
           │             └─► Device Dashboard (/devices/<device_id>)
           │
           └─► [Equipment Selector — global bar] ──► Any Device directly
```

**Key behaviors**:
- Login is a *state*, not a route — any pathname with unauthenticated `auth-store` renders login
- Breadcrumb root is always "Fleet" linking to `/plants`
- Equipment selector is globally mounted (not in page header) so callbacks always have targets
- Device dashboard uses `/devices/<device_id>` (flat) not nested under plant/transformer
- URL query params (`?metric=...&period=...&start=...&end=...`) are shareable and preserved on navigation

---

## 3. Section 3.4 Process-Flow Mapping

Based on PAD Section 3.4 "Process Flow" (business activities around transformer monitoring, device operations, user/role admin, device assignment, reporting, notifications), mapped against current implementation:

| PAD Business Activity | Existing Support | Relevant Current Page/Code | Status | Gap |
|----------------------|------------------|---------------------------|--------|-----|
| **Monitor transformer temperature** | Full | Device dashboard (metric chart, KPIs, snapshot strip), Plant/Transformer attribution card, hierarchy drill-down | **COMPLETE** | — |
| **Monitor transformer vibration** | **None** | No vibration metric in 8-metric registry (`config/metrics.py`), no vibration tables, no vibration readings | **NOT IMPLEMENTED** | Entire metric missing from data model, repository, service, UI |
| **RTL device operations (register/activate/deactivate)** | Partial | Device records exist with `status` field; inactive devices reachable by URL and marked (`status_panels.inactive_notice`) | **PARTIAL** | No UI to register new device, edit device, change status, assign to transformer |
| **User-related administration** | None | Demo auth only (`auth_service.py` — single hardcoded credential pair) | **NOT IMPLEMENTED** | No user management, no roles, no Entra ID integration |
| **Role-related activities** | None | No role model in hierarchy or auth | **NOT IMPLEMENTED** | Role concept absent |
| **RTL device assignment** | None | Devices have `transformer_id` FK; hierarchy is fixed at seed time | **NOT IMPLEMENTED** | No UI to assign/move device between transformers |
| **Report generation** | None | Readings table shows recent data; no export, no scheduled reports, no report builder | **NOT IMPLEMENTED** | No reporting workflow |
| **Notifications / business interactions** | Partial | Auto-refresh (60s), stale/no-data badges, error panels; no push notifications, no SMS/email, no alert acknowledgment | **PARTIAL** | Only passive freshness indication; no active notification system |

**Important**: The PAD Section 3.4 process flow diagram itself was not extractable from the PDF (page 11 shows only "3.4 PROCESS FLOW" header). The above activities are inferred from the PAD Table of Contents and the business architecture context. The actual diagram may contain additional or different activities.

---

## 4. Monitoring Readiness

| Capability | Readiness | Evidence |
|------------|-----------|----------|
| **Transformer monitoring** | **95%** | Plant/Transformer pages list transformers/devices with freshness, status, KPIs, attribution. Missing: vibration metric, no transformer-level trend chart (only device-level). |
| **Temperature monitoring** | **100%** | Full device dashboard (chart, KPIs, snapshot, table, freshness). Attribution card at plant/transformer level shows hottest device. All 30-min cadence, UTC timestamps. |
| **Vibration monitoring** | **0%** | Not in 8-metric registry, no schema tables, no repository queries, no service logic, no UI. |
| **Device monitoring** | **100%** | Device dashboard is the reference implementation — equipment context, 8 metrics, period controls, aggregation-aware KPIs, Plotly chart with zoom/pan, trend grid, readings table, auto-refresh, URL-shareable state. |
| **Data freshness / communication health** | **100%** | Three-tier freshness (FRESH/STALE/NO_DATA) with configured threshold (90 min = 3×30 min). Worst-of rollup: metric→device→plant→fleet with affected counts. Header badge, table column, KPI card, distribution bar. Relative + absolute UTC timestamps. Anchored to wall-clock now (not last reading). |
| **Overview/dashboard monitoring** | **95%** | Fleet overview has KPI cards (Plants/Transformers/Devices/Data Health), health distribution bar, exception-first plant table with freshness column. Missing: "Needs attention" panel (designed in HMI spec §8, not yet implemented). |
| **Drill-down investigation** | **100%** | Hierarchy navigation: Fleet → Plant → Transformer → Device. Equipment selector allows cross-plant jump. Row identity preserved through sort/filter/page via stable `row_id`. Breadcrumb links functional. |

---

## 5. Non-Monitoring Business-Flow Gaps (from PAD Section 3.4)

| Workflow | Definitely Needs Standalone Page | Could Be Dialog/Drawer | Too Unclear to Design |
|----------|----------------------------------|------------------------|----------------------|
| **Device registration** | ✅ Yes — multi-step form (plant→transformer→device details, commissioning) | — | — |
| **Device update/edit** | — | ✅ Yes — drawer from device table or dashboard | — |
| **Device deactivation** | — | ✅ Yes — confirmation dialog (status toggle) | — |
| **Device assignment/move** | — | ✅ Yes — drawer (select new transformer) | — |
| **User administration** | ✅ Yes — user list, create, edit, deactivate, role assignment | — | — |
| **Role management** | ✅ Yes — role definitions, permissions matrix | — | **Depends on client auth model** (Entra ID vs local) |
| **Report generation** | ✅ Yes — report builder (template, schedule, recipients, format) | — | — |
| **Report viewing/history** | ✅ Yes — report library with downloads | — | — |
| **Notifications/alerts** | ✅ Yes — notification center (inbox, filters, acknowledgment) | — | **Depends on notification channels** (SMS, email, push — PAD §7.2.3–5) |
| **Alarm/configuration** | — | — | ✅ **Blocked on client thresholds** — PAD §9.1 "no production warning/critical thresholds" |

**Key insight**: The PAD Sections 1–3.4 describe *business processes* (what operators/administrators *do*), while the current application is purely *monitoring* (what operators *observe*). The gap is administrative/operational workflows, not monitoring capability.

---

## 6. What Should Be Preserved (Strong Existing Assets)

| Area | Files/Components | Why Preserve |
|------|------------------|--------------|
| **Routing & URL state** | `routes.py`, `callbacks/routing.py` | Single source of truth for URL parsing/building; shareable deep links with metric/period/custom range; clean separation from page logic |
| **Authentication isolation** | `services/auth_service.py`, `callbacks/auth.py` | Demo auth behind `verify_credentials()`; ready for client SSO swap; memory-only `auth-store`; login form as callback contract (not hardcoded) |
| **Hierarchy service** | `services/hierarchy_service.py` | Active-only filtering centralized; parent validation (`get_transformer_in_plant`, `get_device_in_transformer`); breadcrumb via `get_device_context`; hierarchy counts match listings |
| **Monitoring service** | `services/monitoring_service.py` | View models (`MetricView`, `MetricSnapshot`, `FleetHealth`, `MetricHealth`); aggregation dispatch on `MetricConfig.aggregation`; freshness policy from config; delta/consumption binning; period anchoring to wall-clock; temperature attribution |
| **Repository layer** | `repositories/plant_monitoring_repository.py` | Only module with raw SQL; lateral seeks for latest readings; batched range queries; parameterized metric lists; validated schema identifier; no unbounded queries |
| **Metric configuration** | `config/metrics.py` | Single source for 8 metrics: label, unit, precision, chart_type, aggregation; `ordered_metrics()`; no branching on metric key outside this module |
| **Freshness system** | `services/monitoring_service.py` + `components/freshness_badge.py` + CSS | Three states, worst-of rollup with counts, relative+absolute UTC formatting, CSS tokens for state colors, accessibility (text+color) |
| **Device dashboard** | `pages/device_dashboard.py`, `callbacks/device.py`, `components/metric_chart.py`, `components/kpi_card.py`, `components/trend_grid.py`, `components/readings_table.py` | Reference implementation: single callback owns whole dashboard; batched fetch for all 8 metrics; aggregation-aware KPIs; chart revision for viewport reset; URL sync; trend grid; reserved heights prevent layout shift |
| **Entity tables** | `components/entity_table.py`, `callbacks/listings.py` | Stable `row_id` navigation (survives sort/filter/page); exception-first ordering; freshness column with semantic `_state`/`_severity`; numeric sorting; error panel separation |
| **Equipment selector** | `components/equipment_selector.py`, `callbacks/equipment_selector.py` | Global mount (callbacks always have targets); cascading Plant→Transformer→Device; cross-plant jump; hidden on login |
| **Test suite** | `tests/` (168 tests, `pytest -m "not db"` = 131 pure logic) | Hierarchy generation, freshness policy, metric config, timestamp parsing, KPI calculations, routing, repository range filtering, seed integrity, component architecture |
| **CSS/Design tokens** | `assets/app.css` | Semantic tokens (roles not raw colors); responsive breakpoints; focus-visible with `!important` for vendor overrides; tabular numerals; vertical budget awareness |
| **Documentation** | `UI_SPEC.md`, `HMI_UI_UX_SPEC.md`, `ARCHITECTURE.md`, `REQUIREMENTS.md`, `IMPLEMENTATION_PLAN.md`, wireframes | Living specs, acceptance records, design status tracking, implementation phases |

---

## 7. What May Need Redesign (Risks & Conflicts)

| Assumption | Risk | Evidence |
|------------|------|----------|
| **Fleet → Plant → Transformer → Device hierarchy** | PAD Sections 1–3.4 describe *business processes* not hierarchy; client's production schema uses `trfr_temperature` with ~2,112 tables named `aa12_29017` (transformer_device) — our `plant_monitoring` schema is a *development model*, not the production schema. The 30/71/120 counts are synthetic. | `PROJECT_CONTEXT.md`: "The `plant_monitoring` schema is our development schema, not the client's production schema." `db/hierarchy.py`: "SYNTHETIC DEVELOPMENT DATA... NO relationship to plant capacity, to real transformer counts, or to any client equipment inventory." |
| **Device dashboard at `/devices/<device_id>` (flat)** | PAD process flow may imply device operations scoped to transformer/plant context; flat route loses hierarchy context for administrative actions (assignment, deactivation) | `routes.py`: device route is `/devices/<device_id>` — breadcrumb reconstructs parents from `page-context` |
| **8 metrics fixed (temperature, voltage, current, active_power, reactive_power, power_factor, frequency, energy)** | PAD mentions "temperature and vibration" — vibration is missing; client's production tables appear to be temperature-only (`timestamp`, `temperature` varchar) | `config/metrics.py`: 8 metrics defined; PAD Section 3.4 "Monitoring transformer temperature and vibration" |
| **Active-only population everywhere** | Administrative workflows (device registration, assignment) may need to show *inactive* or *unassigned* equipment | `hierarchy_service.py`: `_active_only` default; `include_inactive` flag exists but unused in UI |
| **No user/role model** | PAD Section 3.1–3.2 lists Business Owner, Business Requester, Team Lead, SME, BA, Lead Architect, Solution Architect — but these are *project* stakeholders, not necessarily *runtime* roles. Runtime roles unclear. | `auth_service.py`: single credential pair; no role field in hierarchy records |
| **MonitoringCondition always UNKNOWN** | PAD may imply alerting workflows (TemperatureAlert sequence diagram in §7.2.4) but thresholds not defined | `monitoring_service.py`: `_current_condition` returns UNKNOWN; `config/metrics.py`: "No warning/critical thresholds are defined" |
| **Auto-refresh = 60s** | PAD mentions "readings are roughly 30 minutes apart" — 60s refresh polls 30× faster than data arrives | `config/settings.py`: `refresh_interval_seconds = 60`; `device_dashboard.py`: `dcc.Interval` at 60s |

---

## 8. Proposed Frontend Information Architecture (Based on PAD 1–3.4 + Current Repo)

### A. Existing Pages to Keep (Minimal Adjustment)

| Page | Route | Adjustments Needed |
|------|-------|-------------------|
| Login | `/` | None — already production-quality |
| Fleet Overview | `/plants` | Add "Needs attention" exception panel (HMI §8) |
| Plant Detail | `/plants/<plant_id>` | Visual consistency with Fleet (UX-4) |
| Transformer Detail | `/plants/<plant_id>/<transformer_id>` | Visual consistency (UX-4) |
| Device Dashboard | `/devices/<device_id>` | Already reference implementation; meet vertical budget (§6.8) |

### B. Existing Pages Needing Adjustment

| Page | Issue |
|------|-------|
| **Equipment Selector** (global bar) | Visual integration with header needed for vertical budget (§6.8 step 3) — but must stay in global layout (HMI §5 constraint) |

### C. Missing Pages Likely Required by PAD Section 3.4

| Page | Route | Purpose | Priority |
|------|-------|---------|----------|
| **Device Administration** | `/admin/devices` | List all devices (incl. inactive), register new, edit, deactivate, assign/move | **High** — core to "RTL device operations" and "device assignment" |
| **User Administration** | `/admin/users` | List users, create, edit, assign roles, deactivate | **High** — "User-related administration", "Role-related activities" |
| **Report Center** | `/reports` | Report builder, schedule, history, downloads | **Medium** — "Report generation" |
| **Notification Center** | `/notifications` | Inbox, filters, acknowledgment, preferences | **Medium** — "Notifications / business interactions" |
| **Alarm Configuration** | `/admin/alarms` | Threshold rules per metric/device/group (when client provides) | **Blocked** — requires client thresholds |

**Design pattern for C**: Admin pages should use the same `app_header`, `breadcrumb`, `entity_table`, `kpi_card` components. Device admin could be a tabbed page: List | Register | Bulk Actions.

### D. Requirements Too Ambiguous (Need Client Clarification)

| Question | Why Unclear |
|----------|-------------|
| **What are the runtime user roles?** | PAD §3.1–3.2 lists project stakeholders, not operational roles. Are operators, engineers, admins distinct? |
| **Does "device assignment" mean initial commissioning or re-assignment?** | Affects whether move operation needs history/audit trail |
| **What notification channels are required?** | PAD §7.2.3–5 shows Email, SMS, TemperatureAlert sequences — but are these *produced by* RTL app or *consumed by* it? |
| **Is vibration a separate metric or part of temperature device?** | PAD says "temperature and vibration" — same device? different sensor? same table? |
| **What does "report generation" mean?** | Scheduled PDFs? Ad-hoc CSV? Dashboard snapshots? Regulatory submissions? |
| **How does RTL app integrate with Maximo?** | PAD §7.2.2, 7.2.6 show AssetDetails and AssetCondition sequences — but Sections 1–3.4 scope excludes integration architecture |

---

## 9. Completion Estimate

### A. Monitoring/Dashboard Readiness: **95%**

**Derivation**:
- All 4 hierarchy levels implemented and tested (100%)
- Device dashboard is reference implementation with all FR-03 through FR-08 requirements met (100%)
- Freshness system complete with policy, rollup, presentation, tests (100%)
- Only gaps: vibration metric (0%), "Needs attention" panel on Fleet (designed not built), vertical budget on Device page (in progress per HMI §6.8)

### B. Overall Readiness for PAD Sections 1–3.4 Frontend Scope: **60%**

**Derivation**:
- Monitoring (95%) × weight 0.6 = 57%
- Administrative workflows (device admin, user admin, reports, notifications) ≈ 10% (only inactive marking exists) × weight 0.3 = 3%
- Vibration metric = 0% × weight 0.1 = 0%
- **Total ≈ 60%**

The PAD Sections 1–3.4 describe a **business application** (monitoring + administration + reporting + notifications), while the current repo is a **monitoring dashboard** only. The monitoring piece is nearly complete; the business-process pieces are largely absent.

---

## 10. Recommended Next Steps (Priority Order)

1. **Clarify PAD Section 3.4 scope with client** — Obtain the actual process flow diagram (page 11 of PDF was header-only). Confirm which business activities are in scope for *this* frontend phase vs. later integration.

2. **Decide on vibration metric** — Is it a 9th metric? Same device? Different sensor? Requires: `config/metrics.py` addition, repository queries, service logic, UI tile/chart — but only if confirmed by client.

3. **Design Device Administration page** (`/admin/devices`) — Core gap for "RTL device operations" and "device assignment". Use existing `entity_table`, `entity_context`, `status_panels`. Decide: standalone page vs. drawer from Fleet/Plant/Transformer pages.

4. **Design User Administration page** (`/admin/users`) — Requires: role model definition (clarify with client), auth service extension, UI for CRUD + role assignment.

5. **Implement "Needs attention" exception panel on Fleet Overview** — Already designed in HMI §8, uses existing `FleetHealth` data. Low effort, high visibility.

6. **Meet vertical budget on Device Dashboard** — HMI §6.8: consolidate selector/header/equipment context (3 bars → 1 visual row). Must keep selector in global layout (HMI §5 constraint). CSS-only visual integration.

7. **Add report generation placeholder** — `/reports` page with "Coming soon" or minimal builder if requirements clarify. Avoids empty nav destination.

8. **Extend seed data for admin workflows** — Add inactive plants/transformers/devices, unassigned devices, to test admin pages realistically.

9. **Document frontend IA decision** — Record chosen routes, page purposes, component reuse map in `docs/` for client review.

10. **Run full test suite** — `python -m pytest -v` (requires Docker + seeded DB) to ensure no regressions from any cleanup.

---

## DECISION FOR HUMAN REVIEW

### 1. What We Already Have
- **Complete monitoring dashboard** for 8 metrics across 30-plant hierarchy (Fleet → Plant → Transformer → Device)
- **Production-quality foundations**: isolated auth, service/repository layering, typed view models, worst-of freshness rollup, URL-shareable state, comprehensive tests (168), responsive CSS with design tokens
- **Device dashboard** is the reference implementation — aggregation-aware KPIs, Plotly chart with zoom/pan, trend grid, readings table, auto-refresh

### 2. What Appears Missing
- **Vibration metric** (mentioned in PAD 3.4, absent from 8-metric registry)
- **Administrative workflows**: device registration/edit/assignment, user/role management, report generation, notification center
- **"Needs attention" exception panel** on Fleet Overview (designed, not built)
- **Vertical budget compliance** on Device page (in progress per HMI §6.8)

### 3. What We Recommend Designing Next
1. **Device Administration page** (`/admin/devices`) — list, register, edit, assign, deactivate
2. **User Administration page** (`/admin/users`) — pending role model clarification
3. **Fleet "Needs attention" panel** — quick win using existing `FleetHealth`
4. **Vertical budget fix** — CSS consolidation of global shell (selector + header + equipment context)

### 4. What Must Be Clarified with Client Before Implementation
- **Actual PAD Section 3.4 process flow diagram** (PDF page 11 was header-only)
- **Runtime user roles** — PAD lists project stakeholders, not operational roles
- **Vibration metric** — separate metric? same device? data source?
- **Notification scope** — does RTL app *send* alerts (SMS/email) or only *display* freshness?
- **Report requirements** — scheduled? ad-hoc? format? regulatory?
- **Device assignment model** — initial commissioning only, or re-assignment with history?
- **Maximo integration impact on frontend** — PAD shows sequences but Sections 1–3.4 exclude integration architecture