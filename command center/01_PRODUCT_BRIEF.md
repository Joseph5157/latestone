# Command Center Product Brief

## Product objective
Create a new parallel operational workspace that answers, within one screen:

1. What requires attention now?
2. At which plants is that attention concentrated?
3. What changed recently?
4. Which transformer / RTL should the operator inspect next?

During CC-1 this page is **not** the application root landing route. `/` and `/plants` continue to resolve to the existing Fleet Overview. Making Command Center the default landing page is a separate future gate after side-by-side validation.

## Primary users
### Administrator / control-room operator
Needs fast situational awareness across the visible fleet and direct drill-through into assets.

### Technician
May use the Command Center in the field. A high-contrast light appearance is therefore mandatory alongside the dark control-room appearance.

## UX philosophy
- Exception-first rather than inventory-first.
- Healthy / normal state is visually quiet.
- Abnormal or attention-relevant state carries visual weight.
- Operators should not need to browse four hierarchy levels to find a problem.
- Trends and event context should reduce time-to-insight.
- Monitoring and configuration remain different interaction modes.
- Event occurrences and current monitoring state must never be conflated.

## Location vocabulary
For CC-1, **Location = Plant**. The UI may display the friendlier word `Location`, but every selected/ranked location must resolve to a real Plant identity from the existing hierarchy.

## Electrical/event semantics
- A persisted `power_down` event may be presented as `Critical` for that event occurrence.
- A persisted `battery_low` event may be presented as `Warning` for that event occurrence.
- Voltage thresholds shown in legends/tooltips document the device event meaning only; the Command Center must not perform numeric threshold classification.
- There is no approved event closure/resolution model today, so Command Center must not claim a current Critical/Warning fleet population from historical event presence.

## Non-goals for this tranche
- Rewriting the application in React / Vue.
- Removing or redesigning the current Fleet Overview.
- Changing `/` to land on Command Center.
- Building a GIS map.
- Building alarm acknowledgement.
- Inventing temperature critical thresholds.
- Reclassifying battery/power events from numeric payloads.
- Rebuilding existing backend repositories or adding new SQL for data already available.

## Success criteria
- Operator can identify the top affected Plant without scrolling.
- Operator can select a Plant and immediately see which transformers drive current freshness attention.
- Operator can see recent persisted events in a larger operational stream.
- Operator can open a relevant asset from Plant, transformer or recent-event surfaces.
- Current Critical/Warning slots render honestly when current-state aggregation is unavailable.
- No current Fleet Overview presentation component is disturbed.
- Dark and light modes include the surrounding application chrome on `/command-center` while non-CC routes remain visually unchanged.
