"""Command Center appearance — the route-scoped theme (CC-1 Phase 11, ADR-006).

This application had no theme system before this module: not a dark mode
users could miss, an absence of the concept. So the interesting decision is
not what dark looks like, it is how narrow the blast radius can be.

THE HOOK IS THE ONE THE COCKPIT ALREADY USES. `assets/app.css` already
reaches the whole shell — sidebar included — with
`.app-shell:has(.page--command-center)`, and it does so with no Python
change to `app_shell.py`, `app_sidebar.py` or `app_header.py`. This module
adds one more class beside the route class on the SAME element, and the
stylesheet reacts to it the same way. Nothing in the shell learns that a
theme exists.

That is why nothing here writes to `<html>` or `<body>`: a `data-theme` on
the document root would be a global switch guarded only by discipline,
whereas a class on a page that only exists while the route is active cannot
outlive the route. The containment is structural.

VOCABULARY, NOT DECORATION. The palette carries meaning: Stale is
ochre/gold, No Data purple, Warning amber, Critical red, and normal/fresh
stays deliberately quiet — a fleet that is fine should not glow. Two of
those differ from what the rest of the application renders today, so they
are defined inside the route scope in BOTH appearances rather than in
`:root` (ADR-006, amended). Colour still never carries meaning alone; every
coloured state keeps its word, exactly as in Phases 6, 9 and 10.
"""
from __future__ import annotations

from dash import html

#: The two appearances. Strings rather than an Enum because this value round
#: trips through `dcc.Store` as JSON, and an Enum would serialise to its
#: value anyway while inviting a `.value` to be forgotten on the way back.
DARK = "dark"
LIGHT = "light"

#: Dark is the default: the control room is the primary environment ADR-006
#: describes, and the light appearance is the daylight/field case chosen
#: deliberately rather than fallen into.
DEFAULT_THEME = DARK

#: The id the toggle's callback rewrites. The page root, so one className
#: swap re-themes the workspace AND — via `:has()` — the shell around it.
ROOT_ID = "command-center-root"

#: The classes the stylesheet keys on. Namespaced `cc-theme--` rather than
#: a bare `dark`, so a rule can never accidentally match some other page's
#: idea of the word.
THEME_CLASS_DARK = "cc-theme--dark"
THEME_CLASS_LIGHT = "cc-theme--light"

#: The route class the cockpit layout keys on. Carried here so composing a
#: root className cannot drop it — losing it would silently un-fix the
#: fixed-viewport layout while looking like a theme bug.
ROUTE_CLASS = "page page--monitoring page--command-center"

#: The dark canvas from ADR-006. Named here so a test can assert it never
#: appears in `:root`.
DARK_CANVAS = "#121820"

_CLASSES = {DARK: THEME_CLASS_DARK, LIGHT: THEME_CLASS_LIGHT}

TOGGLE_DARK_ID = "command-center-theme-dark"
TOGGLE_LIGHT_ID = "command-center-theme-light"
STORE_ID = "command-center-theme-store"


def theme_class(choice: str | None) -> str:
    """The class for one appearance.

    Anything unrecognised resolves to the default rather than raising or
    returning nothing. `dcc.Store` session data is user-writable, and a
    hand-edited value must land on an appearance — a page rendering with no
    theme class at all would inherit half a palette.
    """
    return _CLASSES.get(choice, _CLASSES[DEFAULT_THEME])


def other(choice: str) -> str:
    """The appearance a toggle would switch to."""
    return LIGHT if choice == DARK else DARK


def root_class_name(choice: str | None) -> str:
    """The Command Center page root's full className.

    Exactly one appearance class, always beside the route classes.
    """
    return f"{ROUTE_CLASS} {theme_class(choice)}"


def option_state(choice: str, active: str | None) -> tuple[str, str]:
    """One toggle button's (className, aria-pressed) for a given selection.

    Public so the callback can recompute button state without destructuring
    a rendered component — Dash does not expose a dashed prop like
    `aria-pressed` as an attribute, and reaching into `to_plotly_json()` to
    get it back out would couple a callback to Dash's serialisation shape.
    Both the initial render and the callback go through this one function,
    so the two cannot disagree about what "active" looks like.
    """
    is_active = theme_class(active) == theme_class(choice)
    return (
        "command-center__theme-option"
        + (" command-center__theme-option--active" if is_active else ""),
        "true" if is_active else "false",
    )


def _option(label: str, choice: str, active: str, component_id: str) -> html.Button:
    class_name, pressed = option_state(choice, active)
    return html.Button(
        label,
        id=component_id,
        className=class_name,
        type="button",
        n_clicks=0,
        **{
            # The state an assistive technology reads. The visual "which one
            # is on" is a background change, and a background change is
            # exactly the kind of signal that reaches nobody using a screen
            # reader — the same reason every status dot in this family
            # carries a word.
            "aria-pressed": pressed,
            "aria-label": f"{label} appearance",
        },
    )


def theme_toggle(active: str | None = None) -> html.Div:
    """The `Dark | Light` control.

    Two buttons rather than a switch: a switch has an implied "off", and
    neither appearance is the absence of the other. Buttons, not links —
    this changes appearance, it does not navigate, and a link would put a
    URL in the status bar and offer "open in new tab" for something that is
    neither a place nor a document.

    Deliberately NOT driven by `prefers-color-scheme`. The frozen spec does
    not ask for it, and an operator's ambient light is not something the
    operating system knows: a daylight control room and a night shift on the
    same machine want different answers from the same OS setting.
    """
    choice = active if active in _CLASSES else DEFAULT_THEME
    return html.Div(
        className="command-center__theme",
        role="group",
        **{"aria-label": "Command Center appearance"},
        children=[
            _option("Dark", DARK, choice, TOGGLE_DARK_ID),
            _option("Light", LIGHT, choice, TOGGLE_LIGHT_ID),
        ],
    )
