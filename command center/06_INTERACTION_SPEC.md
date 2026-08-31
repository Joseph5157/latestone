# Command Center Interaction Specification

## Header
### Search
Search assets by supported identifiers/names. Search result routes to the authoritative existing asset page.

### Scope — read-only indicator
The scope indicator is **read-only in CC-1**. There is no scope switching.
`DeviceScope` is authorization-derived, so no dropdown or scope-changing
control may be added. Render `Scope · Current access`, or a truthful
monitored-RTL count. Do not create a fake authorization boundary in the UI.

### Auto refresh — Command Center-owned
Command Center owns its own `dcc.Interval`; it does not reflect a Fleet
cadence, because none exists.

- cadence comes from `monitoring.refresh_interval_seconds`
- show `Last updated` and `Auto refresh · On`
- a manual `Refresh` control may also be provided
- show `data as of` separately from browser wall-clock time
- polling only — never describe it as live/streaming/push

Across a routine refresh:
- the currently selected Plant must survive where possible
- refreshing must not blank the whole page
- a failed refresh retains the last successful snapshot and shows a truthful
  stale/error state, following existing application conventions

### Theme toggle
Dark / Light. Persist in session. On `/command-center`, the choice affects the whole visible shell; on other routes, the existing appearance remains unchanged.

## Communication / No Data
- No Data has **no duration buckets** in CC-1.
- Show the No Data count, its share of monitored RTLs, and the explanatory
  line "At least one monitored metric has no reading."
- Do not derive age buckets from `device_last_updated`: an RTL is `NO_DATA`
  when any one metric has never reported, so that timestamp may be recent and
  describes a different metric.
- Do not label these RTLs `Never reported`.

## Needs Attention / electrical slots
- Stale and No Data values may be interactive current-state counts because they come from current freshness truth.
- Critical and Warning visual slots are built now but render an explicit unavailable/current-state-pending treatment until event closure semantics exist.
- Do not make unavailable Critical/Warning slots look like zero incidents.
- `Unavailable` must remain visually and semantically distinct from numeric
  zero everywhere it appears.

## Affected Locations
For CC-1, **Location = Plant**.
- Default sort: affected RTL count descending.
- Current affected count = Stale + No Data.
- Clicking a row selects that Plant without navigating away.
- Selected row visibly highlights.
- `View all locations` may deep-link only if a real Plant/asset explorer destination exists.

## Selected Location
Selected Location means Selected Plant.
- Updates when Affected Locations selection changes.
- Shows transformers sorted by current freshness attention burden.
- Critical/Warning current-state columns render unavailable until closure semantics are approved.
- Clicking transformer name opens authoritative transformer view.
- `Open plant` routes to existing plant detail.

## Recent Operational Events
- Newest first.
- Persisted events only.
- `power_down` event occurrence may display Critical presentation.
- `battery_low` event occurrence may display Warning presentation.
- No numeric voltage threshold evaluation in UI/callback/service consumers.
- No Acknowledge button.
- `Open asset` only when the event resolves to a known device/transformer route.
- Unregistered UID events remain plain identity text if no asset route exists.

## Shortcuts
Only expose real destinations. Candidate destinations:
- Asset Explorer / existing asset-navigation destination if implemented
- Needs Attention anchor or filtered view if real
- Reports
- Notifications
- Operations / Device Management when authorized

## Loading
Each major panel has an independent loading boundary where possible.

## Error behavior
One panel failing must not blank the entire Command Center.

## Empty states
Examples:
- No monitored RTLs in current scope.
- No affected Plants.
- No recent operational events.
- No transformer freshness attention in selected Plant.

Avoid optimistic phrases such as `All systems healthy` unless the underlying semantics genuinely support them.
