# CC-08 Recent Operational Events

## Purpose
Answer: `What changed recently?`

## Visual
Dense list/table with more width than Affected Locations.

## Columns
- time
- RTL / entity
- event
- Location (Plant where resolvable)
- detail
- action

## Rules
- newest first
- persisted events only
- no acknowledge control
- Open Asset only when resolvable
- unregistered UID remains non-link text where appropriate
- `power_down` event may use Critical event presentation
- `battery_low` event may use Warning event presentation
- classification is by event type, never numeric battery payload
- event occurrence does not imply current-state persistence

## Browser-verification prerequisite
Existing standard demo seeds do not populate persisted events. Use the separate opt-in deterministic Command Center event demo seed specified in the implementation plan when a populated browser state is required.
