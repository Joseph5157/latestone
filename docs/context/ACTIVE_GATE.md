# Active Gate

Status: Open
Date: 2026-08-31
Gate: CC-2 Rank Bar Legibility
Branch: `cc-1-command-center-foundation` @ `00644f3`, pushed and in sync
with `origin`.

## Why this gate exists

CC-1 acceptance passed and its record stands at
`docs/context/CC1_ACCEPTANCE.md`. This is a defect gate opened afterwards
against a panel that gate accepted.

Measured on the running application at 1920x1080, `Affected Locations`:

| element | width | share of row |
|---|---|---|
| plant name | 160px | 15% |
| bar track | 847px | 80% |
| affected count | 23px | 2% |

The bar is 80% of the row. What it encodes across all 30 plants is four
distinct values (7, 6, 3, 1); inside the cockpit panel's top 8 it is **two**
(7 and 6). Five of the eight visible bars are pixel-identical, and the one
real distinction — 6 versus 7 — draws as 121px of difference behind 726px of
shared, information-free fill.

The count is the answer to the panel's question and it is the smallest thing
in the row. `affected_locations.py:89-91` already says the bar is decoration
over a number that is in the DOM beside it; the decoration outweighs the
number 37 to 1.

A second, separate defect surfaced while measuring: the bar is **not
theme-aware**. `--state-stale-text` (#713f12) and `--state-none-bg` (#f1f3f5)
are `:root` light-mode tokens with no dark restatement, so in the Command
Center's dark appearance the bar renders a dark-brown fill on a near-white
track inside a #1a232e panel. The route-scoped `--cc-stale` token that exists
for exactly this was never wired to this mark.

## Scope

1. Cap the bar column so surplus panel width stops flowing to the least
   informative element.
2. Point the fill and track at theme-aware tokens.
3. Nothing else.

## Non-goals

- **The encoding basis does not change.** `bar_width_percent` stays
  worst-relative from a zero baseline. Whether a proportional bar is the
  right mark at all for a 4-value distribution is a real question and is
  explicitly NOT decided here.
- No service, ranking, or `TOP_N` change. ADR-011 stands.
- No change to `/command-center/locations` semantics.

## Known ambiguity

`--cc-stale` is scoped to `.page--command-center`, which
`/command-center/locations` deliberately does not carry
(`pages/command_center_locations.py:31`). The fill must therefore fall back
to the existing token there, or the bars on that page render transparent.

## Relevant files

- `assets/app.css` (`.command-center__rank-row`, `__rank-bar`,
  `__rank-bar-fill`, `__rank-value`)
- `components/command_center/affected_locations.py`
- `components/command_center/selected_location.py`
- `tests/test_command_center_affected_locations.py`
- `tests/test_command_center_selected_panel.py`

## Required tests

`python -m pytest -m "not db" -v`

## Commit/push permission

GRANTED and exercised. The user reviewed the rendered result and approved
both the commits and the push on 2026-08-31. Branch pushed at `2c9a17d`.

## Status of the work

Both defects in scope are fixed, recorded in ADR-012, and pushed:

- `e33d0e1` — bar capped, tokens made route-scoped
- `59f92a9` — bar track made shrinkable, scrollbar gutter reserved

`59f92a9` also fixed a regression `e33d0e1` introduced: a bare `15rem`
track cannot shrink, so at 1000-1100px viewports the count was pushed
50-84px outside the panel. Verified at eight widths; 2,459 not-db tests
pass. This gate is complete.

## Also landed on this branch, outside the gate

`scripts/build_context_pack.py --check`. Not a CC-2 decision and not an ADR —
a tooling fix, recorded here only so a commit outside this gate's scope is not
a mystery to the next reader.

Step 0 of `AGENTS.md` and a read-only charter were in direct conflict: an
audit agent forbidden from writing could not run the generator, because
`docs/context/CURRENT_STATE.md` is TRACKED and the script stamps a timestamp
into it, so an ordinary run dirties the tree even when nothing has drifted.
A verification step was only available as a side-effecting write. `--check`
runs every validation, renders both documents, discards them, and writes
nothing. Five tests pin that it stays that way, including one that a real run
still writes.

## Carried forward, not done here

- In light appearance the cockpit bar is `--cc-stale` (#8a5a00) and
  `/command-center/locations` is the fallback (#713f12). Unifying them means
  extending the route-scoped semantics block to
  `.page--command-center-locations` — an ADR-006 theming change.
- Whether a proportional bar is the right mark at all for a four-value
  distribution. See "What this ADR does not decide" in ADR-012.
