# ADR-003: Location means Plant — no Zone/Feeder/GIS level exists

Status: Approved
Date: 2026-08-28
Evidence: `repositories/plant_monitoring_repository.py:30-35` (`PlantRecord` fields: `country`, `latitude`, `longitude` — nothing else); `alembic/versions/001_baseline.py`
Implemented-by: `699ece0` (normalized `plant_monitoring` schema)
Supersedes: a CC-1 planning draft assuming a Zone/Feeder/GIS hierarchy above Plant

## Decision

**Location = Plant.** There is no Zone, Feeder, Sector, or GIS level in this
schema to hang a richer location concept on. `plants` carries `country`,
`latitude`, `longitude` and nothing else location-shaped
(`repositories/plant_monitoring_repository.py:30-35`).

This is the same gap `services/event_semantics.py:286-295` already
documents from the report side: `AlarmEventProjection` hard-codes
`ou`/`zone`/`sector`/`cnc`/`feeder_name` to `None` because "the client's
OU/Zone/Sector/CNC/Feeder taxonomy has no confirmed mapping yet" (R2-D2, from
REPORT-2). Command Center hits the identical wall for the identical reason:
it is not a CC-1-specific limitation, it is a standing fact about the schema
that will recur in every surface until the client supplies that taxonomy.

Any Command Center "Location" ranking or grouping is a Plant-level rollup:
Plant → affected RTL count (Stale + No Data, per ADR-002) in the caller's
visible scope. Do not invent an intermediate grouping level to make the panel
look more granular than the data actually is.

## Affected areas

- `repositories/plant_monitoring_repository.py` — `PlantRecord`, the actual
  shape of what exists
- `services/event_semantics.py:280-306` — `AlarmEventProjection`, the prior
  instance of this same gap
- `command center/components/CC07_AFFECTED_LOCATIONS.md`,
  `command center/components/CC09_SELECTED_LOCATION.md` — must key on
  `plant_id`, never introduce a zone/feeder field
- Reopens only on new client evidence — a real OU/Zone/Sector/CNC/Feeder
  mapping supplied by the client, not a UI preference for more hierarchy
