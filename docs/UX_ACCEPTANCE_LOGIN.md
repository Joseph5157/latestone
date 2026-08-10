# UX Acceptance — Login Page Visual Refinement

Verification pass for the login split-composition slice and the follow-up polish
pass. Measured in real browsers with `getComputedStyle` and
`getBoundingClientRect`, not inferred from source — per this project's own rule:
a stylesheet-source assertion has passed twice in this codebase while the
browser rendered something different (DEF-1's focus ring, the
`.dash-cell-value` `text-overflow: inherit` finding).

**Scope.** Visual refinement only. No change to `callbacks/auth.py`,
`callbacks/routing.py`, the demo authentication flow, `auth-store` memory
behaviour, or any Fleet/Plant/Transformer/Device layout.

**Environment.** Measurements taken with **Playwright**, which manages its own
viewport independently of physical screen size (`page.setViewportSize`), giving
genuine 1366×768 and 1920×1080 CSS-pixel viewports. App on port **8050** from
the root/main checkout; DB container `plant_monitoring_postgres` on 5436,
already running and already seeded.

**Note on routing.** There is no `/login` route. `routes.py` defines no login
path; `callbacks/routing.py` returns `login_layout()` for *any* pathname while
`auth-store` is unauthenticated. Login is a **state**, not a URL — so nothing in
the login CSS or layout keys off a pathname.

---

## 1. Measurements at 1366×768

| Metric | Before | After | Target |
|---|---|---|---|
| `.login-shell` | 1220×640 | **1286×690** | fills the frame without crowding it |
| Viewport used | 89.3% × 83.3% | **94.1% × 89.8%** | more of the viewport |
| Split (form / visual) | 44.9 / 54.9 | **44.9 / 54.9** | 45 / 55 — unchanged by the polish pass |
| `.login-form` width | 380px | **400px** | 360–400px |
| Occupied height (32 + shell + 32) | 736px | **754px** | ≤ 768 |
| **Vertical clearance** | 32px | **14px** | ≥ 12px |
| Vertical scroll | none | **none** | none |
| Horizontal scroll | none | **none** | none |

### On the height cap

The shell is `height: min(690px, calc(100vh - 64px))` — capped, never fixed. The
polish pass first set this to **700px**, which measures clean (764 against 768)
but leaves only **4px** of clearance. That is the kind of margin that survives a
measurement and then loses to browser chrome, OS display scaling, a zoom step,
or a font stack that rounds one line taller. **690px** leaves 14px and is not
visibly smaller.

The `calc(100vh - 64px)` arm means a short viewport shrinks the shell rather
than overflowing it, so the no-scroll property holds by construction below
768px too.

Screenshots: `docs/ux-baseline/login-before-1366.png`,
`docs/ux-baseline/login-after-1366.png`.

## 2. Measurements at 1920×1080

| Metric | Before | After |
|---|---|---|
| `.login-shell` | 1220×640 | **1320×690** |
| Viewport used | 63.5% × 59.3% | **68.8% × 63.9%** |
| Split (form / visual) | 44.9 / 54.9 | **44.9 / 54.9** |
| Vertical clearance | — | **326px** |
| Vertical / horizontal scroll | none | **none** |

The width cap engages here (1320 < 1920 − 80), so the composition centres with
generous outer whitespace rather than stretching — the same "maximum, never a
target" behaviour as `--w-monitoring` on Fleet.

Screenshot: `docs/ux-baseline/login-after-1920.png`.

## 3. Typography

Increased for readability while preserving the existing hierarchy and rank.

| Element | Before | After | Contrast on white |
|---|---|---|---|
| Eyebrow (`POWER PLANT MONITORING`) | 11px / 600, `--color-muted` | **12px / 700, `--color-text`** | 5.98:1 → **13.6:1** |
| Heading (`Welcome back`) | 28px / 700 | **30px / 700** | 11.48:1 |
| Supporting copy | 14px / 400 | **15px / 400** | 5.98:1 |
| Field labels | 13px / 600 | **14px / 600** | 14.68:1 |
| Inputs | 14px / 400 | **15px / 400** | 14.68:1 |
| Sign in button | 13px / 700 | **14px / 700** | 11.48:1 (white on `--color-brand`) |
| Hero headline | 22px / 600 | **24px / 600** | 18.39:1 on scrim |
| Hero supporting copy | 14px / 400 | **15px / 400** | 11.26:1 on scrim |

The eyebrow was the weakest text on the screen: uppercase at 11px with 0.10em
tracking is the smallest size doing the most work. Every value clears WCAG AA.

Login-block type sizes are literal px rather than tokens, deliberately. Fleet
earned `--fs-fleet-*` by spanning many components; login is one block on one
screen, and a second name for a one-use value is the drift the token layer
exists to prevent.

## 4. Focus verification (`getComputedStyle`, keyboard-driven)

Tab order, measured by a `focusin` recorder with real `Tab` presses so
`:focus-visible` genuinely engages:

`login-username` → `login-password` → `toggle-password-btn` → `login-button`

Every control:

| Property | Value |
|---|---|
| `:focus-visible` matched | `true` |
| `outline` | `solid 2px rgb(37, 99, 235)` |
| `outline-offset` | `2px` |
| `box-shadow` | `rgba(37, 99, 235, 0.45) 0 0 0 3px` — **one** shadow |

This is the project's DEF-1 treatment: one outline plus one halo, not a doubled
ring. The previous `.login-input:focus { box-shadow: var(--focus-ring) }` was
removed — it gave a mouse click a halo with no outline, and a keyboard tab a
halo *plus* the global outline. The rule now sets `border-color` only; the ring
belongs to the global `:focus-visible` rule.

The inline show/hide control's ring was measured as falling **entirely inside**
the password field's bounds, so moving it into the field did not push its
indicator outside the input.

Labels: `<label for="login-username">` and `<label for="login-password">` both
resolve to a real element (`document.getElementById` non-null). The previous
form carried placeholders only.

## 5. Show/hide password behaviour

The control now sits **inside** the field — borderless, transparent, right-aligned
— rather than as an adjacent bordered button, which read as a second competing
box next to the input.

| Check | Result |
|---|---|
| Click → `login-password.type` | `password` → **`text`** |
| Click → button label | `Show` → **`Hide`** |
| Icon state | eye → **eye-off** (slash `line` present, pupil `circle` absent) |
| Control width | **78px**, fixed — the row does not twitch when the label swaps |
| Inside field bounds | **true** |
| Text runs under the control | **false** — field reserves `padding-right: 88px` |
| Still a focusable `<button>` | **true** |

The icon is selected by `.login-input[type="password"]` vs `[type="text"]` — the
field's own `type`, which is exactly the property the callback writes. The eye
and the word therefore cannot disagree, and **no callback contract changed** to
get a stateful icon. A state *class* would have needed something to toggle it,
and nothing does; that would have been a contract change dressed up as styling.

The label text stays server-rendered (`Show`/`Hide` come from the callback), so
it remains the control's accessible name.

## 6. Invalid-login state

Triggered with deliberately invalid input (not real credentials), submitted with
**Enter** — which also confirms the Enter-key submit path (NEW-14) still works.

| Check | Result |
|---|---|
| Message | `Invalid username or password.` |
| `role` | **`alert`** — announced without a page change |
| Reserved height (idle) | **40px** |
| Layout shift: Sign in button | **0px** |
| Layout shift: heading | **0px** |
| Layout shift: shell height | **0px** |
| Marker | CSS-drawn `"!"` in a `currentColor` ring — no emoji font dependency |
| Contrast | **7.6:1** (`#991b1b` on `#fef2f2`) |

State is carried by a sentence, so it is never communicated by colour alone; the
tint, left rule and marker are additive. The `:not(:empty)` guard keeps all of
them off the reserved-but-idle box — the callback clears the region to `""`,
which renders no child node.

## 7. Responsive behaviour

| Viewport | Shell | Behaviour |
|---|---|---|
| 1920×1080 | 1320×690 | 45/55, width cap engaged, centred |
| 1366×768 | 1286×690 | 45/55, 14px vertical clearance |
| 1000×720 | 904×690 | visual panel yields first (form share 51.9%), form still 400px |
| 420×720 | 380×auto | visual panel `display: none`, form is the whole page |

At 420px: `scrollWidth` 420 = `innerWidth` 420, so **no horizontal overflow**;
the inline toggle stays inside the field with 230px of usable text width. Mobile
is a fallback — the desktop composition is not compromised to serve it.

## 8. Equipment selector regression

The globally mounted selector must stay completely hidden while unauthenticated.

| Check | Result |
|---|---|
| In DOM on login | **true** (mounted, never unmounted — keeps callback targets alive) |
| Computed `display` | **`none`** |
| Measured size | **0 × 0** — reserves no space |
| Rendered inside `login_layout()` | **false** |
| Initial shell style (server-rendered) | `{"display": "none"}` |

There is no selector flash: the shell is hidden **by construction** in the
server-rendered layout, not by a callback that has to run first. `display: none`
rather than `visibility: hidden` is what stops an empty bar appearing above the
composition.

## 9. Known issue — not introduced by this slice

Typing in either field logs a React warning: *"A component is changing an
uncontrolled input to be controlled."* Both `dcc.Input`s lack a `value` prop —
true before this slice as well, so it is not a regression. The one-line fix is
`value=""`, but that changes what `State("login-username", "value")` delivers on
first submit from `None` to `""`, which touches the locked auth contract.
Recorded here rather than fixed.

## 10. Test baseline

```
python -m pytest -m "not db"    # 595 passed, 53 deselected
python -m pytest                # 648 passed
```

Up from the 607 pre-slice baseline; no net reduction. `tests/test_login_page.py`
adds 41 tests covering the callback-id contract, `n_submit=0` preservation,
label association, the inline-toggle icon contract, hero asset wiring, the
equipment-selector regression, and the responsive/clearance numbers.

Focus *rendering* is deliberately not asserted in pytest — CSS source has passed
in this project while the browser computed something else. What the suite guards
is the one thing source can prove: that the rule which used to double the
indicator is gone. The browser measurements in §4 are the actual proof.

---

## Baseline screenshots

| File | What |
|---|---|
| `docs/ux-baseline/login-before-1366.png` | Split composition before the polish pass |
| `docs/ux-baseline/login-after-1366.png` | Final, 1366×768 |
| `docs/ux-baseline/login-after-1920.png` | Final, 1920×1080 |

`docs/ux-baseline/baseline-login-1366.png` predates this slice and shows the
original single 360px card.
