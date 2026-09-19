# ADR-028: Ring and donut gauges are allowed for part-of-whole counts

Status: Approved
Date: 2026-09-19
Evidence: `AGENTS.md` (UI requirements), `components/attention.py`,
`assets/app.css`, `docs/decisions/ADR-026-one-colour-key-colour-means-urgency.md`
Implemented-by: not yet

## Context

`AGENTS.md` said "Do not add gauges, pie charts". That rule turned down a
donut in CC-VISUALS-1. On 2026-09-19 the user reviewed gauge and donut
patterns (Mobbin), shortlisted a half-circle arc (Okta) and a donut with the
total in the centre (Twenty), and turned down needle and speedometer gauges:
the Hottest-now bars with limit markers already compare temperatures better,
and a zoned dial would add colours ADR-026 does not allow. The user then
asked for both shortlisted shapes on the Command Center (CC-GAUGES-1).

## Decision

- **Allowed:** a ring (full or half) or a donut **only when it shows a count
  as part of a whole**: RTLs working out of all RTLs, or problems split by
  kind.
- **Still not allowed:** needle or speedometer dials, zoned dials, full
  (hole-less) pie charts, and gauges for a single measured value such as a
  temperature. A measurement keeps its bar and limit marker.
- **Colour:** gauges use ADR-026's tones and add none. A share of RTLs
  working is drawn in the calm tone, never in critical or warning.
- **Numbers are always written out** (centre total, labelled counts); the
  shape never carries a number on its own. No animation.
- **Drawing:** CSS `conic-gradient` from the existing colour variables, so
  there is one source for the colours and no new dependency.

## Consequences

- `AGENTS.md`'s UI rule is reworded to cite this ADR.
- The first use is the Command Center's "Fleet at a glance" panel
  (ADR-024 amendment, CC-GAUGES-1).
