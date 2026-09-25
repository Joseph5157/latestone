# Client Clarification Pack 1

- Date: 2026-09-25
- Status: **DRAFT — for internal review before client sharing**
- Current position:
  - Application-layer dashboard features are substantially implemented and
    tested. As of this document, the internal project audit
    (PROJECT-AUDIT-1) recorded 33 requirements COMPLETE, 24 PARTIAL, 16
    MISSING, 7 with a known defect, 5 blocked on a client decision, and 3
    blocked on an external system, out of 89 assessed items.
  - The project is **not yet connected to a real RTL Master or to any
    production Eskom enterprise system**. Everything that looks like a live
    device today (RTL programming, message forwarding, device events) is a
    development simulator that never leaves this application.
  - **No real device or enterprise-provider integration will be claimed as
    complete until it has been tested against a client-approved endpoint or
    environment.** A working simulator is evidence that our side is ready
    to connect — it is not evidence that a connection exists.

This document exists to prepare one meeting where Eskom can answer the
handful of questions that are actually stopping us from moving further,
so we stop guessing and stop drifting from what was actually asked for.

---

## Executive decision summary

| Priority | Decision | Why it matters | What remains blocked until answered |
|---|---|---|---|
| 1 | **C-05 — RTL Master transport contract** | Nothing we build can talk to a real RTL Master, a real RTL device, or send a real SMS until we know the channel and message format Eskom has approved. | Real command dispatch (RTL Programming), real message forwarding delivery, real device-event ingestion, real-time power-down alerts, and every other feature that depends on talking to the field. |
| 2 | **C-06 — Who owns user identity in production** | Determines whether logins come from Eskom's own identity system (Microsoft Entra ID) or from this application's own user table. | The permanent login/credential design; whether a separate password/credential store is even needed. |
| 3 | **C-07 — Client hierarchy field mapping (OU / Zone / Sector / CNC / Feeder)** | Our reports already have columns for these fields; we do not know what real values to put in them. | Truthful population of report columns; any plan to migrate to Eskom's real data structure. |
| 4 | **C-10 — Notification handling and retention** | Determines whether a notification needs to be acknowledged, escalated, or expired, and how long records must be kept. | Any notification lifecycle feature (retention, escalation, "resolved" status) beyond what exists today. |
| 5 | **C-02 — Vibration metric contract** | We built the framework to support a vibration reading, but we do not have the sensor's actual data contract. | Turning the vibration metric on for real devices. |

Lower-priority open questions are listed in **Other open decisions** below;
none of them block current engineering the way the five above do.

---

## Decision 1 — C-05: RTL Master transport contract

### In plain language

Today, when someone in the dashboard clicks "Program RTL" or turns on
message forwarding, the application records that request honestly in its
own database and stops there — it does not send anything to a real device.
A development-only simulator can be switched on to pretend a message was
sent and acknowledged, purely so we can test the rest of the application;
it is clearly labelled "Simulated" everywhere it appears and has no button
anywhere a real user would see.

This is the single biggest reason real device integration cannot proceed.
Every feature that eventually needs to reach a physical RTL or receive data
from one is waiting on this one decision. The Functional Specification
confirms that SMS is the interface concept for RTL Programming, Message
Forwarding, and Deactivate RTL, but it does not specify the message format,
the RTL Master's endpoint, or how a reply or failure would be recognised —
so we cannot build the real connection without more detail from Eskom.

### What we are asking for

For every item below, we need either a confirmed answer or a pointer to
where in Eskom's existing systems the answer already lives.

| Client answer / evidence needed | Why we need it | Work unlocked after confirmation |
|---|---|---|
| Approved protocol and endpoint/environment (e.g., which SMS gateway, or another confirmed channel) | The application has no transport built in; it needs a real destination to send to and a real source to receive from. | Building the first real `DeviceTransport` adapter instead of the current test-only simulator. |
| Inbound telemetry and outbound command message/payload formats | The Functional Specification names SMS conceptually (§7.5) but supplies no message schema. Without a format, any message we send would be guessing. | Real RTL Programming, Message Forwarding, and Deactivate RTL commands that a physical RTL Master would actually understand. |
| Device identity/mapping rules | The spec confirms RTL devices identify themselves by a 5-digit UID (e.g., UID: 29xxx) and that RTL Programming also checks the requester's registered cellphone number. We need to know exactly how that identity check should work end-to-end in production, and whether anything besides UID + cellphone number is required. | Correctly matching an incoming or outgoing message to the right device and the right authorised user. |
| Authentication, certificates, network/TLS requirements | No transport exists yet, so nothing has been secured — there is nothing to secure until we know what we are connecting to. | Building the connection in a way that meets Eskom's security requirements from the start, rather than retrofitting it later. |
| Command acknowledgement, failure, timeout, and retry rules | The application already models a command lifecycle (queued → sent → acknowledged → succeeded/failed/timed out), but retries are currently switched off on purpose because no approved retry policy exists. A command that times out today cannot currently be reconciled if a real, late acknowledgement arrives afterward. | Turning on real retry behaviour, and deciding what should happen if an acknowledgement shows up after we already gave up on a command. |
| Test devices or a safe test environment | We cannot verify a real integration without something real, or a sanctioned stand-in, to test against. | The first genuine end-to-end test of device communication, rather than another simulation. |
| Named technical contact and acceptance process | Once a transport is built, someone on Eskom's side needs to confirm it actually works against the real system and sign off on it. | A clear, agreed way to call this integration "done," instead of an internal judgment call. |

---

## Remaining high-priority decisions

### C-06 — Production identity/role-source ownership

- **The client decision needed:** Should production logins and roles come
  from Microsoft Entra ID, from this application's own database, or from
  another Eskom-owned identity source?
- **Why it matters operationally:** This decides who can prove they are who
  they say they are, and where that proof comes from, before anyone is
  trusted to view plant data or send a command.
- **What the product currently does / deliberately does not do:** Login
  today uses a clearly-labelled placeholder credential system, built so it
  can be swapped out for the real answer without reworking the rest of the
  application. It is not connected to Entra ID or any other identity
  provider.
- **What stays blocked if unanswered:** Any real production login. The
  placeholder cannot be used in production regardless of this answer — the
  only open question is what replaces it.
- **Answer/evidence field:**

  | Client answer / evidence needed | Why we need it | Work unlocked after confirmation |
  |---|---|---|
  | Confirmed identity source (Entra ID / application database / other) | Determines the entire login and role-storage design. | Building the real production authentication adapter. |
  | If Entra ID: tenant, app registration, redirect URI, and access details | These are Eskom-owned and cannot be created by this team. | Actually connecting to Entra ID once approved. |

### C-07 — Client hierarchy field mapping

- **The client decision needed:** How do Eskom's real hierarchy fields (OU
  / Zone / Sector / CNC / Feeder / Feeder Name) map onto this application's
  plant/transformer/device structure?
- **Why it matters operationally:** These fields already appear as column
  headers in the Installed RTLs and RTL Alarms reports required by the
  Functional Specification. Right now they are shown honestly empty rather
  than filled with guessed values.
- **What the product currently does / deliberately does not do:** The
  application's current hierarchy is plant → transformer → device only. It
  deliberately does not invent an OU/Zone/Sector/CNC/Feeder structure.
- **What stays blocked if unanswered:** Truthful, production-ready values
  in those report columns, and any future data-migration plan toward
  Eskom's real asset structure.
- **Answer/evidence field:**

  | Client answer / evidence needed | Why we need it | Work unlocked after confirmation |
  |---|---|---|
  | Mapping table from OU/Zone/Sector/CNC/Feeder to our plant/transformer records (or confirmation that "Plant" already equals "Feeder") | Without this, report columns cannot be filled truthfully. | Populating those columns for real, and settling the related "Plant vs. Feeder" naming question raised in the second client review. |

### C-10 — Notification acknowledgement/closure/escalation workflow + retention

- **The client decision needed:** What should happen to a notification over
  time — does it need to be acknowledged, escalated if ignored, and for how
  long should records be kept?
- **Why it matters operationally:** Right now, acknowledging an alarm in
  the dashboard is purely an internal record — it does not clear or resolve
  anything, and nothing is escalated or expired automatically. That may or
  may not match what Eskom actually needs operationally.
- **What the product currently does / deliberately does not do:** The
  Notification Center shows real, persisted device events with no
  acknowledgement, retention, or escalation logic layered on top by design,
  because none of that has been confirmed by the client yet.
- **What stays blocked if unanswered:** Any notification lifecycle feature
  beyond the current "view and internally acknowledge" behaviour, and any
  real message delivery (SMS/email), since delivery, retry and retention
  are the same open decision.
- **Answer/evidence field:**

  | Client answer / evidence needed | Why we need it | Work unlocked after confirmation |
  |---|---|---|
  | Required workflow per notification category (acknowledge / escalate / auto-close) | Determines what state machine, if any, needs to be built. | The notification lifecycle feature itself. |
  | Required retention window | Determines how long records must be kept and whether anything needs to be purged or archived. | Retention/archiving logic, if required. |

### C-02 — Vibration metric contract + anomaly thresholds

- **The client decision needed:** The full sensor data contract for
  vibration — what key, unit, aggregation type, axis, reporting cadence,
  and storage shape the real vibration reading will use, plus any anomaly
  threshold values.
- **Why it matters operationally:** Vibration is one of the metrics named
  in the Functional Specification's purpose, but no real sensor contract
  for it has ever been supplied.
- **What the product currently does / deliberately does not do:** The
  metric framework is generic and ready to add a new metric; vibration has
  deliberately not been activated because activating it without a real
  contract would mean displaying invented numbers.
- **What stays blocked if unanswered:** Turning vibration on for any real
  device.
- **Answer/evidence field:**

  | Client answer / evidence needed | Why we need it | Work unlocked after confirmation |
  |---|---|---|
  | Full vibration sensor contract (key, unit, aggregation, axes, cadence, storage) and any threshold values | Without a real contract, the metric cannot be turned on honestly. | Building and activating the vibration metric end to end. |

---

## Scope confirmation — enterprise integrations

The five items below appear in earlier planning material (the PAD-based
build plan) but the Functional Specification — which is the authoritative
client requirement document for RTL functionality — does not mention any
of them. We need an explicit confirmation of whether each is actually part
of the current delivery, a later phase, or out of scope, so we stop
carrying five unconfirmed integrations as if they were agreed requirements.

| Integration | Required now (yes/no/phase-later) | Notes |
|---|---|---|
| Microsoft Entra ID | | Login is currently a placeholder, deliberately isolated so it can be replaced. See C-06 above — this is the same decision. |
| SAP HR | | No code, no interface, no stub exists for this today. |
| Maximo (inbound — asset details) | | No code, no interface, no stub exists for this today. |
| Maximo (outbound — asset condition, possibly via eDNA/PowerOn) | | Three possible destination systems were named in planning material; none has been confirmed. No code exists for any of them. |
| Microsoft Exchange/email | | The Functional Specification names only SMS as the interface; email is not mentioned there at all. |

Please confirm for each row:
1. required for the current delivery;
2. required in a later phase; or
3. out of scope.

---

## Other open decisions

Lower-priority items, grouped by topic. None of these currently blocks a
piece of engineering work the way the five decisions above do, but each
still needs an eventual answer.

**Report content and format**
- **C-04** — Production report output format (CSV / Excel / PDF / a
  combination) and any retention requirement for generated reports. A
  working default (PDF + CSV, no retention yet) exists but is not
  client-confirmed.
- **C-15** — The reporting period for the Maximum Temperature report. A
  working default (rolling 30 days, with a custom range option) exists but
  is not client-confirmed.
- **Q6** — Whether "Plant" in the application should be renamed "Feeder" or
  "Feeder Name" to match the client's terminology — depends on the C-07
  mapping above.
- **Q8** — Whether "Power Down" should be shown as its own alarm category,
  separate from "Comms Alarm" (the Functional Specification currently
  groups them together).
- **Q9** — What the Notification Center should actually list: device
  events (today's behaviour), application-generated notices, or records of
  messages actually delivered by SMS/email.

**Detection, thresholds, and monitoring semantics**
- **C-01** — The confirmed numeric high-temperature warning/critical
  threshold values (the configurable framework already exists; only the
  real values are missing).
- **C-03** — The full rule set for anomaly detection beyond comms/freshness
  checks.
- **C-09** — Whether the application itself should monitor the RTL "active
  list," or whether that is purely the RTL Master's responsibility.
- **Q7** — Whether different RTLs report on different schedules, and if so,
  which RTLs and at what interval (affects per-device freshness settings).

**Operational ownership**
- **C-13** — Who owns remediation of invalid or unregistered device UIDs in
  production (currently an administrator-only development default).
- **C-14** — Whether the programming screens should show the transformer
  name or its code.

**Non-functional and compliance**
- **C-11** — Real transaction volume, reading frequency, and latency
  targets (the Functional Specification's own volume figure is marked
  uncertain).
- **C-12** — The approved browser support list.
- **C-16** — Remaining "TBC" items in the Functional Specification itself.
- **C-17** — Which Eskom security standards apply, and what evidence is
  required to demonstrate compliance.

---

## Proposed 60-minute meeting agenda

1. Current project position — 5 minutes
2. C-05 transport contract — 20 minutes
3. C-06, C-07, C-10, C-02 — 20 minutes
4. Enterprise-scope confirmation — 10 minutes
5. Owners, evidence, dates, and next steps — 5 minutes

---

## Meeting outcome record

| Question ID | Decision | Owner | Evidence/location | Target date | Status |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |

---

## Appendix — implementation boundary

- The current simulator and application-layer mechanisms (the protocol-
  neutral command lifecycle, the simulated device-event source, and the
  mock notification delivery interface) are useful for development and
  demonstration. They let us build and test the rest of the application
  while the real transport decision is pending.
- They are **not** evidence of a live Eskom device or enterprise
  integration. A simulated command "succeeding" only means our own test
  code reported success — it does not mean a physical RTL received or did
  anything.
- The team will **not** create simulated production adapters merely to
  mark a blocked requirement complete. A requirement stays honestly
  MISSING or BLOCKED_CLIENT/BLOCKED_EXTERNAL until it is tested against a
  real, client-approved endpoint or environment.
