# CC-02 Fleet Health

## Purpose
Answer: `How much of the monitored fleet is currently fresh vs freshness-attention-requiring?`

## Visual
Compact ring/donut plus total monitored RTL count and nearby labels.

## Data
- monitored RTL total
- Fresh count
- Stale count
- No Data count

## Semantics
This card is current monitoring freshness only. It does not infer Critical/Warning electrical state from event history.

## Rule
Fresh/normal should not dominate the page with bright green. Keep it visually restrained.
