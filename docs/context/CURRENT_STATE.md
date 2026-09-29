# Current State

Status: generated
Date: 2026-09-29T03:17:33Z

Regenerate with `python scripts/build_context_pack.py`. Never hand-edit —
every fact here is derived from git, the test suite, and docs/decisions/.
For judgment calls (why something is frozen, what's in scope right now),
see docs/context/ACTIVE_GATE.md and the ADRs, not this file.

## Baseline

- `main` = `0d2f4fd` "feat(data): establish read-only client RTL database boundary"
- Working tree: 10 entries — see below

## Test baseline

- `python -m pytest -m "not db"` → 3158 passed, 2 skipped, 731 deselected in 41.72s

## Branches

Fully merged into `main` — stale pointers, safe to delete, not pending work:

- `admin-1-administration-summary`
- `admin-2-administration-cards`
- `admin-3-unassigned-rtl-panel`
- `admin-dashboard-final`
- `alarm-history`
- `app-dark-mode`
- `assign-toolbar`
- `auth-sidebar-sync`
- `bootstrap-1-alembic-authority`
- `cc-1-command-center-foundation`
- `cc-banner-retire`
- `cc-filter-fast`
- `cc-gauges`
- `cc-severity-cards`
- `cc-visuals`
- `click-to-filter`
- `client-sync-5`
- `colour-key`
- `ctx-1-context-architecture`
- `dark-mode-polish`
- `docs-sync`
- `ent-6-ui-and-live-simulator`
- `fix-registration-window-clock-domain`
- `live-sim-scenarios-1`
- `nav-1-utility-route-visibility`
- `nav-2-breadcrumb-placement`
- `nav-3-remaining-field-labels`
- `overview-cc-polish`
- `overview-cc-redesign`
- `overview-stats-cards`
- `problem-dots`
- `problem-groups`
- `problem-groups-fold`
- `problem-text-colour`
- `role-1-session-identity`
- `role-2-route-authorization`
- `role-3-device-scope`
- `severity-palette`
- `tech-workspace-1`
- `ui-1-frontend-audit`
- `working-card`
- `worktree-fleet-overview-visual-v2`
- `worktree-plant-monitoring-architecture`

Diverged from `main` (has commits `main` doesn't):

| Branch | Unique commits | Behind main | Note |
|---|---|---|---|
| `cc-1-command-center-progress` | 15 | 475 | REVIEW — unexpected divergence |
| `client-demo-1` | 7 | 325 | expected — delivery branch, see docs/CLIENT_DELIVERY.md |
| `client-release` | 12 | 475 | expected — delivery branch, see docs/CLIENT_DELIVERY.md |

## Decisions

28 ADR(s) in `docs/decisions/`. See `docs/context/DECISION_INDEX.md` for the full index.

| ADR | Status | Implemented-by |
|---|---|---|
| ADR-001-event-classification-no-thresholds.md | Approved | `bb1e2e9` (event consumption), extended by every commit that reads `services/event_semantics.py` |
| ADR-002-fleet-attention-is-freshness-only.md | Superseded | `29a4c5a` (Fleet Condition panels on the Overview page) |
| ADR-003-location-is-plant.md | Approved | `699ece0` (normalized `plant_monitoring` schema) |
| ADR-004-device-scope-is-not-user-selectable.md | Approved | `9966bd7` (`DeviceScope` as the single device-visibility authority), merged to `main` at `71b8db6` |
| ADR-005-auto-refresh-is-page-owned-polling.md | Approved | `23642da` (device dashboard interval), `699ece0` (`refresh_interval_seconds` setting), `b8315c8` (Command Center's own interval and failure contract) |
| ADR-006-route-scoped-theming-is-architecture.md | Superseded | `267b11a` |
| ADR-007-event-demo-seed-uses-ingest-event.md | Approved — not yet implemented | not yet — this ADR is the pre-commitment; the seed itself is a CC-1 Phase 0 prerequisite |
| ADR-008-command-center-reuses-existing-read-paths.md | Approved | `1940b93` (`FleetHealth`/freshness rollups), `bb1e2e9` (`list_recent_device_events`); Command Center call sites `cc6b67a` (Phase 3+4), `1a1be90` (Phase 5), `04e3bfa` (Phase 6) |
| ADR-009-priority-investigation-ranks-on-freshness-only.md | Superseded | `ce5d4ac` |
| ADR-010-monitoring-reset-preserves-operational-history.md | Approved | `29f5290` |
| ADR-011-affected-locations-is-top-n-with-disclosure.md | Superseded | `6aafc4c` |
| ADR-012-rank-bars-are-capped-and-route-themed.md | Superseded | `e33d0e1` (bar cap, route-scoped tokens), `59f92a9` (shrink, scrollbar gutter) |
| ADR-013-export-data-is-a-capability.md | Approved | `723dd0b` |
| ADR-014-latest-reads-are-bounded-seeks.md | Approved | `3b33015` (`fix(db): bound latest-reading query cost`; full sha 3b330152c176a51af570f148008413c05c435d45 — the commit carries this ADR too, so the sha is recorded here afterwards, as FIX-1 did in `5901945`) |
| ADR-015-credentials-name-logins-not-roles.md | Approved | `f0862d0` (`feat(auth): add credentialed demo personas`; full sha f0862d085680ca0d4b0f774d6b44f5d224810b75 — the commit carries this ADR too, so the sha is recorded here afterwards, as ADR-014 did) |
| ADR-016-operational-actions-are-shared-administration-is-not.md | Approved | `08e44af` (`feat(roles): expose technician device operations`; full sha 08e44af75c344533ccca50ce3d72de27c45e1243 — the commit carries this ADR too, so the sha is recorded here afterwards, as ADR-014 and ADR-015 were) |
| ADR-017-rtl-commands-are-the-protocol-neutral-transport-seam.md | Approved | `831ea2b3ea612921d9fb44813924aeea43922fb0` (`feat(integration): add protocol-neutral RTL command foundation`) |
| ADR-018-simulator-transport-is-not-the-eskom-protocol.md | Approved | `bb7fea3af0c85cff3cdf84dd82a36a2ed397644a` (`feat(integration): add simulated RTL command lifecycle`) |
| ADR-019-simulated-event-source-reuses-canonical-ingestion.md | Approved | `a89fbf97b523aee6b63f8f6b80d5bda0fd0876e8` (`feat(integration): add simulated RTL event ingestion`) |
| ADR-020-notification-delivery-is-separate-from-the-in-app-projection.md | Approved | `0b2a4d5ec2c88d5a395729d30dee86abf1b6fb4d` (`feat(integration): add notification delivery abstraction`) |
| ADR-021-freshness-threshold-is-admin-configurable-and-read-live.md | Approved | `08acb6e` (`feat(freshness): let Administrators set the freshness threshold live`) |
| ADR-022-registration-enforces-the-5-digit-uid-fleet-wide.md | Approved | `c47cf87` (`feat(register): redesign Register Device and enforce the 5-digit UID fleet-wide`) |
| ADR-023-temperature-condition-uses-admin-limits.md | Approved | `a0f1223` (`feat(temperature): condition per RTL against administrator limits (ADR-023)`) |
| ADR-024-overview-and-command-center-split-by-question.md | Approved | `2cfad36` (switch-over; built in FO-NEW-1, CC-NEW-1, CC-ACTIONS-1) |
| ADR-025-dark-mode-is-app-wide-and-remembered.md | Approved | `07d1b02` (app-wide theme, store, toggle); `0503480` (components) |
| ADR-026-one-colour-key-colour-means-urgency.md | Approved | `21a5d1f`; `0a84648` (badge-vs-dot); `fd84225` (coloured text) |
| ADR-027-device-page-alarm-history.md | Approved | `6bbf26c` |
| ADR-028-ring-gauges-for-part-of-whole-counts.md | Approved | `7973853` |

## Active gate

NONE — full detail in `docs/context/ACTIVE_GATE.md`.

## Working tree

```
D "DEM-2788838 Digital Incubator - RTL PAD  v0.7.pdf"
 M docs/context/ACTIVE_GATE.md
 M docs/context/CURRENT_STATE.md
 M docs/database/RTL_READ_ONLY_ACCESS.md
 M repositories/rtl_temperature_repository.py
 M tests/test_rtl_temperature_repository.py
?? .test-tmp/
?? "Remote Temperature Logger  Functional Specification RTL v0.md"
?? docs/audit/project-audit-1/results/
?? docs/audit/rtl-fleet-02/
```

