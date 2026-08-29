# ADR-007: The Command Center event demo seed must call `ingest_event()`, never `insert_device_event()` directly

Status: Approved — not yet implemented
Date: 2026-08-28
Evidence: `services/device_event_service.py:281-306` (`ingest_event`, the only caller of the repository insert); `repositories/plant_monitoring_repository.py:2326` (`insert_device_event`, the low-level write); confirmed by grep that no existing seed file references `device_events` today
Implemented-by: not yet — this ADR is the pre-commitment; the seed itself is a CC-1 Phase 0 prerequisite
Supersedes: n/a — first decision on this question

## Decision

Nothing seeds `device_events` today. `db/seed_plant_monitoring.py` and
`db/seed_admin_demo.py` were checked directly; neither references the table.
That means the largest Command Center panel (recent events / attention
legend) renders empty in local dev unless CC-1 adds a seed — which the
implementation plan already names as a Phase 0 prerequisite, opt-in and
deterministic, separate from core seed behaviour, never run implicitly in
production.

The constraint this ADR fixes: that seed **must call
`services.device_event_service.ingest_event()`**, not
`repositories.plant_monitoring_repository.insert_device_event()` directly.

`ingest_event()` is not a thin wrapper — it is where the real invariants
live:

- **INGEST-D5 atomicity** — the event INSERT, any startup activation, and the
  RTL_ACTIVATED audit row share one transaction
  (`services/device_event_service.py:283-286`). A seed calling `insert_device_event`
  directly gets none of that: no activation logic, no audit trail, silently
  divergent behaviour from every real event the ingestion pipeline has ever
  produced.
- **Identity resolution** (`_resolve_identity`) — decides `device_id`
  resolved / unresolved / ambiguous before the row is written. Bypassing it
  means the seed writes rows a real device could never have produced this
  way, since every real event passes through resolution first.

Calling `insert_device_event` directly would be a second, parallel event
model with its own (missing) invariants — precisely the two-tables-answering-
one-question failure this repository has already named and rejected once, in
`services/device_scope.py`'s own docstring (see ADR-004), and in
`services/authorization.py`'s "DEFAULT DENY... two tables would each pass
their own tests while contradicting each other." The seed is not exempt from
that principle merely because it's demo data.

## Affected areas

- New: the CC-1 event demo seed script (path not yet decided — likely
  `db/seed_command_center_demo.py`, opt-in, following the
  `db/seed_admin_demo.py` precedent of a separate, explicitly-invoked seed)
- `services/device_event_service.py` — `ingest_event`, the required entry
  point
- `repositories/plant_monitoring_repository.py:2326` — `insert_device_event`,
  explicitly **not** a valid direct call site for seed code
- `command center/07_IMPLEMENTATION_PLAN.md` Phase 0 — the prerequisite this
  ADR fixes the shape of
