# Active Gate

Status: **CLOSED / committed locally after this commit — not pushed**
Date: 2026-09-04
Gate: UI-A11Y-POLISH-1 — accessible device search name + shared listing-error styling
Branch: `main`, baseline `1571adf7a04747e4fea4711f4ae73b339cc68db8`
Commit: this commit — see `git log -1 --oneline` on `main` (subject:
"fix(ui): improve accessibility and error presentation"); the SHA is not
self-referenced here because it depends on this file's own committed
content.
Commit/push permission: **Commit GRANTED, push NOT GRANTED.** Reviewed and
verified per this file's Verification section; committed locally only.
Pushing to the remote is a separate, later action.

## Purpose

Two small, unrelated presentation-layer fixes bundled into one narrow,
dependency-free frontend gate:

1. `dcc.Input(id="device-admin-search")` on the Device Management toolbar had
   no accessible name — a sighted-only `placeholder` is not a reliable
   accessible name (it disappears once the field has a value, and AT support
   for it as a name source is inconsistent).
2. `id="command-center-error"` and `id="command-center-locations-error"`
   render as bare, unstyled `html.Div`s when populated — no shared error
   styling.

## What changed

**`dcc.Input` accepts no `aria-*` props in this Dash version.** Attempting
`dcc.Input(..., **{"aria-label": "Search devices"})` raises `TypeError` at
render time — dcc.Input's prop schema (Dash 2.17.1) is closed to arbitrary
kwargs, unlike `html.Div`/`html.Label`, which pass unrecognised kwargs
straight through as DOM attributes. So the accessible name has to come from
a mechanism the component actually accepts: a native `<label for=...>`
association.

**`pages/device_admin.py`** — added
`html.Label("Search devices", htmlFor="device-admin-search", className="visually-hidden")`
immediately before the existing `dcc.Input`. `id`, `placeholder`, callback
wiring (`callbacks/device_admin.py` still reads `Input("device-admin-search",
"value")` unchanged), and visible layout are untouched — the label
contributes zero rendered layout.

**`assets/app.css`** — added one new utility class, `.visually-hidden`, using
the standard clipped/off-screen technique (`position: absolute; width: 1px;
height: 1px; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space:
nowrap; border: 0;`). No existing class in the stylesheet fit this need: the
only prior "hidden" utility, `.app-shell__utility--hidden`, is `display:
none` and belongs to the sidebar utility column — reusing it for the label
was this gate's own first draft and was reverted, because `display: none`
(and `visibility: hidden`) both remove an element from the accessibility
tree in some browser/AT combinations, which would silence the very label it
exists to provide. Verified in Chromium (see Verification below) that the
clipped label stays in the accessibility tree while contributing no visible
layout, and that the input's computed accessible name is "Search devices".

**`pages/command_center.py`, `pages/command_center_locations.py`** — added
`className="listing-error"` to `command-center-error` and
`command-center-locations-error` respectively. No new CSS: `.listing-error`
already existed and is already used by `device-admin-error`.

## Why no ADR

Presentation-only. No architectural concept, data flow, service boundary, or
business rule changes — a label-association pattern and one CSS utility
class following an established web-accessibility technique, not a new
project-level decision.

## In scope

- `pages/device_admin.py` — accessible-name label for the search input.
- `assets/app.css` — new `.visually-hidden` utility class only.
- `pages/command_center.py`, `pages/command_center_locations.py` —
  `listing-error` className on the two error containers.
- `tests/test_device_admin.py` — label-association and CSS-utility tests.
- `tests/test_command_center_page.py` — `listing-error` class test.
- `tests/test_command_center_locations_page.py` (new) — layout tests for a
  page that previously had none.

## Explicitly out of scope — and not touched

- Drawer/dialog accessibility (deferred per the original task instruction).
- Any backend, service, repository, or business-rule code.
- Any callback wiring — `callbacks/device_admin.py` is unchanged.
- `debug.log` — untracked, untouched throughout.
- Pushing to the remote.
- Any broader accessibility audit. This gate fixes the one reported input
  and the two reported error containers only — it is not a WCAG conformance
  pass over the page, the app, or even the rest of the Device Management
  toolbar (its status-filter dropdown, register button, etc. were not
  reviewed here).

## Verification

- Focused: `tests/test_device_admin.py::TestDeviceAdminPageLayout` (10
  passed, including the 3 new a11y tests),
  `tests/test_command_center_page.py::TestCommandCenterLayout` (listing-error
  test), `tests/test_command_center_locations_page.py` (2 passed, new file).
- Browser accessibility check: rendered the label+input markup with the real
  `assets/app.css` in Chromium via Playwright and captured the accessibility
  tree. Result: `textbox "Search devices"` — non-empty accessible name
  computed correctly from the label association, and the label text itself
  remains present as a separate accessibility-tree node (confirming the
  clip technique does not remove it, unlike `display: none`).
- Non-DB suite: `python -m pytest -m "not db" -q` — 2696 passed, 510
  deselected.
- `python scripts/build_context_pack.py --check` — CLEAN.
- `git diff --check` — clean, no whitespace errors.
- DB suite not run — not required for a presentation-only change.

## Next queued gate

None queued. This gate is closed and committed locally; the remote push and
whatever comes next are separate, later decisions.
