"""Equipment selector callbacks — cascade and cross-plant device navigation.

Implements Phase 16 Step 3: jump straight to a device under any plant without
walking the drill-down pages.

The callback bodies are module-level functions so they can be tested without a
Dash runtime; `register()` only wires them up. Same shape as the rest of the
callback layer: gather inputs -> call service -> format outputs.

Two design points worth keeping:

1. The selector lives in the *global* layout (see components/equipment_selector),
   so these callbacks always have their targets. It is hidden rather than
   unmounted on the login route.
2. Data flows one way: selector -> URL. The route deliberately does not write
   back into the dropdowns. A route -> selector sync would close the loop
   selector -> url -> page-context -> selector, and re-entrant navigation is
   the failure this feature was previously half-built into. The breadcrumb
   already shows where the user is.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update

from components.equipment_selector import (
    DEVICE_ID,
    HIDDEN_STYLE,
    PLANT_ID,
    SHELL_ID,
    TRANSFORMER_ID,
)
from routes import device_href
from services import hierarchy_service
from services.device_scope import DeviceScope, scope_from_session

logger = logging.getLogger(__name__)

VISIBLE_STYLE: dict = {}


def _is_authenticated(auth_data) -> bool:
    return bool(auth_data) and bool(auth_data.get("authenticated"))


def selector_visibility(auth_data) -> dict:
    """Show the selector only to an authenticated user."""
    return VISIBLE_STYLE if _is_authenticated(auth_data) else dict(HIDDEN_STYLE)


def plant_options(auth_data) -> list[dict]:
    """List plants, but never before login.

    The component sits in the DOM on the login page, so this gate is what keeps
    plant names out of an unauthenticated page.
    """
    if not _is_authenticated(auth_data):
        return []
    scope = scope_from_session(auth_data)
    return [
        {"label": p.name, "value": p.plant_id}
        for p in hierarchy_service.list_plants(scope=scope)
    ]


def transformer_options(plant_id, scope: DeviceScope) -> tuple[list[dict], bool, None]:
    """Options, disabled-state, and a cleared value for the transformer field.

    The value is always reset: keeping a transformer from the previous plant
    selected would let the device field navigate somewhere the user did not
    pick.

    `scope` is resolved once by the enclosing callback and passed down, not
    re-resolved here.
    """
    if not plant_id:
        return [], True, None
    transformers = hierarchy_service.list_transformers(plant_id, scope=scope)
    options = [{"label": t.transformer_code, "value": t.transformer_id} for t in transformers]
    return options, False, None


def device_options(transformer_id, scope: DeviceScope) -> tuple[list[dict], bool, None]:
    """Options, disabled-state, and a cleared value for the device field.

    `scope` is resolved once by the enclosing callback and passed down, not
    re-resolved here.
    """
    if not transformer_id:
        return [], True, None
    devices = hierarchy_service.list_devices(transformer_id, scope=scope)
    options = [{"label": d.device_code, "value": d.device_id} for d in devices]
    return options, False, None


def device_navigation_target(device_id, context):
    """Destination pathname for a selected device, or `no_update`.

    Returns `no_update` when the device is already the one on screen. Without
    that guard, cascade resets that re-emit the current value would bounce the
    router for no reason.
    """
    if not device_id:
        return no_update
    if (context or {}).get("device_id") == device_id:
        return no_update
    return device_href(device_id)


def register(app) -> None:
    """Register equipment selector callbacks on the Dash app."""

    @app.callback(
        Output(SHELL_ID, "style"),
        Input("auth-store", "data"),
    )
    def _toggle_visibility(auth_data):
        return selector_visibility(auth_data)

    @app.callback(
        Output(PLANT_ID, "options"),
        Input("auth-store", "data"),
    )
    def _populate_plants(auth_data):
        try:
            return plant_options(auth_data)
        except Exception:
            # A selector that cannot load must not take the page down with it;
            # the drill-down navigation still works. Logged in full, generic
            # in the UI (empty dropdown), per AGENTS.md.
            logger.exception("Equipment selector failed to list plants")
            return []

    @app.callback(
        Output(TRANSFORMER_ID, "options"),
        Output(TRANSFORMER_ID, "disabled"),
        Output(TRANSFORMER_ID, "value"),
        Input(PLANT_ID, "value"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def _populate_transformers(plant_id, auth_data):
        try:
            return transformer_options(plant_id, scope_from_session(auth_data))
        except Exception:
            logger.exception("Equipment selector failed for plant_id=%r", plant_id)
            return [], True, None

    @app.callback(
        Output(DEVICE_ID, "options"),
        Output(DEVICE_ID, "disabled"),
        Output(DEVICE_ID, "value"),
        Input(TRANSFORMER_ID, "value"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def _populate_devices(transformer_id, auth_data):
        try:
            return device_options(transformer_id, scope_from_session(auth_data))
        except Exception:
            logger.exception(
                "Equipment selector failed for transformer_id=%r", transformer_id
            )
            return [], True, None

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input(DEVICE_ID, "value"),
        State("page-context", "data"),
        prevent_initial_call=True,
    )
    def _navigate_to_device(device_id, context):
        return device_navigation_target(device_id, context)
