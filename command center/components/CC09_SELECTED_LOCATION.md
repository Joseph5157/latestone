# CC-09 Selected Location / Transformer Attention Concentration

## Purpose
Replace the unsupported map with a higher-value Plant-to-transformer investigation surface.

## Vocabulary
Selected Location = Selected Plant.

## Header
- selected Plant name
- affected RTL total
- Open Plant

## Rows
- transformer code
- Critical current-state slot — unavailable in CC-1
- Warning current-state slot — unavailable in CC-1
- Stale count
- No Data count
- total affected = Stale + No Data
- % of transformer's visible RTLs
- last update
- optional trend where meaning is already supported

## Ordering
Most currently affected transformer first.

## Interaction
Transformer code opens transformer detail.

## Electrical-event guardrail
Do not populate Critical/Warning columns from historical `power_down` / `battery_low` event presence. Those events have no approved clear/resolve semantics. Render `—` / unavailable until a future current-state contract exists.

## Empty state
`No transformers currently require freshness attention in this Plant.`
