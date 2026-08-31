# Codex Prompt — CC-1 Implementation

Implement the approved fresh Command Center in the existing RTL / Powerplant Dash application.

## Non-negotiable scope
- New route: `/command-center`
- `/` remains existing Overview during CC-1.
- Existing `/plants` Fleet Overview must not be redesigned, moved or refactored.
- Build a fresh Command Center component family and fresh CSS namespace.
- Reuse services/business truth, not Fleet Overview presentation.
- `services/command_center_service.py` is mandatory.
- `Location = Plant`.
- No map.
- No acknowledgement.
- No new schema migration.
- No duplicate SQL where current APIs already expose the facts.

## Route/authorization
Implement `/command-center` deliberately in:
- `routes.py`
- `services/authorization.py`

Update navigation mapping/item only after the route has explicit authorization policy. Preserve default-deny behavior for unknown routes.

## Required layout
### Header
- Command Center title
- fleet operational awareness subtitle
- asset search
- read-only scope indicator (`Scope · Current access`, or a truthful monitored-RTL count). No selector, no dropdown: `DeviceScope` is authorization-derived.
- Command Center-owned auto-refresh: its own `dcc.Interval`, cadence from `monitoring.refresh_interval_seconds`, plus `Last updated` and `Auto refresh · On`. Polling only; never claim live/streaming/push.
- Dark / Light toggle
- user context
- data-as-of timestamp

### Top row — four cards
1. Fleet Health
2. Needs Attention
3. Communication
4. Inventory

Communication ships with NO No Data age buckets. Freshness is per (device,
metric) with a worst-of RTL rollup, so a `NO_DATA` RTL may hold fresh readings
for other metrics and `device_last_updated` cannot establish how long the
missing metric has been absent. Render count + share of monitored RTLs + "At
least one monitored metric has no reading." Do not label them `Never reported`.

### Semantic strip
Explain:
- Critical event = persisted `power_down` event; device threshold `<3.61V` is explanatory copy only
- Warning event = persisted `battery_low` event; device threshold `<3.75V` is explanatory copy only
- Stale = existing current freshness threshold exceeded
- No Data = existing current monitoring no-data state

Do not implement any numeric battery-voltage classification in Command Center code.

### Middle row
Left: Affected Locations (Top 5), where Location = Plant, ranked by current Stale + No Data RTL burden.
Right: Recent Operational Events, larger than the location panel.

Do not add a second Plant/location stacked-bar overview.

### Lower row
Left: Selected Location / Transformer Attention Concentration, where selected Location = selected Plant.
Right: Shortcuts.

## Critical/Warning current-state rule
Build the visual slots now, but the current fleet-wide state is not derivable from persisted event history because no clear/resolve/closure semantics exist.

Therefore:
- current `critical_count` / `warning_count` values are unavailable (`None`) in CC-1;
- render a clear neutral unavailable/pending state, not zero;
- do not infer state persistence from most recent event;
- do not invent precedence between Critical/Warning and freshness states;
- Recent Operational Events may truthfully display Critical/Warning styling for already-classified `power_down` / `battery_low` event occurrences.

Never classify high temperature as Critical/Warning until a future client-approved contract exists.

## Mandatory Command Center service facade
Create `services/command_center_service.py` and centralize:
- scoped FleetHealth/current freshness view models
- current Requires Attention = Stale + No Data
- unavailable current Critical/Warning fields
- Plant ranking
- selected-Plant transformer concentration
- persisted event presentation mapping by event type

Callbacks must remain thin and must not duplicate semantic rules.

## Event rules
- use approved persisted-event read path
- newest first
- Open asset when resolvable
- no Acknowledge action
- do not classify from numeric payloads

## Event demo seed
Add an opt-in deterministic Command Center event demo seed only if required for browser verification. It must:
- remain separate from default/core seed behavior
- not run implicitly in production
- use the approved event ingestion/persistence path
- create representative persisted events such as startup, invalid_uid, power_down and battery_low where those event types are supported
- be documented and test-safe

## Theme architecture
Implement theme early, not as final polish:
- existing light tokens are reused where appropriate
- dark tokens are new and route-scoped
- while `/command-center` is active, selected appearance covers sidebar + content + utility/Asset Navigator chrome
- persist preference in session
- leaving `/command-center` restores existing appearance
- do not globally redesign other pages

Any additional shared shell/sidebar/navigation file beyond `routes.py` and `services/authorization.py` must match the approved planning output and be justified as the minimal theme hook.

## Styling
- IBM Plex Sans
- tabular numeric values
- restrained industrial borders/shadows
- Fresh/normal visually quiet
- Warning event amber
- Critical event red
- No Data purple
- Stale uses a distinct ochre/gold token, not the Warning token
- unavailable Critical/Warning current state uses neutral dashed/outlined treatment

## Verification
Run relevant tests and browser verification at 1440, 1366, 1024 and 768.
Verify:
- whole-shell dark mode on Command Center
- whole-shell light mode on Command Center
- non-CC pages retain existing appearance
- `/plants` has not regressed
- `/` still maps to existing Overview
- no horizontal overflow
- all direct links
- each panel's populated/empty/error/unavailable states
- Recent Events with deterministic persisted demo events where needed
- no numeric threshold classification in Command Center consumer code

## Git gate
Do not commit or push.

Finish with:
- files added
- files modified
- tests run/results
- browser checks
- known limitations
- explicit statement that Fleet Overview was left untouched
- explicit statement that current Critical/Warning state remains unavailable pending event closure semantics
- stop before commit/push
