# Data Semantics and Contracts

## Non-negotiable concept separation
The Command Center must keep these axes distinct:

1. Administrative status
2. Current data freshness
3. Persisted event classification
4. Current electrical/operational condition, where and only where a persistence/closure contract exists

## Freshness states
### Fresh
Use the existing monitoring freshness policy.

### Stale
Use the existing monitoring freshness policy. Stale is a current data-recency condition, not an electrical warning.

### No Data
Use the existing monitoring no-reading / data-availability semantics. No Data represents monitoring blindness, not proof of transformer failure.

## Electrical/event presentation — EVT-D4 guardrail
The event pipeline already receives classified event types. Command Center consumers must not reclassify those events from numeric payloads.

### Critical presentation
For a **persisted event occurrence**, UI label `Critical` maps to event type `power_down`.

Functional-Spec copy may explain that the device defines Power Down at battery voltage `< 3.61 V`, but this number is documentation/legend text only. It must not appear in a Command Center consumer predicate, filter, threshold function or aggregation rule.

### Warning presentation
For a **persisted event occurrence**, UI label `Warning` maps to event type `battery_low`.

Functional-Spec copy may explain that the device defines Battery Low at battery voltage `< 3.75 V`, but this number is documentation/legend text only. It must not be evaluated by Command Center consumers.

### Payload rule
`battery_voltage` on an event is display/audit payload. It is not a classification input for Command Center.

### Temperature rule
Do not classify high temperature as Critical/Warning until a separate client-approved temperature condition contract exists.

## The real open semantic gap: event occurrence -> current state
Persisted `power_down` / `battery_low` rows say **an event occurred**. The current event model has no approved clear/resolve/closure semantics, so an old event cannot establish that an RTL is still Power Down or Battery Low now.

Therefore CC-1 must distinguish:

### Truthfully available today
- recent `power_down` event occurrences -> Critical event presentation
- recent `battery_low` event occurrences -> Warning event presentation
- current Fresh/Stale/No Data from monitoring freshness

### Not currently derivable
- `current_critical_rtls`
- `current_warning_rtls`
- a fleet-wide `Critical + Warning + Stale + No Data` mutually-exclusive current-state total

Until a future state/closure contract is approved, current Critical/Warning summary values are represented as `None` / unavailable, never `0` and never inferred from event history.

## Command Center service is mandatory
`services/command_center_service.py` owns all Command Center view-model composition and policy seams. It must:
- reuse existing scoped monitoring/FleetHealth truth;
- read persisted events through the approved existing event read path rather than new duplicate SQL;
- map already-classified event types to presentation categories without numeric threshold logic;
- expose unavailable current-state Critical/Warning fields explicitly;
- define Plant ranking and selected-Plant transformer concentration once;
- keep callbacks presentational/thin.

## Attention aggregation for CC-1
The **current attention population** is based only on current freshness states that are actually derivable:

`Requires Attention = Stale + No Data`

Do not add historical Critical/Warning event occurrences into that current total. That would mix time semantics and can double-count devices.

A future gate may extend the current-state model after clear/resolve semantics are defined.

## Communication panel
No Data age buckets such as `>24h`, `>48h`, `>72h` are **not shown in CC-1**.

Freshness is evaluated per (device, metric) and the RTL takes the worst state,
so an RTL is `NO_DATA` when any one monitored metric has never reported — even
while other metrics deliver fresh readings. There is no per-metric
missing-since fact, and `device_last_updated` is the newest timestamp across
*any* metric, so it cannot establish how long the missing metric has been
absent. Deriving buckets from it would state a duration the backend does not
know. Deriving them from event age is equally disallowed.

CC-1 shows the No Data count, its share of monitored RTLs, and the
explanatory line "At least one monitored metric has no reading." Age buckets
require a future metric-level missing-since / closure contract.

## Recent events
Rows come from the persisted event pipeline, newest first, scoped to the user's visible devices. No acknowledgement or current-state persistence is implied.

`power_down` and `battery_low` events may carry Critical/Warning presentation in this event stream because the event type itself is already classified.

## Location definition and ranking
For CC-1:

**Location = Plant**

Rank Plants by the count of currently affected RTL leaves (`Stale + No Data`) in the caller's visible scope, not by plant rollup-label count.

Each row exposes:
- plant_id
- plant_name (displayed as Location)
- affected RTL total
- Stale count
- No Data count
- selected-state action

Critical/Warning current-state splits are unavailable until state closure semantics exist.

## Selected Location contract
Recommended current CC-1 view model:

```python
@dataclass(frozen=True)
class CommandCenterTransformerRow:
    transformer_id: str
    transformer_code: str
    critical_count: int | None      # None in CC-1: current state unavailable
    warning_count: int | None       # None in CC-1: current state unavailable
    stale_count: int
    no_data_count: int
    affected_count: int             # stale + no_data in CC-1
    total_rtls: int
    last_updated: datetime | None
    trend: list[float] | None
```

The UI must visibly distinguish `None / unavailable` from zero.

## Optional future event-window metrics
If a later design wants counts such as `Power Down events in last 24h`, introduce separate explicitly time-bounded fields (for example `recent_power_down_events`) and label them as event occurrences. Do not overload `critical_count` / `warning_count` with event history.
