# RTL client technical input required

**Purpose:** the smallest consolidated set of client decisions and technical artefacts needed to truthfully complete the remaining items in [RTL_FUNCTIONAL_SPEC_COMPLETION_TRACKER.md](RTL_FUNCTIONAL_SPEC_COMPLETION_TRACKER.md).

**Client requirements authority:** *Remote Temperature Logger Functional Specification RTL v0.3*, Unique Identifier `240-137264801`, Revision 1. This list does not derive answers from older PADs or other historical documents.

**How to use this list:** a **BLOCKER NOW** answer unblocks the next real integration slice. **NEEDED BEFORE PRODUCTION** is required before release, but does not need to delay a development integration proof. **ACCEPTANCE CLARIFICATION** resolves an ambiguous Functional Specification statement or acceptance criterion. Please provide sanitized examples wherever a message, payload, or response is requested; never send production credentials in this document or by email.

## Questions for the next client meeting

1. **[BLOCKER NOW]** What client-provided interface lets the web application communicate with the RTL Master, and what development/test environment can we use? Please identify whether it is direct SMS, an SMS gateway, modem, service/API, or another interface, plus its authentication mechanism.
2. **[BLOCKER NOW]** Please provide the complete command/response contract for Program RTL, Enable Message Forwarding, Disable Message Forwarding, and Deactivate RTL: request syntax, success and failure responses, synchronous versus asynchronous behaviour, correlation/reference identifier, timeout and retry rules, and one safe test UID/device.
3. **[BLOCKER NOW]** How does the application receive RTL Master data and events? Provide sanitized real examples for temperature, battery voltage, startup/check-in, Battery Alarm, Comms Alarm, power-down, sensor-error, and active-list state.
4. **[BLOCKER NOW]** How can the application read or synchronize the RTL Master's active list, including startup activation and the acknowledgement returned after deactivation? Is report `RTL Status` derived from that list or another source?
5. **[BLOCKER NOW]** What is the authoritative source for registered users' mobile numbers, Personal Number, and SMS/Email preference; and which users receive each no-data, alarm, and startup-forwarding notification?
6. **[BLOCKER NOW]** What is the real battery-voltage feed, its unit, precision, reporting cadence, and the RTL Master's representation of Battery Alarm and Power Down? Please include BR006's 24-hour reporting evidence and a sanitized sample record/message.
7. **[BLOCKER NOW]** What authoritative mapping supplies OU, Zone, Sector, CNC, Feeder/Feeder Name, and how do those values join to Transformer and RTL UID?
8. **[NEEDED BEFORE PRODUCTION]** What production identity/authentication mechanism is approved, where are Administrator/Technician/General User roles mastered, what test identities are available, and which session and application-relevant security requirements apply?

## A. RTL MASTER / SMS COMMAND INTERFACE

### 1. Integration endpoint and access — BLOCKER NOW

How does the web application communicate with the RTL Master? State whether the required interface is SMS directly, an SMS gateway, modem, service/API, or another client-provided interface. Provide the test/development endpoint or environment and the approved authentication/credential mechanism (through a secure channel).

### 2. Command contract and integration proof — BLOCKER NOW

Provide, for all four commands, the exact command syntax, exact success/failure responses, whether processing is synchronous or asynchronous, any correlation/reference identifier, timeout/retry rules, and a safe test UID/device:

- Program RTL
- Enable Message Forwarding
- Disable Message Forwarding
- Deactivate RTL

The known Functional Specification Program RTL payload remains `Program->29xxx->TRFRName`. We are not asking the client to redefine it; we need only the delivery envelope, any required addressing/encoding, how the response maps to that request, and the operational details needed to send it truthfully.

## B. RTL MASTER -> APPLICATION DATA / EVENTS

### 3. Inbound data/event contract — BLOCKER NOW

How will the application receive data from the RTL Master: push, poll, shared data source, file exchange, or another client-provided mechanism? Supply sanitized real examples and field definitions for:

- temperature readings and battery voltage;
- startup/check-in;
- Battery Alarm and Comms Alarm;
- power-down condition and sensor-error condition; and
- active-list state.

For each example, identify UID/device and transformer identifiers, event/data time and timezone, source/reference identifier if one exists, and whether the record can be repeated or corrected. This is required to map data without inventing a transport or event taxonomy.

## C. ACTIVE LIST

### 4. Authoritative active-list and RTL Status semantics — BLOCKER NOW

How can the application read or synchronize the RTL Master's active list? Specify how startup activation is represented, the acknowledgement/result returned after Deactivate RTL, and whether report `RTL Status` is derived from the RTL Master active list or another authoritative source.

## D. USERS / NOTIFICATION DELIVERY

### 5. Contact and preference authority — BLOCKER NOW

What is the authoritative source for a registered user's mobile number? What does `Personal Number` mean and where is it mastered? Is an SMS/Email preference required, and if so where is that preference mastered and how is it kept current?

### 6. Recipient policy and delivery contract — BLOCKER NOW

For each of these events, who receives the notification: >24-hour no-data, power-down/Comms Alarm, and startup forwarding? Also provide the approved real SMS delivery interface and any response/delivery-status contract. This asks for the client policy; it does not assume an escalation rule.

## E. BATTERY

### 7. Battery telemetry and alarm representation — BLOCKER NOW

Provide the real battery-voltage field/source, unit, precision, actual reporting cadence, and a sanitized battery record/message. Confirm with evidence how BR006's 24-hour reporting is met, and how the RTL Master represents Battery Alarm (`<3.75V`) and Power Down (`<3.61V`).

## F. REPORT TAXONOMY

### 8. Taxonomy source and asset mapping — BLOCKER NOW

What authoritative source/mapping supplies OU, Zone, Sector, CNC, Feeder, and Feeder Name? Show how each value relates to Transformer and RTL UID, including the joining identifiers and ownership of updates.

## G. PRODUCTION AUTHENTICATION / SECURITY

### 9. Production authentication decision — NEEDED BEFORE PRODUCTION

Functional Specification §5.3 is TBC. What identity/authentication mechanism is approved for production; what is the source of Administrator, Technician, and General User roles; which test identities can be used; and what session/security requirements are relevant to this application?

## H. OTHER FUNCTIONAL-SPEC TBC ITEMS

### 10. §5.1 transaction volume — ACCEPTANCE CLARIFICATION

What does “approximately 4000 application per year?” mean, and what actual transaction volumes should be used for acceptance and production planning?

### 11. §5.2 performance — NEEDED BEFORE PRODUCTION

What measurable performance targets apply (for example, expected response times, concurrent users, availability window, and report/export completion time)?

### 12. §5.7 frequency — ACCEPTANCE CLARIFICATION

What does “Adhoc basis?” mean in §5.7, and which activity or reporting frequency does it govern?

### 13. §5.8 dependencies and §7 module interface — NEEDED BEFORE PRODUCTION

Provide the production dependency inventory and identify any required module interface contract. Include client-owned systems and environments on which the application must rely; do not infer a database integration or endpoint from this question.

### 14. Maximum Temperature reporting period — ACCEPTANCE CLARIFICATION

Confirm the required period for the Maximum Temperature report. The current application supports a rolling 30-day/custom selected range, but that period is an internal assumption pending acceptance confirmation.

### 15. Functional Specification acceptance-text defects — ACCEPTANCE CLARIFICATION

Please resolve §8 Negative Test 1, which is internally inconsistent (correct login details but expected access denied), and confirm any final client-facing wording required for the outstanding login/program/deactivate guidance messages. This is a wording/acceptance decision, not a request to change role rules already confirmed in the Functional Specification.

## What we do NOT need to ask again

- The roles are Administrator, Technician, and General User.
- General User scope is log on, view transformer data, and export data; it does not include operational RTL actions.
- The programming UID is five digits.
- Transformer name is limited to 10 characters.
- The known Program RTL syntax is `Program->29xxx->TRFRName`.
- The client-facing alarm names are Battery Alarm and Comms Alarm.
- BR016's 18:30 forwarding cut-off is owned by the RTL Master.
- Excel export is implemented from the Functional Specification requirement.

## Current application boundary

The current implementation deliberately has a protocol-neutral command transport boundary, a provider-neutral notification-delivery boundary, local active-list projection, and event ingestion that expects normalized events. It does not contain a configured production command transport, real RTL Master event source, recipient-resolution policy, authoritative battery feed, taxonomy mapping, or production authentication adapter. The questions above are therefore inputs for integration rather than requests to retrofit an invented production design.
