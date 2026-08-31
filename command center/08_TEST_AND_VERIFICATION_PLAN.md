# Command Center Test and Verification Plan

## Unit tests
### Event semantics / EVT-D4
- persisted `power_down` event maps to Critical **presentation for that event occurrence**.
- persisted `battery_low` event maps to Warning **presentation for that event occurrence**.
- Command Center event consumers contain no numeric `<3.61` / `<3.75` classification predicate.
- battery-voltage payload changes do not change event category when event type is unchanged.
- Stale remains current freshness, not electrical Warning.
- No Data remains current data-availability state.
- temperature is never classified Critical/Warning without a separate client-approved condition contract.
- current Critical/Warning fleet counts are unavailable when event closure/current-state semantics are absent.
- unavailable is distinguishable from zero.

### No Data semantics
- the No Data count is exactly the `FleetHealth` NO_DATA device count; the
  Command Center never recomputes or redefines it.
- the Communication card renders NO age buckets (`>24h`/`>48h`/`>72h`) in CC-1.
- no Command Center code derives a No Data duration from `device_last_updated`.
  Regression case: an RTL with one never-reported metric and one fresh metric
  is NO_DATA *and* carries a recent `device_last_updated` — asserting that the
  card reports no age for it.
- No Data RTLs are never labelled `Never reported`.

### Header controls
- no interactive scope control exists: the header renders a read-only
  indicator, and the page contains no scope dropdown or scope-changing input.
- the Command Center `dcc.Interval` reads its cadence from
  `monitoring.refresh_interval_seconds` rather than a literal.
- `Last updated` reflects the snapshot, not browser wall-clock time.
- refresh copy never claims live/streaming/push behavior.

### Aggregation
- current Requires Attention = Stale + No Data in CC-1.
- historical power_down/battery_low event rows are not added to that current total.
- Affected Locations rank Plant identities by affected RTL leaves.
- `Location = Plant` identity is preserved in selectors and links.
- Selected-Plant transformer rows reconcile to the Plant's current affected total.
- Scope is applied before aggregation.

### Events
- newest-first ordering
- persisted-event read path used
- asset link when resolvable
- plain text for unregistered UID
- no acknowledgement UI
- deterministic opt-in Command Center event demo seed creates the intended browser-verification cases without altering default production seed behavior

### Authorization / routing
- `/command-center` has an explicit `ROUTE_POLICY` entry.
- route absent from policy remains default-deny.
- sidebar/navigation visibility derives from authorized route.
- `/` still resolves to existing Overview in CC-1.
- shortcuts are filtered by real permissions.

## Component tests
For each card/panel:
- populated state
- zero state
- unavailable state
- error state
- long label handling

Critical/Warning summary components specifically test the neutral unavailable rendering rather than a fabricated zero.

## Theme architecture tests
- route-scoped dark token set
- existing light tokens reused where appropriate
- theme choice persists within session on Command Center
- shell/sidebar/utility/content share the selected Command Center appearance
- semantic categories preserved between appearances
- sufficient text/background contrast
- status does not depend on color alone
- navigating away from `/command-center` leaves `/plants`, Notifications and Reports on their existing appearance

## Browser tests
### 1440 and 1366
- no horizontal overflow
- top four cards aligned
- recent events visually larger than Affected Locations
- Selected Location panel is the dominant lower-left investigation surface
- no map rendered
- no duplicate Plant/location comparison visual
- dark shell and content read as one coherent surface
- light shell and content read as one coherent surface

### Narrower checks
- no clipped controls at 1024
- existing global shell does not regress at 768

## Regression tests
- `/plants` Fleet Overview screenshot and DOM structure unchanged except for explicitly approved non-visual/shared infrastructure hooks that do not alter its rendered presentation.
- existing Plant/Transformer/Device navigation still works.
- Notification Center and Reports remain visually/behaviorally unchanged.

## Approved CC-1 shared modification surface
At minimum:
- `routes.py`
- `services/authorization.py`

Any additional shell/sidebar/navigation file used for the route-scoped appearance hook must be listed by the planning pass and justified before implementation.

## Acceptance checklist
- [ ] All 12 component spec files are present
- [ ] New page is visually independent from Fleet Overview
- [ ] `/` still lands on existing Overview
- [ ] `/command-center` route has explicit authorization policy
- [ ] Location is Plant; no Zone/Feeder/GIS semantics invented
- [ ] No map
- [ ] No duplicate middle-row Plant chart
- [ ] Recent events enlarged
- [ ] Light/Dark toggle themes the whole visible Command Center shell
- [ ] Non-CC routes retain existing appearance
- [ ] Critical legend says persisted Power Down event; `<3.61V` is explanatory device threshold only
- [ ] Warning legend says persisted Battery Low event; `<3.75V` is explanatory device threshold only
- [ ] No numeric threshold classification in Command Center consumer code
- [ ] Current Critical/Warning values render unavailable, not zero
- [ ] No high-temperature Critical label
- [ ] No Acknowledge action
- [ ] Deterministic opt-in event demo seed supports browser verification
- [ ] Communication card shows no No Data age buckets
- [ ] Header scope is a read-only indicator, not a selector
- [ ] Auto-refresh cadence comes from configured monitoring settings
- [ ] `Unavailable` renders distinctly from `0`
- [ ] Direct asset links work
- [ ] No source file outside the approved CC-1 surface changed without explanation
