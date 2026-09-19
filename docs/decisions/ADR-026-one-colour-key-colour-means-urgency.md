# ADR-026: One colour key for the whole dashboard — colour means urgency

Status: Approved
Date: 2026-09-19
Evidence: `components/status_colors.py` (the key and both tone maps),
`components/fleet_overview.py`, `components/attention.py`,
`assets/app.css` (`--sev-*` tokens, `.status-chip`)
Implemented-by: `21a5d1f`

## Context

The Fleet Overview and the Command Center already drew from one palette
(SEVERITY-PALETTE-1), yet read as different systems:

- The same colour carried different meanings. On the Overview red meant a
  temperature at or above the critical limit, nothing else; on the Command
  Center red also covered Power Down and amber also covered Battery Low, and
  the Alarms-per-day legend labelled red plainly "Power Down".
- "Limits not set" was plain grey on the Overview but the Command Center's
  grey-blue, which there also meant Sensor Error.
- Each page kept its own condition-to-tone table, so they could drift.
- Tags were drawn two ways (soft fill vs outline), bars at different heights,
  and the Overview's Hottest-now card used the accent blue, which elsewhere
  marks a selection.

The user decided (2026-09-19): one colour key across the dashboard, so a
colour is learnt once; the Overview stays temperature-only with clearer
labels rather than counting alarms.

## Decision

Colour states **how urgent**; the label states **what**. One key, one module:

| Tone | Name | Covers |
|---|---|---|
| critical (red) | Critical — act now | Temperature at/above the critical limit; Power Down |
| warning (amber) | Warning — check soon | Temperature at/above the warning limit; Battery Low |
| nodata (purple) | No data | No recent reading from the RTL |
| info (grey-blue) | Device fault | Sensor Error |
| normal (green) | Normal | Temperature below the warning limit |
| none (grey) | Not rated | Temperature limits not set |

- Blue (`--color-accent`) marks links and the current selection only; it is
  never a status.
- `components/status_colors.py` owns the key, `CONDITION_TONE` and
  `KIND_TONE`; no page keeps its own table.
- Every status tag is one `.status-chip` style; every status colour is a
  `--sev-*` token (including `--sev-none`), restated for dark.
- Labels name the coverage where a colour covers more than one thing
  ("Critical temperature", "Critical · Power Down").
- Both pages show the key (a "Colour key" disclosure).
- Critical remains the only tone that tints its card (SEVERITY-PALETTE-1).

## Consequences

- A new page with a status must take its tone from `status_colors`; tests
  fail on a tone outside the key or a status colour outside the tokens.
- The Command Center's "Sensor" card is renamed "Device fault".
- The Overview's Critical/Warning counts stay temperature-only and so remain
  smaller than the Command Center's; the labels say why.
