# Active Gate

Status: Approved
Date: 2026-08-29
Gate: CC-1 Phase 0 — Repository reconciliation and demo prerequisites
Precondition: branch `ctx-1-context-architecture` merged to `main`
Flow: PLAN → **REVIEW GATE (this document)** → IMPLEMENT → TEST/VISUAL VERIFY → IMPLEMENTATION REVIEW → COMMIT → PUSH GATE
Commit/push permission: NOT GRANTED. Phase 0 is verification-only. No CC-1
code may be written or committed until the Codex plan (below) returns and is
reviewed against the two named scrutiny points.

This file describes exactly one gate. When CC-1 moves to Phase 1, rewrite
this file for that gate — don't append; a gate file describing two gates at
once is how the old planning prompts went stale. The finished gate's content
belongs in `docs/decisions/` (if it produced a durable decision) or
`docs/archive/` (if it was a one-time planning artifact), not left here.

## Task

Send `command center/09_CODEX_PLANNING_PROMPT.md` to Codex, read-only. Get an
implementation plan back. Review that plan against this repository before
any implementation begins.

Scrutinize hardest:
1. Is the route-scoped theme hook (ADR-006) genuinely minimal, or does it
   drag `app_shell`/`app_sidebar`/`app_header` in together? ADR-006 leaves
   this deliberately open — verify at plan-review time, don't accept a plan
   that touches all three without justification.
2. Does the event demo seed go through `services/device_event_service.py`'s
   `ingest_event()`, or does it open a second write path straight to
   `repositories/plant_monitoring_repository.py`'s `insert_device_event()`?
   ADR-007 requires the former.

## Phase 0 checklist — verified 2026-08-29, not aspirational

- **Branch and HEAD**: `main` = `1d7c414`. This branch adds 3 commits
  (`5d2dfe3`, `1c394ad`, `af86dca`) not yet merged.
- **Working tree**: clean except `command center/` (untracked by design —
  see Verification below), `scripts/generate_workflow_pdf.py` and
  `scripts/generate_workflow_deep_dive_pdf.py` (unrelated, pre-existing).
- **Unmerged local UX commits**: none. Surveyed all 18 non-`main` local
  branches: every branch except `client-demo-1` (+7) and `client-release`
  (+12) shows zero commits not already in `main` — stale pointers, not
  pending work. The two exceptions are the client-delivery branches
  (`docs/CLIENT_DELIVERY.md`) and their divergence is expected, not UX work
  CC-1 needs to account for.
- **Baseline tests**: 2032 passed, 466 deselected (`python -m pytest -m "not
  db"`).
- **12 `components/CC*.md` specs present**: confirmed, `command
  center/components/CC01..CC12`.
- **`Location = Plant`**: confirmed — see ADR-003.
- **`/` remains Overview**: confirmed — `routes.py:66`,
  `parse_pathname`: `pathname in ("/", "/plants", "/plants/")` →
  `Route(name="overview")`. CC-1 must not change this line.
- **Event ingestion path inspected, seed plan written**: see ADR-007.

## Decisions this gate depends on

- [ADR-001](../decisions/ADR-001-event-classification-no-thresholds.md) — event classification, no numeric thresholds
- [ADR-002](../decisions/ADR-002-fleet-attention-is-freshness-only.md) — Requires Attention = Stale + No Data
- [ADR-003](../decisions/ADR-003-location-is-plant.md) — Location = Plant
- [ADR-004](../decisions/ADR-004-device-scope-is-not-user-selectable.md) — device scope is authorization-derived
- [ADR-005](../decisions/ADR-005-auto-refresh-is-page-owned-polling.md) — auto-refresh is page-owned polling
- [ADR-006](../decisions/ADR-006-route-scoped-theming-is-architecture.md) — theming is Phase-1 architecture, open question on shell-hook scope
- [ADR-007](../decisions/ADR-007-event-demo-seed-uses-ingest-event.md) — event seed write path

## Non-goals (explicit)

- No CC-1 implementation code in this gate — planning and verification only.
- No modification to any existing Fleet Overview presentation component
  (`command center/07_IMPLEMENTATION_PLAN.md` gate principle: Fleet Overview
  is frozen; CC-1 is a parallel build, not a refactor of it).
- No branch cleanup, however tempting the stale-branch list above looks.
  `command center/07_IMPLEMENTATION_PLAN.md` Phase 0 says so explicitly: "do
  not mix unrelated branch cleanup into CC-1."
- No shared-file edits beyond `routes.py` and `services/authorization.py`,
  plus whatever the Codex plan names for the theme hook — and that naming
  must happen in the plan-review step, not be assumed in advance.

## Relevant files

- `command center/09_CODEX_PLANNING_PROMPT.md` — what gets sent
- `command center/07_IMPLEMENTATION_PLAN.md` — Phase 0/1 source
- `routes.py` — approved shared-modify surface
- `services/authorization.py` — approved shared-modify surface (`ROUTE_POLICY`)
- `services/device_event_service.py` — `ingest_event()`, the required seed entry point
- `assets/app.css` — theme token surface for Phase 1

## Required tests

- `python -m pytest -m "not db" -v` before and after Phase 0 verification —
  must stay green; this gate changes no application code, so any red test
  here is a pre-existing problem, not something to fix under this gate.

## Known ambiguities

- The two scrutiny points under Task, above — unresolved until the Codex
  plan returns.
- Whether `command center/` itself should ever move into git tracking is an
  open question this gate does not answer. It stays untracked,
  MANIFEST-verified for now (see Verification).

## Verification

The pack is untracked (deliberately — see `docs/CLIENT_DELIVERY.md`), so git
cannot detect drift in it. Its own SHA-256 manifest is the only integrity
check available:

```
cd "command center" && sha256sum -c <(sed -n '/## SHA-256/,$p' MANIFEST.txt | tail -n +5)
```

Last run 2026-08-29: all 23 payload files `OK`, unmodified since the
2026-08-28 freeze. Re-run before trusting the pack if this file's stamped
date is more than a few days old — `scripts/build_context_pack.py` does this
automatically.
