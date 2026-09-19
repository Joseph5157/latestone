# ADR-025: Dark mode is app-wide, dark by default, and remembered per browser

Status: Approved
Date: 2026-09-19
Evidence: `components/command_center/theme.py`, `callbacks/navigation.py`
(theme callbacks), `components/app_sidebar.py` (the toggle), `app.py` (the
store and the `app-root` class), `assets/app.css` (dark token block)
Implemented-by: not yet
Supersedes: ADR-006 (route-scoped theming)

## Context

ADR-006 made dark/light a Command Center-only appearance, contained by a
route class, so no other page could change. Operators asked for dark mode on
every page: choosing Dark on the Command Center and then opening the Fleet
Overview gave a bright page again. The user decided (2026-09-19): dark mode
for the whole dashboard, **Dark by default**, and the choice **remembered on
that computer** between sign-ins.

## Decision

- One class on the application root (`app-root theme--dark` or
  `app-root theme--light`) selects the appearance for the whole shell and
  every page. The dark token block redefines the shared `--color-*` and
  `--sev-*` tokens on that root, so everything built on the tokens follows.
- The choice lives in a `dcc.Store` with `storage_type="local"`: it survives
  sign-out and browser restarts on that computer. No stored value = Dark.
  An unknown stored value falls back to Dark rather than to no theme.
- The toggle is one button in the sidebar footer, beside Logout, so it is on
  every signed-in page.
- The login page stays light (it is outside the signed-in shell and its hero
  image is designed for it).
- Components with their own colours (tables, dropdowns, date pickers,
  drawers, Plotly charts) get explicit dark rules; a page is not done while
  it shows bright leftovers.

## Consequences

- ADR-006's containment ("every other route is unaffected") no longer holds
  by design; `tests/test_command_center_theme.py` is rewritten to the new
  contract.
- ADR-006's persistence line (session-scoped) is replaced by per-browser
  persistence.
