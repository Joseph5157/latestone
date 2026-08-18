# RTL Functional Specification Extract — Frontend-Relevant Requirements

Source document: **Remote Temperature Logger Functional Specification RTL v0.3.pdf**
Document identifier: **240-137264801**
Revision: **1**

## Purpose of this extract

This Markdown file is a frontend-focused extraction of the client Functional Specification so that implementation tools that cannot read the PDF can still analyze the confirmed requirements.

This file intentionally preserves the source document's terminology and separates confirmed requirements from items that are still TBC or undefined.

It should be used together with the current repository and the PAD Sections 1–3.4 scope guard.

---

# 1. Business Background and Purpose

The Remote Temperature Logger solution exists to reduce repeated manual transformer temperature checks by automating data collection and analysis.

The Functional Specification describes a system made up of three parts:

1. **RTL device**
   - Temperature sensing device installed on the transformer tank.
   - Communicates with the RTL Master over the cellular network.

2. **RTL Master**
   - Receives data from RTL devices.
   - Stores and analyses the data.
   - Generates alarms as needed.
   - Uploads data to SharePoint Server for access by RTL Client users.

3. **RTL Client**
   - Allows users to view collected RTL data.
   - Allows users to export collected data.
   - Allows authorized users to upload settings to RTL devices.
   - Allows users to enable/disable various system features as permitted.

Functional flow from the source:

- **Input:** Transformer temperature data captured by RTL device.
- **Process:** Data sent to RTL Master, stored and analysed, notifications sent as required/configured, data exposed for users.
- **Output:** Alerts and notifications regarding transformer temperature performance and anomalies.

---

# 2. Confirmed Data Fields

The Functional Specification lists the following fields as involved in the system.

## User / identity-related

- Mobile Number
- Personal Number
- User ID
- Password
- Name and Surname
- User Role
- Notification Type

## RTL / asset-related

- MSISDN RTL Client
- Unit IT 5 digit UID 29XXX
- Firmware Version
- OU
- Zone
- Sector
- CNC
- Feeder
- Feeder Name
- Transformer
- UID
- Battery(V)
- Firmware
- RTL Status
- Date Installed

## Reading / alarm-related

- Alarm Date & Time
- Temperature (°C)
- Alarm
- Timestamp of Last Recorded Data
- Last Recorded Temperature (°C)
- Date of Maximum Temperature
- Maximum Temperature

## Confirmed role values in the field list

- Admin
- Tech
- General

## Confirmed notification type values in the field list

- SMS
- Email

---

# 3. Confirmed Business Requirements

## BR001 — Authentication

**Requirement:** System must authenticate users.

**Rationale:** Prevent unauthorized users and intruders from accessing the system.

## BR002 — Battery low and power-down thresholds

- Battery low alarm below **3.75 V**.
- Power-down mode below **3.61 V**.

## BR003 — Enable message forwarding

RTL Master must allow users to enable message forwarding.

## BR004 — Disable message forwarding

RTL Master must allow users to disable message forwarding.

## BR005 — Technician can program assigned RTL only

Technician must be able to program RTL devices assigned to them only.

## BR006 — Battery reporting frequency

RTL must report battery voltage to RTL Master every **24 hours**.

## BR007 — Active RTL monitoring

RTL Master must monitor data received from all RTLs on its active list.

## BR008 — Missing data notification

RTL Master must notify registered users when an RTL on the active list has failed to send data for more than **24 hours**.

Important: this formal notification condition is separate from the application's existing shorter freshness STALE threshold.

## BR009 — Battery Alarm / Comms Alarm

- Low battery → **Battery Alarm** notification.
- Other alarms → **Comms Alarm** notification.

## BR010 — Device switched-on message

When an RTL is switched on it must send a message to RTL Master.

## BR011 — Power-down alarm

When battery continues to decrease:
- RTL goes into power-down mode.
- Sends **Power down** alarm.
- RTL Master forwards alert to users in real time.

## BR012 — Active list behavior

When switched on, RTL Master must consider the RTL active and add its UID to the active list.

## BR013 — Erroneous temperature detection

RTLs must detect erroneous temperature readings outside the sensor range and inform RTL Master.

## BR014 — Consecutive erroneous readings

After **3 consecutive erroneous temperatures**, RTL stops measurements for **24 hours** before trying again.

## BR015 — Installation message forwarding

During installation, user must be able to enable forwarding of startup messages to their phone, then disable it afterward.

## BR016 — Automatic forwarding disable

RTL Master must automatically disable message forwarding at **6:30 PM daily**.

---

# 4. Guidance / User Messages

- **GM001:** `Please enter the correct user name or password`
- **GM002:** `Request denied. User is not authorised to program this logger.`
- **GM003:** `Request is granted. New settings sent to Unit UID. Message forwarding enabled.`
- **GM004:** `Enable message forwarding.`
- **GM005:** `Disable message forwarding.`
- **GM006:** `Request granted. UID: uid number removed from active list.`
- **GM007:** `Request denied. UID: uid number is not on the active list.`
- **GM008:** `Request denied. User is not authorized to delete this logger.`

---

# 5. Confirmed Runtime Roles and Access

## Administrator

- Real runtime role.
- Can upload settings to any RTL on the system.
- Has broader RTL-management access than Technician.

## Technician

- Can remotely program an RTL.
- Can remove an RTL from active list after removal from transformer.
- Can access/program only RTLs assigned to them.

## General User

- Eskom employee not assigned as Administrator or Technician.
- Can log on.
- Can view transformer data.
- Can export data only.
- Message forwarding/programming options should not be available.

---

# 6. Overall Process Flow — Frontend-Relevant Interpretation

After login, the Functional Specification shows role-based paths.

## Administrator path
Includes concepts such as:
- assign RTL
- manage/program RTL
- enable/disable message forwarding
- view transformer data
- download/export transformer data

## Technician path
Includes:
- work with assigned RTLs
- program assigned RTL
- enable/disable message forwarding
- deactivate/remove RTL from active list
- view transformer data
- download/export transformer data

## General User path
Includes:
- view transformer data
- download/export transformer data

This extract does not invent exact screen count or route structure.

---

# 7. High-Level Requirements

1. Ease of use
2. Validate user authentication
3. Send notifications and alarms
4. Create report

---

# 8. RTL Programming Requirements

Programming involves uploading:

- RTL Master MSISDN number
- 5-digit RTL UID, e.g. `29xxx`
- Transformer name

Transformer-name constraint:
- maximum **10 characters**

Remote programming authorization:
- RTL UID must be valid
- user's cellphone number must be registered
- for Technician, RTL must be assigned to that technician

SMS instruction format shown in source:

`Program->29xxx->TRFRName`

This confirms business behavior, but does not require the web frontend to literally use SMS syntax.

---

# 9. Message Forwarding

Confirmed:
- enable forwarding
- disable forwarding
- used during installation for startup/check-in messages
- automatically disabled at **6:30 PM daily**

The web UI representation is not fully defined.

---

# 10. Device Active-List Behavior

Confirmed:
- RTL Master maintains an active list.
- Switched-on RTL can be added to active list.
- Authorized users can remove/deactivate RTL from active list.
- Active RTLs are monitored.
- Active RTL failing to send data for >24 hours triggers notification.

Do not silently equate:
- lifecycle status
- assignment
- active-list membership
- freshness

unless the backend/domain model confirms equivalence.

---

# 11. Confirmed Reports

## 11.1 RTL Alarms (30 Days) Report

- OU
- Zone
- Sector
- CNC
- Feeder
- Transformer
- UID
- Battery(V)
- Alarm Date & Time
- Temperature (°C)
- Alarm
- Firmware

## 11.2 Installed RTLs Report

- OU
- Zone
- Sector
- CNC
- Feeder Name
- Transformer
- UID
- Timestamp of Last Recorded Data
- Last Recorded Temperature (°C)
- RTL Status

## 11.3 Maximum Temperature Report

- OU
- Zone
- Sector
- CNC
- Feeder Name
- Transformer
- Date Installed
- Date of Maximum Temperature
- Maximum Temperature (°C)

---

# 12. Communications Interface — Frontend-Relevant Business Actions

The source says SMS interaction supports three main functions:

1. RTL Programming
2. Message Forwarding
3. Deactivate RTL

This confirms these business functions, but does not require the web frontend to implement the SMS transport.

---

# 13. Confirmed Testing Scenarios Relevant to Frontend

## Positive
- Login as Technician/Admin/General with correct credentials → UI access based on profile.
- RTL switched on → Master indicates device switched on.
- Technician enables forwarding → enabled.
- Technician programs RTL → programmed.
- Administrator enables forwarding → enabled.
- Administrator programs RTL → programmed.
- RTL sends no data for >24h → registered user notified.
- Battery <3.75V → alarm sent.
- Battery continues decreasing → power-down and alarm.

## Negative
- General User tries to enable forwarding → option not available.
- General User tries to program RTL → option not available.

The source also contains an internally inconsistent login negative-test row: it says correct login details but expected access denied. Do not silently correct it; flag it if used for detailed test design.

---

# 14. Requirements Still TBC / Undefined

The Functional Specification leaves these unresolved:

- Performance requirements
- Security requirements
- Pre-requisites for configuration
- Proposed configuration changes
- Dependencies
- Some module interfaces
- Detailed software interfaces
- Detailed hardware interfaces
- Interface data schema
- Sample file
- History requirements: None
- Archiving requirements: None
- Frequency: `Adhoc basis?`

Do not invent them.

---

# 15. Impact on Existing Frontend Phases

## Phase 3/4 — Device Administration / Registration / Assignment

Newly confirmed:
- Device-to-technician assignment is real.
- Technician may act only on assigned RTL.
- Programming RTL is real.
- Deactivate/remove-from-active-list is real.
- UID is real.
- Transformer is real.
- RTL Status is real.
- Firmware Version is real.
- Message forwarding is real.

Still unresolved:
- production persistence
- API/backend ownership
- complete registration form
- assignment history/audit behavior
- exact distinction between assignment and active-list status

## Phase 5 — User Administration

Confirmed runtime roles:
- Administrator
- Technician
- General User

Still unresolved:
- production identity source
- authentication provider implementation
- user persistence
- full permission matrix
- whether roles come from Entra ID/groups/local system/API

## Phase 6 — Reports

Generic report types can now be aligned to:
- RTL Alarms (30 Days)
- Installed RTLs
- Maximum Temperature

Still unresolved:
- file generation
- output format
- backend report service
- scheduling
- delivery
- retention

## Phase 7 — Notifications

Confirmed conditions:
- >24-hour missing-data notification
- Battery Alarm below 3.75 V
- Power-down below 3.61 V
- sensor/erroneous temperature condition
- startup/check-in messages
- message-forwarding state

Do not equate current STALE freshness with the >24h formal notification rule.

---

# 16. Frontend vs Backend Boundary

## Frontend can implement/design now

- confirmed role labels and prototype role selector
- role-aware visual availability in prototype UX
- confirmed report names/layouts
- device programming action placement
- technician assignment UX
- deactivate/remove-from-active-list UX
- message-forwarding UX
- notification-center categories/layout
- confirmed guidance/error message presentation
- report column specifications

## Frontend design now / backend later

- actual program-device command
- real device-technician assignment persistence
- active-list mutation
- real message forwarding
- >24h notification generation
- battery alarms
- power-down events
- erroneous sensor event generation
- actual report generation/export
- real authorization enforcement

## Blocked on production data/API/backend contract

- production DB schema mapping
- durable users/roles
- durable assignments
- device command transport
- notification history
- alarm event persistence
- report-file generation
- SMS/email delivery
- production authorization source

---

# 17. Rules for OpenCode Analysis

1. Treat this extract as source authority for the requirements listed here.
2. Do not use later PAD sections to expand implementation scope unless explicitly requested.
3. Do not turn TBC items into assumptions.
4. Keep current freshness semantics separate from the formal >24-hour notification rule.
5. Keep prototypes separate from real backend/persistence claims.
6. Preserve working monitoring architecture unless there is a direct source conflict.
7. Report source inconsistencies rather than silently fixing them.
