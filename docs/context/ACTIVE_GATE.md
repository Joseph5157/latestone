# Active Gate

Status: Approved
Date: 2026-08-30
Gate: CC-1 Phase 10 — Priority Investigation
Precondition: Phase 9 complete and committed (`a49620f`), browser-verified.
Flow: DECIDE (complete) → IMPLEMENT (complete) → TEST (complete) →
FRESHNESS SEED (built, **deliberately not applied**) → VISUAL VERIFY
(**deferred — see below**) → COMMIT → **FULL STOP**
Commit/push permission: Commit GRANTED on `cc-1-command-center-foundation`
with the deferred-verification note below intact. Push NOT GRANTED.
**Stop after committing.**

## Outcome

> **Phase 10 implementation and semantic verification complete. Mixed
> Fresh/STALE/NO_DATA browser verification deferred because the available
> freshness seed is destructive and lacks a safe rollback path.**

This is a blocked visual-verification condition, not a Phase 10 failure.
The blocker is tracked as **SEED-RESET-1** in
`docs/context/KNOWN_DEFECTS.md`, to be fixed before the Phase 12 visual
acceptance pass and explicitly not inside this tranche.

`db/seed_freshness_demo.py` ships built, tested and unapplied. It is
dry-run by default; running it with `--apply` is a one-way local change
until SEED-RESET-1 is fixed.

## Task

The last question in the investigation chain:

> How much? → Where? → Which transformer? → What just happened? →
> **Which exact RTLs do I open first?**

A compact ranked list of individual RTLs. It must NOT become an alarm
queue.

## The decision record

`docs/decisions/ADR-009-priority-investigation-ranks-on-freshness-only.md`
holds the reasoning. The five rulings it fixes:

- **D1** Population is `STALE + NO_DATA`, the same as Needs Attention
  (ADR-002). FRESH never appears. No event affects membership or order.
- **D2** Order: NO_DATA before STALE via `severity_rank` (never a private
  copy) → within NO_DATA, plant / transformer / device case-insensitively →
  within STALE, oldest lagging metric first → `device_id` always last.
- **D3** A STALE age is the **min** over the device's metric timestamps, on
  a new `FleetHealth.device_oldest_metric_updated` derived from rows
  already fetched. Populated **only when every metric row has a
  timestamp**, so a NO_DATA device holds `None` and there is no number to
  fabricate a duration from.
- **D4** Copy names what it measures. NO_DATA reuses
  `situation_summary.NO_DATA_EXPLANATION`; STALE says "Oldest monitored
  metric last reported …", never "latest available monitored data".
- **D5** Eight rows, and no footer link — `/command-center/locations` is
  the ranked PLANT list (ADR-003), not an RTL list, and an approximate
  destination is worse than none.

## The correction that produced D3

Worth restating, because the plan and the code disagreed and the code won
(`SOURCE_AUTHORITY.md` rung 2 over rung 4):

`device_last_updated` is a MAX over metric rows
(`services/monitoring_service.py:388-394`). On a device that is STALE
because one of eight metrics stopped, it holds the FRESHEST metric's time —
so a row built on it reads `STALE · 2m ago` and the ranking key sorts a
nine-hour outage below a forty-minute one. The min is the honest number and
is available from the same pass.

## Read paths — ADR-008 is UNCHANGED

Phase 10 adds no read path. It composes:

- `get_fleet_health()` — already fetched once per render by the façade.
- `hierarchy_service.list_device_paths()` — the batched label lookup
  ADR-008 approved in Phase 9, called ONCE for the whole render: the union
  of the event rows' devices and the attention population. The NO_DATA
  order is by plant NAME, so the names decide which eight rows survive the
  cap and cannot be fetched for the eight alone. Two batched calls would
  still be two queries — the façade's contract is one per read path.

If this phase appears to need a third read, that is the signal to stop and
re-open ADR-008, not to add one quietly.

## Boundary

`command_center_service.py` produces presentation-ready priority rows —
tone, badge label, hierarchy label, age sentence, href. The component
renders them and reproduces no freshness ranking (AGENTS.md rule 8).

## Required tests

- only STALE / NO_DATA RTLs enter the list; FRESH never appears
- NO_DATA ranks before STALE
- one fresh metric + one never-reported metric stays NO_DATA
- NO_DATA never gets a fabricated duration
- a STALE age comes only from trustworthy stale timestamps — asserted
  against the mixed 7-fresh/1-stale device, where a max-based age would
  pass a naive test and this one must not
- events do not change priority ranking (a storm of events, identical
  order)
- a missing hierarchy label falls back to the stable id without dropping
  the device
- ordering is fully deterministic
- the device link resolves through the existing route contract
- an empty attention population renders a measured calm state
- zero monitored RTLs stays distinct from zero affected RTLs
- Phase 5-9 cards remain unchanged

## Blocking debt: the freshness seed — BUILT, NOT APPLIED

`db/seed_freshness_demo.py` covers four RTLs: a Fresh control, a plainly
Stale one, a **mixed-metric Stale** one (D3's case — seven metrics fresh,
one silent for hours) and a mixed-metric NO_DATA one.

It cannot be applied safely. Staleness and absence cannot be INSERTED —
freshness is `now - max(reading_ts)` and NO_DATA is the absence of a row —
so the seed must DELETE readings, and SEED-RESET-1 means there is no
working way back. The seed is therefore complete and parked.

Consequence, stated plainly: **D3's mixed-metric branch is verified by test
only.** It has not been seen on screen.

## Non-goals

⛔ event severity ranking · ⛔ Critical/Warning current counts · ⛔ theming ·
⛔ auto-refresh · ⛔ Top-N Affected Locations refinement · ⛔ Asset Navigator
changes · ⛔ `/` landing-route change · ⛔ acknowledge/resolve workflows ·
⛔ no push

## Carried forward, not in this gate

- Browser-verify EVT-D5 with a NON-ADMIN before the final client pass. The
  positive case was verified in Phase 9 (an administrator sees the
  unregistered-UID row); the negative case is covered by test only.
- Consider renaming the Recent Events footer to "Open Notification
  Center →". The destination is correct; the label says *notifications* on
  a panel titled *Events*.
