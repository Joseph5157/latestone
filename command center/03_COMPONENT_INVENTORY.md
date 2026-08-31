# Command Center Component Inventory

## Fresh component family
Do not import Fleet Overview presentation components merely to save time. New Command Center components have their own namespace and styles.

```text
components/command_center/
  __init__.py
  shell_header.py
  fleet_health_card.py
  attention_card.py
  communication_card.py
  inventory_card.py
  attention_legend.py
  affected_locations.py
  recent_events.py
  selected_location.py
  shortcuts.py
  theme_toggle.py
  primitives.py
```

Page:

```text
pages/command_center.py
```

Callbacks:

```text
callbacks/command_center.py
```

Required semantic/view-model facade:

```text
services/command_center_service.py
```

`command_center_service.py` is **not optional**. It is the single seam for Command Center aggregation, view models, event-occurrence presentation, unavailable current-state fields, Plant ranking and transformer concentration. Callbacks must not independently reimplement these policies.

## Component catalogue

### CC-01 Command Center Header
Search, READ-ONLY scope indicator (no selector), Command Center-owned auto-refresh state, theme toggle, user identity, data-as-of stamp.

### CC-02 Fleet Health
Monitored RTL total + current Fresh/Stale/No Data distribution from existing monitoring semantics. Do not over-emphasize Fresh.

### CC-03 Needs Attention
Current data-attention summary plus reserved Critical/Warning UI slots. Stale/No Data are current freshness states. Critical/Warning event labels are supported, but current fleet-wide Critical/Warning counts remain unavailable until event closure/current-state semantics are approved.

### CC-04 Communication
No Data / monitoring blindness summary. No age buckets in CC-1: freshness is per-metric worst-of, so No Data duration is not derivable.

### CC-05 Inventory
Plants, transformers and RTLs in the operator's visible monitoring scope.

### CC-06 Attention Summary + Semantic Legend
Compact strip explaining that Critical/Warning presentation comes from already-classified `power_down` / `battery_low` events. Numeric voltages are explanatory device thresholds only and must not be evaluated by Command Center consumers.

### CC-07 Affected Locations
Ranked horizontal bars. **Location = Plant.** This is the only top-level Plant comparison visualization.

### CC-08 Recent Operational Events
Large read-only persisted event stream, newest first, with direct open-asset action where identity is resolvable. This is the surface where `power_down` and `battery_low` events can be truthfully presented as Critical/Warning occurrences today.

### CC-09 Selected Location / Transformer Attention Concentration
Selected Plant investigation surface using current freshness burden. Critical/Warning columns may exist visually but must render unavailable until current-state event aggregation is defined; do not infer persistence from historical event rows.

### CC-10 Shortcuts
Direct links only to real routes/capabilities and role-filtered from real authorization policy.

### CC-11 Theme Toggle
Controls route-scoped whole-shell dark/light appearance for `/command-center`; non-CC routes keep their current appearance.

### CC-12 Primitives
Fresh Command Center-local visual primitives and loading/error/empty states.

## Specification files
All 12 detailed component specs are included under `components/CC01_HEADER.md` through `components/CC12_PRIMITIVES.md`.
