# Mobbin UX Reference

Status: Reference (not an ADR, not a gate)
Date: 2026-09-16

Preserves the accepted directions from two Mobbin design-research passes
(desktop-only; this application has no mobile surface to design for): one
covering static screen/component patterns, one covering multi-step
workflows. Both passes searched Mobbin for comparable SaaS/ops-console
patterns and checked each candidate against `AGENTS.md`'s existing UI
constraints before it was accepted or rejected.

**Mobbin references are design inspiration only.** A cited screen or flow
never becomes a business requirement by being cited here, and nothing in
this file changes scope, adds a screen, or overrides `AGENTS.md`,
`ACTIVE_GATE.md`, or any ADR. Where a suggestion would have needed new scope
(e.g. an audit-log event-count histogram) it was explicitly flagged as
out-of-scope below rather than accepted.

## Guiding rule

> Show progression only where the backend genuinely has ordered lifecycle
> states.

A status becomes a multi-step progression display only when a real,
already-modeled state machine backs it (e.g. `rtl_commands.state`). Where no
such backend ordering exists, the correct UI is a plain status label, not an
invented progress bar.

## Accepted directions

- **Program RTL / command execution** — render the existing `rtl_commands`
  lifecycle (`QUEUED` → `SENT`/`ACKNOWLEDGED` → `SUCCEEDED`/`FAILED`/
  `TIMED_OUT`, per RTL-PROG-EXEC-1/RTL-PROG-SIM-1) as a discrete lifecycle
  rail — named states in sequence. **No percentage progress bar**: the
  backend has no continuous progress signal to back one.
  **Implemented 2026-09-16** in `components/programming_activity.py`
  (`_lifecycle_rail`/`_lifecycle_steps`) — presentation-only; no change to
  `config/commands.py`, `services/rtl_command_service.py`,
  authorization, `DeviceScope`, schema, or audit behaviour. A
  `FAILED`/`TIMED_OUT` outcome truncates the rail after `SENT` rather than
  showing `ACKNOWLEDGED`/`SUCCEEDED` as still reachable.
- **Device registration** — keep the current single-screen form → Review →
  Success flow as-is. The only addition is inline RTL UID validation
  feedback on the field itself; no multi-step wizard, no new screens.
- **Technician assignment** — the assignment action must show explicit
  Saving → Saved/Failed feedback tied to the real persistence call. No
  optimistic "assigned" state shown before the write is confirmed.
  **Implemented 2026-09-16** in `callbacks/device_assign.py`
  (`confirm_assignment`'s `running=` argument) — transient-state only, via
  Dash's own `running=` contract on the existing callback: the Confirm
  Assignment button reads "Saving…" and is disabled for the request's
  duration, then reverts, with no change to the callback's own
  Saved/Failed/No-op/refusal outcomes or copy, and no optimistic table
  state before persistence returns.
- **Reports (Report Center)** — generation/export shows Preparing export →
  Download/Failure feedback. No blocking modal beyond what's needed to
  communicate that state; nothing decorative.
  **Implemented 2026-09-16** in `callbacks/report_center.py`
  (`download_report_csv`'s `running=` argument) — transient-state only, via
  Dash's own `running=` contract on the existing export callback: the
  Download button reads "Preparing export…" and is disabled for the
  request's duration, then reverts, with no change to CSV/PDF generation,
  DeviceScope, `EXPORT_DATA` authorization, report periods, filenames, row
  gathering, or preview/export parity. `report-download-btn.disabled` had a
  pre-existing owner (`toggle_download_button`, R4-D9); both callbacks now
  declare `allow_duplicate=True` on that prop, Dash's own mechanism for two
  legitimate writers of one Output.
- **Plant / Transformer detail** — improve the empty states so they are
  truthful about why a page looks empty (no transformers yet, stale/no
  seed data, etc.). Do not add charts to fill the space.
- **Fleet Overview** — preserve the current KPI / Data Health structure.
  Do not invent new KPIs such as "offline" or "active alarms" counts that
  the backend does not actually compute — a KPI tile must correspond to a
  real, already-queryable fact.
- **Device Manage drawer** — preserve the current action architecture
  (Program RTL, Simulate execution, Assign, etc.). Any Mobbin-informed
  change here is presentation polish only, not a rearchitecture of what
  actions exist or how they're authorized.
- **Notifications** — keep the current operational table shape. No "Mark
  all read" or bulk-acknowledgement affordance without explicit client
  approval — acknowledgement semantics are not this application's call to
  make unilaterally.
- **Command history** — lifecycle progression display, same rule as
  Program RTL above: only because a real ordered state machine backs it.
- **Audit history** — a compact, reverse-chronological activity log
  (actor, action, target, timestamp), matching patterns like Railway's and
  Zoho CRM's audit logs. No event-count histogram or other chart bolted
  onto it — that would be new scope on a screen `AGENTS.md` doesn't list as
  carrying a chart, not a presentation refinement.
  **Implemented 2026-09-16** in `components/programming_activity.py`
  (`_audit_entry`) — a decorative marker, the action, then "Requester ·
  Timestamp" beneath it, replacing the old per-row detail-card treatment.
  Renders exactly the three facts `DeviceAuditHistoryView` supplies
  (`operation`, `requester_name`, `occurred_at`); **no "target" field
  exists on that read model**, so none is shown — this corrects the
  "actor, action, target, timestamp" wording above, which assumed a field
  this application does not have. The marker carries no severity class
  (audit actions have no severity concept); the redundant filler rows
  ("Lifecycle: Audit record" / "Execution: Not applicable" / "Result:
  Recorded in this application") were removed since none added a fact.
  Data retrieval, ordering, authorization and `DeviceScope` are unchanged;
  the command lifecycle rail is unchanged.

## Explicitly rejected / avoid

- Donut charts, gauges, and progress rings — `AGENTS.md` already prohibits
  gauges and pie charts by name; donuts and rings are the same family.
  (Seen in Toggl Track's and ClickUp's dashboards during research — not
  adopted for this reason.)
- Decorative animation of any kind.
- Audit or activity histograms / "events over time" bar charts (seen in
  Okta's System Log) — flagged during research as a genuinely good pattern
  for an ops audit trail in the abstract, but out of scope here without a
  deliberate scope decision, since no current screen carries a chart in
  that location.
- Generic SaaS-style decoration adopted for its own sake, without a
  corresponding operational fact it communicates. Every tile, badge, or
  progression shown must trace back to a real, already-computed value or
  state — never invented to make a screen look fuller.

## Provenance

Both research passes used Mobbin's screen and flow search against real
published SaaS/ops products (Railway, Sentry, Cloudflare, Deel, Airwallex,
Vapi, Apollo, Squarespace, PlanetScale, Laravel Cloud, Zoho CRM, Okta,
Jobber, 7shifts, and others) filtered through this repository's existing
constraints (`AGENTS.md` §UI requirements, §Architecture rules). No client
evidence, ADR, or requirement was consulted or altered by this research —
it is presentation-pattern reference only, ranked below every tier in
`docs/context/SOURCE_AUTHORITY.md`.
