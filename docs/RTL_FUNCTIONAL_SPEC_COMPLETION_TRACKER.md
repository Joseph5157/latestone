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
| P0 | `FS-BR016-1` | Correct ownership of 18:30 forwarding auto-disable | `CONFLICT` | Internal / RTL Master |
| P0 | `FS-SMS-1` | Real SMS/RTL Master integration for Program, Forwarding, Deactivate | `MISSING` | Client/RTL Master details |
| P0 | `FS-PROG-1` | Align Program RTL fields/validation to Master MSISDN, UID, transformer name | `PARTIAL` | Internal + transport |
| P0 | `FS-ACTIVE-1` | Startup-driven active list + real deactivation result | `PARTIAL` | RTL Master |
| P0 | `FS-NOTIFY-1` | Real alarm/startup delivery to registered users | `MISSING` | SMS/recipient details |
| P1 | `FS-ALARM-1` | Align alarm semantics to BR002/009/011/013 | `CONFLICT` | Internal + real events |
| P1 | `FS-BATTERY-1` | Real battery voltage + 24h reporting evidence | `MISSING` | RTL/RTL Master |
| P1 | `FS-REPORT-1` | Complete OU/Zone/Sector/CNC/Feeder report data | `PARTIAL` | Production data mapping |
| P1 | `FS-EXPORT-1` | Resolve/implement Excel export shown in client UI | `PARTIAL` | Internal/client confirmation |
| P1 | `FS-BATTERY-VIEW-1` | Battery Profile Viewer | `MISSING` | Real battery data |
| P2 | `FS-AUTH-1` | Production authentication | `PARTIAL` | §5.3 Security TBC |
| P2 | `FS-NFR-1` | Performance/security/dependencies/volume/frequency | `CLIENT INPUT` | Client |

## 4. Business requirements BR001–BR016

| ID | FS page | Requirement | Current code | Status | What closes it | Dependency | Completion evidence |
|---|---:|---|---|---|---|---|
| BR001 | 7 | Authenticate users | Credentialed login, persisted roles, trusted server session, fail-closed authorization | `PARTIAL` | Replace dev credentials with client-approved production authentication when §5.3 is clarified | Client security TBC | — |
| BR002 | 7 | Battery low <3.75V; power-down <3.61V | Battery Alarm/Power Down event semantics exist; no authoritative real battery/device proof | `PARTIAL` | Real battery/event ingestion + integration verification of thresholds | RTL/RTL Master evidence | — |
| BR003 | 7 | Enable message forwarding | Per-user state + auth + audit exist; no real RTL Master forwarding | `PARTIAL` | Send/reflect real forwarding state and verify startup delivery | SMS/RTL Master contract | — |
| BR004 | 7 | Disable message forwarding | Per-user state + auth + audit exist; no real RTL Master action | `PARTIAL` | Real disable operation and delivery-stop verification | SMS/RTL Master contract | — |
| BR005 | 7 | Technician programs assigned RTL only | Assignment scope is enforced; Program request/lifecycle exists; physical program absent | `PARTIAL` | Real programming transport + result confirmation | SMS/RTL Master contract | — |
| BR006 | 7 | RTL reports battery voltage every 24h | No authoritative 24h battery telemetry integration | `MISSING` | Receive/store/display real battery voltage and verify cadence | RTL/RTL Master data | — |
| BR007 | 7 | RTL Master monitors RTLs on active list | Local active state exists; no authoritative RTL Master active-list integration | `PARTIAL` | Synchronize/consume authoritative active-list state | RTL Master integration | — |
| BR008 | 7 | Notify registered users after >24h no data | Exact >24h in-app rule exists; external delivery absent | `PARTIAL` | Real active/readings source + registered-recipient delivery | Data and SMS/recipient contract | — |
| BR009 | 7 | Low battery = “Battery Alarm”; other alarms = “Comms Alarm” | Battery maps correctly; Power Down/Sensor Error are separate client-facing labels | `CONFLICT` | Reconcile notification delivery naming/semantics with BR009 | Internal alignment + real events | — |
| BR010 | 7 | RTL sends startup message when switched on | Startup/check-in semantics exist; real ingestion absent | `PARTIAL` | Ingest real startup/check-in messages | RTL/RTL Master integration | — |
| BR011 | 7 | Power-down alarm forwarded in real time | Power Down event exists; no production external delivery | `PARTIAL` | Real event + recipient resolution + real-time delivery | RTL Master and SMS contract | — |
| BR012 | 7 | Startup makes RTL active and adds UID to active list | `services/device_event_service.ingest_event()` resolves a persisted startup event and atomically projects it to local `rtl_active_state`; no real RTL Master source/synchronization exists | `PARTIAL` | Connect real startup ingestion and synchronize the authoritative RTL Master active list | RTL Master integration | Local projection tested; no production integration evidence |
| BR013 | 7 | Sensor-range error informs RTL Master | Sensor Error representation exists; physical detection external | `EXTERNAL VERIFY` | Verify real RTL/RTL Master event and application ingestion | RTL/RTL Master evidence | — |
| BR014 | 7 | 3 erroneous readings -> stop measurements 24h | Device firmware behaviour, not dashboard logic | `EXTERNAL VERIFY` | Device/integration acceptance evidence | RTL/device firmware | — |
| BR015 | 7 | Forward startup messages to installer phone | Forwarding state + startup semantics exist; no real SMS delivery | `PARTIAL` | Resolve registered phone + deliver startup/check-in SMS | Recipient and SMS contract | — |
| BR016 | 8 | **RTL Master** auto-disables forwarding at 18:30 | Dashboard currently owns scheduler + admin override as internal baseline | `CONFLICT` | Remove/reclassify app ownership or obtain explicit client change; synchronize RTL Master state | Internal code + RTL Master responsibility | — |

### Current code evidence for the table above

- `services/auth_service.py`
- `services/authorization.py`
- `services/device_scope.py`
- `services/rtl_programming_service.py`
- `services/rtl_command_dispatch_service.py`
- `services/message_forwarding_service.py`
- `services/forwarding_auto_disable_service.py`
- `services/rtl_deactivation_service.py`
- `services/notification_service.py`
- `services/event_semantics.py`
- `services/notification_delivery.py`

## 5. Programming requirements — §4.4.1

| ID | Requirement | Current state | Status | Remaining work | Dependency | Completion evidence |
|---|---|---|---|---|---|
| PROG-01 | RTL Master MSISDN included in programming data | Manually entered and persisted | `PARTIAL` | Use it in real programming transport; confirm authoritative source/default behaviour | SMS/RTL Master contract | — |
| PROG-02 | 5-digit UID, example `29xxx` | Device code exists; strict 5-digit/prefix contract is not fully enforced | `PARTIAL` | Align UID validation at programming/registration boundary | Internal validation + transport | — |
| PROG-03 | Transformer name max 10 characters | Transformer code/name exists; exact programming-boundary compliance needs verification | `PARTIAL` | Enforce max 10 chars for value sent to RTL | Internal validation + transport | — |
| PROG-04 | Validate UID, registered cell, Technician assignment | Assignment check exists; `users.mobile_number` exists, but no registered-cell/SMS authorization rule is implemented | `PARTIAL` | Add authoritative contact use and SMS authorization rule | Client contact ownership + SMS contract | — |
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
| REP-01 | RTL Alarms (30 Days) required columns | Real data-backed report exists; taxonomy fields not populated; BR009 labels need review | `PARTIAL` | Populate OU/Zone/Sector/CNC/Feeder, real battery data, aligned alarm labels | Production taxonomy and event data | — |
| REP-02 | Installed RTLs required columns | Real data-backed report exists; taxonomy fields intentionally `None` | `PARTIAL` | Populate authoritative taxonomy and confirm RTL Status semantics | Production taxonomy mapping | — |
| REP-03 | Maximum Temperature required columns | Real data-backed report exists; taxonomy missing; current 30-day/custom period is internal assumption | `PARTIAL` | Populate taxonomy; client-confirm period if needed for acceptance | Production taxonomy and client period confirmation | — |
| EXPORT-01 | Export Data; screenshots show `Export to Excel` | CSV + PDF exist; no native XLSX | `PARTIAL` | Implement XLSX or obtain explicit acceptance that CSV/PDF replace Excel | Client format confirmation | — |

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
| UI-04 | Auto Update | Page-owned polling/refresh exists | `PARTIAL` | Verify refresh against authoritative producer cadence | Production data integration | — |

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
