# ADR-024: Fleet Overview and Command Center are split by the question each answers

Status: Approved
Date: 2026-09-19
Evidence: `pages/plants_overview.py`, `callbacks/fleet_overview.py`,
`services/fleet_overview_service.py`, `components/fleet_overview.py`;
`pages/command_center.py`, `callbacks/command_center.py`,
`services/attention_service.py`, `components/attention.py`;
`callbacks/routing.py` (`landing_route_name`)
Implemented-by: `2cfad36` (switch-over; built in FO-NEW-1, CC-NEW-1, CC-ACTIONS-1)
Supersedes: ADR-002, ADR-009, ADR-011, ADR-012 (the panels they governed
were removed)

## Context

The Remote Temperature Logger Functional Specification (ID 240-137264801) is
about transformer temperature and battery / communications alarms. The old
Fleet Overview led with freshness summaries (Fleet Condition, Needs
Attention) and the old Command Center with freshness and electrical panels
(Affected Locations, Priority Investigation, Electrical Conditions). Both
pages showed overlapping "condition" summaries. The redesign was agreed with
the user on 2026-09-19, one decision at a time (internal design notes, not
tracked).

## Decision

- **Fleet Overview** (`/plants`, every role) answers "where is everything and
  how hot is it?": one expandable row per plant, transformers with their
  30-day maximum temperature, RTLs with their latest temperature and
  condition (ADR-023). No alarm counts, no electrical metrics (a link per
  RTL to the Device page instead), no Administration section.
- **Command Center** (`/command-center`, Administrator and Technician)
  answers "what needs my attention now?": status bar, one ranked problem
  list (Critical temperature, Power Down, no data > 24 h, Warning
  temperature, Battery Low, Sensor error; oldest first within a kind), the
  hottest five RTLs, alarms per day for 7 days, recent activity for 24 h.
  Acknowledge and Manage reuse the existing guarded flows (ADR-016).
- **No panel appears on both pages.**
- **Landing:** `/` renders the Command Center for Administrators and
  Technicians and the Fleet Overview for General Users.
- Technician scope is unchanged on both pages (ADR-004).

## Consequences

- Freshness still drives "no data" (BR008) and the Device page; it is no
  longer a panel of its own on either page.
- The Unassigned RTLs panel is gone from the Overview; Assignments and
  Device Management already hold that work.
- CSS rules for the removed panels remain in `assets/app.css` as dead rules
  until a separate clean-up.
