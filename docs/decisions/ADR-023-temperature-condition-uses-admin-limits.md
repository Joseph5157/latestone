# ADR-023: Temperature condition is evaluated against Administrator-configured limits

Status: Approved
Date: 2026-09-19
Evidence: `services/temperature_condition_service.py` (`classify`,
`device_temperatures`); `services/temperature_threshold_service.py`
(`get_current_threshold_config`); `alembic/versions/011_temperature_threshold_config.py`;
`repositories/plant_monitoring_repository.py` (`latest_metric_readings`,
`fleet=True`); `tests/test_temperature_condition_service.py`
Implemented-by: `a0f1223` (`feat(temperature): condition per RTL against administrator limits (ADR-023)`)
Supersedes: the `AGENTS.md` §Data rules line "No production warning/critical
thresholds — `MonitoringCondition` is always `UNKNOWN`", for temperature
condition only. Amends ADR-001 (see "Relationship to ADR-001").

## Context

The Functional Specification's purpose is detecting overloaded transformers
(§2 Background) and its System Overview lists a "High" RTL alarm; the RTL
Master "stores and analyses" data "to generate alarms". Administrators could
already store a warning/critical limit pair (`c83cf94`, migration 011), but
nothing read it back, so a transformer above the limit showed nowhere
(tracker row UI-05). The rule that kept it that way existed because no limit
values were confirmed. The limits are not invented by the application: an
Administrator enters them and every change is audited.

The user approved evaluating temperature against those stored limits on
2026-09-19, with one global limit pair (not per transformer).

## Decision

1. `services/temperature_condition_service.py` is the **only** place a
   temperature is compared against a limit. Pages and components consume
   its `TemperatureCondition`; none holds a threshold.
2. Input is each RTL's **latest** temperature reading, not an aggregate.
3. Rule order: no reading, or a reading older than the live freshness
   threshold (ADR-021, strict `>`) → **No recent data**; no limits stored →
   **Limits not set**; otherwise `>=` critical → **Critical**, `>=` warning →
   **Warning**, else **Normal**. Neither No recent data nor Limits not set is
   ever shown as Normal.
4. Comparison is in `Decimal` (the stored column's type), never float.
5. Every surface showing a condition carries "Limits set by an
   administrator", so it is never read as an Eskom-confirmed value.
6. It is a derived **condition**, not an event: nothing is persisted, no
   `high_temperature` event is raised, no notification is sent.

## Relationship to ADR-001

ADR-001 is unchanged for what it governs: events are pre-classified facts
and no consumer holds a battery-voltage threshold; `event_semantics.py`
still has no `high_temperature` entry. This ADR does not classify events. It
adds a separate, derived temperature condition whose limits come from stored
Administrator configuration, not from a constant in a consumer.

## Consequences

- The Device page's `MonitoringCondition` KPI stays `UNKNOWN`; the Device page
  is outside the Fleet Overview + Command Center redesign.
- Persisted High Temperature alarms (raise on crossing, clear on drop,
  notify) are a separate later decision.
- If Eskom supplies confirmed limits, they are entered through the same
  Administrator setting; no code change.
