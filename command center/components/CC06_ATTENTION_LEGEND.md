# CC-06 Attention Summary + Semantic Legend

## Purpose
Remove ambiguity from red/amber/purple status language and state what Command Center does **not** infer.

## Required copy
- `Critical event = Power Down` — persisted `power_down` event occurrence. Device definition: battery voltage `<3.61V`.
- `Warning event = Battery Low` — persisted `battery_low` event occurrence. Device definition: battery voltage `<3.75V`.
- `Stale = current data older than freshness threshold`.
- `No Data = current reading unavailable according to monitoring policy`.

## EVT-D4 note
The voltage values are explanatory device/Functional-Spec thresholds only. Command Center consumers do not classify events from numeric voltage payloads.

## Current-state note
Critical/Warning event occurrence does not imply that state is still active. Current Critical/Warning fleet counts remain unavailable until clear/resolve semantics are defined.

## Interaction
Optional info tooltip may explain that temperature criticality is not yet defined by a client-approved threshold.
