# Current State

Status: generated
Date: 2026-09-03T14:49:09Z

Regenerate with `python scripts/build_context_pack.py`. Never hand-edit —
every fact here is derived from git, the test suite, and docs/decisions/.
For judgment calls (why something is frozen, what's in scope right now),
see docs/context/ACTIVE_GATE.md and the ADRs, not this file.

## Baseline

- `main` = `0c40478` "docs(context): close ROLE-4 browser acceptance"
- Working tree: 39 entries — see below

## Test baseline

- `python -m pytest -m "not db"` → 2651 passed, 510 deselected in 20.72s

## Branches

Fully merged into `main` — stale pointers, safe to delete, not pending work:

- `admin-1-administration-summary`
- `admin-2-administration-cards`
- `admin-3-unassigned-rtl-panel`
- `admin-dashboard-final`
- `bootstrap-1-alembic-authority`
- `cc-1-command-center-foundation`
- `ctx-1-context-architecture`
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
| `cc-1-command-center-progress` | 11 | 241 | REVIEW — unexpected divergence |
| `client-demo-1` | 7 | 91 | expected — delivery branch, see docs/CLIENT_DELIVERY.md |
| `client-release` | 12 | 241 | expected — delivery branch, see docs/CLIENT_DELIVERY.md |

## Decisions

16 ADR(s) in `docs/decisions/`. See `docs/context/DECISION_INDEX.md` for the full index.

| ADR | Status | Implemented-by |
|---|---|---|
| ADR-001-event-classification-no-thresholds.md | Approved | `bb1e2e9` (event consumption), extended by every commit that reads `services/event_semantics.py` |
| ADR-002-fleet-attention-is-freshness-only.md | Approved | `29a4c5a` (Fleet Condition panels on the Overview page) |
| ADR-003-location-is-plant.md | Approved | `699ece0` (normalized `plant_monitoring` schema) |
| ADR-004-device-scope-is-not-user-selectable.md | Approved | `9966bd7` (`DeviceScope` as the single device-visibility authority), merged to `main` at `71b8db6` |
| ADR-005-auto-refresh-is-page-owned-polling.md | Approved | `23642da` (device dashboard interval), `699ece0` (`refresh_interval_seconds` setting), `b8315c8` (Command Center's own interval and failure contract) |
| ADR-006-route-scoped-theming-is-architecture.md | Approved — implemented at CC-1 Phase 11 | `267b11a` |
| ADR-007-event-demo-seed-uses-ingest-event.md | Approved — not yet implemented | not yet — this ADR is the pre-commitment; the seed itself is a CC-1 Phase 0 prerequisite |
| ADR-008-command-center-reuses-existing-read-paths.md | Approved | `1940b93` (`FleetHealth`/freshness rollups), `bb1e2e9` (`list_recent_device_events`); Command Center call sites `cc6b67a` (Phase 3+4), `1a1be90` (Phase 5), `04e3bfa` (Phase 6) |
| ADR-009-priority-investigation-ranks-on-freshness-only.md | Approved | `ce5d4ac` |
| ADR-010-monitoring-reset-preserves-operational-history.md | Approved | `29f5290` |
| ADR-011-affected-locations-is-top-n-with-disclosure.md | Approved | `6aafc4c` |
| ADR-012-rank-bars-are-capped-and-route-themed.md | Approved | `e33d0e1` (bar cap, route-scoped tokens), `59f92a9` (shrink, scrollbar gutter) |
| ADR-013-export-data-is-a-capability.md | Approved | `723dd0b` |
| ADR-014-latest-reads-are-bounded-seeks.md | Approved | `3b33015` (`fix(db): bound latest-reading query cost`; full sha 3b330152c176a51af570f148008413c05c435d45 — the commit carries this ADR too, so the sha is recorded here afterwards, as FIX-1 did in `5901945`) |
| ADR-015-credentials-name-logins-not-roles.md | Approved | `f0862d0` (`feat(auth): add credentialed demo personas`; full sha f0862d085680ca0d4b0f774d6b44f5d224810b75 — the commit carries this ADR too, so the sha is recorded here afterwards, as ADR-014 did) |
| ADR-016-operational-actions-are-shared-administration-is-not.md | Approved | `08e44af` (`feat(roles): expose technician device operations`; full sha 08e44af75c344533ccca50ce3d72de27c45e1243 — the commit carries this ADR too, so the sha is recorded here afterwards, as ADR-014 and ADR-015 were) |

## Active gate

AUTH-HARDEN-1 (+ AUTH-HARDEN-1R, AUTH-HARDEN-1R2) — server-trusted authorization — full detail in `docs/context/ACTIVE_GATE.md`.

## Working tree

```
M .env.example
 M app.py
 M callbacks/auth.py
 M callbacks/command_center.py
 M callbacks/device.py
 M callbacks/device_admin.py
 M callbacks/device_assign.py
 M callbacks/device_manage.py
 M callbacks/device_register.py
 M callbacks/equipment_selector.py
 M callbacks/listings.py
 M callbacks/notifications.py
 M callbacks/report_center.py
 M callbacks/routing.py
 M callbacks/user_admin.py
 M config/settings.py
 M docs/context/ACTIVE_GATE.md
 M services/auth_service.py
 M services/authorization.py
 M services/device_scope.py
 M services/hierarchy_service.py
 M tests/test_action_guard_callbacks.py
 M tests/test_admin_summary_wiring.py
 M tests/test_command_center_refresh.py
 M tests/test_device_admin_action_routing.py
 M tests/test_device_admin_inactive_filter.py
 M tests/test_equipment_selector.py
 M tests/test_fleet_condition.py
 M tests/test_report_center.py
 M tests/test_report_export_authorization.py
 M tests/test_route_enforcement.py
 M tests/test_route_scope.py
 M tests/test_route_scope_db.py
 M tests/test_technician_operations.py
 M tests/test_user_admin_callbacks.py
?? debug.log
?? tests/auth_test_support.py
?? tests/test_auth_harden.py
?? tests/test_auth_harden_repair.py
```

