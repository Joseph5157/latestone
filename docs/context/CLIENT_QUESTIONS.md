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

**What it unlocks:** RTL programming execution, event data ingestion, message forwarding delivery, real-time power-down forwarding, and all producer-dependent work.

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

## Suggested Meeting Priority

1. **C-05 — Communication method** — Unblocks the largest set of device integration work.
2. **C-08 — Auto-disable ownership** — Unblocks scheduler infrastructure and forwarding delivery.
3. **C-15 — Max Temperature report period** — Unblocks one complete report feature independently.
4. **C-04 — Report format** — Zero code changes if CSV is confirmed; immediate production sign-off path.
5. **C-07 — Hierarchy mapping** — Unblocks truthful report column population.
