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
from services.auth_service import current_identity
from services.authorization import AuthorizationError, REGISTER_DEVICE
from services.device_registration import RegistrationError, register_device

logger = logging.getLogger(__name__)


def _plant_options() -> list[dict]:
    """Plant options for the dropdown — reused by plant and equipment selectors.

    AUTH-HARDEN-1R (blocker 1). Registration IS Administrator-only content, so
    the UNRESTRICTED scope below is correct once authorized — that was never
    the defect. The defect was this function, and every callback that calls
    it, running with no authorization check of its own: `/admin/devices/new`
    being administrator-only gates the PAGE, not this independently
    invokable data callback. Callers below authorize first and query second.
    """
    return [
        {"label": p.name, "value": p.plant_id}
        for p in hierarchy_service.list_plants(scope=device_scope.UNRESTRICTED)
    ]


def _transformer_options(plant_id: str) -> list[dict]:
    """Transformer options for a given plant. See `_plant_options` — same
    fleet-wide-once-authorized reasoning; callers authorize first."""
    if not plant_id:
        return []
    return [
        {"label": t.transformer_code, "value": t.transformer_id}
        for t in hierarchy_service.list_transformers(
            plant_id, scope=device_scope.UNRESTRICTED
        )
    ]


def _validate_code(code: str | None) -> str | None:
    """The RTL UID / Device Code field-level rule: required, trimmed <= 10
    characters. The one place this rule is written (MOBBIN-UX-6) — both
    Review-time validation and the live inline hint call this, so the two
    can never drift apart. Returns an error message, or None when `code`
    passes.
    """
    if not code or not code.strip():
        return "Device code is required."
    if len(code.strip()) > 10:
        return "Device code must be 10 characters or fewer."
    return None


def _code_field_guidance(raw_value: str | None) -> str:
    """Live, inline guidance for the device code input, before Review.

    Uses only the rule `_validate_code` already enforces — no 5-digit or
    numeric-only assumption, no uniqueness check, nothing this application
    does not already validate:

    - nothing typed yet (pristine/emptied): neutral guidance stating the
      rule, not phrased as an error.
    - typed but invalid (whitespace-only, or over the length limit): the
      SAME message `_validate_code`/Review would show, so live feedback
      and Review validation say the identical thing for the identical
      input.
    - typed and currently valid: a concise, present-tense note that means
      only "passes this field's rule right now" — never "confirmed" or
      "registered", since nothing here reaches the database.
    """
    if not raw_value:
        return "Required · maximum 10 characters."
    error = _validate_code(raw_value)
    if error:
        return error
    return "Meets the device code format (10 characters or fewer)."


def _validate_form(code: str, plant_id: str, transformer_id: str) -> dict[str, str]:
    """Validate required fields. Returns {field: error_message} dict.

    Empty dict means valid.
    """
    errors = {}
    code_error = _validate_code(code)
    if code_error:
        errors["code"] = code_error
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
        # AUTH-HARDEN-1R (blocker 1). This callback fires on mount, for
        # anyone who can invoke it directly — not only an Administrator who
        # navigated here through the (administrator-only) route. Authorize
        # BEFORE the fleet-wide read, not after.
        try:
            require_capability(current_identity(), REGISTER_DEVICE)
        except AuthorizationError:
            return []

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
        # AUTH-HARDEN-1R (blocker 1). Same reasoning as _populate_plants.
        try:
            require_capability(current_identity(), REGISTER_DEVICE)
        except AuthorizationError:
            return [], True

        try:
            options = _transformer_options(plant_id)
            return options, not options
        except Exception:
            logger.exception("Failed to populate transformers for %r", plant_id)
            return [], True

    @app.callback(
        Output("device-register-code-hint", "children"),
        Input("device-register-code", "value"),
        prevent_initial_call=True,
    )
    def _code_hint(value):
        """Live guidance only — never the Review-time authoritative error.

        A separate Output/slot from `device-register-code-error`
        (MOBBIN-UX-6), so this fires on every keystroke without a second
        writer for the `role="alert"` slot `_show_review` owns; the layout's
        static initial text already matches the pristine-empty case, so this
        does not need `prevent_initial_call=False` to be correct on load.
        """
        return _code_field_guidance(value)

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
        # AUTH-HARDEN-1R (blocker 1). This is the review step: it resolves
        # `plant_id`/`transformer_id` — browser-supplied — to real names via
        # the UNRESTRICTED fleet-wide lookup below. That lookup is legitimate
        # ONLY for an authorized Administrator; a Technician or General User
        # invoking this callback directly with arbitrary IDs must not receive
        # those names. Same refusal shape as _submit_registration below, so
        # a caller sees one consistent "not permitted" outcome regardless of
        # which registration callback they reached.
        try:
            require_capability(current_identity(), REGISTER_DEVICE)
        except AuthorizationError:
            return (
                "", "", "",
                no_update,               # form stays as it was
                no_update,               # review stays as it was
                no_update,
                {"display": "block"},    # error visible
                action_refused_notice(),
            )

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
            user = current_identity()
            require_capability(user, REGISTER_DEVICE)
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
            register_device(
                transformer_id,
                code.strip(),
                status or "active",
                actor_user_id=user.user_id,
            )
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
