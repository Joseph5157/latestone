# Command Center Page Architecture

## Route decision
New route: `/command-center`

During CC-1:
- `/` remains mapped to the existing Fleet Overview.
- `/plants` remains the existing Fleet Overview.
- `/command-center` is a parallel workspace.

Adding the route requires deliberate edits to both `routes.py` and `services/authorization.py` because route policy is default-deny. A navigation item may be added only when the new route has an explicit policy entry.

## Existing route protection
The existing `/plants` Fleet Overview must remain visually and behaviorally unchanged during the Command Center build.

## Layout map

```text
GLOBAL APP SHELL  [route-scoped Command Center appearance]
|
|-- Left primary navigation
|
|-- COMMAND CENTER
|   |
|   |-- Header / search / scope indicator (read-only) / CC auto-refresh / theme / user
|   |
|   |-- Summary row
|   |   |-- Fleet Health
|   |   |-- Needs Attention
|   |   |-- Communication
|   |   `-- Inventory
|   |
|   |-- Attention Summary + Semantic Legend
|   |
|   |-- Operational row
|   |   |-- Affected Locations (Top 5)  [Location = Plant]
|   |   `-- Recent Operational Events   [larger panel]
|   |
|   |-- Investigation row
|   |   |-- Selected Location / Transformer Attention Concentration
|   |   `-- Shortcuts
|   |
|   `-- Refresh / data-as-of context
|
`-- Existing utility / Asset Navigator area if retained by the shared shell
```

## Theme architecture — locked for CC-1
The repository currently has one light token set and no global theme architecture. A dark Command Center rendered inside unchanged light chrome would be visually broken, so theme cannot be deferred to a late polish phase.

CC-1 therefore introduces a **minimal route-scoped appearance hook** at the application shell/root:
- while route is `/command-center`, the visible shell, sidebar, utility area and Command Center content share the selected `dark` or `light` appearance;
- the choice persists in session storage;
- existing light tokens remain the light foundation where possible;
- dark values are added as route-scoped overrides;
- leaving `/command-center` restores the existing application appearance without restyling Fleet Overview or other pages;
- no unrelated global design-system rewrite is allowed.

The read-only planning pass must identify the smallest shared shell/navigation files needed for this hook before implementation.

## Location definition
`Location` is not a new domain object. In CC-1:

**Location = Plant**

Every location ranking row, selector value and `Open plant` action uses the existing Plant ID/name. Do not invent Zone, Feeder or GIS entities.

## Why the map is removed
The research recommends geospatial/topology views when verified spatial data exists. The current hierarchy contract provides Plants but no approved Command Center GIS-coordinate model. Therefore CC-1 replaces the map with a Plant-to-transformer attention concentration panel, which is both more actionable and supported by existing hierarchy/FleetHealth truth.

## Hierarchy behavior
The Command Center does not remove the hierarchy. It short-circuits manual browsing.

```text
Affected Locations (Plants)
  -> select Plant
     -> transformer concentration
        -> open Transformer
           -> existing transformer / RTL investigation route
```

## Responsive intent
Primary design target is 1366–1440px desktop. Existing narrower-width behavior must not regress. The route-scoped light appearance is required for field use, but CC-1 does not redefine the application's mobile information architecture.
