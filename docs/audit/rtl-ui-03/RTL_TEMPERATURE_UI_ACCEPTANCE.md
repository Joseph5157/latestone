# RTL-UI-03 — RTL temperature UI acceptance

Status: PASS â€” browser acceptance completed 2026-09-29.

The selected screen is the existing authorized `/devices/<app-device-id>`
dashboard: it already owns the temperature chart, range controls and readings
table. An Administrator may add explicit `?rtl_uid=<raw integer>`; no canonical
fleet or mapping is inferred. The router first enforces the existing app-device
scope, then restricts raw UID use to Administrator because no safe raw
UID-to-device authorization mapping exists.

For Temperature only, `rtl_temperature_ui_service` calls the read-only RTL
repository for latest, then a bounded 24h/7d/30d range ending at that source
latest timestamp. Raw values, order and naive database timestamps are retained;
there is no conversion, cleaning or synthetic fallback. An unavailable reader
returns the dashboard error state. Non-temperature metrics retain the existing
PostgreSQL path. The page exposes restrained source provenance in its
temperature workspace for QA.

## Browser acceptance evidence

- Services: local PostgreSQL and the isolated `client_rtl_sqlserver` Docker
  service were healthy before the acceptance run and after its controlled
  source-unavailable check.
- Authentication: the normal local username/password form was used to sign in
  as the configured Administrator. An unauthenticated request for the same
  device URL returned the login form; no session was manufactured or edited.
- Controlled screen: `/devices/plant-01-t1-d1?rtl_uid=29743`. The app device
  is an authorized dashboard route only. It is **not** asserted or recorded as
  a canonical mapping to RTL UID `29743`.
- Direct read-only RTL result for UID `29743`: latest source timestamp
  `2026-09-17 03:39:00`, temperature `16.00`.
- Browser result: `2026-09-17 03:39`, `16.0 °C`, with the visible
  provenance `Temperature source: client RTL SQL Server`. The values match
  exactly at the source precision retained by the UI. The raw source clock's
  timezone is unresolved: the RTL path intentionally makes no UTC, SAST, IST
  or local-time claim. Its equipment context says `Last data (source timezone
  unresolved)` and its table column says `Timestamp (source timezone
  unresolved)`.
- Bounded history: 24h, 7d and 30d each rendered the temperature chart and
  readings history, retained that provenance and retained the direct latest
  fact. Their URLs retained `rtl_uid=29743` while changing only `period`.
  This pins the UI adapter's latest-anchored bounded range contract; it does
  not introduce an unbounded history request.
- Unknown UID `999999`: rendered the client-source no-data state (`No
  readings` / no readings for the selected period), with no PostgreSQL or
  synthetic fallback.
- Controlled source outage: stopping only `client_rtl_sqlserver` yielded the
  generic safe error state. No synthetic temperature, client provenance, SQL,
  credential, or connection detail appeared. The service was restarted and
  returned healthy.
- Non-temperature regression: Voltage, Current, Active Power, Reactive Power,
  Power Factor, Frequency and Energy each rendered their existing metric path
  with no RTL temperature provenance and no `16.0 °C` raw temperature value.
- Authorization regression: the router carries raw `rtl_uid` only for an
  Administrator after the existing app-device scope check; General users do
  not receive that context, and out-of-scope Technician device routes remain
  forbidden (covered by focused routing tests).

## Read-only source recheck

`rtl_app_reader` remained read-only: an `UPDATE ... WHERE 1 = 0` attempt was
denied by SQL Server. Final counts were unchanged: `master_temperature`
2,456,901; telemetry UIDs 400; `device_list` 339; `trfr_list` 185.
