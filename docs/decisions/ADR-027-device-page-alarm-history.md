# ADR-027: The Device page shows the RTL's own alarm history and reading gaps

Status: Approved
Date: 2026-09-19
Evidence: `repositories/plant_monitoring_repository.py`
(`list_recent_device_events`), `services/device_timeline_service.py`,
`components/metric_chart.py`, `components/device_alarms.py`,
`callbacks/device.py`, `services/authorization.py` (`ROUTE_POLICY`)
Implemented-by: `6bbf26c`

## Context

Alarms (Power Down, Battery Low, Sensor Error) appear only on the Command
Center and the Notifications page. A technician who opens an RTL from the
problem list sees its readings but not what happened to it or when. The user
approved a mockup (Mobbin review: Render's event timeline, Better Stack's
monitor page) and three decisions on 2026-09-19.

## Decision

- **Markers on the chart.** Each alarm in the selected time range is a
  dashed vertical line with a marker at the top, in its ADR-026 tone, on
  every metric's chart (a Power Down matters on voltage too).
- **Alarm history list under the chart**, newest first: time (UTC), kind,
  and "Acknowledged … later" or "Unacknowledged". **Read-only** — the
  Command Center remains where alarms are acknowledged (ADR-016).
- **Shaded "No readings" gaps.** A gap is shaded when it is more than
  **4 × this RTL's median reading spacing in the shown window**. No fixed
  cadence is assumed: the application does not know any RTL's reporting
  cadence (`config/settings.py`, `resolve_freshness_stale_after_minutes`).
  Fewer than three readings in the window: no gaps are drawn. The silence
  after the last reading, up to the window end (never past now), counts too:
  for an RTL that stopped reporting it is the gap that matters most.
- **Who sees it:** Administrators and Technicians (the roles that may open
  Notifications and the Command Center, `ROUTE_POLICY`). General Users keep
  the Device page without the alarm history. Technicians see only their
  assigned RTLs (ADR-004); the read goes through
  `list_recent_device_events` scoped to the one RTL — no new query, table or
  migration.

## Consequences

- The time range selector now also bounds the alarms shown.
- Delta (bar) metrics get the markers but no gap shading: their bins already
  mark intervals they could not compute.
- A later decision may add Acknowledge to the list through the existing
  guarded flow.
