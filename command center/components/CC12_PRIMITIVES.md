# CC-12 Command Center Primitives

Create Command Center-local presentation primitives so the new page can evolve independently.

## Suggested primitives
- `cc_card()`
- `cc_card_header()`
- `cc_stat()`
- `cc_state_marker()`
- `cc_rank_bar()`
- `cc_unavailable_state()`
- `cc_empty_state()`
- `cc_error_state()`
- `cc_loading_region()`

## Styling namespace
All component classes begin with `.command-center__` or `.cc-`.

## Shared-token rule
Fresh presentation does not mean duplicating existing light design tokens. Reuse shared token values where appropriate; keep Command Center-specific layout/component styles isolated.

## Semantic rule
Primitives receive already-decided state/view-model values. They must not contain battery thresholds, event classification logic or current-state inference.

## Isolation rule
Do not make Fleet Overview depend on these primitives during CC-1.
