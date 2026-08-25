# REQ-1A — Authoritative Client Requirement Inventory

**Project:** Powerplant / Remote Temperature Logger (RTL)  
**Purpose:** Establish the authoritative client requirement baseline before comparing the requirements against the current codebase.  
**Status:** Baseline established  
**Primary sources:**
1. `Remote Temperature Logger Functional Specification RTL v0.3.pdf`
2. `DEM-2788838 Digital Incubator - RTL PAD v0.7(1).pdf`

---

## 0. Source Interpretation Rule

Use the client documents as the source of truth.

The PAD lists the Functional Specification as a normative reference. Therefore:

- Use the **Functional Specification** as the primary source for functional/business behaviour.
- Use the **PAD** primarily for target architecture, integration, security, deployment, data architecture, and broader target-state requirements.
- Do not invent requirements where the documents are silent.
- Do not invent thresholds, workflows, acknowledgement rules, escalation rules, report formats, or production integration behaviour.
- Mark unresolved items as **CLIENT CLARIFICATION REQUIRED** rather than guessing.

This file is **REQ-1A only**. It does not judge the current codebase.  
The next phase, **REQ-1B**, should map every requirement to:

- COMPLETE
- PARTIAL
- NOT IMPLEMENTED
- DEFERRED
- CLIENT CLARIFICATION REQUIRED

---

# 1. Product Purpose and System Boundary

| ID | Client requirement / intent | Source | Classification |
|---|---|---|---|
| RTL-PUR-01 | Automate transformer temperature data collection and analysis | Functional Spec §2 | Core business |
| RTL-PUR-02 | Reduce the need for frequent physical transformer site visits | Functional Spec §2 | Business outcome |
| RTL-PUR-03 | Detect transformer performance problems/anomalies and generate alarms | Functional Spec §2 | Core business |
| RTL-PUR-04 | Allow users to view collected RTL/transformer data | Functional Spec §2 | Core application |
| RTL-PUR-05 | Allow users to export collected data | Functional Spec §2 | Core application |
| RTL-PUR-06 | Allow authorized users to upload/configure RTL settings | Functional Spec §2 | Core operation |
| RTL-PUR-07 | Send alerts/notifications to Eskom users | Functional Spec §2 | Core operation |
| RTL-PUR-08 | Monitor and analyse transformer temperature and vibration | PAD §6.3.1 | Target functional scope |
| RTL-PUR-09 | Provide reporting for recorded temperature and vibration readings | PAD §6.3.1 | Target functional scope |
| RTL-PUR-10 | Configure RTL devices through the RTL application | PAD §6.3.1 | Target functional scope |

### Client system model

The Functional Specification describes three conceptual parts:

```text
RTL Device
    ↓
RTL Master
    ↓
RTL Client
```

- **RTL Device:** sensing device installed on transformer tank.
- **RTL Master:** receives, stores and analyses RTL data and generates alarms.
- **RTL Client:** allows users to view/export data and perform authorized RTL configuration and feature operations.

The PAD evolves this toward a web-based RTL Application and enterprise target architecture.

---

# 2. Functional Specification Business Requirements BR001–BR016

These IDs are the client's own requirement identifiers and must retain their original traceability.

| ID | Requirement | Domain |
|---|---|---|
| BR001 | System must authenticate users | Authentication |
| BR002 | RTL sends a battery-low alarm below **3.75 V** and enters power-down below **3.61 V** | Device / alarms |
| BR003 | RTL Master allows users to enable message forwarding | RTL operations |
| BR004 | RTL Master allows users to disable message forwarding | RTL operations |
| BR005 | Technician can programme only an RTL assigned to that technician | Authorization / programming |
| BR006 | RTL reports battery voltage every 24 hours | Device telemetry |
| BR007 | RTL Master monitors data received from all RTLs on its active list | Monitoring |
| BR008 | RTL Master notifies registered users when an RTL on the list has failed to send data for more than 24 hours | Notifications |
| BR009 | Battery-low event produces a Battery Alarm; other alarms produce a Comms Alarm notification | Notifications |
| BR010 | When an RTL is switched on it sends a message to the RTL Master | Device lifecycle |
| BR011 | Continued battery decline causes power-down and a Power Down alarm, forwarded in real time | Device / notification |
| BR012 | When an RTL is switched on, the RTL Master considers it active and adds the UID to the active list | Active-list management |
| BR013 | RTL detects erroneous/out-of-range temperature readings and informs the RTL Master | Sensor validation |
| BR014 | After three consecutive erroneous temperature readings, RTL stops measurements for 24 hours before retrying | Device protection |
| BR015 | During installation, a user can have startup messages forwarded to their phone and later disable the feature | Installation workflow |
| BR016 | RTL Master automatically disables message forwarding at 18:30 / 6:30 PM daily | Automation / forwarding |

### Functional grouping

```text
AUTHENTICATION
BR001

DEVICE / TELEMETRY
BR002
BR006
BR010
BR012
BR013
BR014

MONITORING
BR007

NOTIFICATIONS / ALARMS
BR008
BR009
BR011

DEVICE OPERATIONS
BR003
BR004
BR005
BR015
BR016
```

---

# 3. Role and Authorization Requirements

The Functional Specification defines three roles:

- Administrator
- Technician
- General User

## 3.1 Administrator

| ID | Requirement |
|---|---|
| RTL-ROLE-ADM-01 | Administrator can upload settings to any RTL |
| RTL-ROLE-ADM-02 | Administrator assigns RTL devices to technicians |
| RTL-ROLE-ADM-03 | Administrator can perform operational actions beyond General User capability |

## 3.2 Technician

| ID | Requirement |
|---|---|
| RTL-ROLE-TECH-01 | Technician may program an RTL remotely |
| RTL-ROLE-TECH-02 | Technician programming is restricted to RTLs assigned to that technician |
| RTL-ROLE-TECH-03 | Technician can instruct the RTL Master to remove an RTL from its active list after removal from a transformer |
| RTL-ROLE-TECH-04 | Technician can access/receive alarms from RTLs assigned to them |
| RTL-ROLE-TECH-05 | Technician assignment has operational authorization meaning, not only display meaning |

## 3.3 General User

| ID | Requirement |
|---|---|
| RTL-ROLE-GEN-01 | General User can log in |
| RTL-ROLE-GEN-02 | General User can view transformer data |
| RTL-ROLE-GEN-03 | General User can export data |
| RTL-ROLE-GEN-04 | General User must not be offered RTL programming |
| RTL-ROLE-GEN-05 | General User must not be offered message-forwarding operations |

### Authorization interpretation

The client documents establish both:

```text
WHAT A USER CAN SEE
+
WHAT A USER CAN DO
```

Do not treat route visibility alone as sufficient authorization.

---

# 4. RTL Programming Requirements

| ID | Requirement |
|---|---|
| RTL-PROG-01 | RTL must be programmed before installation |
| RTL-PROG-02 | Programming includes the RTL Master's MSISDN |
| RTL-PROG-03 | Programming includes the RTL's unique five-digit UID (`29xxx`) |
| RTL-PROG-04 | Programming includes transformer name |
| RTL-PROG-05 | Transformer name has a stated maximum length of 10 characters |
| RTL-PROG-06 | Programming request must validate that RTL UID is valid |
| RTL-PROG-07 | Remote programming validates that the user's cell number is registered |
| RTL-PROG-08 | If the user is a Technician, the assigned-device relationship must be validated |
| RTL-PROG-09 | Unauthorized programming must be refused |
| RTL-PROG-10 | Successful programming provides positive confirmation |

### Legacy programming interaction

The Functional Specification shows an SMS interaction equivalent to:

```text
Program -> 29xxx -> TRFRName
```

Treat this as a legacy interaction mechanism around the programming business operation.  
Do not assume the future web UI must reproduce the SMS syntax literally.

---

# 5. Message Forwarding Requirements

| ID | Requirement |
|---|---|
| RTL-FWD-01 | Authorized user can enable message forwarding |
| RTL-FWD-02 | Authorized user can disable message forwarding |
| RTL-FWD-03 | Forwarded startup/check-in messages relate to assigned RTLs |
| RTL-FWD-04 | Message forwarding supports on-site installation verification |
| RTL-FWD-05 | User can disable forwarding after installation work is complete |
| RTL-FWD-06 | System automatically disables forwarding at 18:30 daily |
| RTL-FWD-07 | System gives clear feedback after enable/disable operations |

Related client requirements:

- BR003
- BR004
- BR015
- BR016

---

# 6. Active RTL Lifecycle Requirements

| ID | Requirement |
|---|---|
| RTL-ACT-01 | RTL startup message indicates the device has been switched on |
| RTL-ACT-02 | Startup causes RTL Master to add the RTL UID to the active list |
| RTL-ACT-03 | Active list determines which RTLs the Master monitors |
| RTL-ACT-04 | Authorized user can remove/deactivate an RTL after it is removed from the transformer |
| RTL-ACT-05 | Active-list state is conceptually distinct from administrative device-record state |
| RTL-ACT-06 | Attempt to remove a UID not on the active list should be refused |

Important architectural principle:

```text
DEVICE ADMINISTRATIVE STATUS
≠
RTL MASTER ACTIVE-LIST STATE
```

Do not automatically merge these concepts.

---

# 7. Alarm and Event Requirements

| ID | Event / condition | Expected behaviour |
|---|---|---|
| RTL-EVT-01 | No data for >24h | Notify registered user |
| RTL-EVT-02 | Battery low | Battery Alarm |
| RTL-EVT-03 | Power down | Power-down alarm, real-time forwarding |
| RTL-EVT-04 | Sensor error / out-of-range temperature | Inform RTL Master / user |
| RTL-EVT-05 | Startup | Inform RTL Master and potentially forward |
| RTL-EVT-06 | Check-in | Used especially with message forwarding |
| RTL-EVT-07 | High temperature | Alarm / anomaly handling |
| RTL-EVT-08 | Vibration event | PAD target notification |
| RTL-EVT-09 | Invalid UID | Handle invalid/unregistered device identity appropriately |

The PAD functional decomposition also names:

- Check-In Notifications
- Sensor Error Notifications
- Battery Low Notifications
- High Temperature Notifications
- Vibration Event Notifications

### Important unresolved item

The available client documents do **not** provide a confirmed high-temperature threshold.

Do not invent one.

---

# 8. Monitoring and Data Requirements

## 8.1 User data

Client fields include:

- Mobile Number
- Personal Number
- User ID
- Password
- Name and Surname
- User Role
- Notification Type

## 8.2 RTL/device data

Client fields include:

- UID / five-digit `29xxx`
- MSISDN
- Firmware Version
- Battery Voltage
- RTL Status
- Date Installed

## 8.3 Asset hierarchy

Client fields include:

- OU
- Zone
- Sector
- CNC
- Feeder
- Feeder Name
- Transformer

## 8.4 Reading/event data

Client fields include:

- Temperature
- Alarm Date & Time
- Alarm
- Timestamp of Last Recorded Data
- Last Recorded Temperature
- Date of Maximum Temperature
- Maximum Temperature

The PAD target data model additionally includes:

- Temperature readings
- Vibration readings
- Device
- Transformer
- Device/Transformer assignment
- Notification type
- User/device assignment

---

# 9. Reporting Requirements

The Functional Specification defines exactly three named reports.

## RTL-REP-01 — RTL Alarms (30 Days)

Required fields:

- OU
- Zone
- Sector
- CNC
- Feeder
- Transformer
- UID
- Battery(V)
- Alarm Date & Time
- Temperature(°C)
- Alarm
- Firmware

## RTL-REP-02 — Installed RTLs Report

Required fields:

- OU
- Zone
- Sector
- CNC
- Feeder Name
- Transformer
- UID
- Timestamp of Last Recorded Data
- Last Recorded Temperature(°C)
- RTL Status

## RTL-REP-03 — Maximum Temperature Report

Required fields:

- OU
- Zone
- Sector
- CNC
- Feeder Name
- Transformer
- Date Installed
- Date of Maximum Temperature
- Maximum Temperature(°C)

### Report interpretation

Treat these as client-defined report contracts.

Do not add additional production reports automatically unless confirmed by the client.

---

# 10. User Experience Requirements

| ID | Requirement |
|---|---|
| RTL-UX-01 | Application uses a web-based user interface |
| RTL-UX-02 | Application is accessible through Eskom-approved browsers |
| RTL-UX-03 | Interface should be easy to navigate |
| RTL-UX-04 | Interface should provide clear error messages |
| RTL-UX-05 | Available UI actions should reflect the user's permitted profile |

The documents define operational behaviour much more strongly than visual styling.  
This gives the project room to later take inspiration from enterprise industrial software without changing client functionality.

---

# 11. Audit Requirements

The PAD states that system user activities should be audited.

| ID | Requirement |
|---|---|
| RTL-AUD-01 | Record system user activity |
| RTL-AUD-02 | Record timestamp |
| RTL-AUD-03 | Record acting user |
| RTL-AUD-04 | Record operation |
| RTL-AUD-05 | Record old/previous values |
| RTL-AUD-06 | Record new values |
| RTL-AUD-07 | Persist audit records in the RTL Application database |

This is a client architecture requirement, not merely an optional enhancement.

---

# 12. Target Integrations

These are primarily PAD target-state integration requirements.

## 12.1 Authentication / employee data

| ID | Target integration |
|---|---|
| RTL-INT-01 | Microsoft Entra ID → RTL Application user authentication |
| RTL-INT-02 | SAP HR → RTL Application employee details |

## 12.2 Asset ecosystem

| ID | Target integration |
|---|---|
| RTL-INT-03 | Maximo → RTL Application asset details |
| RTL-INT-04 | RTL Application → Maximo asset condition |
| RTL-INT-05 | RTL Application → Wonderware eDNA asset condition |
| RTL-INT-06 | RTL Application → PowerOn Advantage temperature alerts |

## 12.3 Notifications

| ID | Target integration |
|---|---|
| RTL-INT-07 | RTL Application → Microsoft Exchange email notifications |
| RTL-INT-08 | RTL Application → SMS Gateway notifications |

## 12.4 Device communication

| ID | Target integration |
|---|---|
| RTL-INT-09 | RTL devices communicate over Eskom/private APN connectivity |
| RTL-INT-10 | MQTT is used for RTL-device / application messaging |
| RTL-INT-11 | Message broker / RabbitMQ receives device messages |
| RTL-INT-12 | Application consumes device messages and persists incoming data |

These should be tracked separately from immediately required prototype functionality.

---

# 13. Application Architecture Requirements

The PAD defines a three-tier target architecture:

```text
PRESENTATION TIER
        ↓
APPLICATION TIER
    - API Layer
    - Business Logic Layer
    - Data Access Layer
        ↓
DATA TIER
```

| ID | Requirement |
|---|---|
| RTL-ARCH-01 | Web Presentation Tier |
| RTL-ARCH-02 | Application Tier |
| RTL-ARCH-03 | API layer within Application Tier |
| RTL-ARCH-04 | Business Logic layer |
| RTL-ARCH-05 | Data Access layer |
| RTL-ARCH-06 | Database/Data Tier |
| RTL-ARCH-07 | Responsibilities should be separated between layers |
| RTL-ARCH-08 | Target application components should support independent scaling, management and deployment |

---

# 14. Security Target Requirements

| ID | Requirement |
|---|---|
| RTL-SEC-01 | Authenticate users using Microsoft Entra ID in target architecture |
| RTL-SEC-02 | Secure browser/application communication with HTTPS |
| RTL-SEC-03 | Encrypt data in transit |
| RTL-SEC-04 | RTL device communication uses private APN connectivity |
| RTL-SEC-05 | Network traffic is filtered by firewalls / NSGs |
| RTL-SEC-06 | RTL devices use a secure bootloader |
| RTL-SEC-07 | RTL devices include physical tamper-resistance controls |
| RTL-SEC-08 | Device data is encrypted at rest and in transit |
| RTL-SEC-09 | Firmware/software security patches and updates are maintained |
| RTL-SEC-10 | RTL Application complies with the Eskom security standards identified in the PAD |

---

# 15. Target Deployment / Infrastructure

The PAD target architecture includes:

- Microsoft Azure
- Azure ExpressRoute
- Azure Firewall
- Virtual Networks
- Private Subnets / NSGs
- Kubernetes
- Separate web application container
- Separate application/backend container
- Database containers / instances
- Primary and replica database
- RabbitMQ / MQTT broker
- Azure Monitor
- Application Insights
- Microsoft Defender for Cloud
- Log Analytics
- Private APN device connectivity

These are target-state infrastructure requirements.

Do not automatically make them the next implementation priority.  
The PAD describes the solution as a pilot whose broader rollout depends on pilot success.

---

# 16. Client Clarification Register

The following items are explicitly unresolved or not sufficiently defined by the available client documents.

## Explicit TBC / unresolved items

- Performance requirements — TBC
- Functional Specification security requirements — TBC
- Dependencies — TBC
- Transaction volume — stated uncertainly
- Frequency — stated uncertainly / ad hoc
- Configuration prerequisites — TBC
- Proposed configuration changes — TBC
- Some software/module interface details — TBC / N/A

## Behaviour not defined well enough to implement safely

- High-temperature alarm threshold
- Vibration metric contract
- Vibration anomaly thresholds
- Full anomaly-detection rules
- Notification acknowledgement workflow
- Notification closure workflow
- Notification escalation workflow
- Notification-history retention
- Production report delivery format
- CSV vs PDF expectations
- Report retention/history requirements
- Final modern replacement for some legacy SMS-based workflows
- Production role-source ownership between Entra ID, application database, or another enterprise service
- Final authoritative production database mapping

These must remain:

```text
CLIENT CLARIFICATION REQUIRED
```

until confirmed.

---

# 17. Product Domain Model

The complete client requirement set naturally divides into seven product domains.

```text
1. IDENTITY & ACCESS
   - Authentication
   - Administrator / Technician / General User
   - Technician-device assignment
   - Route/content/action authorization

2. ASSET & RTL MANAGEMENT
   - Plant / Transformer / RTL hierarchy
   - RTL registration
   - Technician assignment
   - Active-list lifecycle

3. MONITORING
   - Temperature
   - Vibration
   - Battery
   - Communication / freshness

4. RTL OPERATIONS
   - Programming
   - Message forwarding
   - Activation / deactivation

5. EVENTS & NOTIFICATIONS
   - No-data / communications
   - Battery low
   - Power down
   - Sensor error
   - Startup / check-in
   - High temperature
   - Vibration events

6. REPORTING
   - RTL Alarms (30 Days)
   - Installed RTLs
   - Maximum Temperature

7. GOVERNANCE / ENTERPRISE INTEGRATION
   - Audit trail
   - Entra ID
   - SAP HR
   - Maximo
   - Wonderware eDNA
   - PowerOn Advantage
   - SMS / Email
   - MQTT / RabbitMQ
   - Azure target architecture
```

---

# 18. Stable Requirement Families

Use these IDs in all future planning, audits, tests, and implementation prompts:

```text
RTL-PUR-*    Product purpose
BR001-016    Original client business requirements
RTL-ROLE-*   Roles and authorization
RTL-PROG-*   RTL programming
RTL-FWD-*    Message forwarding
RTL-ACT-*    Active-list lifecycle
RTL-EVT-*    Alarms and events
RTL-REP-*    Reporting
RTL-UX-*     User experience
RTL-AUD-*    Audit
RTL-INT-*    Enterprise integrations
RTL-ARCH-*   Application architecture
RTL-SEC-*    Security
RTL-INF-*    Infrastructure / deployment
```

---

# 19. REQ-1A Completion Rule

REQ-1A is complete when:

- all explicit client requirements have a stable identifier;
- requirements are traceable back to the Functional Specification or PAD;
- target-state architecture is separated from current functional requirements;
- unresolved items are not guessed;
- known client ambiguities are entered into the clarification register;
- no codebase implementation status is mixed into this inventory.

**REQ-1A Status: BASELINE ESTABLISHED**

---

# 20. Next Task — REQ-1B

REQ-1B must compare this inventory against the verified current repository baseline.

For every requirement, produce:

| Requirement ID | Requirement | Source | Current implementation evidence | Status | Gap | Recommended action |
|---|---|---|---|---|---|---|

Allowed status values:

- COMPLETE
- PARTIAL
- NOT IMPLEMENTED
- DEFERRED
- CLIENT CLARIFICATION REQUIRED

Important:

1. Inspect the repository; do not rely only on remembered project status.
2. Distinguish UI/prototype behavior from persisted/production behavior.
3. Distinguish authorization for an action from implementation of the action itself.
4. Distinguish schema scaffolding from application wiring.
5. Distinguish target enterprise architecture from immediate pilot implementation.
6. Do not modify code during REQ-1B.
7. Do not create new requirements from assumptions.

The result of REQ-1B should become the authoritative implementation-gap matrix and should determine the next engineering phase.
