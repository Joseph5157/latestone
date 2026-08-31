# Command Center Visual Design System

## Visual target
Industrial control-room dashboard, not generic SaaS analytics.

## Typography
- UI: IBM Plex Sans (already used by the application)
- Dense numeric values: tabular numeric treatment; monospaced numerals only where it materially improves telemetry scanning
- Required CSS: `font-variant-numeric: tabular-nums;`

## Hierarchy
- Page title: high contrast, restrained size
- Card eyebrow: uppercase, muted, compact
- Asset IDs: bold, uppercase tracking
- Metric labels: muted / compact
- Numeric values: high contrast, tabular

## Theme architecture
The repository's existing light token system is the starting point, not something to replace.

### Light appearance
Reuse existing application light tokens where possible, including the current `#F4F6F8` canvas family. Command Center-local tokens may extend the existing light system but should not fork identical values under needless new names.

### Dark appearance
Introduce a route-scoped Command Center dark token layer, with a foundation around:
- canvas: `#121820`
- panels: slightly lighter than canvas
- borders: cool muted gray/blue
- primary text: near-white, not pure white
- secondary text: muted gray

### Scope of appearance
While `/command-center` is active, the selected appearance covers the whole visible shell: sidebar, content and utility/Asset Navigator chrome. This requires a minimal route-scoped root/shell class or data attribute. Non-Command-Center routes must retain the existing appearance unchanged.

Theme preference persists in the session. This is an architectural feature of CC-1, not late Phase-9 polish.

## Semantic color discipline
### Fresh / normal
Neutral gray/slate by default. Avoid a sea of green.

### Warning / Battery Low event
Amber `#F59E0B` family. Use only when presenting an already-classified `battery_low` event occurrence, or after a future current-state contract is approved.

### Critical / Power Down event
Red `#EF4444` family. Use only when presenting an already-classified `power_down` event occurrence, or after a future current-state contract is approved.

### No Data / monitoring blindness
Purple `#8B5CF6` family or restrained dashed/neutral treatment.

### Stale
Use a distinct ochre/gold or muted amber family, not the same token as Warning. Label/icon differences are mandatory so electrical-event Warning and freshness Stale are never visually interchangeable.

### Green
Reserve mainly for connected/completed/successful operational states or explicit positive system state.

### Unavailable Critical/Warning current state
Use neutral dashed/outlined treatment and `—`/`Unavailable`, never red/amber zeroes. Color must not imply a state the backend cannot establish.

## Chart rules
- Prefer horizontal bars for ranking.
- Use ring/donut only for compact proportional summaries.
- Keep labels adjacent to values; do not force legend hunting.
- Avoid decorative gradients unless they preserve category readability.
- Never use red merely for emphasis when no Critical semantics exist.
- Current Affected Locations ranking uses Stale + No Data until electrical current-state semantics are approved.

## Density
Command Center is intentionally denser than Fleet Overview. Use tighter card spacing while preserving pointer targets, readable labels and clear scan paths.

## Accessibility
- Status must never depend on color alone.
- Use label + icon/shape + color.
- Verify contrast in both route-scoped appearances.
- Focus states must remain visible on dark and light chrome.
