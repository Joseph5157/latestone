# RTL-NETWORK-USE-01 — acceptance

Date: 2026-09-30 · Baseline `d4788dd` · 1366×900 · local app, restored client `RTL` SQL Server (SELECT only). Raw log: `acceptance-run.log`; console: `console-errors.log` (0 errors).

## RTL detail (`/rtls/<uid>`)

Network context now comes from `rtl_network_service.get_network_row` (ADR-031); `rtl_detail_service` holds no mapping/hierarchy/precedence code. Temperature, timestamp, ambiguity and 24h/7d/30d history are untouched.

| RTL | Observed |
|---|---|
| 29042 | Transformer EMV35 · Pietermaritzburg Zone / Sector · Howick CNC · Edendale NBEC 22kV feeder · "Mapping review: latest temperature reading references ozw28." (live disagreement) · 29.0 °C, 18 Sep 2022 20:20 SAST, 1 reading |
| 29639 | DA10 · Empangeni Zone / Sector / CNC · Ngoye NB29 feeder · no review note |
| 29006 (unmapped) | "No current transformer mapping" |
| 29646 (hierarchy unavailable) | PINS206 · "Hierarchy unavailable" |

No Plant, Online/Offline, raw null or unsupported metric on any of them.

## Dashboard summary

The "main dashboard" is role-dependent (ADR-024): General User lands on `/rtls`, Administrator and Technician on the Command Center.

- `/rtls` (General User): the existing cards plus one line "Network coverage: 185 of 339 … 178 hierarchy resolved · 7 hierarchy unavailable · View Network" → `/rtls/network`. Same fleet snapshot, no extra read.
- Command Center (Administrator): compact "Registered RTLs (client directory)" panel — Registered 339 · Mapped 185 · Unmapped 154 · Temperature data available 319 — with links to `/rtls` and `/rtls/network`. One `get_real_fleet` per page render, not polled.
- Technician: no panel, no counts, no `/rtls/<uid>` links, no network text on the Command Center; `/rtls/29042` → "No access". Narrower behaviour chosen: the summary follows `may_view_real_fleet`, no new policy.

Counts equal the source (339 / 185 / 154 / 178 / 7 / 319 / 20).
