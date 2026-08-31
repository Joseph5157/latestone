# ADR-012: The rank bar is a capped mark on route-scoped tokens

Status: Approved
Date: 2026-08-31
Evidence: `assets/app.css` (`.command-center__rank-row`,
`.command-center__rank-bar`, `.command-center__rank-bar-fill`);
`components/command_center/affected_locations.py:46` (`bar_width_percent`,
unchanged); `pages/command_center_locations.py:31` (the page that does not
carry `page--command-center`)
Implemented-by: not yet
Supersedes: nothing — ADR-011 stands unchanged

## Context

CC-1 acceptance passed with the rank bar on `1fr`. Measured afterwards on
the running application at 1920x1080, that allocation produced:

| element | width | share of a 1053px row |
|---|---|---|
| plant name | 160px | 15% |
| bar track | 847px | 80% |
| affected count | 23px | 2% |

`Affected Locations` is the only panel carrying `--wide`, so it is the widest
cell in the cockpit — and because the bar was the flexible track, every extra
pixel of panel went to the bar. **Widening the panel made the chart worse.**
On `/command-center/locations` the same rule gave the bar 1207px.

What those pixels encode is four distinct values across the whole fleet
(7, 6, 3, 1) and **two** within the cockpit panel's top 8. Five of eight
visible bars were pixel-identical. The single real distinction, 6 against 7,
drew as 121px of difference trailing 726px of shared fill that carried no
information at all.

The count is the answer to the panel's question. `affected_locations.py`
already describes the bar as "decoration over a number that is already in the
DOM beside it" and hides it from assistive technology on that basis. The
decoration outweighed the number 37 to 1.

A second, independent defect surfaced in the same measurement. The mark was
painted with `--state-stale-text` (#713f12) on `--state-none-bg` (#f1f3f5) —
`:root` light tokens with no dark restatement. In the Command Center's dark
appearance the bar therefore rendered a dark-brown fill on a near-white track
inside a #1a232e panel: the one element on the page still painted for light
mode. ADR-006 established the route-scoped semantic layer and `--cc-stale`
exists there, restated at dark-appropriate luminance. This mark was never
wired to it.

## Decision

### The bar is a fixed 15rem track; no track absorbs the surplus

`grid-template-columns: minmax(0, 18rem) 15rem auto`, with
`justify-content: start`.

240px resolves a four-value distribution comfortably, and the pixels past it
were encoding nothing. 18rem clears the longest plant name in the fleet,
which was ellipsising under the old 10rem cap.

Leftover width falls after the count rather than inside the row. Two earlier
attempts are recorded because both look correct and are not:

- **Giving the surplus to the name** (`minmax(0, 1fr) 15rem auto`) only moved
  the void. The name sat at the left edge and the bar at the right with
  ~500px of nothing between them; the row stopped reading as one object.
- **Leaving the count column `auto` without `justify-content: start`.** An
  `auto` track absorbs free space under the default `normal`/stretch, so the
  count column silently stretched across the leftover ~500px and its
  right-aligned glyph landed back at the card's right edge — undoing the fix
  while every measurement of the *track* said it had worked. `justify-content`
  is load-bearing here, not cosmetic.

### The fill is `--cc-stale`, the track is `--color-border`

Both follow the appearance. The fill carries a fallback:

```css
background: var(--cc-stale, var(--state-stale-text));
```

The fallback is not defensive noise. `--cc-stale` is scoped to
`.page--command-center`, which `/command-center/locations` deliberately does
not carry (it is not the fixed cockpit). Without the fallback the bars on
that page would render transparent; with it, that page keeps exactly the
colour it has today.

### The encoding basis does not change

`bar_width_percent` stays worst-relative from a zero baseline. Only the
mark's geometry and tokens change.

## Consequences

- The bar is 240px on all three surfaces — cockpit dark, cockpit light, and
  the full locations page — where it was previously 847px and 1207px.
  The two surfaces now scale identically in pixels as well as in percent,
  which `ranked_locations_list` already claimed.
- The `.command-center__locations-full` grid override was deleted rather than
  adjusted. It set `minmax(0, 22rem) 1fr auto`, which put the bar back on
  `1fr` on the widest rows in the application; the base rule now gives the
  name every spare pixel, which is what that override was reaching for.
  Only the name-wrapping rule remains page-specific.
- **Known inconsistency, deliberately left.** In light appearance the cockpit
  bar is `--cc-stale` (#8a5a00) and the locations page is the fallback
  (#713f12). Making them identical means extending the route-scoped semantics
  block to `.page--command-center-locations`, which is a theming-architecture
  change under ADR-006 and is out of this gate's scope.
- No test changed. The suite asserts structure and class names over these
  rows, not geometry, so all 2,459 not-db tests pass unmodified — which is
  the correct outcome for a presentation-only change, not a gap in coverage.

## What this ADR does not decide

Whether a proportional bar is the right mark at all for a distribution with
four distinct values. A dot plot, a tier grouping, or plain right-aligned
counts with a rank number would carry the same information, and one of them
may be better. That is a real question, it is not answered here, and
`bar_width_percent`'s existing rationale stands until it is.
