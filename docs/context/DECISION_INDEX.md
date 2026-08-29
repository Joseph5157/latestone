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
| [ADR-005](../decisions/ADR-005-auto-refresh-is-page-owned-polling.md) | Auto-refresh is a page-owned `dcc.Interval`, not a shared "live" feed | Approved | `23642da` (precedent); Command Center's own interval not yet built |
| [ADR-006](../decisions/ADR-006-route-scoped-theming-is-architecture.md) | Route-scoped dark/light theming is CC-1 Phase-1 architecture, not later polish | Approved | not yet |
| [ADR-007](../decisions/ADR-007-event-demo-seed-uses-ingest-event.md) | The CC-1 event demo seed must call `ingest_event()`, never `insert_device_event()` directly | Approved | not yet |

## Reading this table

- **All seven currently gate CC-1** (`docs/context/ACTIVE_GATE.md`, once
  written, will link the subset each task actually touches — don't load all
  seven for every CC-1 task; load what the gate names).
- Four of the seven (001-004) are not new decisions invented for CC-1 — they
  are pre-existing, already-shipped behaviour (event semantics, fleet
  freshness, the plant schema, ROLE-3 device scope) that CC-1 must conform
  to. They are backfilled here because CC-1 depends on them and they had no
  durable record before now, not because CC-1 changed them.
- Three (005-007) are CC-1-original decisions, approved in the frozen
  planning pack (`command center/`) but not yet built.
- None is Superseded or Rejected yet. When one is, edit its own file's
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
