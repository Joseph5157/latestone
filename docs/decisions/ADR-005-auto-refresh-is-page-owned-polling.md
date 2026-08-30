# ADR-005: Auto-refresh is a page-owned `dcc.Interval`, not a shared "live" feed

Status: Approved
Date: 2026-08-28
Evidence: `pages/device_dashboard.py:216` (existing page-owned `dcc.Interval`); `components/fleet_summary.py:153` and `tests/test_fleet_overview.py:442` (Fleet Overview deliberately has none); `config/settings.py:136` (`refresh_interval_seconds`)
Implemented-by: `23642da` (device dashboard interval), `699ece0` (`refresh_interval_seconds` setting), `b8315c8` (Command Center's own interval and failure contract)
Supersedes: an assumption that an app-wide refresh interval exists for Command Center to hook into

## Decision

There is no shared, app-wide `dcc.Interval`. Auto-refresh in this codebase is
already a **per-page** concern by convention: the device dashboard owns one
(`pages/device_dashboard.py:216`); Fleet Overview deliberately has none — its
own component comment and a dedicated test both assert this
(`components/fleet_summary.py:153`, `tests/test_fleet_overview.py:442`).

Command Center follows the existing convention, not a new one: it owns its
own `dcc.Interval`, cadence sourced from `monitoring.refresh_interval_seconds`
(`config/settings.py:136`, default 60s via `UI_REFRESH_INTERVAL_SECONDS`).
Do not add a global interval to the app shell to serve Command Center — that
would change Fleet Overview's tested behaviour to support a page that doesn't
need it to.

Presentation constraints that follow from this being polling, not a push
feed:

- Show `Last updated` (data-as-of time) separately from browser wall-clock
  time, and an `Auto refresh · On` indicator. A manual `Refresh` control may
  also be offered.
- Never describe this as "live" or "streaming" in UI copy — it is polling on
  a fixed interval, and "live" implies a push guarantee this doesn't provide.
- A refresh cycle must not blank the page or discard the selected Plant.
- A failed refresh keeps the last successful snapshot and shows a truthful
  stale/error state — it does not clear the screen to a spinner.

## Affected areas

- New: Command Center's own `dcc.Interval` component and callback
- `config/settings.py` — `monitoring.refresh_interval_seconds`, the one
  cadence source; do not hardcode a different interval for Command Center
- `command center/06_INTERACTION_SPEC.md` §"Auto refresh" — CC-1's own
  restatement; this ADR is the durable record if that document is archived
  after CC-1 ships
- Does not touch `pages/device_dashboard.py` or Fleet Overview — each page's
  interval (or absence of one) stays independent
