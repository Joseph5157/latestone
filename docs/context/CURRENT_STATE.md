# Current State

Status: generated
Date: 2026-08-29T10:25:11Z

Regenerate with `python scripts/build_context_pack.py`. Never hand-edit —
every fact here is derived from git, the test suite, and docs/decisions/.
For judgment calls (why something is frozen, what's in scope right now),
see docs/context/ACTIVE_GATE.md and the ADRs, not this file.

## Baseline

- current branch `ctx-1-context-architecture` = `4d3beba` "docs(ctx-1): add the project-context skill, close out CTX-1" (not `main`)
- Working tree: 9 entries — see below

## Test baseline

- `python -m pytest -m "not db"` → 2032 passed, 466 deselected in 12.63s

## Branches

Fully merged into `main` — stale pointers, safe to delete, not pending work:

- `admin-1-administration-summary`
- `admin-2-administration-cards`
- `admin-3-unassigned-rtl-panel`
- `admin-dashboard-final`
- `bootstrap-1-alembic-authority`
- `ent-6-ui-and-live-simulator`
- `fix-registration-window-clock-domain`
- `nav-1-utility-route-visibility`
- `nav-2-breadcrumb-placement`
- `nav-3-remaining-field-labels`
- `role-1-session-identity`
- `role-2-route-authorization`
- `role-3-device-scope`
- `ui-1-frontend-audit`
- `worktree-fleet-overview-visual-v2`
- `worktree-plant-monitoring-architecture`

Diverged from `main` (has commits `main` doesn't):

| Branch | Unique commits | Behind main | Note |
|---|---|---|---|
| `client-demo-1` | 7 | 39 | expected — delivery branch, see docs/CLIENT_DELIVERY.md |
| `client-release` | 12 | 189 | expected — delivery branch, see docs/CLIENT_DELIVERY.md |
| `ctx-1-context-architecture` | 6 | 0 | current branch — this session's in-progress work, not a stale fork |

## Decisions

8 ADR(s) in `docs/decisions/`. See `docs/context/DECISION_INDEX.md` for the full index.

| ADR | Status | Implemented-by |
|---|---|---|
| ADR-001-event-classification-no-thresholds.md | Approved | `bb1e2e9` (event consumption), extended by every commit that reads `services/event_semantics.py` |
| ADR-002-fleet-attention-is-freshness-only.md | Approved | `29a4c5a` (Fleet Condition panels on the Overview page) |
| ADR-003-location-is-plant.md | Approved | `699ece0` (normalized `plant_monitoring` schema) |
| ADR-004-device-scope-is-not-user-selectable.md | Approved | `9966bd7` (`DeviceScope` as the single device-visibility authority), merged to `main` at `71b8db6` |
| ADR-005-auto-refresh-is-page-owned-polling.md | Approved | `23642da` (device dashboard interval), `699ece0` (`refresh_interval_seconds` setting) |
| ADR-006-route-scoped-theming-is-architecture.md | Approved — not yet implemented | not yet — this ADR is the pre-commitment; implementation is CC-1 Phase 1 |
| ADR-007-event-demo-seed-uses-ingest-event.md | Approved — not yet implemented | not yet — this ADR is the pre-commitment; the seed itself is a CC-1 Phase 0 prerequisite |
| ADR-008-command-center-reuses-existing-read-paths.md | Approved — not yet implemented | `1940b93` (`FleetHealth`/freshness rollups), `bb1e2e9` (`list_recent_device_events`) — pre-existing; Command Center's own call sites not yet written |

## Active gate

CC-1 Phase 3+4 — Foundation and shell — full detail in `docs/context/ACTIVE_GATE.md`.

## Working tree

```
M docs/context/ACTIVE_GATE.md
 M docs/context/CURRENT_STATE.md
 M docs/context/DECISION_INDEX.md
 M docs/decisions/ADR-002-fleet-attention-is-freshness-only.md
?? "command center/"
?? docs/context/CC1_ROADMAP.md
?? docs/decisions/ADR-008-command-center-reuses-existing-read-paths.md
?? scripts/generate_workflow_deep_dive_pdf.py
?? scripts/generate_workflow_pdf.py
```

