# Power RTL — Master Build Plan

**Date:** 04 September 2026  
**Project:** Eskom Remote Temperature Logger (RTL) Application  
**Current repository checkpoint:** `e115624abf29702db2f67ddd6bbc787b44b1ca47`  
**Working tree expectation:** only `?? debug.log`  
**Purpose:** Freeze the client-aligned scope, show what is already built, identify what remains, separate build-now work from client-dependent work, and define the order in which the rest of the project should be completed.

---

# 1. Governing Client Documents

This plan is controlled by the following client documents:

1. **Remote Temperature Logger — Functional Specification RTL v0.3**
2. **DEM-2788838 Digital Incubator — RTL PAD v0.7**

When there is a conflict between our implementation ideas and the client documents, the client documents control unless the client formally approves a change.

## Traceability rule

Every future implementation tranche must state:

- Client document
- Page
- Section / BR / table / diagram
- Requirement being satisfied
- What is clear
- What remains unclear
- Whether client clarification is required

We will not invent business rules where the PDFs are silent.

---

# 2. What the Client Asked Us to Build

## 2.1 Core business system

The Functional Specification describes a three-part RTL solution:

- **RTL Device** — installed on a transformer and sends readings/alarms.
- **RTL Master** — receives and analyses RTL data and generates alarms.
- **RTL Client/Application** — allows users to view/export data, upload settings and enable/disable system features.

**Reference:** Functional Specification, p.4.

## 2.2 Core application use cases

The PAD states that the application must support:

1. Monitoring and analysing transformer temperature and vibration.
2. Reporting recorded temperature and vibration readings.
3. Configuration of RTL devices via the RTL application.

**Reference:** PAD, p.20, §6.3.1.

## 2.3 Main functional areas

The PAD functional decomposition includes:

- RTL device operations
- Record/send temperature readings
- Record/send vibration readings
- Configure RTL devices
- RTL device assignment
- Message forwarding
- Temperature anomaly analysis
- Vibration anomaly analysis
- Check-in notifications
- Sensor error notifications
- Battery-low notifications
- High-temperature notifications
- Vibration-event notifications
- RTL Alarms Report
- Installed RTL Report
- Maximum Temperature Report

**Reference:** PAD, p.21, §6.3.2.

---

# 3. Client Roles

## Administrator

Client intent:

- May upload settings to any RTL.
- Administrative access to the fleet.
- Assign RTLs to Technicians.

## Technician

Client intent:

- May program assigned RTLs only.
- May remove an RTL from the active list.
- May receive alarms only for RTLs assigned to them.
- May use message forwarding during installation.

## General User

Client intent:

- Log in.
- View transformer data.
- Export data only.
- No programming.
- No message forwarding.

**Reference:** Functional Specification, p.13, §5.9.

---

# 4. Client Business Requirements

| ID | Client requirement | PDF reference | Current project position |
|---|---|---|---|
| BR001 | Authenticate users | Functional Spec p.7 | **Implemented and hardened** |
| BR002 | Battery Low below 3.75 V; Power Down below 3.61 V | Functional Spec p.7 | **Event semantics/foundation implemented; production source still external** |
| BR003 | Enable message forwarding | Functional Spec p.7 | **Application persistence implemented** |
| BR004 | Disable message forwarding | Functional Spec p.7 | **Application persistence implemented** |
| BR005 | Technician programs assigned RTL only | Functional Spec p.7 | **Implemented and authorization tested** |
| BR006 | RTL reports battery voltage every 24 h | Functional Spec p.7 | **Requires real RTL/device behavior** |
| BR007 | Monitor data from all RTLs on active list | Functional Spec p.7 | **Active-state model exists; monitoring semantics require confirmation** |
| BR008 | Notify registered users after >24 h no data | Functional Spec p.7 | **In-app detection exists; production recipient/delivery rules pending** |
| BR009 | Battery Alarm / Comms Alarm notification behavior | Functional Spec p.7 | **Partial; exact production routing/taxonomy still needs client mapping** |
| BR010 | RTL sends startup message when switched on | Functional Spec p.7 | **Canonical ingestion + simulator implemented; real device source pending** |
| BR011 | RTL sends Power Down alarm and Master forwards in real time | Functional Spec p.7 | **Event foundation implemented; real forwarding pending** |
| BR012 | Startup makes RTL active and adds UID to active list | Functional Spec p.7 | **Application activation projection implemented** |
| BR013 | RTL detects erroneous temperature and informs Master | Functional Spec p.7 | **Sensor-error event path exists; real device generation pending** |
| BR014 | After 3 erroneous temperatures, RTL stops measurements for 24 h | Functional Spec p.7 | **Device/firmware responsibility — client/device confirmation required** |
| BR015 | User can forward startup messages to phone during installation | Functional Spec p.7 | **Underlying preference persistence exists (shared with BR003/BR004); recipient eligibility for forwarding is itself an undefined business rule (not only delivery transport) — REQ-1B rates this NOT IMPLEMENTED, not PARTIAL** |
| BR016 | RTL Master automatically disables forwarding at 18:30 daily | Functional Spec p.8 | **Not implemented; ownership/timezone confirmation required** |

---

# 5. RTL Programming — Client Requirement

The Functional Specification defines programming clearly.

## Programming data

The RTL requires:

- RTL Master MSISDN
- 5-digit RTL UID (`29xxx`)
- Transformer name
- Transformer name maximum: 10 characters

**Reference:** Functional Specification, p.10, §4.4.1.1.

## Legacy/mobile programming

The Functional Specification describes SMS-based programming:

`Program->29xxx->TRFRName`

The RTL Master authenticates:

- UID validity
- registered mobile number
- Technician assignment to the RTL

**Reference:** Functional Specification, p.10, §4.4.1.2.

## New PAD direction

The PAD states:

- the application configures RTL devices,
- RTL devices communicate using MQTT,
- RabbitMQ is the MQTT broker,
- the architecture sends commands to devices.

**References:** PAD p.20, p.29, p.30, p.32.

## What we have built

- trusted authorization
- Technician assignment enforcement
- programming request persistence
- protocol-neutral `rtl_commands`
- command lifecycle
- deterministic SimulatorTransport
- success/failure/timeout simulation
- no fake claim of physical RTL programming

## What is still required

Client must confirm the production programming transport contract:

- MQTT topic(s)
- command payload
- command response/ACK payload
- correlation identifier
- what confirms successful programming
- whether SMS programming remains supported
- whether web programming goes directly to RTL or through RTL Master

---

# 6. MQTT / Device Integration

The PAD explicitly requires MQTT.

## Client-stated architecture

- RTL device uses MTN/Vodacom private APN.
- MQTT is used for RTL device communication.
- RabbitMQ hosts MQTT topics.
- RTL Application consumes messages and stores them.
- Application architecture sends commands to devices.

**References:** PAD p.29–30 and p.32.

## Current implementation

### Completed foundation

- protocol-neutral command entity
- command lifecycle
- DeviceTransport seam
- SimulatorTransport
- canonical NormalizedEvent ingestion
- simulated incoming event source

### Not yet production-connected

- RabbitMQ/MQTT client
- real broker connection
- TLS/authentication
- real topics
- real wire payloads
- real ACK handling
- reconnect/session rules
- production retry/recovery

## Rule

Do not invent Eskom topic names, credentials or payload structure.

---

# 7. Event / Alarm Foundation

## Existing supported simulated event families

- startup
- check-in
- battery low
- power down
- sensor error

## Current architecture

`Simulated event source → NormalizedEvent → device_event_service.ingest_event() → persistence/projections/consumers`

This preserves one canonical event pipeline.

## Still client/device-dependent

- real MQTT producer messages
- high-temperature rule
- vibration rule
- physical battery/power-down device behavior
- exact production alarm taxonomy where ambiguous
- recipient routing

---

# 8. Notifications

## Current state

### Implemented

- Notification Center
- event-driven in-app projection
- provider-neutral `NotificationDelivery`
- SMS / EMAIL internal channel vocabulary
- deterministic mock delivery

### Not implemented

- real SMS Gateway
- real Microsoft Exchange delivery
- production recipient-routing policy
- acknowledgement
- escalation
- retry policy
- delivery retention
- durable delivery table

## Client references

- SMS Notification interface: PAD p.22–24.
- Email Notification interface: PAD p.22 and p.26.
- SMS sequence: PAD p.27.
- Functional notification requirements: Functional Spec p.7.
- Technician receives alarms only for assigned RTLs: Functional Spec p.13.

---

# 9. Message Forwarding

## Client requirement

- Enable forwarding — BR003.
- Disable forwarding — BR004.
- Startup-message forwarding during installation — BR015.
- Automatic disable at 18:30 daily — BR016.

**References:** Functional Specification p.7–8.

## Current state

Implemented:

- per-user forwarding preference
- enable/disable workflow
- authorization
- DB timestamps
- audit

Not implemented:

- actual message delivery
- recipient message contract
- 18:30 automatic disable
- scheduler/worker
- production SMS integration

## Clarification required

Ask the client:

1. Does the new application own BR016's 18:30 automatic disable, or does an existing RTL Master/service own it?
2. Which timezone controls 18:30?
3. Exactly which startup/check-in messages are forwarded?
4. Which phone number/source of recipient data should be used?

---

# 10. Active List / Deactivation

## Client references

- BR007 — monitor all RTLs on active list.
- BR012 — startup adds RTL UID to active list.
- Functional Spec p.13 — Technician may remove an RTL from active list after removal from transformer.
- Guidance messages GM006/GM007 reference removal from active list.

## Current state

Implemented:

- `rtl_active_state`
- startup activation
- deactivation
- idempotent transitions
- audit

Not yet applied globally to:

- fleet freshness
- no-data detection
- alarm generation
- report populations
- hierarchy/device lists

## Clarification required

When an RTL is removed from the active list, should it immediately be excluded from:

- failed-reporting checks
- alarm generation
- fleet-health calculations
- notifications
- reports
- simulator/monitoring populations

Do not assume until client confirms.

---

# 11. Reports

The Functional Specification defines three reports.

## 11.1 RTL Alarms (30 Days)

Fields:

- OU
- Zone
- Sector
- CNC
- Feeder
- Transformer
- UID
- Battery(V)
- Alarm Date & Time
- Temperature
- Alarm
- Firmware

**Reference:** Functional Spec p.12.

**Current state:** substantially implemented; production hierarchy mapping and final format still require confirmation.

## 11.2 Installed RTLs

Fields:

- OU
- Zone
- Sector
- CNC
- Feeder Name
- Transformer
- UID
- Timestamp of Last Recorded Data
- Last Recorded Temperature
- RTL Status

**Reference:** Functional Spec p.12.

**Current state:** substantially implemented; production hierarchy mapping/final format pending.

## 11.3 Maximum Temperature

Fields:

- OU
- Zone
- Sector
- CNC
- Feeder Name
- Transformer
- Date Installed
- Date of Maximum Temperature
- Maximum Temperature

**Reference:** Functional Spec p.12.

**Current state:** not finalized.

## Clarification required

The PDF does not define the period over which "Maximum Temperature" is calculated.

Ask whether it means:

- current day
- previous 24 hours
- 7 days
- 30 days
- user-selected date range
- lifetime since installation

---

# 12. Organisation / Asset Hierarchy

The PAD and Functional Specification use:

- Operating Unit / OU
- Zone
- Sector
- CNC
- Feeder / Feeder Name
- Transformer
- RTL UID

**References:** Functional Spec p.6 and p.12; PAD p.15, p.17, p.23.

## Current project hierarchy

Current product navigation is mainly:

`Plant → Transformer → RTL`

This is useful operational UI, but it must eventually map correctly to the client's organisational hierarchy.

## Client information needed

Confirm authoritative source and mapping for:

- OU
- Zone
- Sector
- CNC
- Feeder
- Feeder Name
- Transformer identifier/name

PAD p.23 indicates AssetDetails comes from Maximo, so final production mapping should align with the Maximo contract.

---

# 13. User Authentication / Identity

## Client target

- Microsoft Entra ID
- authentication tokens
- SAP HR for employee details

**References:** PAD p.22–25 and p.35–36.

## Current state

Implemented:

- application authentication
- signed server-trusted sessions
- DB identity revalidation
- role-based authorization
- production cookie hardening

Not implemented:

- Microsoft Entra ID
- SAP HR employee sync
- client production role source

## Production requirement

Integrate Entra only when the client provides:

- tenant/app registration
- redirect URIs
- claims
- role mapping
- user lifecycle
- required security configuration

---

# 14. Enterprise Interfaces

The PAD specifies the following:

| Interface | Source | Destination | Purpose |
|---|---|---|---|
| AssetDetails | Maximo | RTL Application | Update transformer details |
| AssetCondition | RTL Application | Maximo / eDNA / PowerOn | Update transformer condition |
| EmailNotifications | RTL Application | Microsoft Exchange | Email users |
| SMSNotifications | RTL Application | SMS Gateway | SMS users |
| UserAuthentication | Microsoft Entra ID | RTL Application | Authentication |
| EmployeeDetails | SAP HR | RTL Application | Employee details |

**References:** PAD p.22–24.

## Current state

Application-side seams exist for some of these concepts, but the real enterprise integrations are not connected.

They belong to a later integration phase after interface/access details are supplied.

---

# 15. Security and Audit

## Client requirements

PAD requires:

- HTTPS
- private networking
- Entra authentication
- security standards compliance
- audit trail with timestamp, user, operation, old value and new value

**References:** PAD p.34–36.

## Current state

Strongly implemented:

- route/action authorization
- signed sessions
- trusted server identity
- Technician device scope
- General User restrictions
- production cookie hardening
- audit infrastructure

Remaining production items:

- Entra
- Eskom security-standard verification
- Azure/network deployment
- real transport credentials/secrets
- security acceptance in client environment

---

# 16. Current Project Position

## Major completed foundations

### Application / UX

- Fleet overview
- Command Center
- Plant/Transformer/RTL drill-down
- Device administration
- Device registration
- Technician assignment
- Notifications
- Reports
- Users
- role-aware navigation
- accessibility/error polish

### Security

- role model
- server-side authorization
- Technician scope
- General User read-only behavior
- auth hardening
- production session/cookie hardening

### Operational services

- programming request persistence
- deactivation persistence
- message-forwarding preference
- event ingestion
- audit
- reports
- notifications

### Integration foundation

#### RTL-IF-1
Protocol-neutral command persistence.

#### RTL-IF-2
Command lifecycle + deterministic SimulatorTransport.

#### RTL-IF-3
Simulated incoming events through canonical ingestion.

#### RTL-IF-4
Provider-neutral notification delivery abstraction + mock delivery.

---

# 17. What Is Complete vs What Is Not

## COMPLETE / STRONG

- three roles
- route/action authorization
- Technician assignment scope
- General User restrictions
- registration
- assignments
- fleet UI
- device/transformer monitoring UI
- programming request authorization/persistence
- command foundation
- simulator command lifecycle
- event ingestion foundation
- simulator event source
- notification delivery seam
- audit
- two main report foundations

## PARTIAL / APPLICATION-SIDE IMPLEMENTED

- programming
- deactivation
- forwarding
- alarms
- notification delivery
- reports
- active-list behavior

## PRODUCTION INTEGRATION NOT YET COMPLETE

- MQTT/RabbitMQ
- real RTL programming
- real RTL events
- real SMS
- real email
- Entra
- SAP HR
- Maximo
- eDNA
- PowerOn
- Azure/Kubernetes/network production architecture

## CLIENT-DEPENDENT / CLARIFICATION

- programming MQTT command/ACK contract
- SMS programming retained or replaced
- 18:30 scheduler ownership/timezone
- active-list monitoring semantics
- Maximum Temperature report period
- hierarchy mapping
- production report/export format
- real notification recipient rules
- notification lifecycle
- high-temperature rule
- vibration rule
- production volume/performance expectations
- Eskom security acceptance details

---

# 18. Client Clarification Pack — Priority Questions

**Ordering note (POWER-MASTER-PLAN-1 correction):** the priority order below
was corrected to match `REQ-3I_Clarification_Register.md` §5 ("Engineering-
gate ranking"), the repository's authoritative clarification register, which
explicitly states it supersedes conflicting summaries elsewhere. REQ-3I ranks
C-08 (18:30 ownership) as leading blocker #1 and C-05 (transport contract) as
leading blocker #2 — the original drafting of this section had them reversed.
`docs/context/CLIENT_QUESTIONS.md` itself is internally inconsistent on this
point (its numbered list leads with C-08, but its "Suggested Meeting Priority"
footer leads with C-05) — that inconsistency is a pre-existing repository
issue, noted here rather than silently fixed in that file.

## Priority 1 — Message Forwarding / 18:30

**PDF basis:** BR003, BR004, BR015, BR016; Functional Spec p.7–8.

Please confirm:

- component responsible for automatic 18:30 disable
- timezone
- messages to forward
- recipient rule
- SMS gateway contract

---

## Priority 2 — RTL Programming Transport

**PDF basis:** Functional Spec p.10; PAD p.20 and p.29–30.

**Question:**

The Functional Specification describes SMS-based RTL programming through the RTL Master, while the PAD shows the new RTL Application sending commands to RTL devices through MQTT/RabbitMQ.

Please confirm:

1. Is the SMS programming method still required?
2. Should the web application program the RTL directly through MQTT or through an existing RTL Master?
3. Please provide the production programming MQTT topic, payload and ACK/response specification.
4. What response proves that programming completed successfully?

---

## Priority 2a — MQTT Device Contract

**PDF basis:** PAD p.29–30.

Please provide:

- broker/interface details
- authentication
- TLS requirements
- topic naming
- event payload schema
- command payload schema
- ACK/result schema
- QoS requirements
- retained/non-retained policy
- reconnect/session expectations

---

## Priority 4 — Active List

**PDF basis:** BR007, BR012; Functional Spec p.7 and roles p.13.

Please confirm whether inactive RTLs must be excluded from:

- monitoring
- failed-reporting alarms
- notifications
- fleet health
- reports

---

## Priority 5 — Maximum Temperature Report

**PDF basis:** Functional Spec p.12.

Please define the reporting period for Maximum Temperature.

---

## Priority 6 — Hierarchy Mapping

**PDF basis:** Functional Spec p.6/p.12; PAD p.23.

Please confirm authoritative mapping/source for:

OU → Zone → Sector → CNC → Feeder → Transformer.

---

## Priority 7 — Notification Recipients

**PDF basis:** Functional Spec p.13 and BR008–BR011.

Please confirm:

- who receives each alarm
- whether Administrators receive fleet alarms
- whether Technicians receive only assigned-RTL alarms
- whether General Users receive notifications
- SMS/email selection rules

---

# 19. Build Roadmap

The remaining project should be built in controlled phases.

---

## PHASE A — Requirement Fidelity and Client Decisions

### Goal

Freeze all client ambiguities before production integration.

### Work

- maintain PDF traceability
- issue clarification pack
- record client answers
- update project ledger
- do not invent production protocol/business rules

### Exit condition

Priority client questions answered or explicitly deferred.

---

## PHASE B — Complete Unblocked Application Requirements

### B1 — Report fidelity

Finish exact report layout/field alignment where the client specification is already sufficient.

### B2 — Notification/role fidelity

Ensure in-app alarm visibility follows confirmed role/assignment behavior.

### B3 — Operational guidance messages

Align important user-facing messages with client guidance where appropriate and where not superseded by modern UX.

### B4 — Device lifecycle completeness

Only after active-list semantics are confirmed.

---

## PHASE C — Real RTL MQTT Integration

### C1 — Production transport adapter

Implement the real RabbitMQ/MQTT adapter using the client-supplied contract.

### C2 — Programming delivery

Connect:

`rtl_commands → MQTT → RTL/RTL Master → ACK/result → lifecycle`

### C3 — Incoming events

Connect:

`RabbitMQ/MQTT → protocol parser → NormalizedEvent → ingest_event()`

### C4 — Recovery/resilience

Add only the confirmed:

- retry
- timeout
- reconnect
- duplicate handling
- late ACK handling

### Acceptance

Test with real/sandbox RTL equipment.

---

## PHASE D — Real Notification Integration

### D1 — Recipient resolver

Implement confirmed server-side recipient rules.

### D2 — SMS Gateway

Map Power delivery contract to Eskom SMS interface.

### D3 — Exchange Email

Map Power delivery contract to Microsoft Exchange/approved email interface.

### D4 — Delivery persistence/retries

Only after lifecycle/retention rules are confirmed.

---

## PHASE E — Forwarding Completion

### E1 — Real startup/check-in forwarding

Connect forwarding preferences to confirmed delivery path.

### E2 — 18:30 automatic disable

Implement in the confirmed owner/component and timezone.

### E3 — Restart/idempotency tests

Ensure scheduled behavior is reliable.

---

## PHASE F — Reports Completion

### F1 — RTL Alarms (30 Days)

Finalize exact fields/hierarchy/export.

### F2 — Installed RTLs

Finalize exact fields/hierarchy/export.

### F3 — Maximum Temperature

Implement once period is confirmed.

---

## PHASE G — Identity and Enterprise Integration

### G1 — Microsoft Entra ID
### G2 — SAP HR employee details
### G3 — Maximo AssetDetails
### G4 — Maximo/eDNA/PowerOn AssetCondition
### G5 — production role/user lifecycle

Each integration receives its own contract, tests and acceptance gate.

---

## PHASE H — Production Infrastructure

Align deployment with the PAD target as client environment becomes available:

- Azure
- Kubernetes
- network segmentation
- private endpoints
- ExpressRoute
- firewall rules
- RabbitMQ
- database deployment
- monitoring/logging
- secrets
- backup/recovery
- Eskom security controls
- CI/CD

Do not reproduce unavailable Eskom infrastructure locally as if it were production.

---

## PHASE I — End-to-End Acceptance

Use the client Functional Specification testing scenarios as the final acceptance baseline.

### Required positive flows

- Admin/Technician/General login
- RTL startup
- Technician forwarding
- Technician programming
- Administrator forwarding
- Administrator programming
- >24 h no data
- battery below 3.75 V
- power-down condition

### Required negative flows

- denied authentication/access
- General User cannot forward
- General User cannot program

**Reference:** Functional Specification p.17.

---

# 20. Recommended Next Build Decision

## Do not immediately invent a reference MQTT protocol.

The client PAD already mandates MQTT/RabbitMQ, but the production message contract is absent.

### Recommended immediate sequence

1. **Freeze this master plan.**
2. **Prepare the client clarification pack with PDF page references.**
3. **Send the top priority questions to the client.**
4. While waiting, build only requirements that are already unambiguous.
5. Once MQTT/programming details arrive, begin the real production adapter.
6. Validate against real/sandbox RTL hardware before claiming programming/device integration complete.

---

# 21. Definition of Done

A client requirement is **COMPLETE** only when:

1. Requirement is traced to the client PDF.
2. Application implementation exists.
3. Authorization is correct.
4. Persistence/business behavior is tested.
5. Integration is real where the requirement involves an external system/device.
6. Browser or operator acceptance is complete where applicable.
7. Client-specific ambiguities are resolved.
8. Documentation reflects the actual state.
9. Commit is pushed and remote-verified.

A simulator or mock can make a requirement **IMPLEMENTED / FOUNDATION READY**, but not **production complete**.

---

# 22. Development Workflow From This Point

For every major tranche:

```text
CLIENT PDF REQUIREMENT
        ↓
Requirement / clarification check
        ↓
ACTIVE_GATE
        ↓
Claude Code implementation
        ↓
Focused tests
        ↓
DB / non-DB / full regression
        ↓
Codex verification for high-risk changes
        ↓
Commit
        ↓
Push + remote verify
        ↓
PROJECT_LEDGER update
```

## Model usage

- **Claude Code:** implementation.
- **Codex:** independent verification for migrations, auth/security, device integration and high-risk changes.
- **Free/OpenRouter model:** small inspections/mechanical work when available.
- **ChatGPT:** architecture, requirements analysis, client-PDF traceability and implementation prompts.

---

# 23. Current Freeze Point

As of this plan:

- `RTL-IF-1` — closed / pushed / remote-verified.
- `RTL-IF-2` — closed / pushed / remote-verified.
- `RTL-IF-3` — closed / pushed / remote-verified.
- `RTL-IF-4` — closed / pushed / remote-verified.
- Current authoritative repository checkpoint:
  `e115624abf29702db2f67ddd6bbc787b44b1ca47`.

The RTL integration foundation should remain frozen here until the next tranche is tied explicitly to a client requirement and does not invent missing client protocol/business semantics.

---

# 24. Final Project Direction

The Power RTL project should now be managed as:

```text
CLIENT REQUIREMENTS
        ↓
APPLICATION                    largely mature
        ↓
INTEGRATION FOUNDATION         complete enough to proceed
        ↓
CLIENT-SPECIFIC CONTRACTS      current main dependency
        ↓
REAL RTL / SMS / EMAIL         next production stage
        ↓
ENTERPRISE INTEGRATIONS        later stage
        ↓
ESKOM PRODUCTION DEPLOYMENT    final environment stage
```

The objective is not to build a generic IoT platform.

The objective is to deliver the **RTL Application described by the Eskom Functional Specification and PAD**, with every implementation decision traceable back to those documents and every production integration based on confirmed Eskom interface details.
