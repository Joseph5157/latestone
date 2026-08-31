# CC-01 Command Center Header

## Purpose
Provide global context and control without consuming excessive vertical space.

## Content
- `Command Center`
- `Fleet operational awareness`
- Search assets
- Read-only scope indicator
- Auto-refresh state and `Last updated`
- Light/Dark toggle
- User identity
- Data-as-of timestamp

## Scope indicator — read-only in CC-1
There is no user-selectable scope concept in the application today.
`DeviceScope` is authorization-derived, so a dropdown would either do nothing
or imply a security boundary the UI does not own.

CC-1 therefore renders an indicator, not a control:

> `Scope · Current access`

or, where a truthful name/count is available:

> `Scope · 120 monitored RTLs`

No dropdown. No scope-changing behavior. Do not add one in CC-1.

## Auto refresh — a Command Center deliverable
The application has no fleet-wide refresh cadence to "reflect": the only
existing `dcc.Interval` belongs to the device dashboard. Command Center owns
its own refresh.

- add a Command Center-owned `dcc.Interval`
- source the cadence from the existing `monitoring.refresh_interval_seconds`
  configuration; do not hardcode a value
- refresh the snapshot through the Command Center callback/service boundary
- show `Last updated`
- show `Auto refresh · On`
- a manual `Refresh` control may also be provided

Copy rule:

> **Auto-refresh uses the configured monitoring refresh interval.**

Never claim WebSocket, push or live-streaming behavior. It is polling.

## Rules
- Search routes to authoritative asset pages.
- The scope indicator must not imply security beyond existing authorization
  and device scope.
- Theme toggle persists in session.
- On `/command-center`, theme applies to the whole visible app shell, not only
  the page body.
- Non-CC routes retain their current appearance.
- Data-as-of is the timestamp of the snapshot being displayed, not merely
  current browser time.
