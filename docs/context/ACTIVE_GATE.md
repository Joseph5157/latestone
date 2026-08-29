# Active Gate

Status: Approved
Date: 2026-08-29
Gate: CC-1 Phase 6 — Electrical Condition Presentation
Precondition: Phase 5 complete and committed (`1a1be90`), approved by the
user 2026-08-29.
Flow: PLAN → REVIEW GATE (complete) → **IMPLEMENT** → TEST/VISUAL VERIFY → COMMIT → **FULL STOP (no Phase 7)**
Commit/push permission: Commit permitted on `cc-1-command-center-foundation`
once every item under "Required tests" and "Verification gate" passes. Push
NOT GRANTED. **Stop after committing — Phase 7 (Affected Locations) needs
its own approval.**

## Task

Build the Critical/Warning **visual system**, without pretending the backend
can establish current electrical state.

```
ELECTRICAL CONDITIONS

● CRITICAL
Power Down
Current state        —  Unavailable
Device definition       < 3.61 V

● WARNING
Battery Low
Current state        —  Unavailable
Device definition       < 3.75 V
```

The card shows the system **knows the category definitions** while being
explicit that it **does not know the current fleet count**.

## The semantic distinction this gate exists to encode

```
power_down  event → Critical presentation
battery_low event → Warning  presentation
```

**Never**:

```
battery_voltage < 3.61 → Critical
battery_voltage < 3.75 → Warning
```

The events arrive already classified by the device (ADR-001, EVT-D4). No
consumer-side voltage threshold logic may exist anywhere in Command Center.
The two numbers are **legend/display metadata only**.

Provenance: both figures are already spec-frozen in
`config/notifications.py` — the `power_down` category description says
"Battery voltage below 3.61 V ... (BR002, BR011)" and `battery_alarm` says
"below 3.75 V (BR002)". Command Center's short legend strings must be
bound to that source by test, not independently retyped, so a spec change
fails loudly instead of silently diverging.

## Current state stays Unavailable

Persisted events say something **occurred**. There is no trusted
resolve/clear/closure contract (ADR-001), so this gate must not produce
`3 Critical RTLs`, `5 Warning RTLs`, `0 Critical`, or `0 Warning` — every
one of those implies a current-state model that does not exist.

`current_count` is `None` as a **deliberate domain result**, not a missing
UI implementation. `Unavailable` must stay visually *and* structurally
distinct from numeric zero — a dash plus the word, never a rendered `0`.

## Explicitly out of scope this gate

- `Power Down events · last 24h` / `Battery Low events · last 24h` — these
  are event-window **occurrence** metrics, not current electrical state.
  They belong with Recent Operational Events (Phase 9), not here.
- Any current Critical/Warning count.
- Everything already withheld: affected-location bars, Plant selection,
  transformer concentration, priority assets, auto-refresh, dark/light
  theme, Asset Navigator on Command Center, changes to `/`, changes to
  Fleet Overview.

## Visual semantics

Colour describes the **event category/legend**, never the unavailable value:

- Critical / Power Down → red
- Warning / Battery Low → amber
- Unavailable current state → neutral/dashed

Colour never carries meaning alone — the severity label is always present
beside its marker.

## Service boundary (unchanged rule)

Components receive already-decided presentation values. They must not
import `event_semantics` and assemble meaning themselves. The façade
supplies a small model per condition: severity label, event type,
condition label, `current_count=None`, and the definition string.

## Decisions this gate depends on

- [ADR-001](../decisions/ADR-001-event-classification-no-thresholds.md) — events are pre-classified; no consumer threshold; no current-state count without a closure contract
- [ADR-002](../decisions/ADR-002-fleet-attention-is-freshness-only.md) — this card must not feed the attention total
- [ADR-008](../decisions/ADR-008-command-center-reuses-existing-read-paths.md) — service composes, components render

## Required tests

- `power_down` maps to Critical presentation
- `battery_low` maps to Warning presentation
- **No numeric threshold comparison exists** in Command Center service or
  component logic — a structural (AST) test, since `< 3.61 V` legitimately
  appears inside a display string and a naive text scan cannot tell the two
  apart
- Current Critical state is `None` / Unavailable
- Current Warning state is `None` / Unavailable
- Unavailable renders as `—` / `Unavailable`, never `0`
- Power Down definition text includes `< 3.61 V`
- Battery Low definition text includes `< 3.75 V`
- A high-temperature event does **not** become Critical merely because the
  visual system now has a Critical category
- Phase 5 freshness/attention values unchanged
- Fleet Overview unchanged

## Verification gate

Browser at 1440 / 1366 / 1024. Fleet Overview screenshot unchanged. No new
console errors. Then commit locally and **stop**.

## Relevant files

- `services/command_center_service.py` — the electrical condition model
- `components/command_center/situation_summary.py` — sibling card family
- `pages/command_center.py` — mounts the Exception Intelligence slot
- `callbacks/command_center.py` — populates it
- `assets/app.css` — `.command-center__` namespace only
- `config/notifications.py` — read-only; the definition figures' source
