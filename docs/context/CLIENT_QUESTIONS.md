# Client Questions — Top 5 Decisions Needed

**Project:** Powerplant Monitoring Dashboard
**Date:** 2026-09-04
**Source:** `docs/context/CLIENT_CLARIFICATION_PACK.md`

---

## 1. C-08 — Message Forwarding Auto-Disable Ownership

**Question:** Who is responsible for the daily 18:30 auto-disable of message forwarding — the web application or the RTL Master?

**Why we need this:** This determines whether we need to build scheduling infrastructure into the application, or whether the RTL Master handles it externally.

**What it unlocks:** Scheduler/background-worker infrastructure design; message forwarding delivery completeness.

---

## 2. C-05 — Communication Method Between Application, RTL Master and Devices

**Question:** What is the approved communication method between the application, the RTL Master, and RTL devices? Please clarify the transport (MQTT / SMS / API / broker) and the message or command format at a high level.

**Why we need this:** Every device-facing feature depends on knowing how the application will send commands and receive data from the field.

**What it unlocks:** Physical RTL command transport, real device-event ingestion, message-forwarding delivery, real-time power-down forwarding, and all producer-dependent work. The repository already has protocol-neutral command lifecycle/dispatch readiness and development-only simulation; neither supplies the production transport or protocol decision.

---

## 3. C-15 — Maximum Temperature Report Period

**Question:** What time period should the Maximum Temperature report cover?

**Why we need this:** The report cannot generate data without a defined reporting window. The current specification does not specify one.

**What it unlocks:** Full implementation and export of the Maximum Temperature report.

---

## 4. C-04 — Production Report Format

**Question:** What report output format is required for production — CSV, Excel, PDF, or a combination?

**Why we need this:** A CSV export exists as a development default. We need your confirmation before treating it as the production standard, or we will implement the format you specify.

**What it unlocks:** Production sign-off of report export; any retention or history requirements for generated reports.

---

## 5. C-07 — Client Hierarchy Field Mapping

**Question:** How should the client hierarchy fields map to the application's data model?

```
OU / Zone / Sector / CNC / Feeder / Feeder Name
```

**Why we need this:** These fields currently appear as placeholders in the Installed RTLs and RTL Alarms reports. We need your mapping to populate them truthfully.

**What it unlocks:** Accurate, production-ready report columns; data migration design for production deployment.

---

Once these decisions are confirmed, we can proceed with the corresponding backend and integration work without making assumptions.

---

## Development Baselines Set — 2026-09-06 (Pending Client Confirmation)

**These are internal decisions made by the development team/user so
implementation can proceed. They are NOT confirmed Eskom/client answers
unless repository evidence proves otherwise.** Formal client confirmation
remains pending for all items marked "baseline" below.

1. **C-08 — Auto-disable ownership: DEVELOPMENT BASELINE SET, pending
   client confirmation.** The RTL Application will own BR016. Default
   cutoff 18:30 Africa/Johannesburg. An Administrator may set a temporary,
   same-day-only override with a mandatory reason; it expires automatically
   and the default 18:30 cutoff resumes the next day without action. Every
   override change and every automatic disable must be audited. See
   `REQ-3I_Clarification_Register.md` C-08 and
   `docs/context/ACTIVE_GATE.md` (gate `C08-AUTO-DISABLE-1`, now queued
   against this baseline).
2. **C-05 — Communication method: NOT ANSWERED.** Confirmed to remain
   Eskom-controlled/external. It remains the gate for physical transport and
   producer integration, despite completed application-side command lifecycle,
   scoped activity/history, alarm acknowledgement, and protocol-neutral
   dispatch readiness. Those development capabilities do not determine an
   Eskom transport, payload, endpoint, ACK format, or device behaviour — see
   `REQ-3I_Clarification_Register.md` §5.
3. **C-15 — Max Temperature report period: DEVELOPMENT BASELINE SET,
   pending client confirmation.** Rolling 30 days by default, plus a custom
   date range. The period used must be shown on the report and its export.
4. **C-04 — Production report format: DEVELOPMENT BASELINE SET (format
   only), pending client confirmation.** PDF + CSV. Native XLSX is not
   required at this time. Retention/history for reports remains open.
5. **C-07 — Hierarchy field mapping: HOLD.** Still genuinely pending client
   clarification; no mapping supplied yet — not a development baseline.

Also reconfirmed as Eskom-controlled/external (unanswered, not part of this
round): **C-06** (production identity/role-source ownership, Entra ID) and
the **Azure / private-APN infrastructure family**.

Two further clarifications outside this document's original top-5, recorded
in `REQ-3I_Clarification_Register.md` C-01 and C-02, also got development
baselines set (shape only, pending client confirmation): high-temperature
thresholds (C-01) and the vibration metric (C-02) must both be
administrator-configurable frameworks with audited changes, never
permanently hardcoded — the actual Eskom threshold values and full
vibration sensor contract remain unconfirmed.

---

## Suggested Meeting Priority

Ordered per `REQ-3I_Clarification_Register.md` §5 engineering-gate ranking, the repository's authoritative clarification register — matching the numbered list above.

1. **C-08 — Auto-disable ownership** — Unblocks scheduler infrastructure and forwarding delivery.
2. **C-05 — Communication method** — Unblocks the largest set of device integration work.
3. **C-15 — Max Temperature report period** — Unblocks one complete report feature independently.
4. **C-04 — Report format** — Zero code changes if CSV is confirmed; immediate production sign-off path.
5. **C-07 — Hierarchy mapping** — Unblocks truthful report column population.
