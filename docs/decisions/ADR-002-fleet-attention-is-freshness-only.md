# ADR-002: "Requires Attention" is Stale + No Data only — never mixed with event history

Status: Approved
Date: 2026-08-28
Evidence: `components/fleet_condition.py:1-5`; `command center/04_DATA_SEMANTICS_AND_CONTRACTS.md` §"Attention aggregation for CC-1" and §"Communication panel"
Implemented-by: `29a4c5a` (Fleet Condition panels on the Overview page)
Supersedes: a CC-1 planning draft that included a third attention bucket derived from Critical/Warning event occurrences

## Decision

`Requires Attention = Stale + No Data`, and nothing else. This is the current
Fleet Overview behaviour (`components/fleet_condition.py:3-5`: "Attention
remains Stale + No Data. No classification or queries are performed here")
and Command Center must not diverge from it.

Do not fold recent `power_down`/`battery_low` event occurrences into this
total. Events answer "did something happen"; freshness answers "is the data
current now." Mixing them either double-counts a device that is both stale
and recently alarmed, or implies a resolved-alarm state the event model
cannot support (see ADR-001 — events have no clear/resolve/closure contract,
so an old event cannot establish that a device is *still* Power Down now).

### The freshness model this depends on

Freshness is evaluated **per (device, metric)**, and the device/RTL takes the
*worst* state across its 8 metrics. Consequences that must hold everywhere
this is displayed:

- An RTL is `NO_DATA` when **any one** monitored metric has never reported —
  even while its other 7 metrics are delivering fresh readings.
- `device_last_updated` is the newest timestamp across *any* metric. It can
  therefore be recent on a device that is currently `NO_DATA`, because the
  recent timestamp belongs to a different metric than the missing one. Do not
  use it to imply the device is fully current, and do not label a `NO_DATA`
  device "Never reported" — some of its metrics may be reporting fine.
- **No Data has no age buckets** (`>24h`, `>48h`, `>72h`, etc.) in CC-1. There
  is no per-metric missing-since fact to derive one from, and deriving a
  duration from `device_last_updated` or from event age would state a number
  the backend does not actually know. Show the count and share, and the line
  "At least one monitored metric has no reading" — nothing more precise than
  that is honest.

## Affected areas

- `services/monitoring_service.py` — the reusable unit. `get_fleet_health(now,
  *, scope: DeviceScope) -> FleetHealth` (line 430) is one query, scoped,
  worst-of-aggregated; its own docstring: "call it once per render and pass
  the result down... calling it per component would issue N queries and,
  worse, let two parts of one screen disagree about which devices are
  stale." `FleetHealth.counts: dict[Freshness, int]` is the `Requires
  Attention` input. `evaluate_freshness`/`aggregate_freshness`/
  `FreshnessRollup` (lines 198-249) are the classification itself.
- `components/fleet_condition.py` is **not** the reusable unit — corrected
  2026-08-29. It is Fleet Overview page-specific *presentation*: its own
  functions take an already-computed `dict[Freshness, int]` and render HTML
  (`fleet_condition_summary`, `fresh_data_coverage`, `data_freshness`), and
  its docstring is explicit that "no classification or queries are performed
  here." A fresh consumer (Command Center included) reuses
  `get_fleet_health()`, never imports this component — importing it would
  pull one page's markup/CSS classes into another page's presentation layer,
  which is a components/→components/ dependency this codebase doesn't have
  anywhere else.
- `command center/components/CC02_FLEET_HEALTH.md`,
  `command center/components/CC03_NEEDS_ATTENTION.md`,
  `command center/components/CC06_ATTENTION_LEGEND.md` — must present exactly
  this model, including the no-age-buckets rule
- Any future Command Center service — must call `get_fleet_health()` once
  per render and pass the result down; never issue a second freshness query
  and never re-derive the classification from raw readings
