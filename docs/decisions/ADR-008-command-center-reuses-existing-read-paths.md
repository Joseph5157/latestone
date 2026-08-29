# ADR-008: Command Center's read side is `get_fleet_health()` and `list_recent_device_events()` — never new duplicate SQL

Status: Approved — not yet implemented
Date: 2026-08-29
Evidence: `services/monitoring_service.py:430` (`get_fleet_health`), `repositories/plant_monitoring_repository.py:2450` (`list_recent_device_events`)
Implemented-by: `1940b93` (`FleetHealth`/freshness rollups), `bb1e2e9` (`list_recent_device_events`) — pre-existing; Command Center's own call sites not yet written
Supersedes: n/a — first decision on this question; corrects an imprecision in ADR-002's original "Affected areas" (fixed 2026-08-29, same commit as this ADR)

## Decision

Command Center's service layer has exactly two approved read entry points,
both pre-existing and already load-bearing elsewhere in the app:

**Freshness/health**: `get_fleet_health(now, *, scope: DeviceScope) ->
FleetHealth` (`services/monitoring_service.py:430`). One query, scoped in
SQL, worst-of-aggregated at every level (device/transformer/plant). Its own
docstring states the call discipline directly: "call it once per render and
pass the result down... calling it per component would issue N queries and,
worse, let two parts of one screen disagree about which devices are stale."
`services/command_center_service.py` must call this exactly once per render,
the same discipline ADR-004 already requires of `DeviceScope.scope_for()`.

**Events**: `list_recent_device_events(*, event_types, since=None,
allowed_device_ids=None, include_unattributed=False, limit=500) ->
list[DeviceEventRecord]` (`repositories/plant_monitoring_repository.py:2450`).
Its own docstring: "The single consumer read API (EVT-D2): Notification
Center, report projections and future delivery code all read through this
one function instead of each re-querying `device_events`." Command Center is
exactly the "future delivery code" that sentence anticipates. `event_types`
should be sourced from `services.event_semantics` (e.g.
`mapped_event_types()`), not a hand-written list, so a new event type mapped
there is automatically visible to Command Center without a second edit.

This is the read-side mirror of ADR-007 (which fixes the write side —
`ingest_event()`, never `insert_device_event()` directly). Together they
mean nothing in Command Center issues raw SQL against `readings` or
`device_events` at all: `AGENTS.md` rule 1 ("UI/page/component code must not
execute raw SQL") extends unambiguously to Command Center's own service.

## `components/fleet_condition.py` and `components/needs_attention.py` are not reusable — Command Center does not import them

Both are Fleet Overview page-specific *presentation*, not domain logic:
`fleet_condition.py`'s own docstring says "no classification or queries are
performed here" — it only renders an already-computed `dict[Freshness,
int]`. The reusable unit sits one layer down, in the service functions
above. Command Center gets a fresh `components/command_center/` family
(first subdirectory under `components/` — this codebase's convention has
been one flat file per concern until now; CC-1's ADR-count of distinct
panels, roughly matching the pack's 12 `components/CC*.md` specs, is enough
files to justify a subdirectory rather than 12 more flat entries) that
renders the same underlying data through fresh markup, not shared markup.

This is not a prohibition on ever sharing a component — if implementation
turns up a genuinely generic primitive (a bar/ring gauge shape, say) worth
lifting to something both pages import, that is a legitimate `components/`
addition to propose at that point. It is a prohibition on importing
Fleet-Overview-specific presentation *by default* to save a little typing,
which is how one page's CSS classes and layout assumptions quietly become
Command Center's, undermining the "Fleet Overview is frozen, Command Center
is parallel" gate principle (`command center/07_IMPLEMENTATION_PLAN.md`).

## Route authorization defaults to every confirmed role

`command center/01_PRODUCT_BRIEF.md` §"Primary users" names both
"Administrator / control-room operator" and "Technician" ("may use the
Command Center in the field... a high-contrast light appearance is therefore
mandatory"). General is not named but isn't excluded either, and
`services/authorization.py`'s existing `ROUTE_POLICY` puts every monitoring
route — `overview`, `plant`, `transformer`, `device`, `notifications`,
`reports` — at `_EVERY_ROLE`, reserving `_ADMIN_ONLY` for routes that manage
*what exists* (`admin_devices`, `device_register`, `admin_users`). Command
Center is a monitoring lens on the same fleet, not an administration
surface, so `"command_center": _EVERY_ROLE` is the entry consistent with
every existing precedent in that table — not a new judgment call, an
application of the one already there. ADR-004's "General... read-only is a
constraint on actions, not on sight" is the same principle stated from the
device-scope side.

## Affected areas

- `services/command_center_service.py` (not yet created) — the only caller
  of both functions on Command Center's behalf
- `services/monitoring_service.py`, `repositories/plant_monitoring_repository.py` — unchanged; Command Center is a new caller, not a new implementation
- `services/authorization.py` — `ROUTE_POLICY["command_center"] = _EVERY_ROLE`
- `components/command_center/` (not yet created) — fresh presentation only
