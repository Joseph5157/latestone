"""App-wide appearance (THEME-APP-1, ADR-025; supersedes the Command
Center-only theme of ADR-006).

One class on the application root selects the appearance for the shell and
every page: `app-root theme--dark` or `app-root theme--light`. The dark
token block in `assets/app.css` redefines the shared tokens on that root, so
everything built on them follows without a rule of its own.

The choice lives in a browser-local store, so it is remembered on that
computer across sign-outs. No stored value, or an unknown one, means Dark.

Deliberately NOT driven by `prefers-color-scheme`: an operator's control-room
lighting is not something the operating system knows.
"""
from __future__ import annotations

from dash import html

DARK = "dark"
LIGHT = "light"
DEFAULT_THEME = DARK

#: The application root (`app.py`), whose className carries the theme.
ROOT_ID = "app-root"
ROOT_CLASS = "app-root"
STORE_ID = "app-theme-store"
TOGGLE_DARK_ID = "app-theme-dark"
TOGGLE_LIGHT_ID = "app-theme-light"

THEME_CLASS_DARK = "theme--dark"
THEME_CLASS_LIGHT = "theme--light"
_CLASSES = {DARK: THEME_CLASS_DARK, LIGHT: THEME_CLASS_LIGHT}


def resolve(choice) -> str:
    """The appearance a stored value means; anything unknown is the default.
    The store is browser-writable, so a hand-edited value must still land on
    an appearance rather than on half a palette."""
    if isinstance(choice, dict):
        choice = choice.get("theme")
    return choice if choice in _CLASSES else DEFAULT_THEME


def theme_class(choice) -> str:
    return _CLASSES[resolve(choice)]


def root_class_name(choice) -> str:
    """The application root's full className: exactly one appearance class."""
    return f"{ROOT_CLASS} {theme_class(choice)}"


def option_state(option: str, stored) -> tuple[str, str]:
    """(className, aria-pressed) for one toggle button. Shared by the first
    render and the callback so the two cannot disagree."""
    active = resolve(stored) == option
    return (
        "app-theme__option" + (" app-theme__option--active" if active else ""),
        "true" if active else "false",
    )


def _option(label: str, option: str, component_id: str) -> html.Button:
    class_name, pressed = option_state(option, None)
    return html.Button(
        id=component_id,
        type="button",
        n_clicks=0,
        className=class_name,
        title=f"{label} appearance",
        **{"aria-pressed": pressed, "aria-label": f"{label} appearance"},
        children=[
            html.Span(className=f"app-sidebar__icon app-sidebar__icon--theme-{option}",
                      **{"aria-hidden": "true"}),
            html.Span(label, className="app-sidebar__label"),
        ],
    )


def theme_toggle() -> html.Div:
    """The `Dark | Light` control for the sidebar footer. Two buttons rather
    than a switch: neither appearance is the absence of the other."""
    return html.Div(
        className="app-theme",
        role="group",
        **{"aria-label": "Appearance"},
        children=[
            _option("Dark", DARK, TOGGLE_DARK_ID),
            _option("Light", LIGHT, TOGGLE_LIGHT_ID),
        ],
    )
