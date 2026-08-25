# REQ-1B — Implementation Gap Matrix

**Project:** Powerplant / Remote Temperature Logger (RTL)
**Purpose:** Authoritative comparison of the REQ-1A client requirement inventory against the verified current repository baseline.
**Status:** Gap matrix established
**Repository baseline:** `main` @ `1db0f60bbb99d61f6908363772e2667e97ccc7fc`, clean working tree, 1897/1897 tests passing against live local PostgreSQL.
**Input:** `REQ-1A_Client_Requirement_Inventory.md` (baseline established)
**Method:** Every status below was determined by direct repository inspection on the baseline commit — implementation files, callbacks, services, repositories, migrations, and tests were read; nothing was inferred from remembered project status or from tests alone.

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
| RTL-PUR-01 | Automate transformer temperature data collection and analysis | FS §2 | Analysis/viewing real over stored readings (`services/monitoring_service.py`); no ingestion pipeline exists — all readings are synthetic seed data (`db/generators.py`, `db/seed_plant_monitoring.py`) | PARTIAL | Collection/ingestion (MQTT → broker → persistence) absent; analysis present | Defer ingestion to backend phase; keep dashboard analysis as pilot scope |
| RTL-PUR-02 | Reduce need for physical site visits | FS §2 | Business outcome; no directly implementable feature | DEFERRED | Achievable only once live telemetry and operations exist | Treat as outcome metric for pilot, not a work item |
| RTL-PUR-03 | Detect anomalies/problems and generate alarms | FS §2 | Only comms/freshness detection is real (`evaluate_freshness`, `monitoring_service.py:198`; BR008 notification `services/notification_service.py:45`). `MonitoringCondition` permanently UNKNOWN — no thresholds exist (`monitoring_service.py:664–668`) | PARTIAL | All temperature/battery/vibration anomaly rules undefined or unimplemented | Await client confirmation of anomaly/threshold rules (see clarification register) |
| RTL-PUR-04 | Allow users to view collected RTL/transformer data | FS §2 | Full monitoring drill-down verified: fleet → plant → transformer → device dashboards with KPIs, chart, readings table (`pages/*.py`, `callbacks/listings.py`, `callbacks/device.py`) | COMPLETE | Measurements are synthetic only | None for frontend scope; live data depends on backend |
| RTL-PUR-05 | Allow users to export collected data | FS §2 | `EXPORT_DATA` action constant defined (`services/authorization.py:135`) but has zero consumers; Report Center generates no files (`callbacks/report_center.py:368` returns explicit prototype notice) | NOT IMPLEMENTED | No export path of any kind (CSV/PDF/download) | Confirm delivery format with client, then implement report/export service |
| RTL-PUR-06 | Upload/configure RTL settings | FS §2 | Program RTL drawer + callback exist and are correctly authorized (`components/device_manage_drawer.py:139–231`, `callbacks/device_manage.py:175`) but mutate nothing ("Prototype: Command queued…", MSISDN field disabled at `device_manage_drawer.py:194`); `rtl_programming_requests` table unwired | PARTIAL | Real programming/command path absent | Wire programming to persistence first; SMS/MQTT command transport deferred |
| RTL-PUR-07 | Send alerts/notifications to Eskom users | FS §2 | Notification Center derives and *displays* one formal notification type (`pages/notifications.py`, `services/notification_service.py`); no email/SMS delivery, no persistence | PARTIAL | Delivery integrations (Exchange/SMS gateway) absent; notification history absent | Keep display-only scope until client confirms delivery channels & workflows |
| RTL-PUR-08 | Monitor and analyse temperature and vibration | PAD §6.3.1 | Temperature monitoring complete; vibration appears only as event-type vocabulary (`alembic/versions/006_device_events.py:15–16`) and contract-TBD doc (`docs/VIBRATION_METRIC_CONTRACT_TBD.md`) | PARTIAL | Vibration data contract unresolved | CLIENT CLARIFICATION REQUIRED before any vibration work |
| RTL-PUR-09 | Reporting for temperature/vibration readings | PAD §6.3.1 | Report Center shell aligned to client contracts (`config/reports.py`); no generation, mock recent-reports table (`callbacks/report_center.py:25,368`) | PARTIAL | Report data population and export absent | Implement report service after format confirmation |
| RTL-PUR-10 | Configure RTL devices through the RTL application | PAD §6.3.1 | Same evidence as RTL-PUR-06 | PARTIAL | Prototype-only configuration execution | Same as RTL-PUR-06 |

## 2. Business Requirements BR001–BR016

| ID | Requirement | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| BR001 | System must authenticate users | Working prototype login/session: `auth_service.authenticate/to_session/from_session`; fails closed on unset credentials; inactive/invalid-role refusal (`services/auth_service.py:96–207`). Entra ID deliberately absent (docs only) | COMPLETE | Prototype authentication, not enterprise SSO — Entra ID remains DEFERRED (RTL-SEC-01) |
| BR002 | Battery-low <3.75 V alarm; power-down <3.61 V | Categories declared `backend_required` (`config/notifications.py:24+`); no battery data anywhere in app; `device_events.battery_voltage` column unpopulated | NOT IMPLEMENTED | Blocked on device telemetry (BR006); no action until data contract exists |
| BR003 / BR004 | Enable/disable message forwarding | OPS-FWD-1: per-user preference persisted in `message_forwarding` via `services/message_forwarding_service.py` (atomic mutation+audit, FWD-D1..D9); device drawer authorizes only (`callbacks/device_manage.py`, guard `TOGGLE_MESSAGE_FORWARDING`); drawer prefilled from DB on open. Message delivery and 18:30 auto-disable remain unimplemented by design | COMPLETE (state) | Preference persistence real; SMS transport and scheduler are separate future work |
| BR005 | Technician can programme only an RTL assigned to them | `require_action(..., PROGRAM_RTL)` resolves technician assignment via `action_guard.py:50–89`; `ACTION_POLICY` (`authorization.py:162–168`); DB-tested in `tests/test_action_guard_db.py` | COMPLETE | The *restriction* is fully enforced; the programming act itself is prototype (see RTL-PROG-*) |
| BR006 | RTL reports battery voltage every 24h | Device-side telemetry; nothing in app receives battery data | NOT IMPLEMENTED | Backend/device domain; track under ingestion phase |
| BR007 | Master monitors all RTLs on active list | Freshness monitoring covers registered active devices fleet-wide (`latest_reading_rows(scope=…)`, `monitoring_service.py:413`); separate active-list state (`rtl_active_state`) scaffolded and unwired (`alembic/versions/005_rtl_operational_state.py`) | PARTIAL | Monitoring exists over device registry, not over a true active list. Decide whether active-list semantics matter for the web app (client question) |
| BR008 | Notify users when RTL silent >24h | Real derived notification: `build_no_data_notifications` (`notification_service.py:45–110`) rendered in scoped Notification Center (`callbacks/notifications.py`); distinct from STALE threshold | PARTIAL | Displayed only — no delivery to users, no persistence/history. Delivery deferred pending channel decision |
| BR009 | Battery Alarm vs Comms Alarm notification split | Category definitions exist; both `backend_required`; no events are produced | NOT IMPLEMENTED | Blocked on BR002/BR006 telemetry |
| BR010 | Startup message on switch-on | Event vocabulary only (`device_events` migration 006); nothing produced or consumed | NOT IMPLEMENTED | Requires device-message ingestion |
| BR011 | Power-down alarm forwarded real-time | Nothing implemented beyond category definition | NOT IMPLEMENTED | Requires telemetry + delivery channel |
| BR012 | Startup adds UID to active list | `rtl_active_state` table scaffolded (migration 005), zero application readers/writers | NOT IMPLEMENTED | Schema ready; wiring awaits real startup messages |
| BR013 / BR014 | Sensor-error detection; 3-strike 24h measurement halt | Device-side behaviour; `sensor_error` event vocabulary only | NOT IMPLEMENTED | Device firmware domain; app side blocked on events |
| BR015 | Startup-message forwarding during installation | Forwarding toggle is prototype AND no startup messages exist to forward | NOT IMPLEMENTED | Depends on BR010 + real forwarding |
| BR016 | Auto-disable forwarding at 18:30 daily | Explicitly documented as not built (`alembic/versions/005_rtl_operational_state.py` docstring "No 18:30 scheduler here"); no scheduler exists anywhere in app | NOT IMPLEMENTED | Needs background job infrastructure (does not exist yet); confirm whether it belongs to app or RTL Master |

## 3. Roles and Authorization

| ID | Requirement | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| RTL-ROLE-ADM-01 | Administrator uploads settings to any RTL | `ACTION_POLICY` grants admin any-device program/deactivate/forwarding (`authorization.py:162–168`) | COMPLETE (authorization) | Action execution itself prototype (RTL-PUR-06) |
| RTL-ROLE-ADM-02 | Administrator assigns RTLs to technicians | Fully persisted flow: assign drawer → `prototype_assignments.assign_technician` → `user_device_assignments` with FOR UPDATE close-and-insert (`repositories/plant_monitoring_repository.py:985–1089`); admin-only guard `MANAGE_ASSIGNMENT` (`callbacks/device_assign.py:250`) | COMPLETE | None within prototype scope |
| RTL-ROLE-ADM-03 | Admin actions beyond General User capability | Route policy (admin-only routes), capability policy, action policy all verified (`services/authorization.py`) | COMPLETE | None |
| RTL-ROLE-TECH-01 | Technician may program an RTL remotely | Guarded PROGRAM_RTL allowed for technicians on assigned devices; execution logs only (`device_manage.py:175`) | PARTIAL | Authorization yes, remote programming no |
| RTL-ROLE-TECH-02 | Programming restricted to assigned RTLs | Central enforcement verified: `scope_for()` (`services/device_scope.py:63–77`) + `require_action` assignment condition (`action_guard.py:76`); SQL-level scoping in repository (`_scope_clause`) | COMPLETE | Restriction enforced centrally; keep pattern for future surfaces |
| RTL-ROLE-TECH-03 | Technician removes RTL from Master active list | Deactivate callback returns message without any state change ("Production active-list state was not changed", `device_manage.py:250`); `rtl_active_state` unwired | PARTIAL | Authorization + UI exist; effect does not. Blocked on active-list wiring (BR012) |
| RTL-ROLE-TECH-04 | Technician accesses/receives alarms from assigned RTLs | Notification Center resolves scope per render (`callbacks/notifications.py:40`); only no-data alarms currently derivable | PARTIAL | Scoping correct; alarm coverage limited to BR008 until other events exist |
| RTL-ROLE-TECH-05 | Assignment has operational meaning, not display only | Verified end-to-end: assignments drive SQL visibility filters AND authorization decisions (`list_active_device_ids_for_user`, repo :963–982) | COMPLETE | None |
| RTL-ROLE-GEN-01 | General User can log in | Role accepted at login and in session validation (`CONFIRMED_ROLES`) | COMPLETE | None |
| RTL-ROLE-GEN-02 | General User views transformer data | All monitoring routes open to general role (`ROUTE_POLICY`); read-only | COMPLETE | None |
| RTL-ROLE-GEN-03 | General User can export data | Export permitted in policy (`EXPORT_DATA` includes general) but **no export exists for anyone** | NOT IMPLEMENTED | Implement export (also serves RTL-PUR-05); policy already correct |
| RTL-ROLE-GEN-04 | General User must not be offered RTL programming | `/admin/devices` admin-only route; Program action denied by ACTION_POLICY; capability checks hide controls (`may_perform_capability` usage in `callbacks/listings.py:355`) | COMPLETE | None |
| RTL-ROLE-GEN-05 | General User must not be offered message-forwarding ops | Same enforcement surface as GEN-04 (admin-only route + action denial) | COMPLETE | None |

## 4. RTL Programming (RTL-PROG-*)

| ID | Requirement | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| RTL-PROG-01 | RTL programmed before installation | Registration (`/admin/devices/new`) creates registry records, not RTL programming; no programming transaction exists | NOT IMPLEMENTED | Distinct flows confirmed; build programming flow on `rtl_programming_requests` |
| RTL-PROG-02 | Programming includes RTL Master's MSISDN | Drawer field disabled with placeholder "Not available in current frontend data" (`device_manage_drawer.py:194`) | NOT IMPLEMENTED | Unblocks with PROG-01 |
| RTL-PROG-03 | Programming includes five-digit UID `29xxx` | UID concept exists as `device_code` (sequential 29xxx, reserved pair `aa12`/`29017`, `db/hierarchy.py`); registration generates codes rather than accepting/programming a UID | PARTIAL | Data model supports UIDs; programming-time handling absent |
| RTL-PROG-04 / 05 | Transformer name in programming; max 10 chars | No programming flow; `transformer_code VARCHAR(10)` exists coincidentally in hierarchy schema | NOT IMPLEMENTED | Validate length when programming flow is built |
| RTL-PROG-06 | Validate UID validity at programming | Registration validates uniqueness/hierarchy membership; programming-time UID validation absent | PARTIAL | Reuse registration validation in programming service |
| RTL-PROG-07 | Remote programming validates user cell number registered | `users.mobile_number` column exists; never checked by any flow | NOT IMPLEMENTED | Add check inside programming service when built |
| RTL-PROG-08 | Technician assigned-device relationship validated | `require_action(PROGRAM_RTL)` resolves live assignment (`action_guard.py:76`), DB-tested | COMPLETE | None |
| RTL-PROG-09 | Unauthorized programming refused | `AuthorizationError` → `action_refused_notice()` panel (`components/status_panels.py:49`); guarded callbacks verified by `tests/test_action_guard_callbacks.py` | COMPLETE | None |
| RTL-PROG-10 | Positive confirmation on success | Prototype returns success-style message that explicitly states nothing was sent ("Prototype: Command queued…") | PARTIAL | Honest but non-functional; replace with real confirmation wired to request lifecycle |

## 5. Message Forwarding (RTL-FWD-*)

| ID | Requirement | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| RTL-FWD-01 / 02 | Enable/disable forwarding | Authorized prototype toggle persisting to in-memory dict only (`callbacks/device_manage.py:43,208`) | PARTIAL | Wire to `message_forwarding` table |
| RTL-FWD-03 | Forwarded messages relate to assigned RTLs | Toggle is per-device and technicians are scope-checked to assigned devices; but no messages exist to forward | PARTIAL | Blocked on BR010 events |
| RTL-FWD-04 | Supports on-site installation verification | Entirely dependent on startup/check-in message forwarding (BR010/BR015) | NOT IMPLEMENTED | Defer until device messaging is real |
| RTL-FWD-05 | Disable after installation complete | Same toggle as FWD-01/02 | PARTIAL | Same gap |
| RTL-FWD-06 | Auto-disable at 18:30 daily | No scheduler/background worker exists in the app; explicitly documented as not implemented | NOT IMPLEMENTED | Decide ownership (app vs RTL Master); needs job infrastructure |
| RTL-FWD-07 | Clear feedback after enable/disable | Callbacks return explicit status text including honest prototype disclaimer | COMPLETE | Feedback mechanism present; wording will change when real |

## 6. Active RTL Lifecycle (RTL-ACT-*)

| ID | Requirement | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| RTL-ACT-01 | Startup message indicates switch-on | Event vocabulary only; nothing produced | NOT IMPLEMENTED | Device/backend domain |
| RTL-ACT-02 | Startup adds UID to active list | `rtl_active_state` scaffolded, unwired | NOT IMPLEMENTED | Wiring point identified |
| RTL-ACT-03 | Active list determines monitored RTLs | Monitoring runs over registered active-status devices; true active-list semantics not wired | PARTIAL | Client question: does the web app need active-list semantics, or is that purely RTL-Master-side? |
| RTL-ACT-04 | Authorized removal from active list | Deactivate UI + authorization exist; no state change performed (`device_manage.py:250`) | PARTIAL | Wire to `rtl_active_state` |
| RTL-ACT-05 | Active-list state ≠ administrative status | Deliberately modelled separately (`rtl_active_state.device_id` PK vs `devices.status`); documented throughout migrations/repository | COMPLETE | Architectural principle already honoured — do not merge these |
| RTL-ACT-06 | Refuse removal of UID not on active list | No removal logic exists at all | NOT IMPLEMENTED | Implement together with ACT-04 wiring |

## 7. Alarms and Events (RTL-EVT-*)

| ID | Event | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| RTL-EVT-01 | No data >24h → notify | Derived, displayed, scoped (`build_no_data_notifications`); no delivery/persistence | PARTIAL | Delivery + retention need client decisions |
| RTL-EVT-02 | Battery low → Battery Alarm | Category defined, `backend_required` | NOT IMPLEMENTED | Blocked on battery telemetry |
| RTL-EVT-03 | Power down → alarm + real-time forward | Category defined, `backend_required` | NOT IMPLEMENTED | Blocked on telemetry + delivery |
| RTL-EVT-04 | Sensor error / out-of-range temp | Category defined; `sensor_error` vocabulary only | NOT IMPLEMENTED | Blocked on device events |
| RTL-EVT-05 | Startup event | Vocabulary only | NOT IMPLEMENTED | Blocked on device events |
| RTL-EVT-06 | Check-in event (forwarding context) | Vocabulary only | NOT IMPLEMENTED | Blocked on device events |
| RTL-EVT-07 | High temperature alarm | Report column literals + `high_temperature` vocabulary; no threshold logic anywhere; `MonitoringCondition` always UNKNOWN | CLIENT CLARIFICATION REQUIRED | No confirmed threshold exists — REQ-1A forbids inventing one |
| RTL-EVT-08 | Vibration event | Vocabulary mention + `docs/VIBRATION_METRIC_CONTRACT_TBD.md` (metric not activated; Phase 8 kept registry config-driven) | CLIENT CLARIFICATION REQUIRED | Vibration contract unresolved |
| RTL-EVT-09 | Invalid UID handling | `device_events.reported_uid` column + attribution CHECK scaffolded specifically for this case; nothing produces/handles invalid-UID events | NOT IMPLEMENTED | Schema ready for ingestion phase |

## 8. Monitoring and Data Requirements

| Area | REQ-1A fields | Current implementation evidence | Status | Gap |
|---|---|---|---|---|
| User data | Mobile, Personal Number, User ID, Password, Name/Surname, Role, Notification Type | `users`: username, full_name, email_address, mobile_number, role, status (`alembic/versions/003_users.py`). Password deliberately absent (no credential column — prototype auth via env vars). Personal Number and Notification Type absent | PARTIAL | Password/notification-type depend on Entra ID + notification preferences decisions (client questions) |
| RTL/device data | UID, MSISDN, Firmware, Battery Voltage, RTL Status, Date Installed | `devices` + migration 002: device_code (UID analogue), msisdn, firmware_version, installed_at, status (administrative) — all wired and displayed. Battery voltage absent everywhere | PARTIAL | Battery field requires telemetry; "RTL Status" semantic vs administrative status = client question |
| Asset hierarchy | OU, Zone, Sector, CNC, Feeder, Feeder Name, Transformer | Dev hierarchy is plant → transformer → device only; OU..Feeder appear solely as literal report column headers (`config/reports.py`) with no data mapping | CLIENT CLARIFICATION REQUIRED | Mapping between client taxonomy (OU/Zone/Sector/CNC/Feeder) and dev plant model is undefined |
| Reading/event data | Temperature, Alarm Date&Time, Alarm, Last-data timestamp, Last temp, Max-temp date/value | Temperature/time-series fully real (long-format `readings`, latest-value seeks, max/min/avg KPIs); all alarm fields absent | PARTIAL | Alarm columns blocked on event pipeline |

## 9. Reporting (RTL-REP-*)

| ID | Report | Current implementation evidence | Status | Gap / Recommended action |
|---|---|---|---|---|
| RTL-REP-01 | RTL Alarms (30 Days) — 12 fields | Contract exactly mirrored in `config/reports.py` (`rtl_alarms_30d`, fixed 30d honoured in filter lock); zero rows producible — no alarm data, no generation | PARTIAL | Column contract COMPLETE; data population + export NOT IMPLEMENTED |
| RTL-REP-02 | Installed RTLs — 10 fields | Contract mirrored (`installed_rtls`, no period control per spec); underlying last-data/last-temp values ARE available in DB and could populate | PARTIAL | Best candidate for first real report implementation |
| RTL-REP-03 | Maximum Temperature — 9 fields | Contract mirrored (`max_temperature`); period "not defined by spec" honestly surfaced in UI; max-temp computable from readings today | PARTIAL | Reporting period needs client answer before implementation |

Cross-cutting report gaps: no export/delivery format confirmed (CSV vs PDF), recent-reports table is hardcoded mock (`callbacks/report_center.py:25`), `EXPORT_DATA` policy unused.

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
| RTL-AUD-01…07 | Record activity/timestamp/actor/operation/old/new values, persisted in app database | `audit_log` table matches ALL seven requirements structurally (`alembic/versions/007_audit_log.py`: occurred_at, nullable user_id reserved for system actions, operation, entity_type/entity_id, JSONB old/new values). **AUD-1 wired the write path**: every real persisted mutation (device registration, technician assign/reassign/unassign, user create/update) writes an audit row atomically in the same transaction — an audit failure rolls the mutation back (`services/audit_service.py`, `config/audit.py`; verified by `tests/test_audit_wiring.py` incl. atomicity proof). Strict actor attribution from the authenticated session's user_id. | COMPLETE | Write path complete as of AUD-1. Audit viewer/read UI intentionally out of scope (no client requirement identified for it yet); prototype-only actions will adopt the same architecture when they become real (OPS-* phases). Prototype actions remain unaudited by design |

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
| High-temperature alarm threshold | RTL-EVT-07, RTL-PUR-03 |
| Vibration metric contract + anomaly thresholds | RTL-PUR-08, RTL-EVT-08 |
| Full anomaly-detection rules | RTL-PUR-03 |
| Notification acknowledgement/closure/escalation workflow, retention | Notification Center evolution (currently display-only) |
| Production report delivery format (CSV vs PDF), retention/history | RTL-REP-01…03 completion, RTL-PUR-05, RTL-ROLE-GEN-03 |
| Modern replacement for legacy SMS workflows | RTL-PROG-*, RTL-FWD-04 |
| Production role-source ownership (Entra ID vs DB vs enterprise service) | RTL-SEC-01, users-model evolution |
| Final authoritative production database mapping (incl. OU→plant taxonomy) | §8 asset hierarchy, all report data population |
| Performance requirements / transaction volume / frequency | Any ingestion-scale design |
| Browser support list | RTL-UX-02 |

## 17. Summary counts

| Status | Count | Items |
|---|---|---|
| COMPLETE | 19 | BR001; ADM-01(authz)/ADM-02/ADM-03; TECH-02/TECH-05; GEN-01/02/04/05; PROG-08/09; FWD-07; ACT-05; UX-01/03/04/05*; ARCH-04/05/06/07; PUR-04; AUD-01…07 (write path, as of AUD-1); BR003/004 (state persistence, as of OPS-FWD-1) |
| PARTIAL | 25 | PUR-01/03/06/07/08/09/10; BR005/007/008; TECH-01/03/04; PROG-03/06/10; FWD-01/02/03/05; ACT-03/04; EVT-01; data-fields (user/device/readings); REP-01/02/03; ARCH-02 |
| NOT IMPLEMENTED | 22 | PUR-05; BR002/006/009–016; PROG-01/02/04/05/07; FWD-04/06; ACT-01/02/06; EVT-02/03/04/05/06/09; ARCH-03; GEN-03 |
| DEFERRED | 16 | PUR-02; INT-01…12; SEC-01…09 (deployment/device items); ARCH-08; §15 infrastructure |
| CLIENT CLARIFICATION REQUIRED | 6 | EVT-07; EVT-08; UX-02; SEC-10; asset-hierarchy taxonomy mapping; user-data password/notification-type fields |

\* count method: requirement families counted individually where REQ-1A numbers them; consolidated rows (§8, §15) counted once.

### Highest-leverage observations

1. **The authorization policy/scope architecture is ahead of the functionality it protects — but it is not yet a production security system.** Route policy, device scope, and action guards are mature and well-tested *for the prototype*; the authentication/session boundary remains non-production (memory-backed browser store, plaintext env-var credentials; Entra ID deferred per RTL-SEC-01). Nearly everything the guards protect (programming, forwarding, deactivation, alarms, export) is prototype or absent. Future work should mostly *wire real behavior behind the existing guards*, not add new guards — while treating server-backed authentication as a separate, mandatory milestone before any client-facing deployment.
2. **Five scaffolded tables await a single ingestion/events milestone**: `rtl_programming_requests`, `message_forwarding`, `rtl_active_state`, `device_events`, `audit_log`. One backend/ingestion phase would light up BR002/006/009–016, EVT-02–06/09, ACT-01/02/06, and AUD-01…07 simultaneously.
3. **Audit (RTL-AUD) was the cheapest visible compliance win — DONE (AUD-1)**: write path wired into all real persisted mutations with atomic mutation+audit semantics; viewer UI remains out of scope until a client requirement names one.
4. **Installed RTLs report (REP-02) is the most implementable report today**: its required values already exist in the database; only the generation/export service is missing.
5. **Nothing further should be invented for high-temperature, vibration, acknowledgement, or report format** — all are formally gated on client answers (REQ-1A §16).

## 18. REQ-1B Completion Rule

This matrix is complete when every REQ-1A identifier has a status grounded in cited repository evidence, prototype behavior is labelled as such, and no new requirements were introduced. No code was modified during REQ-1B.

**REQ-1B Status: BASELINE GAP MATRIX ESTABLISHED**

---

# 19. Next Task — REQ-2 / Engineering Phase Selection

The matrix should now drive phase selection. Candidate next engineering phases, ranked by dependency-freedom:

1. ~~AUD wiring~~ — **DONE (AUD-1)**: audit rows written atomically for registration, assignment, and user upsert flows.
2. **REP-02 Installed RTLs implementation + export** (needs CSV-vs-PDF answer only; data already available) — NEXT (REPORT-2: backend/query contract first; delivery format stays client-gated).
3. **Forwarding persistence** (wire prototype toggle to `message_forwarding`; needs 18:30-scheduler ownership answer for full BR016).
4. **Programming request persistence** (wire Program RTL to `rtl_programming_requests`; command transport stays deferred).
5. Everything else is blocked behind the clarification register or the device-telemetry ingestion milestone.

Recommended sequencing rule: no engineering phase should begin on an item marked CLIENT CLARIFICATION REQUIRED until the answer is recorded in the register.
