# REQ-1B — Implementation Gap Matrix

**Project:** Powerplant / Remote Temperature Logger (RTL)
**Purpose:** Authoritative comparison of the REQ-1A client requirement inventory against the verified current repository baseline.
**Status:** Re-baselined (REQ-2B)
**Repository baseline:** `main` @ `4ca5dee35562d5fdc99122bdf815ca3bf8380609`, clean working tree, 2116/2116 tests passing against live local PostgreSQL.
**Input:** `REQ-1A_Client_Requirement_Inventory.md` (baseline established)
**Method:** Every status below was determined by direct repository inspection on the baseline commit — implementation files, callbacks, services, repositories, migrations, and tests were read; nothing was inferred from remembered project status or from tests alone.
**Re-baseline history:** Originally established at `1db0f60`. Re-baselined once (REQ-2B) after the backend/event tranche landed: audit wiring (AUD-1), forwarding persistence (OPS-FWD-1), programming-request persistence (OPS-PROG-1), active-list deactivation (OPS-DEACT-1), canonical event ingestion + startup activation (INGEST-1), event-backed notifications + alarm-domain projection (EVT-CONSUME-1), and the data-backed RTL Alarms report (REPORT-3). Standing rule applied throughout: without a real producer/transport, ingestion/event requirements are PARTIAL, never COMPLETE.

---

## 0. Reading this matrix

Allowed statuses (per REQ-1A §20):

| Status | Meaning used here |
|---|---|
| COMPLETE | Real, persisted, verified behavior exists for the requirement within current development scope |
| PARTIAL | Some verified behavior exists but a defined part of the requirement is missing or prototype-only |
| NOT IMPLEMENTED | No application behavior exists (schema scaffolding alone does not count) |
| DEFERRED | Deliberately out of current scope per planning documents / target-state architecture |
| CLIENT CLARIFICATION REQUIRED | Cannot be implemented safely until the client answers a recorded open question |

Standing distinctions applied throughout (per REQ-1A §20):

1. UI/prototype behavior is distinguished from persisted/production behavior.
2. Authorization **for** an action is distinguished from implementation **of** the action.
3. Schema scaffolding is distinguished from application wiring.
4. Target enterprise architecture is distinguished from immediate pilot implementation.
5. Synthetic seed measurements are not treated as production telemetry.

Evidence references use `path:line` from the baseline commit.

---

## 1. Product Purpose (RTL-PUR-*)

| ID | Requirement | Source | Current implementation evidence | Status | Gap | Recommended action |
|---|---|---|---|---|---|---|
| RTL-PUR-01 | Automate transformer temperature data collection and analysis | FS §2 | Analysis/viewing real over stored readings (`services/monitoring_service.py`); a canonical event-ingestion pipeline now exists for device *events* (`device_event_service`, INGEST-1), but all temperature *readings* remain synthetic seed data (`db/generators.py`) — no reading producer exists | PARTIAL | Reading ingestion (MQTT → broker → persistence) absent; event pipeline + analysis present |
| RTL-PUR-02 | Reduce need for physical site visits | FS §2 | Business outcome; no directly implementable feature | DEFERRED | Achievable only once live telemetry and operations exist | Treat as outcome metric for pilot, not a work item |
| RTL-PUR-03 | Detect anomalies/problems and generate alarms | FS §2 | Comms/freshness detection real; persisted-event alarm surfaces now render Battery/Power/Sensor categories (EVT-CONSUME-1). `MonitoringCondition` permanently UNKNOWN — no thresholds exist and none were added (EVT-D4) | PARTIAL | Temperature/battery/vibration anomaly rules undefined or client-gated |
| RTL-PUR-04 | Allow users to view collected RTL/transformer data | FS §2 | Full monitoring drill-down verified: fleet → plant → transformer → device dashboards with KPIs, chart, readings table (`pages/*.py`, `callbacks/listings.py`, `callbacks/device.py`) | COMPLETE | Measurements are synthetic only | None for frontend scope; live data depends on backend |
| RTL-PUR-05 | Allow users to export collected data | FS §2 | `EXPORT_DATA` action constant defined but has zero consumers; two reports are data-backed in preview (REP-01/REP-02) but generate no files; recent-reports table still mock | NOT IMPLEMENTED | No export path of any kind (CSV/PDF/download) | Confirm delivery format with client, then implement report/export service |
| RTL-PUR-06 | Upload/configure RTL settings | FS §2 | Program RTL persists a pending request + audit atomically (`rtl_programming_service`, OPS-PROG-1); no command is sent to any physical RTL (PROG-D6/D7) | PARTIAL | Request persistence real; command transport deferred |
| RTL-PUR-07 | Send alerts/notifications to Eskom users | FS §2 | Notification Center displays BR008 plus persisted-event categories (Battery/Power/Sensor/Startup-Check-In/Unregistered UID) via the shared semantics layer; no email/SMS delivery, no persistence | PARTIAL | Delivery integrations absent; notification history absent | Keep display-only scope until client confirms delivery channels & workflows |
| RTL-PUR-08 | Monitor and analyse temperature and vibration | PAD §6.3.1 | Temperature monitoring complete; vibration appears only as event-type vocabulary and contract-TBD doc; **no consumer mapping exists** (structurally absent from event semantics) | PARTIAL | Vibration data contract unresolved | CLIENT CLARIFICATION REQUIRED before any vibration work |
| RTL-PUR-09 | Reporting for temperature/vibration readings | PAD §6.3.1 | Report Center has two data-backed reports: Installed RTLs (REPORT-2) and RTL Alarms 30 Days populated from persisted events (REPORT-3); Max-Temperature still prototype; export absent; recent-reports table mock | PARTIAL | Data population largely real; export awaits format confirmation |
| RTL-PUR-10 | Configure RTL devices through the RTL application | PAD §6.3.1 | Same evidence as RTL-PUR-06: requests persist honestly ("recorded ≠ programmed") | PARTIAL | Configuration execution requires device response path |

## 2. Business Requirements BR001–BR016

| ID | Requirement | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| BR001 | System must authenticate users | Working prototype login/session: `auth_service.authenticate/to_session/from_session`; fails closed on unset credentials; inactive/invalid-role refusal (`services/auth_service.py:96–207`). Entra ID deliberately absent (docs only) | COMPLETE | Prototype authentication, not enterprise SSO — Entra ID remains DEFERRED (RTL-SEC-01) |
| BR002 | Battery-low <3.75 V alarm; power-down <3.61 V | Battery Alarm and Power Down notification rows render from device-classified `battery_low`/`power_down` events (`services/event_semantics.py`, EVT-D4: thresholds are never recomputed — the event type IS the classification); no producer exists yet | PARTIAL | Notification display real; delivery + real telemetry outstanding |
| BR003 / BR004 | Enable/disable message forwarding | OPS-FWD-1: per-user preference persisted in `message_forwarding` via `services/message_forwarding_service.py` (atomic mutation+audit, FWD-D1..D9); drawer prefilled from DB on open (`callbacks/device_manage.py`). Message delivery and 18:30 auto-disable remain unimplemented by design | COMPLETE (state) | Preference persistence real; SMS transport and scheduler are separate future work |
| BR005 | Technician can programme only an RTL assigned to them | `require_action(..., PROGRAM_RTL)` resolves technician assignment via `action_guard.py:50–89`; `ACTION_POLICY` (`authorization.py:162–168`); DB-tested in `tests/test_action_guard_db.py` | COMPLETE | The *restriction* is fully enforced; physical programming execution remains transport-gated |
| BR006 | RTL reports battery voltage every 24h | Device-side telemetry; nothing in app receives battery data. `battery_voltage` exists as event display payload only (EVT-D4) | NOT IMPLEMENTED | Blocked on device telemetry (BR006); consumption readiness ≠ data |
| BR007 | Master monitors all RTLs on active list | Freshness monitoring covers registered devices fleet-wide; separate active-list state (`rtl_active_state`) now has real activation/deactivation transitions but monitoring does not consume it (ACT-03 client question stands) | PARTIAL | Active-list monitoring semantics decision still client-gated |
| BR008 | Notify users when RTL silent >24h | Derived BR008 rows composed alongside persisted-event notifications in `current_notifications()` (`services/notification_service.py`, EVT-CONSUME-1); distinct from STALE threshold | PARTIAL | Displayed only — no delivery to users, no persistence/history |
| BR009 | Battery Alarm vs Comms Alarm notification split | Distinct spec-frozen categories render independently from `battery_low`/`power_down`/`comms_alarm` event types (EVT-D1 mapping) | PARTIAL | Categories render from persisted events; no events are produced yet; delivery absent |
| BR010 | Startup message on switch-on | Startup events persist via canonical ingestion (`services/device_event_service.py`, INGEST-1) and surface under Startup/Check-In notifications (EVT-CONSUME-1); startup also drives active-list activation for resolved devices (INGEST-D5, ACT-D1–D7) | PARTIAL | Domain pipeline complete end-to-end within the app; no real device producer/transport |
| BR011 | Power-down alarm forwarded real-time | Power Down rows render from persisted `power_down` events; *real-time forwarding* requires a delivery channel that does not exist | PARTIAL | Display real; real-time delivery transport-gated |
| BR012 | Startup adds UID to active list | Activation projection implemented per ACT-D1–D7: resolved startup atomically inserts/reactivates `rtl_active_state` with system-originated `RTL_ACTIVATED` audit (`repositories/plant_monitoring_repository.py::activate_device_active_state`) | PARTIAL | Internal projection complete and tested; the physical RTL Master is not contacted — Master-side semantics remain out of scope |
| BR013 / BR014 | Sensor-error detection; 3-strike 24h measurement halt | Sensor Error rows render from persisted `sensor_error` events (EVT-CONSUME-1); detection itself remains device firmware domain | BR013 PARTIAL / BR014 NOT IMPLEMENTED | BR013 display real pending producers; BR014 halt logic is device-side with no contract |
| BR015 | Startup-message forwarding during installation | Forwarding preference persistence is real, but recipient eligibility was deliberately NOT defined (EVT-D7 deferral) and no delivery channel exists | NOT IMPLEMENTED | Depends on delivery milestone + unresolved FWD-D1-vs-FWD-03 recipient semantics |
| BR016 | Auto-disable forwarding at 18:30 daily | No scheduler/background worker exists in the app; ownership (app vs RTL Master) unconfirmed | NOT IMPLEMENTED | Needs background job infrastructure + client ownership answer |

## 3. Roles and Authorization

| ID | Requirement | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| RTL-ROLE-ADM-01 | Administrator uploads settings to any RTL | `ACTION_POLICY` grants admin any-device program/deactivate/forwarding (`authorization.py:162–168`) | COMPLETE (authorization) | Action execution itself prototype (RTL-PUR-06) |
| RTL-ROLE-ADM-02 | Administrator assigns RTLs to technicians | Fully persisted flow: assign drawer → `prototype_assignments.assign_technician` → `user_device_assignments` with FOR UPDATE close-and-insert (`repositories/plant_monitoring_repository.py:985–1089`); admin-only guard `MANAGE_ASSIGNMENT` (`callbacks/device_assign.py:250`) | COMPLETE | None within prototype scope |
| RTL-ROLE-ADM-03 | Admin actions beyond General User capability | Route policy (admin-only routes), capability policy, action policy all verified (`services/authorization.py`) | COMPLETE | None |
| RTL-ROLE-TECH-01 | Technician may program an RTL remotely | Guarded PROGRAM_RTL persists a pending programming request for assigned devices (`rtl_programming_service`, OPS-PROG-1); no remote command reaches a physical RTL | PARTIAL | Authorization + request persistence yes; physical programming transport-gated |
| RTL-ROLE-TECH-02 | Programming restricted to assigned RTLs | Central enforcement verified: `scope_for()` (`services/device_scope.py:63–77`) + `require_action` assignment condition (`action_guard.py:76`); SQL-level scoping in repository (`_scope_clause`) | COMPLETE | Restriction enforced centrally; keep pattern for future surfaces |
| RTL-ROLE-TECH-03 | Technician removes RTL from Master active list | Deactivate flow persists the application's active-list transition (`services/rtl_deactivation_service.py`, OPS-DEACT-1) behind the `DEACTIVATE_RTL` guard. The requirement's wording is Master-side ("instruct the RTL Master"); no transport contacts the physical Master, so this stays PARTIAL (frozen correction) | PARTIAL | App-side removal real; Master instruction/confirmation transport-gated |
| RTL-ROLE-TECH-04 | Technician accesses/receives alarms from assigned RTLs | Notification Center resolves scope per render; event-backed rows (Battery/Power/Sensor/Startup-Check-In) are scope-filtered at the SQL level via `current_notifications(scope=…)` | PARTIAL | Scoping correct and now covers event categories; delivery to users still absent |
| RTL-ROLE-TECH-05 | Assignment has operational meaning, not display only | Verified end-to-end: assignments drive SQL visibility filters AND authorization decisions (`list_active_device_ids_for_user`, repo :963–982) | COMPLETE | None |
| RTL-ROLE-GEN-01 | General User can log in | Role accepted at login and in session validation (`CONFIRMED_ROLES`) | COMPLETE | None |
| RTL-ROLE-GEN-02 | General User views transformer data | All monitoring routes open to general role (`ROUTE_POLICY`); read-only | COMPLETE | None |
| RTL-ROLE-GEN-03 | General User can export data | Export permitted in policy (`EXPORT_DATA` includes general) but **no export exists for anyone** | NOT IMPLEMENTED | Implement export (also serves RTL-PUR-05); policy already correct |
| RTL-ROLE-GEN-04 | General User must not be offered RTL programming | `/admin/devices` admin-only route; Program action denied by ACTION_POLICY; capability checks hide controls (`may_perform_capability` usage in `callbacks/listings.py:355`) | COMPLETE | None |
| RTL-ROLE-GEN-05 | General User must not be offered message-forwarding ops | Same enforcement surface as GEN-04 (admin-only route + action denial) | COMPLETE | None |

## 4. RTL Programming (RTL-PROG-*)

| ID | Requirement | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| RTL-PROG-01 | RTL programmed before installation | Programming requests persist with atomic audit (`rtl_programming_service.record_request`, OPS-PROG-1; wired in `callbacks/device_manage.py`); no command is sent to any physical RTL (PROG-D6) | PARTIAL | Request lifecycle real; physical programming execution transport-gated |
| RTL-PROG-02 | Programming includes RTL Master's MSISDN | Operator-supplied Master MSISDN persisted per request (PROG-D1); field no longer disabled — it is entered and stored on the request row. No transmission occurs | PARTIAL | Data captured at request time; delivery of settings transport-gated |
| RTL-PROG-03 | Programming includes five-digit UID `29xxx` | UID concept exists as `device_code`; programming targets registered devices by id, so the UID context is implicit in the request. UID-only resolution exists for events (INGEST-D2 composite/ambiguous rules) | PARTIAL | Data model + request flow support UIDs; device-side programming semantics unconfirmed |
| RTL-PROG-04 / 05 | Transformer name in programming; max 10 chars | Requests snapshot the device's current transformer (`transformer_id`, PROG-D1 rationale); `transformer_code VARCHAR(10)` bound-checked at hierarchy level. Name-vs-code presentation not client-confirmed | PARTIAL | Snapshot persistence real; naming semantics need client confirmation |
| RTL-PROG-06 | Validate UID validity at programming | Requests target registered devices only — the drawer/device context guarantees registration, and event-side UID validation follows INGEST-D2 conservative resolution. Programming-time *device-side* UID acceptance still unverifiable without transport | PARTIAL | Registration-bound validation real; physical acceptance pending transport |
| RTL-PROG-07 | Remote programming validates user cell number registered | `users.mobile_number` column exists; never checked by any flow | NOT IMPLEMENTED | Add check inside programming/delivery flow when transport exists |
| RTL-PROG-08 | Technician assigned-device relationship validated | `require_action(PROGRAM_RTL)` resolves live assignment (`action_guard.py:76`), DB-tested | COMPLETE | None |
| RTL-PROG-09 | Unauthorized programming refused | `AuthorizationError` → `action_refused_notice()` panel (`components/status_panels.py:49`); guarded callbacks verified | COMPLETE | None |
| RTL-PROG-10 | Positive confirmation on success | Honest confirmation that a **request was recorded** ("request persisted ≠ physical RTL programmed", PROG-D7). Successful physical programming cannot be confirmed without a device response path — stays PARTIAL per frozen correction | PARTIAL | Recording confirmation honest and complete; success confirmation requires device feedback path |

## 5. Message Forwarding (RTL-FWD-*)

| ID | Requirement | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| RTL-FWD-01 / 02 | Enable/disable forwarding | Persisted per-user state in `message_forwarding` via `message_forwarding_service` (OPS-FWD-1), authorized and audited; drawer prefilled from PostgreSQL | COMPLETE (state) | State persistence real; message delivery itself is a separate transport milestone |
| RTL-FWD-03 | Forwarded messages relate to assigned RTLs | Forwarding preference is per-user with no device dimension (FWD-D1); recipient eligibility deliberately deferred (EVT-D7) — only forwarding-*relevance* of startup/check-in events is classified | NOT IMPLEMENTED | Recipient semantics (FWD-D1 vs FWD-03 intersection) + delivery channel unresolved |
| RTL-FWD-04 | Supports on-site installation verification | Entirely dependent on startup/check-in delivery (BR010/BR015). Events persist and render as notifications, but nothing is forwarded | NOT IMPLEMENTED | Defer until delivery milestone |
| RTL-FWD-05 | Disable after installation complete | Persisted forwarding disable is implemented and audited (FWD-01/02), but the installation-completion workflow, startup/check-in forwarding delivery, and Master-side integration that would connect the state transition to the actual installation process remain absent | PARTIAL | Underlying state transition real; installation-completion workflow is not |
| RTL-FWD-06 | Auto-disable at 18:30 daily | No scheduler/background worker exists in the app; explicitly documented as not implemented | NOT IMPLEMENTED | Decide ownership (app vs RTL Master); needs job infrastructure |
| RTL-FWD-07 | Clear feedback after enable/disable | Callbacks return truthful status reflecting the persisted state change | COMPLETE | None |

## 6. Active RTL Lifecycle (RTL-ACT-*)

| ID | Requirement | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| RTL-ACT-01 | Startup message indicates switch-on | Startup events persist via canonical ingestion and surface as Startup/Check-In notifications (INGEST-1 + EVT-CONSUME-1). The message originates from the device; no producer exists yet | PARTIAL | Domain pipeline real; device producer/transport absent |
| RTL-ACT-02 | Startup adds UID to active list | Activation projection implemented per ACT-D1–D7: resolved startup atomically inserts/reactivates `rtl_active_state` with NULL-actor `RTL_ACTIVATED` audit; idempotent on already-active (ACT-D3) | PARTIAL | Internal projection complete and tested; physical RTL Master is not contacted — Master-side list remains its own system |
| RTL-ACT-03 | Active list determines monitored RTLs | Monitoring runs over registered active-status devices; true active-list semantics not wired | PARTIAL | Client question: does the web app need active-list semantics, or is that purely RTL-Master-side? |
| RTL-ACT-04 | Authorized removal from active list | Deactivate flow persists the application's active-list transition true→false with atomic audit (`rtl_deactivation_service`, OPS-DEACT-1). App-side removal is real; no instruction reaches a physical RTL Master, so it stays PARTIAL (frozen correction) | PARTIAL | Wire complete on the application side; Master integration transport-gated |
| RTL-ACT-05 | Active-list state ≠ administrative status | Deliberately modelled separately (`rtl_active_state.device_id` PK vs `devices.status`); documented throughout migrations/repository and honoured by activation/deactivation implementations | COMPLETE | Architectural principle already honoured — do not merge these |
| RTL-ACT-06 | Refuse removal of UID not on active list | Absent/already-inactive rows resolve to a truthful idempotent no-op with zero writes/audits (DEACT-D1/D2). Original requirement's *refusal* semantics are Master-side; app behaviour is correct-but-different pending client view | PARTIAL | App handling real; Master-side denial semantics unverifiable without Master integration |

## 7. Alarms and Events (RTL-EVT-*)

| ID | Event | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| RTL-EVT-01 | No data >24h → notify | Derived, displayed, scoped (`build_no_data_notifications`), now composed alongside persisted-event notifications in `current_notifications()` | PARTIAL | Delivery + retention need client decisions |
| RTL-EVT-02 | Battery low → Battery Alarm | Battery Alarm rows render from persisted `battery_low` events; classification arrives pre-made from the device (EVT-D4 — thresholds never recomputed) | PARTIAL | Display real; blocked on real producers + delivery |
| RTL-EVT-03 | Power down → alarm + real-time forward | Power Down rows render from persisted `power_down` events; *real-time* forwarding requires a delivery channel | PARTIAL | Alarm surface real; real-time delivery transport-gated |
| RTL-EVT-04 | Sensor error / out-of-range temp | Sensor Error rows render from persisted `sensor_error` events; detection itself is device firmware domain | PARTIAL | Consumption real; producers + BR014 halt contract absent |
| RTL-EVT-05 | Startup event | Persisted via canonical ingestion; rendered under Startup/Check-In; excluded from the alarms report by design (`is_reportable_alarm`, R3-D1) | PARTIAL | Pipeline + notification surface real; producer/transport absent |
| RTL-EVT-06 | Check-in event (forwarding context) | Persists and renders under Startup/Check-In; classified forwarding-relevant only (EVT-D7 — recipients deliberately unresolved) | PARTIAL | Persistence/notification real; forwarding delivery deferred |
| RTL-EVT-07 | High temperature alarm | Report column literal + vocabulary only; **no consumer mapping exists** (structurally absent from event semantics); no threshold logic anywhere; `MonitoringCondition` always UNKNOWN | CLIENT CLARIFICATION REQUIRED | No confirmed threshold exists — REQ-1A forbids inventing one |
| RTL-EVT-08 | Vibration event | Vocabulary mention + `docs/VIBRATION_METRIC_CONTRACT_TBD.md`; no consumer mapping exists (structurally absent) | CLIENT CLARIFICATION REQUIRED | Vibration contract unresolved |
| RTL-EVT-09 | Invalid UID handling | Unresolvable UIDs quarantine as `invalid_uid` rows with reported UID preserved (INGEST-D2); admin-only Notification Center surface with stable per-UID keys, no href, no auto-registration (EVT-D5) | PARTIAL | Quarantine + visibility real; ultimate operational owner is a client question (default: administrators) |

## 8. Monitoring and Data Requirements

| Area | REQ-1A fields | Current implementation evidence | Status | Gap |
|---|---|---|---|---|
| User data | Mobile, Personal Number, User ID, Password, Name/Surname, Role, Notification Type | `users`: username, full_name, email_address, mobile_number, role, status (`alembic/versions/003_users.py`). Password deliberately absent (no credential column — prototype auth via env vars). Personal Number and Notification Type absent | PARTIAL | Password/notification-type depend on Entra ID + notification preferences decisions (client questions) |
| RTL/device data | UID, MSISDN, Firmware, Battery Voltage, RTL Status, Date Installed | `devices` + migration 002: device_code (UID analogue), msisdn, firmware_version, installed_at, status (administrative) — all wired and displayed. Battery voltage absent everywhere | PARTIAL | Battery field requires telemetry; "RTL Status" semantic vs administrative status = client question |
| Asset hierarchy | OU, Zone, Sector, CNC, Feeder, Feeder Name, Transformer | Dev hierarchy is plant → transformer → device only; OU..Feeder appear solely as literal report column headers (`config/reports.py`) with no data mapping | CLIENT CLARIFICATION REQUIRED | Mapping between client taxonomy (OU/Zone/Sector/CNC/Feeder) and dev plant model is undefined |
| Reading/event data | Temperature, Alarm Date&Time, Alarm, Last-data timestamp, Last temp, Max-temp date/value | Temperature/time-series fully real; alarm fields now have a real domain path: persisted `device_events` → `AlarmEventProjection` → RTL Alarms report rows (REPORT-3), with Alarm Date & Time = source `event_ts` (EVT-D9). Rows exist only once devices actually report alarms | PARTIAL | Report population live; alarm *occurrences* await real producers |

## 9. Reporting (RTL-REP-*)

| ID | Report | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| RTL-REP-01 | RTL Alarms (30 Days) — 12 fields | **Data-backed as of REPORT-3**: persisted `device_events` populate the preview via `rtl_alarms_30d_rows` (`services/report_service.py`), alarm inclusion driven solely by `is_reportable_alarm`, fixed 30-day horizon, one row per qualifying event, taxonomy fields None per R2-D2. Zero rows is a legitimate empty report until devices produce alarms | PARTIAL | Population real; file export/delivery remains client-gated |
| RTL-REP-02 | Installed RTLs — 10 fields | Data-backed generation live (`installed_rtls_rows`, REPORT-2); OU/Zone/Sector/CNC/Feeder stay None pending taxonomy mapping | PARTIAL | Export/delivery format outstanding |
| RTL-REP-03 | Maximum Temperature — 9 fields | Contract mirrored (`max_temperature`); period "not defined by spec" honestly surfaced in UI; max-temp computable from readings today; still prototype generation | PARTIAL | Reporting period needs client answer before implementation |

Cross-cutting report gaps: no export/delivery format confirmed (CSV vs PDF), recent-reports table is hardcoded mock (`callbacks/report_center.py`), `EXPORT_DATA` policy unused. Two of three reports are now data-backed in preview (REP-01 from persisted events, REP-02 from readings); Max-Temperature remains prototype pending the client's period answer.

## 10. User Experience (RTL-UX-*)

| ID | Requirement | Current implementation evidence | Status | Gap |
|---|---|---|---|---|
| RTL-UX-01 | Web-based UI | Plotly Dash browser application (`app.py`) | COMPLETE | None |
| RTL-UX-02 | Accessible via Eskom-approved browsers | No browser-compatibility testing or constraint list found in repo | CLIENT CLARIFICATION REQUIRED | Which browsers/versions must be supported? |
| RTL-UX-03 | Easy to navigate | Sidebar + breadcrumbs + global equipment selector + deep links + shareable query strings (verified across pages/components) | COMPLETE | Subjective polish continues under normal UI work |
| RTL-UX-04 | Clear error messages | Shared panel vocabulary (`status_panels.py`: not-found/forbidden/error/empty/action-refused/inactive); generic messages, no stack traces/SQL leaked; server-side logging only | COMPLETE | None |
| RTL-UX-05 | Actions reflect user's permitted profile | Role-derived navigation, capability-gated content, action-guarded buttons/controls (verified end-to-end) | COMPLETE | None |

## 11. Audit (RTL-AUD-*)

| ID | Requirement | Current implementation evidence | Status | Gap |
|---|---|---|---|---|
| RTL-AUD-01…07 | Record activity/timestamp/actor/operation/old/new values, persisted in app database | `audit_log` matches ALL seven requirements structurally and **AUD-1 wired the write path** for every real persisted mutation (registration, assignments, users, forwarding, programming requests, active-list transitions) atomically. INGEST-1 added the deliberate narrow extension: `record(..., system_originated=True)` permits `user_id = NULL` only for allowlisted system operations (`config.audit.SYSTEM_OPERATIONS`, currently exactly `RTL_ACTIVATED`) — human strict-actor attribution untouched (ACT-D5/INGEST-D6; verified by `tests/test_audit_wiring.py`, `tests/test_device_event_service.py`, activation rollback proofs) | COMPLETE | Write path complete incl. the reserved NULL-system path. Audit viewer/read UI intentionally out of scope (no client requirement identified yet) |

## 12. Target Integrations (RTL-INT-*)

All twelve integration targets (Entra ID, SAP HR, Maximo, Wonderware eDNA, PowerOn Advantage, Exchange, SMS Gateway, private APN, MQTT, RabbitMQ, message consumption/persistence) have **no implementation code** in the repository. Planning docs explicitly exclude them from current frontend scope (`docs/planning/00_README.md`, `docs/rtl_frontend_scope_guard.md`).

**Status: DEFERRED (all: RTL-INT-01 … RTL-INT-12)** — tracked separately from pilot functionality per REQ-1A §12. Note: `rtl_programming_requests.request_method/status` and `device_events.source` provide forward-compatible persistence hooks for the eventual MQTT/message-broker ingestion path.

## 13. Application Architecture (RTL-ARCH-*)

| ID | Requirement | Current implementation evidence | Status | Gap |
|---|---|---|---|---|
| RTL-ARCH-01 | Web presentation tier | Dash UI layer (pages/components/callbacks) | COMPLETE | Monolithic process, not standalone tier |
| RTL-ARCH-02 | Application tier | Services layer exists but lives in the same Dash process | PARTIAL | Single-process deployment |
| RTL-ARCH-03 | API layer within application tier | No HTTP API exists (only Dash callback endpoints) | NOT IMPLEMENTED | Needed before mobile/3rd-party consumers or microservice split |
| RTL-ARCH-04 | Business logic layer | `services/*` verified as the calculation/policy home (KPIs, freshness, notifications, scope, guards) | COMPLETE | Minor callback-layer leaks documented in checkpoint §11.7 |
| RTL-ARCH-05 | Data access layer | Single repository module, raw parameterised SQL, validated identifiers | COMPLETE | None |
| RTL-ARCH-06 | Database/data tier | PostgreSQL 16, Alembic sole DDL authority, no drift detected | COMPLETE | None |
| RTL-ARCH-07 | Separation of responsibilities | Layering verified: UI contains no SQL; callbacks thin; scope/authorization centralised | COMPLETE | Known exceptions listed in checkpoint report §11 (picker parsing, sort policies, `entity_in_scope` placement) |
| RTL-ARCH-08 | Independent scaling/management/deployment | Single container/process; Kubernetes explicitly out of scope until production requirements known (CLAUDE.md rule) | DEFERRED | Target-state; revisit post client audit |

## 14. Security (RTL-SEC-*)

| ID | Requirement | Status | Evidence / note |
|---|---|---|---|
| RTL-SEC-01 | Entra ID authentication | DEFERRED | Zero implementation; login page test even bans SSO branding (`tests/test_login_page.py:129`); prototype auth is plaintext env-var comparison with no credential column |
| RTL-SEC-02 / 03 | HTTPS / encryption in transit | DEFERRED | Deployment-time concern; `railway.json` exists but TLS termination is platform-level |
| RTL-SEC-04 / 05 | Private APN, firewall/NSG filtering | DEFERRED | Infrastructure target-state |
| RTL-SEC-06 / 07 | Secure bootloader, tamper resistance | DEFERRED | Device hardware domain, outside this application |
| RTL-SEC-08 | Device data encrypted at rest/in transit | DEFERRED | Local dev Postgres unencrypted; target-state |
| RTL-SEC-09 | Patch maintenance | DEFERRED | Operational process, pinned deps in `requirements.txt` |
| RTL-SEC-10 | Eskom security standards compliance | CLIENT CLARIFICATION REQUIRED | Specific standards named in PAD not mapped to verifiable controls in repo |

Prototype-authentication caveat carried forward from checkpoint: the memory-based `auth-store` session is explicitly documented as not an authorization boundary (`auth_service.py:18–25`); acceptable for local demo only.

## 15. Target Deployment / Infrastructure

Azure, ExpressRoute, Firewall, VNets, Kubernetes, separated containers, primary/replica database, RabbitMQ/MQTT broker, Azure Monitor, App Insights, Defender, Log Analytics, private APN — **no implementation**; CLAUDE.md forbids adding Kubernetes deployment until production requirements are known.

**Status: DEFERRED** — consistent with PAD framing as a pilot whose broader rollout depends on pilot success.

## 16. Client Clarification Register — impact map

Each open item from REQ-1A §16, with where it blocks implementation:

| Open item | Blocks |
|---|---|
| High-temperature alarm threshold | RTL-EVT-07, RTL-PUR-03 (event semantics structurally omit high_temperature until approved) |
| Vibration metric contract + anomaly thresholds | RTL-PUR-08, RTL-EVT-08 (structurally absent from event semantics) |
| Full anomaly-detection rules | RTL-PUR-03 |
| Notification acknowledgement/closure/escalation workflow, retention | Notification Center evolution (display-only by frozen decision — no invented expiry/retention) |
| Production report delivery format (CSV vs PDF), retention/history | RTL-REP-01…03 export, RTL-PUR-05, RTL-ROLE-GEN-03 |
| Modern replacement for legacy SMS workflows | RTL-PROG execution, RTL-FWD-04 delivery, transport selection |
| Production role-source ownership (Entra ID vs DB vs enterprise service) | RTL-SEC-01, users-model evolution |
| Final authoritative production database mapping (incl. OU→plant taxonomy) | §8 asset hierarchy; report OU/Zone/Sector/CNC/Feeder columns (currently honest None per R2-D2) |
| Performance requirements / transaction volume / frequency | Ingestion-scale design (incl. any future event index) |
| Browser support list | RTL-UX-02 |
| Operational owner for unregistered UIDs (development default: administrators only, EVT-D5) | Widening the invalid_uid surface beyond admins |

## 17. Summary counts

Counted per the footnote method: families numbered individually by REQ-1A count separately; consolidated rows (§8 data fields ×3, §11 audit ×1, §15 deployment ×1) counted once. BR003/004 counted as two items.

| Status | Count | Items |
|---|---|---|
| COMPLETE | 29 | BR001/003/004/005; ADM-01/02/03; TECH-02/05; GEN-01/02/04/05; PROG-08/09; FWD-01/02/07; ACT-05; UX-01/03/04/05; ARCH-04/05/06/07; AUD (write path incl. narrow NULL-system extension); PUR-04 |
| PARTIAL | 45 | PUR-01/03/06/07/08/09/10; BR002/007/008/009/010/011/012/013; TECH-01/03/04; PROG-01/02/03/04/05/06/10; FWD-05; ACT-01/02/03/04/06; EVT-01/02/03/04/05/06/09; data-fields user/device/read+events; REP-01/02/03; ARCH-02 |
| NOT IMPLEMENTED | 11 | PUR-05; BR006/014/015/016; GEN-03; PROG-07; FWD-03/04/06; ARCH-03 |
| DEFERRED | 24 | PUR-02; INT-01…12; SEC-01…09; ARCH-08; §15 infrastructure |
| CLIENT CLARIFICATION REQUIRED | 6 | EVT-07; EVT-08; UX-02; SEC-10; asset-hierarchy taxonomy mapping; user-data password/notification-type fields |

Total enumerated items: 115 (29 + 45 + 11 + 24 + 6).

### Highest-leverage observations

1. **The authorization/scope architecture remains ahead of what is wired behind it — and the gap has narrowed substantially.** Programming requests, forwarding state, active-list transitions, event ingestion, activation, notifications, and two reports are now real persisted behavior behind the mature guards. What still separates the app from production: no device producer/transport (nothing physically sends events or receives commands), display-only notifications, prototype authentication (server-backed auth is a mandatory pre-deployment milestone), and client-gated formats/thresholds.
2. **The five scaffolded tables are now fully wired** — `rtl_programming_requests`, `message_forwarding`, `rtl_active_state`, `device_events`, `audit_log` all have real application writers and readers. The former "await one ingestion milestone" observation is closed; the remaining gap on every event-family requirement is exclusively producer/transport/delivery, which is why they are PARTIAL rather than COMPLETE.
3. **One shared semantics layer prevents rule duplication**: `services/event_semantics.py` is the single authority for what each persisted event means (notification category, reportability, forwarding-relevance). Consumers contain no event-type literals or numeric thresholds (EVT-D4), and high-temperature/vibration are structurally absent until client-approved.
4. **Reports are becoming real in dependency order**: Installed RTLs (REPORT-2) and RTL Alarms 30 Days (REPORT-3) render from the database; export/delivery format is now *the* blocker for both, followed by Max-Temperature's undefined period.
5. **Nothing further should be invented for high-temperature, vibration, acknowledgement, notification retention/expiry, or report format** — all formally gated on client answers (REQ-1A §16). The Notification Center deliberately applies no time window; ALARM_REPORT_WINDOW's 30 days belongs to REP-01 alone.
6. **Remaining engineering slices ranked by dependency-freedom (REQ-2A outcome)**: (a) report export pipeline once format is answered — REP-02 ready today, REP-01 after REPORT-3; (b) 18:30 scheduler infra pending ownership answer; (c) transport adapters last, blocked on producer evidence. The clarification register is the true critical path for most remaining NOT/PARTIAL closures.

## 18. REQ-1B Completion Rule

This matrix is complete when every REQ-1A identifier has a status grounded in cited repository evidence, prototype behavior is labelled as such, and no new requirements were introduced. No application code was modified during this documentation re-baseline (REQ-2B).

**REQ-1B Status: RE-BASELINED at `4ca5dee` (REQ-2B)**

---

# 19. Phase History & Next Selection

Completed since the original matrix:

1. ~~AUD wiring~~ — DONE (AUD-1).
2. ~~REP-02 Installed RTLs implementation~~ — DONE (REPORT-2); export outstanding.
3. ~~Forwarding persistence~~ — DONE (OPS-FWD-1).
4. ~~Programming request persistence~~ — DONE (OPS-PROG-1).
5. ~~Active-list deactivation~~ — DONE (OPS-DEACT-1).
6. ~~Canonical ingestion + startup activation~~ — DONE (INGEST-1).
7. ~~Event consumers: notifications + alarm-domain projection~~ — DONE (EVT-CONSUME-1).
8. ~~RTL Alarms 30 Days population~~ — DONE (REPORT-3).

Next candidates, ranked by dependency-freedom (from REQ-2A):

1. **Report/export pipeline** — needs the CSV-vs-PDF answer (or an explicitly-labeled development default decision); REP-02 is ready immediately, REP-01 follows REPORT-3.
2. **BR016 scheduler infrastructure** — blocked on ownership answer (app vs RTL Master).
3. **Transport adapters** — blocked on producer/format evidence; deliberately last.

Recommended sequencing rule unchanged: no engineering phase should begin on an item marked CLIENT CLARIFICATION REQUIRED until the answer is recorded in the register.
