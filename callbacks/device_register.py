"""Device Registration callbacks — form validation, review, submit.

Form validation and review are pure frontend logic. Submit persists the
device via services/device_registration.py (DB-4), backed by
plant_monitoring.devices. Registration is create-only and attempts exactly
once per Submit click; a failure (unknown transformer, duplicate device
code, or a rare concurrent-registration race) is shown as a friendly error
on the review step rather than a stack trace or raw SQL.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from components.status_panels import action_refused_notice, error_panel
from services import device_scope, hierarchy_service
from services.action_guard import require_capability
from services.auth_service import from_session
from services.authorization import AuthorizationError, REGISTER_DEVICE
from services.device_registration import RegistrationError, register_device

logger = logging.getLogger(__name__)


def _plant_options() -> list[dict]:
    """Plant options for the dropdown — reused by plant and equipment selectors."""
    # Administration surface: the device-management population is deliberately
    # fleet-wide, like list_all_devices (spec §4.6). ROUTE_POLICY gates this page
    # administrator-only. Stated explicitly rather than omitted, per invariant 8.
    return [
        {"label": p.name, "value": p.plant_id}
        for p in hierarchy_service.list_plants(scope=device_scope.UNRESTRICTED)
    ]


def _transformer_options(plant_id: str) -> list[dict]:
    """Transformer options for a given plant."""
    if not plant_id:
        return []
    # Administration surface: the device-management population is deliberately
    # fleet-wide, like list_all_devices (spec §4.6). ROUTE_POLICY gates this page
    # administrator-only. Stated explicitly rather than omitted, per invariant 8.
    return [
        {"label": t.transformer_code, "value": t.transformer_id}
        for t in hierarchy_service.list_transformers(
            plant_id, scope=device_scope.UNRESTRICTED
        )
    ]


def _validate_form(code: str, plant_id: str, transformer_id: str) -> dict[str, str]:
    """Validate required fields. Returns {field: error_message} dict.

    Empty dict means valid.
    """
    errors = {}
    if not code or not code.strip():
        errors["code"] = "Device code is required."
    elif len(code.strip()) > 10:
        errors["code"] = "Device code must be 10 characters or fewer."
    if not plant_id:
        errors["plant"] = "Please select a plant."
    if not transformer_id:
        errors["transformer"] = "Please select a transformer."
    return errors


def _review_summary(code: str, plant_label: str, transformer_label: str, status: str) -> html.Div:
    """Render the review summary before submit."""
    return html.Div(
        className="device-register-review",
        children=[
            html.Div(
                className="device-register-review__row",
                children=[
                    html.Span("RTL UID / Device Code", className="device-register-review__label"),
                    html.Span(code, className="device-register-review__value"),
                ],
            ),
            html.Div(
                className="device-register-review__row",
                children=[
                    html.Span("Plant", className="device-register-review__label"),
                    html.Span(plant_label, className="device-register-review__value"),
                ],
            ),
            html.Div(
                className="device-register-review__row",
                children=[
                    html.Span("Transformer", className="device-register-review__label"),
                    html.Span(transformer_label, className="device-register-review__value"),
                ],
            ),
            html.Div(
                className="device-register-review__row",
                children=[
                    html.Span("Administrative status", className="device-register-review__label"),
                    html.Span(status.capitalize(), className="device-register-review__value"),
                ],
            ),
        ],
    )


def register(app) -> None:
    """Register device registration callbacks on the Dash app."""

    @app.callback(
        Output("device-register-plant", "options"),
        Input("device-register-plant", "id"),
    )
    def _populate_plants(_id):
        try:
            return _plant_options()
        except Exception:
            logger.exception("Failed to populate plant options")
            return []

    @app.callback(
        Output("device-register-transformer", "options"),
        Output("device-register-transformer", "disabled"),
        Input("device-register-plant", "value"),
        prevent_initial_call=True,
    )
    def _populate_transformers(plant_id):
        try:
            options = _transformer_options(plant_id)
            return options, not options
        except Exception:
            logger.exception("Failed to populate transformers for %r", plant_id)
            return [], True

    @app.callback(
        Output("device-register-code-error", "children"),
        Output("device-register-plant-error", "children"),
        Output("device-register-transformer-error", "children"),
        Output("device-register-form", "style"),
        Output("device-register-review", "style"),
        Output("device-register-review-summary", "children"),
        Output("device-register-error", "style"),
        Output("device-register-error", "children"),
        Input("device-register-review-btn", "n_clicks"),
        State("device-register-code", "value"),
        State("device-register-plant", "value"),
        State("device-register-transformer", "value"),
        State("device-register-status", "value"),
        prevent_initial_call=True,
    )
    def _show_review(n_clicks, code, plant_id, transformer_id, status):
        errors = _validate_form(code, plant_id, transformer_id)
        if errors:
            return (
                errors.get("code", ""),
                errors.get("plant", ""),
                errors.get("transformer", ""),
                no_update,  # form stays visible
                no_update,  # review stays hidden
                no_update,
                no_update,
                no_update,
            )
        # Look up labels for review. Administration surface: fleet-wide, like
        # list_all_devices (spec §4.6) — see _plant_options() above.
        plant_label = next(
            (
                p.name for p in hierarchy_service.list_plants(scope=device_scope.UNRESTRICTED)
                if p.plant_id == plant_id
            ),
            plant_id,
        )
        transformer_label = next(
            (
                t.transformer_code
                for t in hierarchy_service.list_transformers(
                    plant_id, scope=device_scope.UNRESTRICTED
                )
                if t.transformer_id == transformer_id
            ),
            transformer_id,
        )
        summary = _review_summary(code.strip(), plant_label, transformer_label, status)
        return (
            "",  # clear errors
            "",
            "",
            {"display": "none"},   # hide form
            {"display": "block"},   # show review
            summary,
            {"display": "none"},   # hide any stale error from a previous attempt
            "",
        )

    @app.callback(
        Output("device-register-form", "style", allow_duplicate=True),
        Output("device-register-review", "style", allow_duplicate=True),
        Output("device-register-error", "style", allow_duplicate=True),
        Output("device-register-error", "children", allow_duplicate=True),
        Input("device-register-edit-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def _back_to_form(n_clicks):
        return {"display": "block"}, {"display": "none"}, {"display": "none"}, ""

    @app.callback(
        Output("device-register-form", "style", allow_duplicate=True),
        Output("device-register-review", "style", allow_duplicate=True),
        Output("device-register-success", "style"),
        Output("device-register-success-detail", "children"),
        Output("device-register-error", "style", allow_duplicate=True),
        Output("device-register-error", "children", allow_duplicate=True),
        Input("device-register-submit-btn", "n_clicks"),
        State("device-register-code", "value"),
        State("device-register-plant", "value"),
        State("device-register-transformer", "value"),
        State("device-register-status", "value"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def _submit_registration(
        n_clicks, code, plant_id, transformer_id, status, auth_data
    ):
        """Submit — exactly one registration attempt per click."""
        if not n_clicks:
            return (no_update,) * 6

        # BEFORE ANY DATABASE ACCESS, including the label reads below. The
        # route is administrator-only, but this callback answers whoever
        # invokes it and the session lives in a browser-side store, so the
        # refusal has to exist here too. The callback supplies identity and
        # capability and nothing else — it compares no role of its own.
        try:
            require_capability(from_session(auth_data), REGISTER_DEVICE)
        except AuthorizationError:
            return (
                no_update,               # form stays hidden (still on review)
                no_update,               # review stays visible
                no_update,               # success stays hidden
                no_update,
                {"display": "block"},    # error visible
                action_refused_notice(),
            )

        # Administration surface: fleet-wide, like list_all_devices (spec
        # §4.6) — see _plant_options() above.
        plant_label = next(
            (
                p.name for p in hierarchy_service.list_plants(scope=device_scope.UNRESTRICTED)
                if p.plant_id == plant_id
            ),
            plant_id or "—",
        )
        transformer_label = next(
            (
                t.transformer_code
                for t in hierarchy_service.list_transformers(
                    plant_id, scope=device_scope.UNRESTRICTED
                )
                if t.transformer_id == transformer_id
            ),
            transformer_id or "—",
        )

        try:
            register_device(transformer_id, code.strip(), status or "active")
        except RegistrationError as exc:
            logger.info("Device registration failed: %s", exc)
            return (
                no_update,               # form stays hidden (still on review)
                no_update,               # review stays visible
                no_update,               # success stays hidden
                no_update,
                {"display": "block"},    # error visible
                error_panel(str(exc)),
            )
        except Exception:
            logger.exception(
                "Unexpected device registration failure: transformer=%s code=%s",
                transformer_id, code,
            )
            return (
                no_update,
                no_update,
                no_update,
                no_update,
                {"display": "block"},
                error_panel("Registration failed. Please try again."),
            )

        detail = html.Div(
            className="device-register-success-detail",
            children=[
                html.P(f"Device Code: {code.strip() if code else '—'}"),
                html.P(f"Plant: {plant_label}"),
                html.P(f"Transformer: {transformer_label}"),
                html.P(f"Status: {(status or 'active').capitalize()}"),
            ],
        )

        return (
            {"display": "none"},   # form hidden
            {"display": "none"},   # review hidden
            {"display": "block"},  # success visible
            detail,
            {"display": "none"},   # error hidden
            "",                     # error cleared
        )
