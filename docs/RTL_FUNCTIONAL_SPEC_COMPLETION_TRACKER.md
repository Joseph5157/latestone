# RTL Functional Specification Completion Tracker

**Project:** Powerplant / Remote Temperature Logger (RTL) Monitoring Dashboard
**Client authority:** `Remote Temperature Logger Functional Specification RTL v0.3.pdf` only — Unique Identifier `240-137264801`, Revision `1`, 18 pages.
**Audit baseline:** `Joseph5157/powerplant-monitoring` `main` @ `1fa20ee2e2dd76dfc318ead15590dffdd0280e19` (2026-09-16).
**Purpose:** The living requirements-completion ledger for RTL functionality against the authoritative Functional Specification. Repository state remains in `docs/context/CURRENT_STATE.md`; this tracker records what remains against the client specification.

> Earlier PADs, planning documents, historical audits, architecture material and internal development assumptions are historical/reference material only. They must not supply, change, or override RTL client requirements.

## 1. Maintenance rules

After every successful implementation gate:

1. Update only the affected row(s).
2. Change a row to `COMPLETE` only when the whole requirement is implemented and verified.
3. Record the completion commit SHA and verification evidence.
4. If only UI/database state exists but real RTL/RTL Master/SMS behaviour is absent, keep the row `PARTIAL`.
5. A simulator is not proof of production RTL behaviour.
6. Use `CONFLICT` whenever current code contradicts this Functional Specification.
7. Use `CLIENT INPUT` for TBC/unclear requirements; do not invent the answer.
8. Do not use requirements from any other client PDF in this tracker.

### Status vocabulary

| Status | Meaning |
|---|---|
| `COMPLETE` | Implemented and verified for the full application responsibility. |
| `PARTIAL` | Useful implementation exists, but required behaviour is still missing. |
| `MISSING` | Required capability is not implemented. |
| `CONFLICT` | Current behaviour/assumption contradicts the Functional Specification. |
| `EXTERNAL VERIFY` | Behaviour belongs mainly to RTL/RTL Master/device and still needs integration evidence. |
| `CLIENT INPUT` | Source itself is TBC/unclear and requires client clarification. |

## 2. Functional architecture baseline

The Functional Specification describes:

`RTL Device -> cellular network -> RTL Master -> stored/analyzed data -> RTL Client`

The RTL Client is used to view/export data and upload settings. The RTL Master receives RTL data, analyses it, generates alarms, manages the active list and handles message-forwarding behaviour.

The Functional Specification explicitly defines an **SMS interface** for:

- RTL Programming
- Message Forwarding
- Deactivate RTL

## 3. Priority backlog

| Priority | Gate | Work | Status | Dependency |
|---|---|---|---|---|
| P0 | `FS-SCOPE-1` | Align General User access with §5.9 | `COMPLETE` | None |
| P0 | `FS-BR016-1` | Correct ownership of 18:30 forwarding auto-disable | `COMPLETE` | RTL Master execution remains an external integration item |
| P0 | `FS-SMS-1` | Real SMS/RTL Master integration for Program, Forwarding, Deactivate | `MISSING` | Client/RTL Master details |
| P0 | `FS-PROG-1` | Align Program RTL fields/validation to Master MSISDN, UID, transformer name | `PARTIAL` | Internal validation DONE (`176dc49`); real transport remains |
| P0 | `FS-ACTIVE-1` | Startup-driven active list + real deactivation result | `PARTIAL` | RTL Master |
| P0 | `FS-NOTIFY-1` | Real alarm/startup delivery to registered users | `MISSING` | SMS/recipient details |
| P1 | `FS-ALARM-1` | Align alarm semantics to BR002/009/011/013 | `COMPLETE` | Application-facing semantics only; real event generation/external delivery remain PARTIAL/EXTERNAL per BR row |
| P1 | `FS-BATTERY-1` | Real battery voltage + 24h reporting evidence | `MISSING` | RTL/RTL Master |
| P1 | `FS-REPORT-1` | Complete OU/Zone/Sector/CNC/Feeder report data | `PARTIAL` | Production data mapping |
| P1 | `FS-EXPORT-1` | Resolve/implement Excel export shown in client UI | `COMPLETE` | Native XLSX implemented and verified (`2d9616d`) |
| P1 | `FS-BATTERY-VIEW-1` | Battery Profile Viewer | `MISSING` | Real battery data |
| P2 | `FS-AUTH-1` | Production authentication | `PARTIAL` | §5.3 Security TBC |
| P2 | `FS-NFR-1` | Performance/security/dependencies/volume/frequency | `CLIENT INPUT` | Client |

## 4. Business requirements BR001–BR016

| ID | FS page | Requirement | Current code | Status | What closes it | Dependency | Completion evidence |
|---|---:|---|---|---|---|---|
| BR001 | 7 | Authenticate users | Credentialed login, persisted roles, trusted server session, fail-closed authorization | `PARTIAL` | Replace dev credentials with client-approved production authentication when §5.3 is clarified | Client security TBC | — |
| BR002 | 7 | Battery low <3.75V; power-down <3.61V | `battery_low`/`power_down` event semantics exist and now carry BR009-aligned client-facing alarm labels; no authoritative real battery/device proof | `PARTIAL` | Real battery/event ingestion + integration verification of thresholds | RTL/RTL Master evidence | `ed82a7b` (label alignment only) |
| BR003 | 7 | Enable message forwarding | Per-user state + auth + audit exist; no real RTL Master forwarding | `PARTIAL` | Send/reflect real forwarding state and verify startup delivery | SMS/RTL Master contract | — |
| BR004 | 7 | Disable message forwarding | Per-user state + auth + audit exist; no real RTL Master action | `PARTIAL` | Real disable operation and delivery-stop verification | SMS/RTL Master contract | — |
| BR005 | 7 | Technician programs assigned RTL only | Assignment scope is enforced; Program request/lifecycle exists, now with server-side UID/transformer-name validation (FS-PROG-1); physical program absent | `PARTIAL` | Real programming transport + result confirmation | SMS/RTL Master contract | `176dc49` (validation only) |
| BR006 | 7 | RTL reports battery voltage every 24h | No authoritative 24h battery telemetry integration | `MISSING` | Receive/store/display real battery voltage and verify cadence | RTL/RTL Master data | — |
| BR007 | 7 | RTL Master monitors RTLs on active list | Local active state exists; no authoritative RTL Master active-list integration | `PARTIAL` | Synchronize/consume authoritative active-list state | RTL Master integration | — |
| BR008 | 7 | Notify registered users after >24h no data | Exact >24h in-app rule exists; external delivery absent | `PARTIAL` | Real active/readings source + registered-recipient delivery | Data and SMS/recipient contract | — |
| BR009 | 7 | Low battery = “Battery Alarm”; other alarms = “Comms Alarm” | `services/event_semantics.py::EventSemantics.alarm_notification_label` now maps `battery_low`→"Battery Alarm" and `power_down`/`sensor_error`→"Comms Alarm" for the Notification Center's `notification_type`, the RTL Alarms (30 Days) report's `Alarm` column, and the summary line — the underlying event type/category (`power_down` vs `sensor_error`) is preserved for bucketing and in each row's `detail` text (e.g. "Power Down — 1 event(s)..."), so no operational distinction is lost | `COMPLETE` | Application-facing semantics only; real event origination/external delivery remain separate BR rows | None (external delivery tracked under BR003/BR004/BR011/BR015) | `ed82a7b`; focused event-semantics/notification/report tests, full non-DB and full DB suites, Administrator + assigned Technician browser verification |
| BR010 | 7 | RTL sends startup message when switched on | Startup/check-in semantics exist; real ingestion absent | `PARTIAL` | Ingest real startup/check-in messages | RTL/RTL Master integration | — |
| BR011 | 7 | Power-down alarm forwarded in real time | Power Down event exists, still represented as a real event/condition (client-facing label now "Comms Alarm" per BR009, underlying `power_down` type unchanged); no production external delivery | `PARTIAL` | Real event + recipient resolution + real-time delivery | RTL Master and SMS contract | — |
| BR012 | 7 | Startup makes RTL active and adds UID to active list | `services/device_event_service.ingest_event()` resolves a persisted startup event and atomically projects it to local `rtl_active_state`; no real RTL Master source/synchronization exists | `PARTIAL` | Connect real startup ingestion and synchronize the authoritative RTL Master active list | RTL Master integration | Local projection tested; no production integration evidence |
| BR013 | 7 | Sensor-range error informs RTL Master | Sensor Error representation exists, still a real event/condition (client-facing label now "Comms Alarm" per BR009, underlying `sensor_error` type unchanged); physical detection external | `EXTERNAL VERIFY` | Verify real RTL/RTL Master event and application ingestion | RTL/RTL Master evidence | — |
| BR014 | 7 | 3 erroneous readings -> stop measurements 24h | Device firmware behaviour, not dashboard logic | `EXTERNAL VERIFY` | Device/integration acceptance evidence | RTL/device firmware | — |
| BR015 | 7 | Forward startup messages to installer phone | Forwarding state + startup semantics exist; no real SMS delivery | `PARTIAL` | Resolve registered phone + deliver startup/check-in SMS | Recipient and SMS contract | — |
| BR016 | 8 | **RTL Master** auto-disables forwarding at 18:30 | Dashboard has no BR016 scheduler or Administrator override; manual forwarding remains a local, authorized preference | `COMPLETE` | Preserve the ownership boundary; real RTL Master execution remains an external integration item | RTL Master integration | `eadf854`; focused forwarding/authorization tests, full non-DB suite, browser verification |

### Current code evidence for the table above

- `services/auth_service.py`
- `services/authorization.py`
- `services/device_scope.py`
- `services/rtl_programming_service.py`
- `services/rtl_command_dispatch_service.py`
- `services/message_forwarding_service.py`
- `services/rtl_deactivation_service.py`
- `services/notification_service.py`
- `services/event_semantics.py`
- `services/notification_delivery.py`

## 5. Programming requirements — §4.4.1

| ID | Requirement | Current state | Status | Remaining work | Dependency | Completion evidence |
|---|---|---|---|---|---|
| PROG-01 | RTL Master MSISDN included in programming data | Manually entered, server-side validated (non-empty, ≤20 chars — the schema's own `VARCHAR(20)` limit) and persisted | `PARTIAL` | Use it in real programming transport; confirm authoritative source/default behaviour | SMS/RTL Master contract | `services/rtl_programming_service.py::_validate_master_msisdn` |
| PROG-02 | 5-digit UID, example `29xxx` | `services/rtl_programming_service.py::record_request` now re-reads the target device's OWN `device_code` from PostgreSQL (never a browser-supplied value, since the drawer's UID field is read-only/pre-filled) and rejects the request unless it is exactly 5 digits (`UID_PATTERN = ^\d{5}$`). No "29" prefix is required — the Functional Specification extract shows `29xxx` only as one worked example, not a rule. All 120 real dev devices already conform (verified directly against the schema; zero conflicts). **REGISTER-UX-1 (ADR-022):** the rule now lives in `services/rtl_uid.py` (`^[0-9]{5}$`, ASCII digits only) and registration enforces it too: live and at Review in `callbacks/device_register.py`, and again in `services/device_registration.py::register_device`. Registration also refuses a code already registered anywhere in the fleet (application-level; no DB constraint). Both are a development baseline, pending client confirmation | `PARTIAL` | Client to confirm (a) the 5-digit rule at registration and (b) whether a UID is unique across the whole network (then add `UNIQUE (device_code)`) | Client confirmation + transport | `176dc49`; REGISTER-UX-1 `c47cf87`; `tests/test_rtl_programming.py::TestUidPatternValidation`, `::TestUidAndTransformerNameServiceValidation`, `tests/test_rtl_uid.py`, `tests/test_device_register.py` |
| PROG-03 | Transformer name max 10 characters | `transformer_code` is already `VARCHAR(10)` at the schema level (`alembic/versions/001_baseline.py`) — no stored transformer name can ever exceed 10 characters. `record_request` now also checks this defensively at the service boundary (before any row is written) as a second, independent layer, matching this repository's existing defense-in-depth pattern (e.g. THRESH-CONFIG-1's CHECK + service validation) | `PARTIAL` | The two proven application-side layers are complete; only production SMS transport of the value remains | Transport only | `176dc49`; `tests/test_rtl_programming.py::TestTransformerNameLengthDefenseInDepth` |
| PROG-04 | Validate UID, registered cell, Technician assignment | Assignment check exists (`services/action_guard.py`, unchanged); UID validity is now enforced (see PROG-02); `users.mobile_number` exists, but no registered-cell/SMS authorization rule is implemented — explicitly out of scope for this gate (no real SMS transport) | `PARTIAL` | Add authoritative contact use and SMS authorization rule | Client contact ownership + SMS contract | — |
| PROG-05 | Send `Program->29xxx->TRFRName` to RTL Master | Command lifecycle exists; no production SMS is sent | `MISSING` | Implement production SMS/RTL Master adapter and truthful result mapping | SMS/RTL Master contract | — |

## 6. Role/access requirements — §5.9

| Role | Functional Specification | Current state | Status | Remaining work | Dependency | Completion evidence |
|---|---|---|---|---|---|
| Administrator | Upload settings to any RTL | Any-device operational authorization exists | `PARTIAL` | Complete real settings/programming transport | SMS/RTL Master contract | — |
| Technician | Program/remove assigned RTL; receive assigned alarms | Assignment-scoped visibility/actions/alarms implemented | `PARTIAL` | Complete real programming/deactivation/external delivery | SMS/RTL Master and recipient contract | — |
| General User | **Only** Log-on, View Transformer Data, Export Data | `ROUTE_POLICY` grants General Users only the monitoring hierarchy and `/reports`; `EXPORT_DATA` remains available and all operational actions remain denied | `COMPLETE` | Preserve §5.9 route, navigation, export and no-action regression coverage | None | `9930ea3`; 297 focused tests, 3,083 non-DB tests, and General User desktop browser verification passed |

## 7. Reports — §4.5.1.1

| ID | Requirement | Current state | Status | Remaining work | Dependency | Completion evidence |
|---|---|---|---|---|---|
| REP-01 | RTL Alarms (30 Days) required columns | Real data-backed report exists; `Alarm` column now BR009-aligned ("Battery Alarm"/"Comms Alarm" only — verified: `power_down`/`sensor_error` never produce a third label); taxonomy fields still not populated | `PARTIAL` | Populate OU/Zone/Sector/CNC/Feeder, real battery data | Production taxonomy and event data | `ed82a7b` (Alarm column alignment only) |
| REP-02 | Installed RTLs required columns | Real data-backed report exists; taxonomy fields intentionally `None` | `PARTIAL` | Populate authoritative taxonomy and confirm RTL Status semantics | Production taxonomy mapping | — |
| REP-03 | Maximum Temperature required columns | Real data-backed report exists; taxonomy missing; current 30-day/custom period is internal assumption | `PARTIAL` | Populate taxonomy; client-confirm period if needed for acceptance | Production taxonomy and client period confirmation | — |
| EXPORT-01 | Export Data; screenshots show `Export to Excel` | CSV + PDF + native XLSX all exist for all three reports (`services/report_export.py::format_xlsx`, openpyxl). XLSX consumes the same `ExportDocument` as CSV/PDF — no query rebuilt; exact column order preserved; None→blank cell, datetime→real Excel datetime (UTC, labelled), numeric→real numeric cell, text→text cell. No client acceptance was needed — XLSX is what the Functional Specification's own UI already shows | `COMPLETE` | None remaining for this row | None | `2d9616d`; new/extended `tests/test_report_export.py` (TestXlsxFormatter, TestWorksheetName), `tests/test_report_export_db.py`, `tests/test_report_export_authorization.py`, `tests/test_report_center.py`; full non-DB and full DB suites; Administrator and General User browser verification (real XLSX downloads opened and inspected) |

Current evidence: `services/report_service.py`, `services/report_export.py`, `services/event_semantics.py`.

## 8. Notifications / active list

| ID | Requirement | Current state | Status | Remaining work | Dependency | Completion evidence |
|---|---|---|---|---|---|
| NOTIFY-01 | Real alerts/notifications to Eskom users | In-app Notification Center + provider-neutral mockable delivery interface | `MISSING` | Production SMS/delivery adapter + recipient resolution | Recipient and SMS contract | — |
| NOTIFY-02 | Forward Startup/Check-In when enabled | Event classified as forwarding-relevant; no real delivery | `PARTIAL` | Connect forwarding state to real startup/check-in SMS | Recipient and SMS contract | — |
| ACTIVE-01 | Switch-on -> active list | Persisted startup events locally activate `rtl_active_state`; no real RTL Master event source or active-list synchronization exists | `PARTIAL` | Connect real startup ingestion and synchronize the authoritative active list | RTL Master integration | Local projection tested; no production integration evidence |
| ACTIVE-02 | Deactivate -> RTL Master removes UID from active list | Local DB true->false state only | `PARTIAL` | Send real deactivation request and confirm result | SMS/RTL Master contract | — |

**Important:** Human alarm acknowledgement currently implemented in the application is an extra internal capability. It does **not** close the Functional Specification's external notification requirements.

## 9. UI/system-overview items

| ID | Item | Current state | Status | Remaining work | Dependency | Completion evidence |
|---|---|---|---|
| UI-01 | Temperature Data Viewer | Monitoring/history/drill-down exists | `PARTIAL` | Connect and verify the authoritative source | Production data integration | — |
| UI-02 | Battery Profile Viewer | No dedicated verified viewer | `MISSING` | Add after real battery telemetry is available | RTL/RTL Master data | — |
| UI-03 | Generate Alarm Reports | 30-day alarm report exists | `PARTIAL` | Complete production fields/data | Production taxonomy and event data | — |
| UI-04 | Auto Update | Page-owned polling/refresh exists. The Functional Specification never defines "Auto Update": it sits under RTL Client beside Eskom Login and Upload Settings, so it may mean client-software self-update rather than page refresh | `CLIENT INPUT` | **Not pursued (user decision 2026-09-19).** Revisit only if the client raises it | Client | — |
| UI-05 | "High" alarm (System Overview → RTL Alarms); §2 purpose: detect overloaded transformers | An Administrator can already set warning/critical temperature limits in Admin Settings → Temperature and vibration (`services/temperature_threshold_service.py`, migration 011, `c83cf94`). **Nothing reads those limits back:** no reading is compared against them, no `high_temperature` event or alarm is raised, no notification is sent. `high_temperature` is deliberately absent from `services/event_semantics.py` and the Command Center's `ELECTRICAL_CONDITIONS` (`services/command_center_service.py`); `MonitoringCondition` stays `UNKNOWN` | `PARTIAL` | Readings are now evaluated against the configured limits (TEMP-CONDITION-1, ADR-023: Normal/Warning/Critical/Limits not set/No recent data, derived, not persisted). Remaining: present it on the pages (redesign Phases 3–5), then persisted High Temperature alarms + notifications | Client confirmation of limit values and who detects | `c83cf94` (configuration); `a0f1223` (evaluation) |
| UI-06 | Weekly Alarm Report (Email) (System Overview → User Interactions) | Not implemented; no scheduled report or email delivery exists | `MISSING` | **Deferred (user decision 2026-09-19):** build only when the client requests it | Client request; email delivery path | — |
| UI-07 | Cloud Storage Archiving (System Overview diagram) | Not implemented. The specification contradicts itself: the diagram shows it, §5.6 says archiving "None" | `CLIENT INPUT` | **Not pursued (user decision 2026-09-19).** Revisit only if the client raises it | Client | — |

## 10. Data-field gaps from §4.1.1

These should be mapped to the correct owning entity before schema changes.

| Field/group | Current state | Action |
|---|---|---|
| Mobile Number | `users.mobile_number` exists and is nullable; it is not yet an authoritative recipient/registration integration | Confirm ownership/verification for SMS workflows |
| Personal Number | Not in authoritative user model | Confirm whether required in new app |
| User ID / Name / Role | Present | Preserve |
| Password | Dev credential config only | Production approach depends on §5.3 Security |
| Notification Type SMS/Email | Delivery interface supports channels; user preference not proven | Add only when authoritative ownership is known |
| RTL UID `29xxx` | Device code exists | Align exact UID rule |
| RTL/MSISDN data | Device metadata + separately-entered Master MSISDN exist | Clarify user/device/master meaning and source |
| Firmware | Metadata support exists | Connect authoritative source |
| OU / Zone / Sector / CNC / Feeder / Feeder Name | Report headers only / unmapped | Production taxonomy mapping required |
| Battery(V) | Event payload possible; no authoritative telemetry | Real battery source required |
| Temperature / last temperature / max temperature | Application model/report calculations exist | Connect real producer |
| RTL Status | Device status exists | Align with authoritative active-list semantics |
| Date Installed | Metadata support exists | Verify authoritative source/population |

## 11. Guidance messages — §4.1.3

| ID | Meaning | Current evidence | Status | Remaining work | Dependency | Completion evidence |
|---|---|---|
| GM001 | Incorrect username/password | Authentication rejects invalid credentials | `PARTIAL` | Verify final source wording | Client acceptance wording | — |
| GM002 | Unauthorized to program logger | Authorization refuses unauthorized programming | `PARTIAL` | Verify final source wording | Client acceptance wording | — |
| GM003 | Request granted; settings sent; forwarding enabled | No real transport/delivery confirmation exists | `MISSING` | Implement end-to-end confirmation; never say sent before real transport succeeds | SMS/RTL Master contract | — |
| GM004 | Enable forwarding | Local preference can be saved | `PARTIAL` | Connect real forwarding command and result | SMS/RTL Master contract | — |
| GM005 | Disable forwarding | Local preference can be saved | `PARTIAL` | Connect real forwarding command and result | SMS/RTL Master contract | — |
| GM006 | UID removed from active list | Local state can become inactive | `PARTIAL` | Confirm RTL Master removal | SMS/RTL Master contract | — |
| GM007 | UID not on active list | Local state can be absent/inactive | `PARTIAL` | Confirm authoritative active-list result | RTL Master integration | — |
| GM008 | User not authorized to delete/deactivate logger | Authorization refuses unauthorized deactivation | `PARTIAL` | Verify final source wording | Client acceptance wording | — |
| GM009 | Blank in source | Functional Specification has no message requirement | `COMPLETE` | No implementation required | None | Source explicitly blank |

## 12. Non-functional requirements — §5

| Section | Source | Current evidence | Status | Remaining work | Dependency | Completion evidence |
|---|---|---|---|
| 5.1 Transaction Volume | “Approximately 4000 application per year?” | Ambiguous source wording | `CLIENT INPUT` | Clarify meaning and actual volume if needed | Client | — |
| 5.2 Performance | TBC | No target supplied | `CLIENT INPUT` | Obtain targets before production sizing | Client | — |
| 5.3 Security | TBC | Development authentication has production safeguards but no client production specification | `CLIENT INPUT` | Obtain production auth/security requirements | Client | — |
| 5.4 Quality Attributes | None | Functional Specification states none | `COMPLETE` | No additional Functional Specification work required | None | Source explicitly states none |
| 5.5 History | None | Functional Specification states none | `COMPLETE` | No mandatory history workflow required | None | Source explicitly states none |
| 5.6 Archiving | None | Functional Specification states none | `COMPLETE` | No mandatory archive workflow required | None | Source explicitly states none |
| 5.7 Frequency | “Adhoc basis?” | Ambiguous source wording | `CLIENT INPUT` | Clarify only if acceptance requires it | Client | — |
| 5.8 Dependencies | TBC | No dependency inventory supplied | `CLIENT INPUT` | Identify production dependencies | Client | — |
| 5.9 Roles | Admin/Tech/General | General User route policy now limits the role to the monitoring hierarchy and report/export surface; operational routes/actions remain denied | `COMPLETE` | Preserve §5.9 authorization regression coverage | None | `9930ea3`; focused route/navigation/action tests and desktop browser verification passed |

## 13. Interface requirements — §7

| ID | Requirement | Current evidence | Status | Remaining work | Dependency | Completion evidence |
|---|---|---|---|
| IF-01 | SMS interface: Program RTL, Message Forwarding, Deactivate RTL | No production adapter or client contract | `MISSING` | Obtain connection/provider details and build production adapter | Client/RTL Master | — |
| IF-02 | Hardware Interfaces N/A | Functional Specification explicitly says N/A | `COMPLETE` | No dashboard hardware interface required | None | Source explicitly states N/A |
| IF-03 | Software Interfaces N/A | Functional Specification explicitly says N/A | `COMPLETE` | No additional software interface required | None | Source explicitly states N/A |
| IF-04 | Module Interfaces TBC | No contract supplied | `CLIENT INPUT` | Ask only if client expects a specific module contract | Client | — |

## 14. Functional Specification acceptance tests — §8

| Test | Current evidence | Status | What closes it | Dependency | Completion evidence |
|---|---|---|
| Positive 1 — login by role | App role login acceptance exists; production auth is unresolved | `PARTIAL` | Production authentication acceptance | Client security requirements | — |
| Positive 2 — switch on RTL -> Master indicates on | No real RTL/RTL Master evidence | `MISSING` | Real RTL/RTL Master test | RTL Master integration | — |
| Positive 3 — Technician enable forwarding | Local preference only | `PARTIAL` | Verify real forwarding | SMS/RTL Master contract | — |
| Positive 4 — Technician program RTL | Local queued request only | `PARTIAL` | Verify real device programming | SMS/RTL Master contract | — |
| Positive 5 — Administrator enable forwarding | Local preference only | `PARTIAL` | Verify real forwarding | SMS/RTL Master contract | — |
| Positive 6 — Administrator program RTL | Local queued request only | `PARTIAL` | Verify real programming | SMS/RTL Master contract | — |
| Positive 7 — >24h no data -> registered user notified | In-app condition only | `PARTIAL` | Verify external delivery | Recipient and SMS contract | — |
| Positive 8 — battery <3.75 -> alarm | No real RTL/event evidence | `EXTERNAL VERIFY` | Real RTL/event test | RTL/RTL Master | — |
| Positive 9 — battery decreases -> power-down alarm | No real RTL/event evidence | `EXTERNAL VERIFY` | Real RTL/event test | RTL/RTL Master | — |
| Negative 1 | Source is internally inconsistent: correct login details but expected access denied | `CLIENT INPUT` | Resolve source defect | Client | — |
| Negative 2 — General cannot enable forwarding | Action policy denies General users | `COMPLETE` | Preserve regression test | None | Authorization tests cover denial |
| Negative 3 — General cannot program RTL | Action policy denies General users | `COMPLETE` | Preserve regression test | None | Authorization tests cover denial |

## 15. Client information still required

Ask only for gaps the Functional Specification does not answer:

1. **RTL Master connection available to the web application** — SMS gateway/modem/API/service mechanism and test environment.
2. **SMS command/response contract** — exact Enable Forwarding, Disable Forwarding and Deactivate commands; success/failure response formats; correlation behaviour.
3. **Real data/event access** — temperature, battery, startup/check-in, alarms and representative samples; UID mapping.
4. **User/contact source** — registered mobile number, Personal Number, Notification Type ownership/source.
5. **Report taxonomy source** — OU, Zone, Sector, CNC, Feeder, Feeder Name mapping.
6. **TBC non-functional items** — Security, Performance, Dependencies and any still-relevant volume/frequency answers.
7. **Maximum Temperature period** — confirm current rolling-30-day + custom-range behaviour if production acceptance depends on it.
8. **Excel export** — confirm whether `Export to Excel` remains required; if yes implement XLSX.
9. **RTL UID rules** — confirm that registration should accept only a 5-digit UID, and whether a UID is unique across the whole network (ADR-022; both enforced in the application as a development baseline, PROG-02).

## 16. Definition of complete

Do **not** declare the project complete because every dashboard screen exists.

The project is complete against this Functional Specification only when:

- §5.9 role/access behaviour matches the source;
- Program RTL, Message Forwarding and Deactivate have truthful real RTL Master/SMS behaviour;
- startup/check-in and active-list behaviour are integrated;
- battery/power-down/sensor-error/no-data workflows are demonstrated using authoritative events/data;
- required user notifications are delivered through the real approved path;
- all three reports contain required fields from authoritative data/mappings;
- export behaviour is accepted against the Functional Specification;
- production-critical TBC items are resolved;
- §8 acceptance scenarios have evidence;
- every applicable row is `COMPLETE` or formally accepted as an external/client responsibility.

## 17. Completion log

Append one row after every successful gate. Never delete previous entries.

| Date | Gate | Requirement IDs closed/advanced | Commit SHA | Verification | Notes |
|---|---|---|---|---|---|
| 2026-09-16 | Initial audit baseline | Tracker created from authoritative Functional Specification vs current `main` | — | Functional Specification + GitHub inspection | No application code changed |
| 2026-09-16 | FS-TRACKER-ADOPT-1 | Tracker authority adopted; BR012 and ACTIVE-01 corrected to `PARTIAL`; General User/BR016 conflicts confirmed | `7d684e0` | 17 focused context tests passed; context-pack structural check clean | Documentation/context only; no application/runtime change |
| 2026-09-16 | FS-SCOPE-1 | `FS-SCOPE-1`; General User §5.9 role scope | `9930ea3` | 297 focused authorization/navigation/action tests; 3,083 non-DB tests; General User desktop browser verification | Notifications, Command Center and Command Center Locations are denied by trusted-session route policy and absent from General User navigation; report/export remains available |
| 2026-09-17 | FS-BR016-1 | `FS-BR016-1`; BR016 ownership | `eadf854` | 192 focused forwarding/authorization/migration tests; full non-DB suite exit 0; Administrator and Technician browser verification | Dashboard scheduler and Administrator override removed; manual per-user preference and Admin/Technician authorization retained. Real RTL Master cutoff execution remains external integration work. |
| 2026-09-17 | FS-PROG-1 | `FS-PROG-1`; PROG-02/PROG-03 application-side validation advanced; PROG-01, PROG-04, BR005 evidence updated | `176dc49` | 15 focused programming-validation tests + full existing programming/command-lifecycle/authorization suites; `python -m pytest -m "not db"` exit 0; full suite (DB included) exit 0 against real reset dev DB; `git diff --check` clean; `python scripts/build_context_pack.py --check` CLEAN; Administrator and assigned-Technician browser verification (device `plant-01-t3-d2`, UID `29005`) | `services/rtl_programming_service.py::record_request` now re-reads the target device's own `device_code`/`transformer_code` from PostgreSQL and rejects a request unless the UID is exactly 5 digits and the transformer name is ≤10 characters, before any row is written. No "29" prefix invented. All 120 real dev devices/71 transformers already conform — verified directly, zero data conflicts, nothing rewritten. Real SMS/RTL Master transport (PROG-05) remains out of scope and MISSING. |
| 2026-09-17 | FS-ALARM-1 | `FS-ALARM-1` COMPLETE (application-facing only); BR002/BR009/BR011/BR013/REP-01 evidence updated; BR009 corrected from `CONFLICT` to `COMPLETE` | `ed82a7b` | Focused event-semantics/notification/report tests + full regression (event_semantics, notification_service, rtl_alarms_report ×2, report_export_db, event_consumption_db, alarm_acknowledgement_db, device_event_ingestion_db); `python -m pytest -m "not db"` exit 0; full suite (DB included) exit 0 against real reset dev DB; `git diff --check` clean; `python scripts/build_context_pack.py --check` CLEAN; Administrator and assigned-Technician (`demo.tech01`) browser verification against real persisted alarm events, including a live acknowledgement | `services/event_semantics.py::EventSemantics.alarm_notification_label` maps `battery_low`→"Battery Alarm", `power_down`/`sensor_error`→"Comms Alarm" (BR009's exact two-way split) for the Notification Center and the RTL Alarms (30 Days) report, while the underlying event type/category stays distinct for bucketing and each row's `detail` text. A real defect was caught only by browser verification and fixed within this gate: the Notification Center summary line was walking the raw per-category label list and silently dropping Comms Alarm counts; new `event_semantics.summary_notification_labels()` fixes it. Startup/check-in remains non-alarm. No schema change. |
| 2026-09-17 | FS-EXPORT-1 | `FS-EXPORT-1`/`EXPORT-01` PARTIAL → `COMPLETE` | `2d9616d` | New/extended `tests/test_report_export.py` (`TestWorksheetName`, `TestXlsxFormatter`), `tests/test_report_export_db.py` (real end-to-end XLSX), `tests/test_report_export_authorization.py` (format parametrization extended), `tests/test_report_center.py`; `python -m pytest -m "not db"` exit 0; full suite (DB included) exit 0 against real reset dev DB; `git diff --check` clean; `python scripts/build_context_pack.py --check` CLEAN; Administrator (RTL Alarms 30 Days) and General User (Installed RTLs) browser verification — real `.xlsx` downloads independently opened and inspected with `openpyxl.load_workbook` outside the app | `services/report_export.py::format_xlsx` (openpyxl) is a third registered formatter consuming the identical `ExportDocument` CSV/PDF already build — no report query rebuilt. Single worksheet, exact `config/reports.py` column order, no metadata preamble (mirrors CSV's shape, not PDF's). Domain-native cell typing via new `_xlsx_value()`: `None`→truly blank cell, numeric→real numeric cell, `datetime`→real UTC/tz-naive Excel datetime with a `"UTC"`-labelled number format. `callbacks/report_center.py` needed zero changes — the pipeline was already format-neutral. A duplicated, independently-hardcoded copy of the export-format honesty text was found in `pages/report_center.py`'s banner (not sourced from `EXPORT_FORMAT_LABEL`) and fixed to single-source it. CSV/PDF behavior, `EXPORT_DATA` authorization, and Maximum Temperature's resolved-period consistency all unchanged and reverified. |
| 2026-09-18 | REGISTER-UX-1 | PROG-02 advanced: registration now enforces the shared 5-digit UID rule and fleet-wide uniqueness (still `PARTIAL`, pending client confirmation) | `c47cf87` | `python -m pytest -m "not db"` exit 0; full suite (DB included) exit 0; `python scripts/build_context_pack.py` CLEAN; Administrator browser verification of form, duplicate refusal, Review, Submit and all four success actions | ADR-022. One rule in `services/rtl_uid.py` (`^[0-9]{5}$`) used by registration and programming; `device_code_problem()` refuses a code registered anywhere in the fleet, naming its plant and transformer. Application-level only, no schema change. Client question added to §15. |
| 2026-09-19 | FS-GAP-RECHECK-1 | Re-read of the Functional Specification found System Overview items the tracker lacked: UI-05 High alarm (`PARTIAL`), UI-06 Weekly Alarm Report email (`MISSING`, deferred), UI-07 Cloud Storage Archiving (`CLIENT INPUT`, not pursued); UI-04 Auto Update re-marked `CLIENT INPUT` (meaning undefined) | — | Functional Specification + code inspection | Documentation only. UI-06/UI-07/UI-04 left out of §15 client questions by user decision; raise only if the client does. |
| 2026-09-19 | DATA-REFRESH-1 | None closed — development data only (Phase 1 of the Fleet Overview + Command Center redesign) | `a2eade4`..`849313b` | Non-DB and full suites exit 0 on the canonical seed; real run against the local dev DB (counts in `docs/context/ACTIVE_GATE.md`) | Simulated events are synthetic and go through `ingest_event()` (ADR-019); they are not evidence for any BR row. |
| 2026-09-19 | TEMP-CONDITION-1 | UI-05 advanced (still `PARTIAL`): temperature condition evaluated against Administrator limits | `38d3fbd`, `a0f1223` | Non-DB and full suites exit 0; real-data check recorded in `ACTIVE_GATE.md` | ADR-023 amends ADR-001 and the `AGENTS.md` data rule. Not yet shown on any page. |
| 2026-09-19 | CC-NEW-1 | UI-05 advanced (still `PARTIAL`): temperature condition now shown on the new Command Center; BR008 and BR009 alarms surfaced as a ranked problem list | `1c5621a`..`e5bd7e7` + fix | Non-DB and full suites exit 0; three-role browser check recorded in `ACTIVE_GATE.md` | New page lives at `/command-center-new` beside the old one until redesign Phase 6. |
