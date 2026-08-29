# ADR-001: Events are closed, pre-classified facts — no consumer holds a numeric threshold

Status: Approved
Date: 2026-08-28
Evidence: `services/event_semantics.py:1-19` (module contract, rules EVT-D1/D4/D7); Functional-Spec battery-voltage figures relayed as legend copy in `command center/04_DATA_SEMANTICS_AND_CONTRACTS.md`
Implemented-by: `bb1e2e9` (event consumption), extended by every commit that reads `services/event_semantics.py`
Supersedes: a CC-1 planning draft that put `<3.61V` (Power Down) / `<3.75V` (Battery Low) directly into Command Center consumer logic

## Decision

An incoming `power_down` or `battery_low` row is already a classified fact by
the time any consumer sees it. No consumer — Notification Center, report
projection, or Command Center — may hold its own reinterpretation of what the
event type means (EVT-D1), and none may hold a numeric threshold (EVT-D4).

`battery_voltage` on an event is display/audit payload only. It is not a
classification input anywhere downstream. It is unrelated to the `voltage`
metric on readings, which is transformer line voltage in kV
(`config/metrics.py:42`) — same word, two different quantities, never to be
conflated in UI copy or code.

The client's own device firmware defines Power Down at `< 3.61V` and Battery
Low at `< 3.75V`. That number is legitimate **legend/help text** explaining
what the device already decided. It must never appear in a predicate, filter,
threshold function, or aggregation rule — the classification already happened
on the device before the row was persisted.

`high_temperature` and `vibration_event` have no entry in
`services/event_semantics.py` at all. This is deliberate, not an oversight:
their domain rules are open client-clarification items (see
`REQ-3I_Clarification_Register.md`), so they are structurally absent rather
than mapped-but-disabled. Do not add an entry to make a UI panel look
complete — absence here is itself a decision, and filling it in requires new
client evidence, not UI convenience.

## Why this is a durable decision, not a CC-1-only rule

This was approved once already, in prose, for a different reason: a CC-1
planning draft independently reinvented the `<3.61V`/`<3.75V` thresholds as
consumer-side logic, because they read naturally as "the" definition of
Critical/Warning. They are not — they are the reason the device emitted the
event, already consumed once, upstream, by the device itself. Any future
panel that wants to show Critical/Warning is bound by the same rule for the
same reason; this is not specific to Command Center's implementation.

## Affected areas

- `services/event_semantics.py` — the binding, and the only place event type
  → presentation mapping may live
- `services/notification_service.py`, `services/report_service.py` — existing
  consumers already honouring this
- `command center/04_DATA_SEMANTICS_AND_CONTRACTS.md` §"Electrical/event
  presentation" — CC-1's own restatement of this rule, kept in sync by hand;
  if the two ever disagree, this ADR and the source file win (see
  `docs/context/SOURCE_AUTHORITY.md`)
- Any future Command Center service (`services/command_center_service.py`,
  not yet created) — must read through `services/event_semantics.py`, never
  reimplement classification
