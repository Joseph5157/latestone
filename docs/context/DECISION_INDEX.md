# Decision Index

Status: Approved
Date: 2026-08-29

Every ADR in `docs/decisions/`, one line each. This file is the map; the ADR
is the territory — read the ADR before acting on a decision, don't act on
the one-line summary alone.

Per `AGENTS.md`: every ADR carries `Status` (Proposed / Approved / Superseded
/ Rejected) and `Implemented-by` (a commit sha, or "not yet") as **independent
fields**. Approved-and-not-yet-implemented is normal — it means the decision
is settled but the code doesn't exist yet. Check both columns before assuming
either "approved" means "built" or "not yet" means "undecided."

| ADR | Decision | Status | Implemented-by |
|---|---|---|---|
| [ADR-001](../decisions/ADR-001-event-classification-no-thresholds.md) | Events are closed, pre-classified facts — no consumer holds a numeric threshold | Approved | `bb1e2e9` |
| [ADR-002](../decisions/ADR-002-fleet-attention-is-freshness-only.md) | Requires Attention = Stale + No Data only, never mixed with event history | Approved | `29a4c5a` |
| [ADR-003](../decisions/ADR-003-location-is-plant.md) | Location = Plant; no Zone/Feeder/GIS level exists in the schema | Approved | `699ece0` |
| [ADR-004](../decisions/ADR-004-device-scope-is-not-user-selectable.md) | Device scope is authorization-derived; no page may offer a scope selector | Approved | `9966bd7` |
| [ADR-005](../decisions/ADR-005-auto-refresh-is-page-owned-polling.md) | Auto-refresh is a page-owned `dcc.Interval`, not a shared "live" feed | Approved | `23642da` (precedent); Command Center's own interval `b8315c8` |
| [ADR-006](../decisions/ADR-006-route-scoped-theming-is-architecture.md) | Route-scoped dark/light theming is CC-1 architecture, not later polish; the semantic palette is route-scoped in BOTH appearances | Approved | `267b11a` |
| [ADR-007](../decisions/ADR-007-event-demo-seed-uses-ingest-event.md) | The CC-1 event demo seed must call `ingest_event()`, never `insert_device_event()` directly | Approved | `a49620f` |
| [ADR-008](../decisions/ADR-008-command-center-reuses-existing-read-paths.md) | Command Center's read side is `get_fleet_health()` + `list_recent_device_events()` + the batched `list_device_paths()`, never new SQL or Fleet Overview's presentation components | Approved | `1940b93`, `bb1e2e9` (precedent); Command Center's call sites `a49620f` |
| [ADR-009](../decisions/ADR-009-priority-investigation-ranks-on-freshness-only.md) | Priority Investigation ranks on freshness only; a STALE age is the OLDEST metric's timestamp, and exists only when every metric has one | Approved | `ce5d4ac` |
| [ADR-010](../decisions/ADR-010-monitoring-reset-preserves-operational-history.md) | A monitoring reset replaces measurements and preserves operational history; the destructive teardown is a separate, acknowledged `--purge`; no CASCADE | Approved | `29f5290` |
| [ADR-011](../decisions/ADR-011-affected-locations-is-top-n-with-disclosure.md) | Affected Locations names the worst 8 Plants and discloses the rest; a selected Plant below the cut is retained and says why | Approved | `6aafc4c` |
| [ADR-012](../decisions/ADR-012-rank-bars-are-capped-and-route-themed.md) | The rank bar is a fixed 15rem track on route-scoped tokens; no track absorbs surplus width, and the encoding basis is unchanged | Approved | `e33d0e1`, `59f92a9` |
| [ADR-013](../decisions/ADR-013-export-data-is-a-capability.md) | EXPORT_DATA is a device-less capability, not a device action; same roles, guard changed to `require_capability`, scope still enforced by the repository's `allowed_device_ids` | Approved | `723dd0b` |
| [ADR-014](../decisions/ADR-014-latest-reads-are-bounded-seeks.md) | Every latest-reading read is a bounded index seek, at device grain too; `get_latest_readings_for_device` no longer scans the device's history, and the guard measures rows examined rather than wall-clock | Approved | `3b33015` |
| [ADR-015](../decisions/ADR-015-credentials-name-logins-not-roles.md) | Credential configuration names logins and can never express a role; the `users` row decides user_id, name, role and status. No password column, no migration — the rule survives the eventual swap to the client's mechanism | Approved | not yet |

## Reading this table

- **Nine of the ten gate CC-1** (`docs/context/ACTIVE_GATE.md` links the
  subset each gate actually touches — don't load all ten for every CC-1
  task; load what the gate names).
- Five of the ten (001-004, 008) are not new decisions invented for CC-1 —
  they are pre-existing, already-shipped behaviour (event semantics, fleet
  freshness, the plant schema, ROLE-3 device scope, the `FleetHealth`/event
  read functions) that CC-1 must conform to and reuse. They are backfilled
  here because CC-1 depends on them and they had no durable record before
  now, not because CC-1 changed them.
- Four (005-007, 009) are CC-1-original decisions, and all four are built.
- ADR-010 is not a CC-1 decision at all: it records the SEED-RESET-1 defect
  fix, which CC-1 acceptance depended on but which governs the seeds rather
  than the Command Center.
- Every ADR in this table carries an `Implemented-by` sha.
- ADR-013 is the first SUPERSESSION in this table, and it supersedes a
  decision that is not an ADR: R4-D3, frozen in
  `services/report_export.py`'s docstring. That docstring is corrected in
  the same commit — a supersession discoverable only from the new record
  is not a supersession (`AGENTS.md`).
- ADR-012 is not a CC-1 decision either. It is the CC-2 defect gate against
  a panel CC-1 accepted, and it deliberately supersedes nothing: ADR-011
  governs *which* plants the panel names, ADR-012 only how the row is drawn.
- ADR-002 was corrected 2026-08-29 (same day as ADR-008): its original
  "Affected areas" pointed at `components/fleet_condition.py` as something
  to reuse. It isn't — see ADR-008. The decision itself (`Requires
  Attention = Stale + No Data`) didn't change, only which file embodies the
  reusable part.
- No ADR is Superseded or Rejected yet — ADR-013 supersedes R4-D3, which
  is a frozen decision in a docstring, not an ADR. When an ADR is
  superseded, edit its own file's
  `Status:` field in the same commit that supersedes it — per `AGENTS.md`,
  a supersession is only real once the old record says so itself, not only
  the new one.

## Provenance

Backfilled 2026-08-29 during CTX-1, scoped deliberately to what the CC-1
planning pack (`command center/`, frozen 2026-08-28) depends on — not a
full sweep of every decision in the project's history. Older tranches
(DB-1..4, ROLE-1..3, ADMIN-0P..3, NAV-1..3, ENT-2..6, BOOTSTRAP-1) have no
ADR yet; they remain recoverable from `git log` and agent memory until
something depends on them enough to justify backfilling. Do not treat their
absence here as evidence they were never decided.
