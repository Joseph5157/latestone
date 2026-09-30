# HISTORICAL-EVENTS-01 — acceptance

Date: 2026-09-30 · Baseline `0c15ee0` · Viewport 1366×900 · local app, restored client `RTL` SQL Server (SELECT only). Raw log: `acceptance-run.log`; console: `console-errors.log` (0 errors; the React "uncontrolled input" warning on the login page, seen in earlier gates, is filtered).

## What was built

`/events` — **Historical Events**: one page, four event classes (High Temperature `alarm_log`, Sensor Error `sensor_error_log`, Battery Low `startup_msg_log` where `status='Battery Low'`, Powerdown `powerdown_log`), filtered by event type, date range and RTL UID. Recorded facts only: no acknowledgement, resolution, severity, assignment or alarm state exists in the model.

Columns: Recorded At · Event · RTL UID · Recorded Value · Recorded Transformer (the `trfr` on the event row) · Current Transformer · Current Network Context (the RTL's *present* mapping, ADR-031; stated as such on the page).

## Rules

- **Window:** default 30 calendar days ending on the newest recorded event (2026-08-25 here → 27 Jul – 25 Aug 2026). Anchored on the data because the source is a restored copy; a rolling window from today would be empty. The range is editable.
- **Bounds:** 50 rows per page, Previous/Next, `OFFSET/FETCH` in SQL; per-class counts are one grouped query for the window, so the browser never holds more than a page. Sort: newest first, then class, then UID.
- **Counts** shown are for the selected window (and UID), not lifetime.
- **Registered vs historical:** every event row is kept. A UID in `device_list` links to `/rtls/<uid>`; any other shows "Historical RTL UID <uid>" as plain text with no link.
- **Reads per interaction:** count query + page query (+ one six-read current-network snapshot only when the page has rows). No per-event lookups.
- **Authorization:** `historical_events` policy = Administrator + General User (same as Network/detail); routing and both callbacks re-check `may_view_real_fleet` before any event source is read. Technician: no sidebar item; `/events` is "No access" with no table, RTL links or event text.

## Observed live (Administrator; General User identical)

| Check | Result |
|---|---|
| Default window | 27 Jul – 25 Aug 2026: High Temperature 15 · Sensor Error 0 · Battery Low 64 · Powerdown 0 = 79 events, 2 pages, newest first (25 Aug 2026 20:27 SAST first) |
| Type filters | High Temperature 15 · Sensor Error 0 · Battery Low 64 (2 pages) · Powerdown 0 — rows contain only the chosen class |
| Wider window (from 2020-01-01) | 3,346 / 695 / 5,791 / 42 = 9,874 events, 198 pages; Next → 51–100; Previous → 1–50 |
| UID 29032 (not registered) | 6 events, "Historical RTL UID 29032", 0 links |
| UID 29763 (registered) | 174 events, 50 links to `/rtls/29763`; opening one → RTL detail; browser back → `/events` |
| UID `12x` | "Check the date range and RTL UID…" message, no query |
| Dashboard | still the factual Dashboard |

Forbidden-word scan (Plant, Online, Offline, Healthy, Inactive, Active, Unresolved, Open, Needs Attention, Voltage, Frequency, Power factor, Energy, undefined, NaN, null, None): no hits on any role. Sidebar: Administrator and General User see "Historical Events"; Technician does not.

## Live event-source counts (whole history, from `count_events`)

High Temperature 3,346 · Sensor Error 1,175 (+2 NULL-time rows = 1,177 in the table) · Battery Low 7,674 · Powerdown 719 = 12,914 time-stamped events. Matches the knowledge base. Events for UIDs not in `device_list`: 402 / 504 / 1,737 / 618 rows.

## SQL Server

`Updateability = READ_ONLY`; write permissions 0; `master_temperature` 2,456,901 · distinct UIDs 400 · `device_list` 339 · `trfr_list` 185 — unchanged. PostgreSQL untouched.

## Legacy Needs Attention (not removed)

The synthetic attention list (Needs Attention / problem groups, acknowledge action) is still built by `pages/command_center.py`, `callbacks/command_center.py`, `components/command_center/*` and `services/attention_service.py` from PostgreSQL. It is reachable only at `/command-center` by the **Technician** (the Administrator's `/command-center` is the factual Dashboard since FACTUAL-DASHBOARD-01; General User has no access). It is not used for Historical Events because it is a synthetic, lifecycle-bearing model over PostgreSQL devices, while Historical Events is a lifecycle-free reading of client logs. Cleanup waits for technician UID assignment.
