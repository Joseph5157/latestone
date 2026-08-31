# CC-03 Needs Attention

## Purpose
Summarize current freshness attention and reserve the visual language for future electrical current-state integration.

## Current CC-1 values
- Stale = current freshness problem
- No Data = current data-availability problem
- Requires Attention = Stale + No Data

## Reserved electrical slots
- Critical presentation corresponds to a persisted `power_down` event occurrence.
- Warning presentation corresponds to a persisted `battery_low` event occurrence.

The device thresholds (`<3.61V` Power Down, `<3.75V` Battery Low) may appear in explanatory copy only. This component/service must not perform numeric voltage classification.

## Current-state limitation
Because persisted events have no approved clear/resolve/closure semantics, current Critical/Warning fleet counts are not derivable in CC-1.

Render those slots as `—` / `Current state unavailable` using neutral styling, not as zero and not as fabricated counts.
