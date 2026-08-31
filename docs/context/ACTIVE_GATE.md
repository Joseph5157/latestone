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

NOT GRANTED. Implement and verify, then show the rendered result and ask.
The user opened this gate; they have not yet seen what it produces.
