# ADR-008: Command Center's read side reuses existing entry points — never new duplicate SQL

Status: Approved
Date: 2026-08-29 (amended three times on 2026-08-29: Phase 7 added the plant
label lookup, Phase 8 generalised it to hierarchy labels, Phase 9 added the
batched device-path lookup and the events failure boundary)
Evidence: `services/monitoring_service.py:430` (`get_fleet_health`), `repositories/plant_monitoring_repository.py:2450` (`list_recent_device_events`), `services/hierarchy_service.py:27` (`list_plants`), `services/hierarchy_service.py:39` (`list_transformers`)
Implemented-by: `1940b93` (`FleetHealth`/freshness rollups), `bb1e2e9` (`list_recent_device_events`); Command Center call sites `cc6b67a` (Phase 3+4), `1a1be90` (Phase 5), `04e3bfa` (Phase 6)
Supersedes: n/a — first decision on this question; corrects an imprecision in ADR-002's original "Affected areas" (fixed 2026-08-29, same commit as this ADR)

## Decision

Command Center's service layer has three approved read CATEGORIES, all
pre-existing and already load-bearing elsewhere in the app. The set is
deliberately small and closed: a fourth needs an amendment here, not a
judgement call at the call site. Categories rather than individual
functions, so that reading one more level of the same hierarchy for the
same reason does not require re-opening this decision each time.

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

**Hierarchy labels** (added Phase 7, generalised Phase 8):
`services/hierarchy_service.py`'s scope-aware listings — `list_plants(*,
scope)` and `list_transformers(plant_id, *, scope)` — as a single category
rather than two entries, because enumerating one per level would mean
amending this ADR again at every depth for the same reason.

Phase 9 adds a third member to the same category:
`services/hierarchy_service.py:list_device_paths(device_ids, *, scope)` over
`repositories/plant_monitoring_repository.py:list_device_paths`, returning
the existing `DevicePath` (plant name, transformer code, device code) for a
BOUNDED set of device ids in ONE query, scope-enforced in SQL by the same
`_scope_clause` idiom as every other read here.

A new function rather than the per-level listings already approved above,
because the per-level route is the pathology this ADR exists to prevent.
Labelling the events on screen through `list_transformers` and `list_devices`
means one query per distinct plant AND one per distinct transformer among the
visible rows — up to ~20 extra queries per render on a page the roadmap
intends to auto-refresh (CC1_ROADMAP Phase 11). One batched query is by far
the smaller commitment, and it is the reason this entry is an addition to the
category rather than a reinterpretation of it.

Its discipline is the same shape as the transformer listing's: called once
per render, for the VISIBLE event rows only — never per row, and never over
the unbounded query window the repository's `limit` allows.

These need their scope stating precisely, because they are the entry
points most likely to be misused later. They supply **labels, not facts**.
`FleetHealth` is keyed by `plant_id` and `transformer_id` and carries no
names or codes, so a display that must read "KZN North" rather than
`plant-07`, or `aa12` rather than `plant-01-t1`, needs those from somewhere.
That is the *only* thing these calls are for. The transformer listing is
additionally called for the ONE selected plant only, never per row.

`list_device_paths` deliberately does NOT apply `hierarchy_service`'s
active-only default. That filter answers "what is selectable for live
monitoring"; naming an event that already happened is a different question,
and dropping the label for a device deactivated after the event would leave a
real, persisted event row wearing raw ids for no operator-visible reason.

Every **number** — affected counts, composition, ranking order, at plant
AND transformer level — is still derived from the `FleetHealth` already
fetched, via `device_counts_for_plant()` and `transformers_for_plant()`. Ranking must never be pushed into SQL: an
`ORDER BY` over a fresh query would be a second definition of "affected",
free to disagree with the one Fleet Overview and the Situation Summary
share. A test asserts the ranking is computed from `FleetHealth` and that
this lookup contributes names only.

An entity present in `FleetHealth` but absent from the label lookup keeps
its id as its label rather than being dropped — the freshness snapshot
is the authority on which plants exist in scope, and a labelling call must
never silently shrink the population the numbers were computed over. The
same rule governs events: the persisted event row is the authority that
something happened, so an event whose device resolves to no path keeps its
raw ids and is still shown. It loses its **link**, not its row — offering
"Open asset" for an asset that did not resolve would be a claim the lookup
just failed to support.

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

## The events read has its own failure boundary (added Phase 9)

Every other read here answers "what is the state of the fleet". The events
read answers "what happened recently", which is CONTEXT around that state,
not the state itself. The two therefore fail differently and must not share
one boundary: an operator who cannot see the last ten events can still act on
Needs Attention, Affected Locations and the transformer concentration, and
blanking all of them because an event query failed would remove far more
truth than the failure actually cost.

So `get_command_center_snapshot` catches the events read specifically, logs
it, and returns a snapshot whose `recent_events_failed` flag is set. The
failure is never flattened into an empty list: "no events occurred" and "the
events could not be read" are different facts and the panel states which one
it has, the same distinction ADR-001 draws between `Unavailable` and `0` and
ADR-002 draws between a calm plant and an unmonitored one.

The boundary is deliberately one-directional. A failure of `get_fleet_health`
or of the plant labels still fails the whole snapshot: those ARE the page.

## Unregistered-UID events are administrator-only (added Phase 9)

`list_recent_device_events` excludes rows with no `device_id` unless
`include_unattributed=True`. Those rows are the `invalid_uid` quarantine, and
an unregistered UID belongs to no device set, so scope alone cannot express
who may see it (EVT-D5).

Command Center therefore applies the precedent already set at
`callbacks/notifications.py:106` (`include_unregistered=is_admin`) rather than
inventing a rule: the callback resolves the caller once, and only an
administrator's snapshot requests unattributed rows. This is an application of
an existing decision to a new surface, not a new decision.

## Affected areas

- `services/command_center_service.py` (not yet created) — the only caller
  of both functions on Command Center's behalf
- `services/monitoring_service.py` — unchanged; Command Center is a new caller, not a new implementation
- `repositories/plant_monitoring_repository.py`, `services/hierarchy_service.py` — Phase 9 adds `list_device_paths`; every pre-existing read is unchanged
- `services/event_semantics.py` — Phase 9 adds `display_label` to `EventSemantics`, so no consumer spells out an event type's human name itself
- `services/authorization.py` — `ROUTE_POLICY["command_center"] = _EVERY_ROLE`
- `components/command_center/` (not yet created) — fresh presentation only
